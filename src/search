"""Recuperação híbrida: BM25 + Chroma, filtros comuns e fusão por posição."""
import logging
from collections import Counter, defaultdict

from src.retrieval_policy import classify, eligible, plan_query, query_variants, vector_filter
from src.settings import CANDIDATE_K, MAX_CONTEXT_CHUNKS

LOGGER = logging.getLogger(__name__)


def key(hit):
    return (hit.get('source'), hit.get('type'), hit.get('page'), hit.get('row'), hit.get('chunk'))


def vector_candidates(collection, question, focus, limit):
    plan = plan_query(question, focus)
    count = collection.count()
    if not count:
        return []
    hits = {}
    for query in query_variants(question, focus):
        result = collection.query(query_texts=[query], n_results=min(limit, count),
                                  where=vector_filter(plan),
                                  include=['documents', 'metadatas', 'distances'])
        for rank, (text, metadata, distance) in enumerate(zip(
                (result.get('documents') or [[]])[0],
                (result.get('metadatas') or [[]])[0],
                (result.get('distances') or [[]])[0]), 1):
            if not text:
                continue
            metadata = classify(metadata or {}, text)
            if not eligible(metadata, plan):
                continue
            hit = {**metadata, 'text': text, 'distance': distance, 'vector_rank': rank}
            identity = key(hit)
            if identity not in hits or rank < hits[identity]['vector_rank']:
                hits[identity] = hit
    return sorted(hits.values(), key=lambda h: (h['vector_rank'], h.get('distance') or 0))


def retrieve(question, top_k=5, focus=None, mode='lexical', collection_factory=None):
    from src.lightweight import retrieve_lexical
    limit = min(max(0, top_k), MAX_CONTEXT_CHUNKS)
    if not limit:
        return []
    plan = plan_query(question, focus)
    candidate_limit = max(CANDIDATE_K, limit * 6)
    lexical = retrieve_lexical(question, candidate_limit, focus=focus)
    vector = []
    if mode in {'vector', 'hybrid'}:
        try:
            vector = vector_candidates(collection_factory(), question, focus, candidate_limit)
        except Exception:
            LOGGER.warning('Busca vetorial indisponível; usando recuperação lexical com filtros.', exc_info=True)
    scores, methods, documents = defaultdict(float), defaultdict(set), {}
    for method, weight, ranked in [('lexical', 1.2, lexical), ('vector', 1.0, vector)]:
        for rank, hit in enumerate(ranked, 1):
            if not eligible(hit, plan):
                continue
            identity = key(hit)
            documents.setdefault(identity, hit)
            scores[identity] += weight / (60 + rank)
            methods[identity].add(method)
    ranked = sorted(documents, key=lambda identity: scores[identity], reverse=True)
    selected = []
    if not plan.legal:
        for code in sorted(plan.municipalities):
            match = next((identity for identity in ranked if str(documents[identity].get('codigo_ibge')) == code), None)
            if match is not None and len(selected) < limit:
                selected.append(match)
    # Dois fragmentos de uma mesma seção bastam; reserve espaço para outras fontes.
    sections = Counter((documents[i].get('source'), documents[i].get('section')) for i in selected)
    for identity in ranked:
        if len(selected) >= limit:
            break
        section = (documents[identity].get('source'), documents[identity].get('section'))
        if identity not in selected and sections[section] < (1 if plan.legal else 2):
            selected.append(identity)
            sections[section] += 1
    results = []
    for identity in selected:
        hit = documents[identity]
        title = hit.get('section') or hit.get('source_locator') or 'trecho'
        results.append({**hit, 'citation': f"{hit.get('source', 'Documento')} — {title}",
                        'retrieval_methods': '|'.join(sorted(methods[identity])), 'rrf_score': scores[identity]})
    return results
