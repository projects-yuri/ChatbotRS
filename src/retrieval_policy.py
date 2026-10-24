"""Taxonomia e filtros compartilhados pela busca lexical e vetorial."""
import re
import unicodedata
from dataclasses import dataclass

TOPICS = {
    'icms': r'\b(?:icms|ipm|reparticao|cota parte)\b',
    'pre': r'\b(?:pre|rateio|porte)\b',
    'imers': r'\b(?:imers|imerrs|iqa|iqi|iqf|aprovacao)\b',
    'saers': r'\bsaers\b',
    'fundeb': r'\bfundeb\b',
    'ldb': r'\bldb\b',
}
LEGAL = r'\b(?:lei|leis|legislacao|legal|legais|juridica|norma|normas|decreto|decretos|regulamenta\w*|regula\w*|constitucional|emenda|artigo|ec|normativ\w*|resolu\w*)\b'


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def topic_names(text):
    text = normalize(text).replace('-', ' ')
    return {topic for topic, pattern in TOPICS.items() if re.search(pattern, text)}


def classify(metadata, text, path=''):
    """Use o título da seção, sem espalhar o tema do arquivo por cada cidade."""
    title = metadata.get('section', '')
    heading = normalize(title or metadata.get('source', ''))
    municipal = bool(metadata.get('codigo_ibge'))
    kind = ('municipal' if municipal else 'legislation' if re.search(LEGAL, heading)
            else 'reference' if re.search(r'limites|dicionario|dados municipais|escopo', heading)
            else 'overview' if re.search(r'media|panorama', heading) else 'methodology')
    # A introdução do arquivo pode mencionar todos os temas, sem ser legislação.
    topics = {'imers', 'pre'} if municipal else topic_names(title)
    if not topics:
        topics = topic_names(text)
    if kind == 'legislation' and topics & {'pre', 'imers', 'saers'}:
        topics.add('icms')
    result = {**metadata, 'scope': 'municipal' if municipal else 'state', 'kind': kind,
              'section_path': path or title or metadata.get('source', '')}
    result.update({f'topic_{topic}': topic in topics for topic in TOPICS})
    return result


@dataclass
class QueryPlan:
    topics: set
    municipalities: set
    legal: bool


def plan_query(question, focus=None):
    from src.lightweight import requested_municipalities
    explicit = topic_names(question)
    focus_topics = topic_names(focus or '')
    return QueryPlan(explicit or focus_topics, requested_municipalities(question),
                     bool(re.search(LEGAL, normalize(question))))


def eligible(metadata, plan):
    municipal = metadata.get('scope') == 'municipal' or bool(metadata.get('codigo_ibge'))
    if plan.legal:
        if municipal or metadata.get('kind') != 'legislation':
            return False
    elif municipal and (not plan.municipalities or str(metadata.get('codigo_ibge')) not in plan.municipalities):
        return False
    if plan.topics and not municipal:
        return any(metadata.get(f'topic_{topic}', False) for topic in plan.topics)
    return True


def vector_filter(plan):
    clauses = []
    if plan.legal:
        clauses.append({'kind': 'legislation'})
    elif plan.municipalities:
        clauses.append({'$or': [{'scope': 'state'}, {'codigo_ibge': {'$in': sorted(plan.municipalities)}}]})
    else:
        clauses.append({'scope': 'state'})
    if plan.topics:
        topics = [{f'topic_{topic}': True} for topic in sorted(plan.topics)]
        topic_filter = topics[0] if len(topics) == 1 else {'$or': topics}
        if plan.municipalities and not plan.legal:
            topic_filter = {'$or': [topic_filter, {'codigo_ibge': {'$in': sorted(plan.municipalities)}}]}
        clauses.append(topic_filter)
    return clauses[0] if len(clauses) == 1 else {'$and': clauses}


def query_variants(question, focus=None):
    plan = plan_query(question, focus)
    variants = [question]
    if plan.legal and plan.topics:
        variants.append(' '.join(sorted(plan.topics)) + ' legislação leis decretos emenda constitucional')
    elif not topic_names(question) and plan.topics:
        # O foco resolve perguntas elípticas, mas não altera o texto do usuário.
        if re.search(r'\b(?:funciona|calcul|distribui|recurso|percentual|formula|significa|diferenca|indicador|prova)\w*', normalize(question)):
            variants.append(question + ' ' + ' '.join(sorted(plan.topics)))
    return variants
