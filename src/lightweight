"""Busca BM25 em memória com identificação exata dos municípios do RS."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

from src.settings import RAW_DIR

STOP_WORDS = set('a ao aos as o os de da das do dos e em na nas no nos para por um uma que qual quais como quanto quantos quando onde se com sobre entre sao ser foi the is what how'.split())
ALIASES = {'imerrs': 'imers', 'leis': 'lei', 'recursos': 'recurso', 'indicadores': 'indicador', 'municipios': 'municipio', 'resultados': 'resultado', 'medias': 'media'}


def normalized(text: str) -> str:
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
    text = re.sub(r"['’]", '', text)
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def tokens(text: str) -> list[str]:
    return [ALIASES.get(t, t) for t in normalized(text).split() if len(t) > 1 and t not in STOP_WORDS]


@lru_cache(maxsize=1)
def municipality_names() -> dict[str, str]:
    # Names/codes only: the registry contains no municipal numerical profiles.
    return json.loads(Path(__file__).with_name('municipalities_rs.json').read_text(encoding='utf-8'))['municipalities']


def requested_municipalities(question: str) -> set[str]:
    query = normalized(question)
    # "Rio Grande" is also a city; exclude the state's full name.
    query = re.sub(r'\brio grande do sul\b', ' ', query)
    matches = []
    for code, name in municipality_names().items():
        phrase = normalized(name)
        for match in re.finditer(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', query):
            if ' ' not in phrase and not re.search(r'\b(?:em|de|do|da|municipio|cidade)\s*$', query[:match.start()]):
                continue
            matches.append((match.start(), match.end(), code))
        for match in re.finditer(r'(?<!\d)' + code + r'(?!\d)', query):
            matches.append((match.start(), match.end(), code))
    # Prefer Vista Alegre do Prata over the shorter contained name Vista Alegre.
    return {code for start, end, code in matches
            if not any(a <= start and b >= end and (a < start or b > end)
                       for a, b, _ in matches)}


@lru_cache(maxsize=2)
def _corpus(signature: tuple):
    from src.ingestion import document_records
    records = list(document_records(RAW_DIR))
    counts = [Counter(tokens(text)) for text, _ in records]
    frequency = Counter(term for count in counts for term in count)
    average = sum(sum(c.values()) for c in counts) / max(1, len(counts))
    return records, counts, frequency, average


def retrieve_lexical(question: str, limit: int = 5, focus: str | None = None) -> list[dict]:
    if limit <= 0:
        return []
    from src.ingestion import selected_document_paths
    signature = tuple((str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in selected_document_paths(RAW_DIR))
    records, counts, frequency, average = _corpus(signature)
    from src.retrieval_policy import eligible, plan_query, query_variants
    plan = plan_query(question, focus)
    query = set(tokens(' '.join(query_variants(question, focus))))
    municipalities = plan.municipalities
    present = {str(metadata.get('codigo_ibge')) for _, metadata in records}
    if municipalities and not plan.legal and not municipalities & present:
        return []
    ranked = []
    for index, ((text, metadata), count) in enumerate(zip(records, counts)):
        entity_code = str(metadata.get('codigo_ibge', ''))
        if not eligible(metadata, plan):
            continue
        length = sum(count.values())
        score = 0.0
        for term in query:
            tf = count[term]
            if tf:
                idf = math.log(1 + (len(records) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / max(1, average)))
        heading = metadata.get('section', '')
        score += 0.6 * len(query & set(tokens(heading)))
        if municipalities and entity_code in municipalities:
            score += 20.0
        if score > 0:
            ranked.append((score, index))
    ranked.sort(reverse=True)
    selected = []
    # Retrieve at least one available passage per city in comparisons.
    for code in sorted(municipalities if not plan.legal else set()):
        match = next(((s, i) for s, i in ranked if str(records[i][1].get('codigo_ibge')) == code), None)
        if match and len(selected) < limit:
            selected.append(match)
    selected += [(s, i) for s, i in ranked if i not in {i for _, i in selected}][:limit - len(selected)]
    hits = []
    for score, index in selected:
        text, metadata = records[index]
        heading = metadata.get('section', '')
        hits.append({**metadata, 'text': text,
                     'citation': f"{metadata['source']} — {heading or 'trecho ' + str(index + 1)}",
                     'distance': 1 / (1 + score)})
    return hits
