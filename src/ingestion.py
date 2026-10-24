from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from itertools import chain
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from src.settings import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    INDEX_BATCH_SIZE,
    INDEX_VERSION,
    RAW_DIR,
    RETRIEVAL_MODE,
)


LEGAL_BOUNDARY = re.compile(
    r"(?=^\s*(?:"
    r"Art\.\s*\d+[ºo°]?"
    r"|§\s*\d+[ºo°]?"
    r"|Parágrafo\s+(?:único|\d+)"
    r"|[IVXLCDM]+\s*[-–]"
    r"|[a-z]\)\s*"
    r"))",
    re.IGNORECASE | re.MULTILINE,
)

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?;:])\s+")
READY_FILE = CHROMA_DIR / ".pi5_index_ready.json"
SUPPORTED_DOCUMENT_SUFFIXES = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
}


class NoReadableDocumentsError(ValueError):
    """Supported files exist, but none contains an indexable text passage."""


def selected_document_paths(raw_dir: Path) -> list[Path]:
    """Prefer the canonical base to numbered browser-download duplicates."""
    if not raw_dir.is_dir():
        return []
    paths = sorted(p for p in raw_dir.iterdir()
                   if p.is_file() and p.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES)
    if any(p.name.casefold() == 'base_unificada_educacao_rs.md' for p in paths):
        paths = [p for p in paths if not re.fullmatch(
            r'base_unificada_educacao_rs\s*\(\d+\)\.md', p.name, re.IGNORECASE)]
    return paths


def bounded_chunks(text: str, size: int, overlap: int) -> Iterable[str]:
    """Bound long tables and paragraphs even without sentence punctuation."""
    size = max(1, size)
    overlap = min(max(0, overlap), size // 3)
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = max(text.rfind('\n', start, end), text.rfind(' ', start, end))
            if boundary > start + size // 2:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end == len(text):
            break
        start = max(start + 1, end - overlap)


def restore_section_headings(text: str) -> str:
    """Reconhece os títulos da base mesmo após copiar o Markdown renderizado.

    Só promove linhas inteiras com rótulos conhecidos. Linhas numéricas como
    IMERS: 2024 = ... continuam sendo dados, não títulos. A base não é alterada
    no disco; a recuperação da estrutura acontece apenas durante a leitura.
    """
    municipality = re.compile(
        r'^Munic[ií]pio:\s*.+?\s*[—–-]\s*IBGE\s*\d{7}\s*$', re.IGNORECASE)
    section = re.compile(
        r'^(?:Visão geral:|SAERS: finalidade|IMERS: significado|'
        r'Panorama geral:|PRE: significado|ICMS Educacional e IPM:|'
        r'Leis principais:|EC\s+108/2020:|Fundeb: finalidade|LDB:|'
        r'Indicadores complementares e interpretação|Limites da base e perguntas|'
        r'(?:Lei estadual|Decreto)(?:\s+estadual)?\s+n[ºo°]?\s*\d)',
        re.IGNORECASE)
    group = re.compile(
        r'^\d+\.\s+(?:ICMS Educacional|PRE\s*[—–-]|SAERS e IMERS|Educação básica)',
        re.IGNORECASE)
    lines = []
    for line in text.splitlines():
        title = line.strip()
        if re.match(r'^#{1,6}\s+', title):
            lines.append(line)
        elif municipality.fullmatch(title):
            lines.append('### ' + title)
        elif len(title) <= 180 and (
                group.match(title) or title.startswith('Dados municipais compactos')):
            lines.append('## ' + title)
        elif len(title) <= 180 and section.match(title):
            lines.append('### ' + title)
        elif not lines and title.startswith('Base Unificada'):
            lines.append('# ' + title)
        else:
            lines.append(line)
    return '\n'.join(lines)


def markdown_records(path: Path) -> Iterable[tuple[str, dict]]:
    """Keep section and municipality context on each bounded Markdown chunk."""
    text = restore_section_headings(clean_text(read_text_file(path)))
    headings = list(re.finditer(r'(?m)^(#{1,6})[ \t]+([^\n]+)$', text))
    sections = []
    if not headings:
        sections.append((1, path.stem, text))
    else:
        if text[:headings[0].start()].strip():
            sections.append((1, path.stem, text[:headings[0].start()]))
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            sections.append((len(heading[1]), heading[2].strip(), text[heading.end():end]))
    hierarchy = []
    chunk_index = 0
    for level, title, body in sections:
        while hierarchy and hierarchy[-1][0] >= level:
            hierarchy.pop()
        hierarchy.append((level, title))
        body = clean_text(body)
        if not body:
            continue
        metadata = {'source': path.name, 'type': 'md', 'page': 1,
                    'source_locator': title, 'section': title}
        for _, parent in reversed(hierarchy):
            match = re.match(r'Munic[ií]pio:\s*(.*?)\s*[—–-]\s*IBGE\s*(\d{7})', parent, re.IGNORECASE)
            if match:
                metadata.update(entity=match[1].strip(), codigo_ibge=match[2])
                break
        metadata['section_path'] = ' > '.join(title for _, title in hierarchy[1:]) or title
        labels = []
        if metadata.get('entity'):
            labels.append(f"Município: {metadata['entity']}. Código IBGE: {metadata['codigo_ibge']}.")
        labels.append(f'Seção: {title}')
        if hierarchy[0][1] != title:
            labels.append(f'Documento: {hierarchy[0][1]}')
        header = next((line for line in body.splitlines() if line.lstrip().startswith('|')), '')
        if header:
            labels.append('Colunas da tabela: ' + header)
        size = max(80, CHUNK_SIZE)
        prefix = '\n'.join(labels)[:size // 2] + '\n\n'
        budget = size - len(prefix)
        for chunk in bounded_chunks(body, budget, min(CHUNK_OVERLAP, budget // 3)):
            yield prefix + chunk, {**metadata, 'chunk': chunk_index}
            chunk_index += 1


def clean_text(text: str) -> str:
    text = text.replace("\x00", "").replace("\u00ad", "")
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


# =========================================================
# PDF
# =========================================================

def extract_pdf(
    path: Path,
) -> Iterable[tuple[str, int]]:

    try:
        # Alguns arquivos baixados da web chegam com extensão .pdf,
        # mas na verdade são HTML/erro de download.
        with path.open("rb") as file:
            prefix = file.read(1024)

        if b"%PDF-" not in prefix:
            print(
                f"[AVISO] Arquivo ignorado porque não é PDF válido: "
                f"{path.name}"
            )
            return

        reader = PdfReader(
            str(path),
            strict=False,
        )

        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            try:
                text = clean_text(
                    page.extract_text() or ""
                )

                if text:
                    yield text, page_number

            except Exception as error:
                print(
                    f"[AVISO] Erro ao extrair {path.name}, "
                    f"página {page_number}: {error}"
                )

    except Exception as error:
        print(
            f"[AVISO] PDF ignorado ({path.name}): {error}"
        )


# =========================================================
# CSV
# =========================================================

def detect_csv_encoding(path: Path) -> str:
    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ):
        try:
            path.read_text(encoding=encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    return "latin-1"


def normalize_column_name(value: str) -> str:
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def find_csv_header(
    rows: list[list[str]],
) -> int:

    for index, row in enumerate(rows):
        normalized = [
            normalize_column_name(cell).lower()
            for cell in row
        ]

        if (
            "uf" in normalized
            and "ente federado" in normalized
        ):
            return index

    for index, row in enumerate(rows):
        filled = [
            cell
            for cell in row
            if cell.strip()
        ]

        if len(filled) >= 2:
            return index

    return 0


def extract_csv(
    path: Path,
) -> Iterable[tuple[str, dict]]:

    encoding = detect_csv_encoding(path)

    raw_text = path.read_text(
        encoding=encoding,
        errors="replace",
    )

    try:
        dialect = csv.Sniffer().sniff(
            raw_text[:20_000],
            delimiters=";,\t|",
        )
        delimiter = dialect.delimiter

    except csv.Error:
        delimiter = ";"

    rows = list(
        csv.reader(
            raw_text.splitlines(),
            delimiter=delimiter,
        )
    )

    if not rows:
        return

    header_index = find_csv_header(rows)

    headers = [
        normalize_column_name(column)
        for column in rows[header_index]
    ]

    for row_number, row in enumerate(
        rows[header_index + 1:],
        start=header_index + 2,
    ):
        if not any(
            cell.strip()
            for cell in row
        ):
            continue

        if len(row) < len(headers):
            row += [""] * (
                len(headers) - len(row)
            )

        data: dict[str, str] = {}

        for header, value in zip(
            headers,
            row,
        ):
            header = clean_text(header)
            value = clean_text(value)

            if header and value:
                data[header] = value

        if not data:
            continue

        uf = data.get("UF", "")
        ente = data.get("Ente Federado", "")

        codigo_ibge = (
            data.get("Código IBGE")
            or data.get("Codigo IBGE")
            or data.get("CódigoIBGE")
            or data.get("CodigoIBGE")
            or ""
        )

        parts = [
            "Dados oficiais do VAAR 2026.",
            "Complementação da União ao Fundeb - VAAR.",
        ]

        if ente:
            parts.append(
                f"Ente Federado: {ente}."
            )

        if uf:
            parts.append(
                f"UF: {uf}."
            )

        if codigo_ibge:
            parts.append(
                f"Código IBGE: {codigo_ibge}."
            )

        for column, value in data.items():
            if column in {
                "UF",
                "Ente Federado",
                "Código IBGE",
                "Codigo IBGE",
                "CódigoIBGE",
                "CodigoIBGE",
            }:
                continue

            parts.append(
                f"{column}: {value}."
            )

        text = "\n".join(parts)

        metadata: dict = {
            "source": path.name,
            "type": "csv",
            "row": row_number,
            "page": 1,
            "chunk": 0,
        }

        if uf:
            metadata["uf"] = uf

        if ente:
            metadata["entity"] = ente

        if codigo_ibge:
            metadata["codigo_ibge"] = str(
                codigo_ibge
            )

        yield text, metadata


# =========================================================
# CHUNKING
# =========================================================

def _split_large_unit(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[str]:

    sentences = SENTENCE_BOUNDARY.split(text)

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if (
            not current
            or len(current) + len(sentence) + 1
            <= chunk_size
        ):
            current = (
                f"{current} {sentence}"
            ).strip()
            continue

        chunks.append(current)

        if overlap > 0:
            prefix = current[-overlap:]
            current = (
                f"{prefix} {sentence}"
            ).strip()
        else:
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def split_legal_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:

    text = clean_text(text)

    if not text:
        return []

    units = [
        clean_text(unit)
        for unit in LEGAL_BOUNDARY.split(text)
        if clean_text(unit)
    ]

    if not units:
        return _split_large_unit(
            text,
            chunk_size,
            overlap,
        )

    chunks: list[str] = []
    current = ""

    for unit in units:
        if len(unit) > chunk_size:
            if current:
                chunks.append(current)
                current = ""

            chunks.extend(
                _split_large_unit(
                    unit,
                    chunk_size,
                    overlap,
                )
            )
            continue

        if not current:
            current = unit
            continue

        candidate = (
            current + "\n\n" + unit
        )

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            chunks.append(current)

            if overlap > 0:
                tail = current[-overlap:]
                current = clean_text(
                    tail + "\n\n" + unit
                )
            else:
                current = unit

    if current:
        chunks.append(current)

    return [
        chunk
        for chunk in chunks
        if len(chunk.strip()) >= 40
    ]


# =========================================================
# DOCUMENTOS
# =========================================================

def document_hint(path: Path) -> str:
    name = path.stem.lower()

    hints: list[str] = []

    if "14.113" in name or "14113" in name:
        hints.append(
            "Documento legal sobre Fundeb, "
            "VAAF, VAAT e VAAR."
        )

    if "imers" in name:
        hints.append(
            "Documento sobre IMERS e ICMS "
            "Educacional do Rio Grande do Sul."
        )

    if "saers" in name:
        hints.append(
            "Documento sobre SAERS e avaliação "
            "educacional do Rio Grande do Sul."
        )

    if (
        "cif" in name
        and "24" in name
    ):
        hints.append(
            "Resolução CIF nº 24/2026 sobre "
            "condicionalidades do VAAR."
        )

    if (
        "cif" in name
        and "25" in name
    ):
        hints.append(
            "Resolução CIF nº 25/2026 sobre "
            "VAAR 2027, atendimento e aprendizagem."
        )

    if "108" in name:
        hints.append(
            "Emenda Constitucional nº 108 "
            "relacionada ao Fundeb e ICMS Educação."
        )

    return " ".join(hints)


def _document_records(
    raw_dir: Path,
) -> Iterable[tuple[str, dict]]:

    for path in selected_document_paths(raw_dir):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()
        hint = document_hint(path)

        if suffix == ".pdf":
            for page_text, page in extract_pdf(path):
                for index, chunk in enumerate(
                    split_legal_text(page_text)
                ):
                    text = chunk

                    if hint:
                        text = (
                            f"{hint}\n\n{chunk}"
                        )

                    yield text, {
                        "source": path.name,
                        "type": "pdf",
                        "page": page,
                        "chunk": index,
                    }

        elif suffix == ".md":
            yield from markdown_records(path)

        elif suffix == ".txt":
            text = clean_text(
                read_text_file(path)
            )

            for index, chunk in enumerate(
                [chunk for section in re.split(r"(?=^## )", text, flags=re.MULTILINE)
                 for chunk in split_legal_text(section)]
            ):
                final_text = chunk

                if hint:
                    final_text = (
                        f"{hint}\n\n{chunk}"
                    )

                yield final_text, {
                    "source": path.name,
                    "type": suffix.removeprefix("."),
                    "page": 1,
                    "chunk": index,
                }

        elif suffix == ".csv":
            for text, metadata in extract_csv(path):
                if len(text) >= 20:
                    yield text, metadata


def document_records(raw_dir: Path) -> Iterable[tuple[str, dict]]:
    from src.retrieval_policy import classify
    for text, metadata in _document_records(raw_dir):
        yield text, classify(metadata, text, metadata.get('section_path', ''))


# =========================================================
# ÍNDICE / MANIFESTO
# =========================================================

def raw_manifest_hash(
    raw_dir: Path,
) -> str:

    # Alterar a estrutura do leitor exige reindexar mesmo com os mesmos bytes.
    digest = hashlib.sha256(b'markdown-structure-v2\0')

    for path in selected_document_paths(raw_dir):
        if (
            not path.is_file()
            or path.suffix.lower()
            not in SUPPORTED_DOCUMENT_SUFFIXES
        ):
            continue

        digest.update(
            path.name.encode("utf-8")
        )
        digest.update(
            str(path.stat().st_size).encode("utf-8")
        )

        # Hash do conteúdo garante reindexação quando um arquivo muda,
        # mesmo mantendo o mesmo nome.
        file_digest = hashlib.sha256()

        with path.open("rb") as file:
            while True:
                block = file.read(
                    1024 * 1024
                )

                if not block:
                    break

                file_digest.update(block)

        digest.update(
            file_digest.digest()
        )

    return digest.hexdigest()


def read_ready_marker() -> dict | None:
    if not READY_FILE.exists():
        return None

    try:
        return json.loads(
            READY_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return None


def write_ready_marker(
    *,
    manifest: str,
    count: int,
) -> None:

    payload = {
        "index_version": INDEX_VERSION,
        "manifest": manifest,
        "count": count,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "distance_metric": "cosine",
    }

    READY_FILE.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def create_embedding_function(
    max_retries: int = 3,
) -> SentenceTransformerEmbeddingFunction:

    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    last_error: Exception | None = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            return SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL, normalize_embeddings=True
            )

        except Exception as error:
            last_error = error

            if attempt < max_retries:
                print(
                    "[AVISO] Falha ao carregar embeddings. "
                    f"Tentativa {attempt}/{max_retries}."
                )
                time.sleep(5)

    raise RuntimeError(
        "Falha ao carregar o modelo de embeddings "
        f"após {max_retries} tentativas: {last_error}"
    )


def create_chroma_client():
    import chromadb
    CHROMA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return chromadb.PersistentClient(
        path=str(CHROMA_DIR)
    )


def index_documents(
    raw_dir: Path = RAW_DIR,
    reset: bool = False,
    batch_size: int = INDEX_BATCH_SIZE,
) -> int:

    if (
        not raw_dir.exists()
        or not any(raw_dir.iterdir())
    ):
        raise FileNotFoundError(
            f"Nenhum documento encontrado em: "
            f"{raw_dir}"
        )

    manifest = raw_manifest_hash(
        raw_dir
    )

    # Validate the documents before downloading a model or replacing an index.
    # A file containing only whitespace is not a usable knowledge base.
    records = iter(document_records(raw_dir))
    try:
        first_record = next(records)
    except StopIteration:
        raise NoReadableDocumentsError(
            "Nenhum trecho de texto foi encontrado nos documentos. "
            "Verifique se os arquivos em raw/ contêm conteúdo e "
            "se os PDFs possuem texto extraível."
        ) from None

    if RETRIEVAL_MODE == "lexical":
        return 1 + sum(1 for _ in records)

    CHROMA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = create_chroma_client()
    embedding = create_embedding_function()

    marker = read_ready_marker()

    if (
        not reset
        and marker
        and marker.get("index_version")
        == INDEX_VERSION
        and marker.get("manifest")
        == manifest
        and marker.get("embedding_model") == EMBEDDING_MODEL
        and marker.get("chunk_size") == CHUNK_SIZE
        and marker.get("chunk_overlap") == CHUNK_OVERLAP
        and marker.get("distance_metric") == "cosine"
    ):
        try:
            collection = client.get_collection(
                COLLECTION_NAME,
                embedding_function=embedding,
            )

            count = collection.count()

            if (
                count > 0
                and count
                == int(marker.get("count", 0))
            ):
                print(
                    f"[OK] Índice já pronto com "
                    f"{count} chunks."
                )
                return count

        except Exception:
            pass

    # Recria apenas a collection pelo próprio Chroma. Não apagamos a pasta
    # SQLite com shutil.rmtree(), pois clientes ainda abertos podem manter
    # referências ao arquivo removido e causar "readonly database".
    try:
        client.delete_collection(
            COLLECTION_NAME
        )
    except Exception:
        pass

    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        embedding_function=embedding,
        metadata={
            "index_version": INDEX_VERSION,
            "hnsw:space": "cosine",
        },
    )

    documents: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    total = 0

    def flush_batch() -> None:
        nonlocal total

        if not documents:
            return

        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        total += len(documents)

        print(
            f"[INDEXAÇÃO] {total} chunks indexados..."
        )

        documents.clear()
        metadatas.clear()
        ids.clear()

    for text, metadata in chain((first_record,), records):
        locator = (
            metadata.get("row")
            or metadata.get("page")
            or 0
        )

        stable_id = hashlib.sha256(
            (
                f"{metadata['source']}|"
                f"{metadata.get('type', 'document')}|"
                f"{locator}|"
                f"{metadata.get('chunk', 0)}|"
                f"{text}"
            ).encode("utf-8")
        ).hexdigest()

        documents.append(text)
        metadatas.append(metadata)
        ids.append(stable_id)

        if len(documents) >= batch_size:
            flush_batch()

    flush_batch()

    if total == 0:
        raise ValueError(
            "Não foi possível extrair texto "
            "dos documentos."
        )

    write_ready_marker(
        manifest=manifest,
        count=total,
    )

    print(
        f"[OK] Indexação concluída: "
        f"{total} chunks em {CHROMA_DIR}"
    )

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Indexa PDFs, TXTs, MDs e CSVs do PI-5 "
            "no Chroma."
        )
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Apaga o índice antes de "
            "recriá-lo."
        ),
    )

    args = parser.parse_args()

    total = index_documents(
        reset=args.reset
    )

    print(
        f"Índice criado/atualizado com "
        f"{total} chunks."
    )
