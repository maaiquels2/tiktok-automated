"""Tipos de gancho: a regra de abertura dos videos.

Seis familias de gancho (curiosidade, autoridade, dor, direto, historia, suspense e FOMO) que o estudio escolheu para prender a atencao nos
primeiros segundos. A lista de 50 ganchos que originou isto e escrita para criadores de conteudo ("teu conteudo nao cresce",
"depois de testar por 2 anos"), entao aqui cada familia vira moldes de PRODUTO, sob as regras do projeto:

- So afirma o que o briefing sustenta. Credencial inventada ("testei por 2 anos", "trabalhando com X marcas") e historia que
  ninguem pode verificar ("o dia que tudo deu errado", "nao cometa o mesmo erro que eu") ficam BLOQUEADAS, ver BLOCKED_RE.
- Autoridade so existe com prova declarada (prova social ou altura/tamanho); dor so com dor ou objecao no briefing.
- Historia e a expectativa contra o que a camera mostra agora, nunca um acontecimento passado.
- O gancho fecha o proprio suspense dentro dele (com {det} ou {pain}): o desenvolvimento e escolhido a parte e nao paga um "...".
- Pergunta so se carregar o fato ou a dor; pergunta vazia ("Voce sabia disso?") nao vale.

A regra: cada cor da campanha recebe um tipo de gancho (type_for_color) e o gerador local, o pedido da IA e a auditoria seguem
esse tipo. Mapa dos 50 originais em docs/ganchos-50.md.
"""
from __future__ import annotations

import re

# O que o briefing declarou vem primeiro (identidade/prova, depois a dor), como a ordem dos ganchos sempre foi.
ORDER = ('autoridade', 'dor', 'curiosidade', 'fomo', 'direto', 'historia')

LABELS = {
    'curiosidade': 'Curiosidade',
    'autoridade': 'Autoridade e prova',
    'dor': 'Dor e problema',
    'direto': 'Direto e chamativo',
    'historia': 'História',
    'fomo': 'Suspense e FOMO',
}

# O que cada tipo precisa do briefing para existir.
NEEDS = {'dor': 'pain', 'autoridade': 'proof'}

# Slots: {dem} esse/essa, {prep} nesse/nessa, {de} do/da, {piece} a peça, {det} o detalhe com artigo, {pain} a dor da objeção.
MOLDS = {
    'curiosidade': (
        'O que ninguém percebe {prep} {piece} é {det}, eu só vi de perto.',
        'Ninguém te conta isso {de} {piece}, mas {det} me {v_chamou} atenção.',
        'Isso parece simples {prep} {piece}, mas {det} me {v_fez} olhar duas vezes.',
        'Eu descobri algo {prep} {piece} que quase ninguém comenta: {det}.',
        'Você já percebeu {det} {prep} {piece}? Eu só vi de perto.',
    ),
    'dor': (
        'Se o seu medo é {pain}, olha o que eu achei {prep} {piece}.',
        'O medo de {pain} me travava, até eu ver {dem} {piece} de perto.',
        'Eu entendo quem evita {dem} {piece} por medo de {pain}.',
        'Não deixa o medo de {pain} te segurar, olha o que eu achei.',
        'Se o medo de {pain} também é seu, olha o que eu achei.',
    ),
    'direto': (
        'Para tudo e olha {det} {prep} {piece}, eu quase passei batido.',
        'Eu vou ser direta: {det} me {v_fez} separar {dem} {piece}.',
        'Presta atenção nessa parte {de} {piece}: {det} {v_foi} o que eu vi primeiro.',
        'Olha {det} {prep} {piece}: {v_foi} o que mais {v_chamou} minha atenção.',
        'Olha isso aqui: {det} {prep} {piece} me {v_ganhou} na hora.',
    ),
    'historia': (
        'Eu pensei que {dem} {piece} não ia me convencer, até ver {det}.',
        'Eu nunca contei isso, mas eu duvidava {de} {piece} até ver {det}.',
        'Tudo mudou quando eu vi {det} {prep} {piece} de perto.',
        'Eu achava {dem} {piece} comum, mas {det} me {v_fez} mudar de ideia.',
        'Parece simples, mas {det} {prep} {piece} me {v_surpreendeu} de verdade.',
    ),
    # Autoridade nao tem molde novo: ela so existe com prova declarada, e esses moldes ja estao em services/persuasion.py
    # (prova social, altura e tamanho, identidade do publico).
    # Suspense e medo de ficar de fora (decisao do estudio): abre uma lacuna que o proprio gancho fecha com o fato. Nao e
    # escassez: estoque, prazo e preco continuam so com oferta real (services/persuasion.py).
    'fomo': (
        'Eu não deveria te contar isso, mas {det} {prep} {piece} me {v_conquistou}.',
        'Você não vai acreditar no que {det} {prep} {piece} me {v_mostrou}.',
        'Se eu te contar o que tem {prep} {piece}, você não acredita: {det}.',
        'A maioria nem repara {det} {prep} {piece}, e eu quase fiz igual.',
        'Você provavelmente nunca reparou {det} {prep} {piece}, eu só vi de perto.',
        'Aqui está o segredo {de} {piece} que eu descobri: {det}.',
        'Eu precisava compartilhar isso: {det} {prep} {piece} me {v_pegou} de surpresa.',
        'Talvez este seja o vídeo que eu queria ter visto antes de escolher {dem} {piece}.',
    ),
    'autoridade': (),
}

# Verbos que concordam com o detalhe: "o bolso me chamou atencao" / "as argolas me chamaram atencao".
_VERBS = {'chamou': 'chamaram', 'fez': 'fizeram', 'foi': 'foram', 'ganhou': 'ganharam', 'surpreendeu': 'surpreenderam',
          'conquistou': 'conquistaram', 'mostrou': 'mostraram', 'pegou': 'pegaram'}

# Prefixo do identificador do molde -> tipo, para os moldes que ja existiam no gerador (services/prompts._hook_pool).
PREFIX_TYPE = {
    'ht': None,            # ht-<tipo>-<n>: o tipo vem do proprio identificador
    'desc': 'curiosidade', 'cont': 'historia', 'nec': 'dor', 'sp': 'autoridade', 'sz': 'autoridade', 'id': 'autoridade',
}

# Credencial e historia que ninguem pode verificar: bloqueadas em QUALQUER gancho (regra do projeto, nao so deste modulo).
BLOCKED_RE = re.compile(
    r'depois de testar|testando h[áa]|testei por \d|trabalhando com (?:\d+|x)\s+marcas|h[áa] \d+\s+(?:anos|meses)|'
    r'faz \d+\s+(?:anos|meses)|o dia que tudo deu errado|aprendi da pior forma|n[ãa]o cometa o mesmo erro que eu|'
    r'isso me fez ganhar|ganhar \+ seguidores|me pediram muito|aprendi isso depois de perder|aprendi isso trabalhando', re.I)

# Pergunta vazia: curta, sem o fato nem a dor dentro ("Voce sabia disso?").
_EMPTY_QUESTION_RE = re.compile(r'^(?:voc[êe]\s+(?:sabia|j[áa]\s+percebeu|nunca\s+viu)\s+(?:isso|disso|isso\s+antes)|'
                                r'sabia\s+disso|j[áa]\s+percebeu\s+isso)\s*\??$', re.I)


def type_of(tid: str) -> str:
    """Tipo de um molde pelo identificador ('' quando o molde nao tem tipo)."""
    parts = str(tid or '').split('-')
    if not parts or parts[0] not in PREFIX_TYPE:
        return ''
    if parts[0] == 'ht':
        return parts[1] if len(parts) > 2 and parts[1] in MOLDS else ''
    return PREFIX_TYPE[parts[0]] or ''


def available(has_pain: bool, has_proof: bool) -> list[str]:
    """Tipos que o briefing sustenta, na ordem de rotacao."""
    ok = {'pain': has_pain, 'proof': has_proof}
    return [t for t in ORDER if not NEEDS.get(t) or ok[NEEDS[t]]]


def type_for_color(index: int, has_pain: bool = False, has_proof: bool = False) -> str:
    """Tipo de gancho da cor `index`: os tipos disponiveis giram na ordem, uma cor por tipo."""
    seq = available(has_pain, has_proof)
    return seq[int(index or 0) % len(seq)]


def slot_in_type(index: int, has_pain: bool = False, has_proof: bool = False) -> int:
    """Quantas cores antes desta ja usaram o mesmo tipo: escolhe o molde dentro do tipo sem repetir."""
    return int(index or 0) // len(available(has_pain, has_proof))


def typed_hooks(forms: dict, det: str, pain: str = '') -> list[tuple[str, str]]:
    """Moldes novos ja preenchidos, como pares (id, texto) para o pool de ganchos."""
    plural = bool(re.match(r'^(os|as)\s', str(det).strip(), re.I)) or ' e ' in f' {det} '
    values = {**forms, 'det': det, 'pain': pain, **{f'v_{k}': (v if plural else k) for k, v in _VERBS.items()}}
    out = []
    for kind in ORDER:
        for n, mold in enumerate(MOLDS[kind]):
            if '{pain}' in mold and not pain:
                continue
            if '{det}' in mold and not det:
                continue
            text = re.sub(r'\s+', ' ', mold.format_map(_Slots(values))).strip()
            if '{' not in text:
                out.append((f'ht-{kind}-{n}', text))
    return out


def restrict(pool: list, kind: str) -> list:
    """Candidatos do tipo, com os moldes novos na frente (na dor, os do briefing vem primeiro).

    Devolve o pool inteiro quando nenhum candidato tem o tipo: melhor um gancho de outro tipo que nenhum."""
    own = [item for item in pool if isinstance(item, tuple) and type_of(item[0]) == kind]
    if not own:
        return pool
    if kind == 'dor':
        return own
    new = [item for item in own if item[0].startswith('ht-')]
    return new + [item for item in own if not item[0].startswith('ht-')]


def problems(hook: str) -> list[str]:
    """Violacoes da regra de gancho no texto falado (vale para o gerador local e para a IA)."""
    text = re.sub(r'\s+', ' ', str(hook or '')).strip()
    found = []
    if BLOCKED_RE.search(text):
        found.append('o hook inventa credencial ou história que ninguém pode verificar')
    if _EMPTY_QUESTION_RE.match(text):
        found.append('o hook é uma pergunta vazia; a pergunta precisa carregar o fato ou a dor')
    return found


# Marcas de medo, receio e duvida: so o gancho do tipo Dor pode falar disso (e so da dor que o briefing declarou).
_FEAR_RE = re.compile(r'\b(?:medo|receio|insegur\w*|trav(?:o|a|ava|ando)|d[úu]vida|sab(?:er|ia) se\b[^.;,]{0,30}\bserv\w+)\b', re.I)

# O que o hook de cada tipo faz (vai no pedido da IA, na linha do tipo obrigatorio da cor).
TYPE_BRIEF = {
    'curiosidade': 'abra com um fato confirmado do produto (um dos Detalhes) numa frase que fecha o suspense sozinha',
    'fomo': 'abra uma lacuna de suspense e feche com um fato confirmado do produto, como "Você não vai acreditar no que o bojo me mostrou"',
    'direto': 'chame a atenção para um detalhe confirmado do produto, sem rodeio, como "Para tudo e olha o bojo, eu quase passei batido"',
    'historia': 'conte a expectativa contra o que se vê agora, com um fato confirmado, como "Eu achava comum, até ver o bojo"',
    'autoridade': 'abra com a prova declarada no briefing (vendas, nota, altura, tamanho ou identidade do público)',
    'dor': 'parta do receio ou da objeção declarados no briefing e feche com o que resolve a dúvida',
}


def type_problems(hook: str, kind: str) -> list[str]:
    """O hook de uma cor que NAO e do tipo Dor nao fala de medo, receio nem duvida: era o que a IA fazia em todas as cores
    quando o briefing tinha objecao (teste real no site, 2026-11-05), e o medo inventado ("medo de nao me sentir bonita")
    passava pela auditoria. Sem tipo na cor, nao confere."""
    if not kind or kind == 'dor':
        return []
    if _FEAR_RE.search(str(hook or '')):
        return [f'o hook desta cor é do tipo "{LABELS.get(kind, kind)}" e não pode falar de medo, receio ou dúvida: '
                'abra com um fato confirmado do produto']
    return []


def classify(hook: str) -> str:
    """Tipo provavel de um gancho escrito (IA ou operador), por padrao de abertura. '' quando nao reconhece."""
    low = re.sub(r'\s+', ' ', str(hook or '')).strip().casefold()
    rules = (
        ('autoridade', r'já vendeu|tem nota|eu tenho \d|\bamigas\b|se você é\b'),
        ('dor', r'\bmedo\b|\bme travava\b|\bproblema\b|se você se identifica|evitando'),
        ('fomo', r'não deveria te contar|não vai acreditar|você não acredita|^a maioria nem repara|provavelmente nunca|aqui está o segredo|eu precisava compartilhar|^talvez este seja'),
        ('historia', r'^eu (?:pensei|achava|nunca contei|duvidava)|^tudo mudou|^eu achei que|^esperava|^parece simples'),
        ('curiosidade', r'ninguém (?:te conta|percebe)|o que ninguém|que quase ninguém|^isso parece simples|você já percebeu|descobri'),
        ('direto', r'^para tudo|^eu vou ser diret|^presta atenção|^olha (?:isso|o|a|os|as) '),
    )
    for kind, pattern in rules:
        if re.search(pattern, low):
            return kind
    return ''


def rule_text() -> str:
    """O trecho da regra que entra no pedido para a IA (services/copywriter.py)."""
    return (
        'TIPO DE GANCHO (regra): cada cor recebe um TIPO de gancho e o hook segue esse tipo. '
        'Curiosidade = abre uma dúvida e fecha dentro do próprio hook com o fato ("O que ninguém percebe nessa peça é o '
        'bolso."). '
        'Dor = parte do receio declarado no briefing ("O medo de errar o tamanho me travava, até eu olhar de perto."). '
        'Direto = chama a atenção para o detalhe, sem enrolar ("Para tudo e olha o acabamento, eu quase passei batido."). '
        'História = a expectativa contra o que se vê agora ("Eu pensei que não ia me convencer, até ver a barra."). '
        'Autoridade = só com prova social, altura ou tamanho declarados no briefing. '
        'Suspense e FOMO = abre uma lacuna e fecha dentro do hook ("Você não vai acreditar no que o bolso me mostrou."). '
        'PROIBIDO no hook: credencial ou história que ninguém pode verificar ("depois de testar por 2 anos", "trabalhando com '
        'X marcas", "o dia que tudo deu errado", "não cometa o mesmo erro que eu"), urgência de estoque, prazo ou preço sem oferta '
        'real, e pergunta vazia ("você sabia disso?"). Pergunta só se carregar o fato ou a dor.')


class _Slots(dict):
    def __missing__(self, key):
        return '{' + key + '}'
