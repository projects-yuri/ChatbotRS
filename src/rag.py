from __future__ import annotations

import os
from functools import lru_cache


from src.settings import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MAX_CONTEXT_CHUNKS,
    RAW_DIR,
    TOP_K,
    RETRIEVAL_MODE,
)


SYSTEM_PROMPT = """
Você é o assistente educacional do RS. Responda de forma breve e clara,
somente com as informações dos trechos recuperados. Cite a seção e a fonte.
Não invente leis, fórmulas, datas, índices, valores ou municípios.
Diferencie ano da avaliação, ano da publicação e exercício de distribuição.
A base compacta contém conceitos, principais normas, panorama estadual
e um recorte dos 497 municípios: IMERS 2024/2025, variação, componentes e PRE 2025.
Use apenas os valores municipais explicitamente presentes nos trechos.
PRE já está em porcentagem; não multiplique por 100, não a trate como reais ou IPM.
Um ranking estadual exige comparar todos os municípios; não conclua a partir de poucos trechos.
Não transfira os dados de uma cidade para outra nem a média estadual para uma cidade.
Se faltar um dado pedido, informe explicitamente o limite e não estime.
Não confunda SAERS, IMERS, PRE, IPM, ICMS Educacional e Fundeb.
"""


# =========================================================
# CHROMA
# =========================================================

@lru_cache(maxsize=1)
def get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL, normalize_embeddings=True
    )


@lru_cache(maxsize=1)
def get_collection():
    """
    Abre a collection já preparada pela inicialização do aplicativo.

    Este módulo é somente de consulta: ele nunca apaga nem reconstrói o
    índice. Isso evita que uma pergunta tente escrever no SQLite enquanto
    outro cliente do Chroma ainda está usando o banco.
    """
    import chromadb
    try:
        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        )

        return client.get_collection(
            COLLECTION_NAME,
            embedding_function=get_embedding_function(),
        )
    except Exception as error:
        raise RuntimeError(
            "O índice vetorial não está disponível. "
            "Reinicie o aplicativo para preparar a base documental."
        ) from error


def clear_rag_caches() -> None:
    get_collection.cache_clear()
    get_embedding_function.cache_clear()
    from src.lightweight import _corpus
    _corpus.cache_clear()


# =========================================================
# INVENTÁRIO / RECUPERAÇÃO
# =========================================================

def is_document_inventory_question(question: str) -> bool:
    q = question.lower()

    triggers = [
        "quais documentos",
        "que documentos",
        "documentos você tem",
        "documentos voce tem",
        "documentos disponíveis",
        "documentos disponiveis",
        "arquivos você tem",
        "arquivos voce tem",
        "base documental",
    ]

    return any(trigger in q for trigger in triggers)


def available_document_names() -> list[str]:
    if not RAW_DIR.exists():
        return []

    supported = {
        ".pdf",
        ".txt",
        ".md",
        ".csv",
    }

    from src.ingestion import selected_document_paths
    return [path.name for path in selected_document_paths(RAW_DIR)]


def retrieve(question: str, top_k: int = TOP_K, focus: str | None = None) -> list[dict]:
    from src.search import retrieve as retrieve_hybrid
    return retrieve_hybrid(question, top_k, focus=focus, mode=RETRIEVAL_MODE,
                           collection_factory=get_collection)


# =========================================================
# CONTEXTO / LLM
# =========================================================

def build_context(
    hits: list[dict],
) -> str:

    blocks: list[str] = []

    for index, hit in enumerate(
        hits,
        start=1,
    ):
        blocks.append(
            f"TRECHO {index}\n"
            f"Fonte: {hit['citation']}\n"
            f"{hit['text']}"
        )

    return "\n\n".join(blocks)


def answer(
    question: str,
    focus: str | None = None,
):

    if is_document_inventory_question(question):
        documents = available_document_names()

        if not documents:
            return (
                "Não encontrei documentos na pasta raw/.",
                [],
            )

        lines = [
            "Tenho estes documentos disponíveis na base documental:",
            "",
        ]

        lines.extend(
            f"- {document}"
            for document in documents
        )

        return (
            "\n".join(lines),
            [],
        )

    hits = retrieve(question, focus=focus)

    if not hits:
        from src.lightweight import requested_municipalities, municipality_names
        municipalities = requested_municipalities(question)
        if municipalities:
            names = municipality_names()
            return (
                "A base essencial não possui dados municipais suficientes sobre "
                + ", ".join(names[code] for code in sorted(municipalities))
                + ". Consulte o [IMERSVis](https://imersvis.dee.rs.gov.br/) para os resultados oficiais. "
                "Os valores de outro município ou a média do RS não substituem esse dado.",
                [],
            )
        return (
            "Não encontrei informações suficientes "
            "nos documentos indexados para responder "
            "com segurança.",
            [],
        )

    context = build_context(
        hits
    )
    from src.lightweight import requested_municipalities, municipality_names
    covered = {str(hit.get('codigo_ibge')) for hit in hits}
    from src.retrieval_policy import plan_query
    missing = set() if plan_query(question, focus).legal else requested_municipalities(question) - covered
    if missing:
        names = municipality_names()
        context += "\n\nLIMITE DE COBERTURA: não há resultados municipais nos trechos para " + ", ".join(names[c] for c in sorted(missing)) + ". Informe essa ausência; não use os números de outra cidade."

    api_key = os.getenv(
        "OPENROUTER_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY não configurada."
        )

    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.getenv(
            "OPENROUTER_MODEL",
            "z-ai/glm-5.2:free",
        ),
        api_key=api_key,
        base_url=os.getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        ),
        temperature=0,
        max_tokens=700,
        timeout=60,
        max_retries=1,
    )

    user_prompt = f"""
PERGUNTA:
{question}

TÓPICO SELECIONADO (apoio à interpretação):
{focus or "Todos os tópicos"}

TRECHOS RECUPERADOS:
{context}

INSTRUÇÕES:
- Responda diretamente à pergunta.
- Use somente os trechos recuperados.
- Considere todos os trechos relevantes, não apenas o primeiro.
- Para conceitos, percentuais, requisitos e metodologias, prefira
  legislação, decretos e resoluções presentes nos trechos.
- Não use exemplos de municípios como definição de conceitos.
- Não acrescente dados municipais se a pergunta não solicitar.
- Se a pergunta pedir comparação ou relação entre temas, combine
  informações de mais de um trecho quando necessário.
- Cite as fontes usando exatamente os rótulos apresentados em "Fonte:".
- Se a documentação recuperada realmente não trouxer a informação,
  diga que ela é insuficiente.
"""

    response = llm.invoke(
        [
            (
                "system",
                SYSTEM_PROMPT,
            ),
            (
                "human",
                user_prompt,
            ),
        ]
    )

    text = response.content

    if not isinstance(
        text,
        str,
    ):
        text = str(text)

    return (
        text.strip(),
        hits,
    )

