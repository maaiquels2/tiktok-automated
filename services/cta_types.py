"""Tipos de CTA dos videos longos (sequencia de 2 ou 3 clipes): o fechamento do ultimo clipe.

A lista de 10 CTAs (reforcar custo-beneficio, urgencia com oferta, quebrar objecao, prova real, diferencial, publico
especifico, comparar com alternativa, experiencia pessoal, relembrar o problema, deixar a decisao com o comprador) e escrita
para criadores. Aqui cada uma vira um fechamento de PRODUTO, sob as regras do projeto:

- So afirma o que o briefing sustenta. Urgencia so com oferta real; prova real so com prova social ou de tamanho declarada;
  objecao so com objecao; publico so com identidade declarada; "relembrar o problema" so com dor ou nos arcos que abrem numa
  duvida ou num problema.
- Comparar nao afirma nada sobre outro produto: so convida a pessoa a comparar com o que ela ja tem.
- Custo-beneficio nao cita preco (nao existe campo de preco): e opiniao em primeira pessoa sobre os tres motivos.
- Experiencia pessoal e gosto ("eu ficaria com ela"), nunca historia de uso que ninguem verifica.
- Todo fechamento chama o carrinho laranja, e so o ultimo clipe pode pedir a compra (services/story_arcs.clip_problems).

A regra: a cor 0 mantem o fechamento validado de sempre; da cor 1 em diante cada cor recebe um tipo (type_for_slot), na
ordem de ORDER e so entre os que o briefing sustenta. Mapa completo em docs/ctas-10.md.
"""
from __future__ import annotations

from services import persuasion

# O que o briefing declarou vem primeiro; depois os que sempre existem.
ORDER = ('oferta', 'objecao', 'prova', 'publico', 'problema', 'diferencial', 'experiencia', 'custo', 'comparar', 'decisao')

LABELS = {
    'oferta': 'Urgência com oferta',
    'objecao': 'Quebrar objeção',
    'prova': 'Prova real',
    'publico': 'Público específico',
    'problema': 'Relembrar o problema',
    'diferencial': 'Destacar um diferencial',
    'experiencia': 'Experiência pessoal',
    'custo': 'Custo-benefício',
    'comparar': 'Comparar com uma alternativa',
    'decisao': 'Deixar a decisão com o comprador',
}

# O que cada tipo pede do briefing (chaves de profile()).
NEEDS = {'oferta': 'offer', 'objecao': 'pain', 'prova': 'proof', 'publico': 'audience', 'problema': 'problem'}

# Orientacao de cada tipo para a IA (uma frase, no fechamento do ultimo clipe).
GUIDE = {
    'oferta': 'cite a oferta real do briefing com os números exatos e mande para o carrinho laranja',
    'objecao': 'responda à objeção do briefing em uma frase e mande para o carrinho laranja',
    'prova': 'cite só a prova real do briefing (vendas, nota, altura ou tamanho) e mande para o carrinho laranja',
    'publico': 'chame o público declarado no briefing pelo nome e mande para o carrinho laranja',
    'problema': 'relembre o problema ou a dúvida que abriu o vídeo e mande para o carrinho laranja',
    'diferencial': 'destaque um dos motivos (fatos do briefing) como o que mais te ganhou e mande para o carrinho laranja',
    'experiencia': 'diga em primeira pessoa o que VOCÊ escolheria (gosto, não história de uso) e mande para o carrinho laranja',
    'custo': 'diga em primeira pessoa que os três motivos compensam, sem citar preço, e mande para o carrinho laranja',
    'comparar': 'convide a comparar com o que a pessoa já tem, sem falar mal de outro produto, e mande para o carrinho laranja',
    'decisao': 'devolva a decisão à pessoa, sem pressão, e lembre que o carrinho laranja está aí',
}

# Opcoes de fala de cada tipo, em ordem: a primeira que o briefing sustenta e que nao repete a abertura das cores
# anteriores vale. {l1} fato, {pron} ele/ela, {pain}, {sold}, {rating}, {h} altura, {s} tamanho, {verb}/{plural} do publico.
MOLDS = {
    'objecao': (
        'Com receio de {pain}? Tira essa dúvida no carrinho laranja.',
        'Quebra essa dúvida de vez: confere no carrinho laranja.',
    ),
    'prova': (
        '{Pron} já vendeu {sold}: confere no carrinho laranja.',
        '{Pron} tem nota {rating}: vai conferir no carrinho laranja.',
        'Eu tenho {h} e peguei o {s}: confere no carrinho laranja.',
        'Eu tenho {h}: confere no carrinho laranja.',
        'Peguei o {s}: escolhe o teu no carrinho laranja.',
    ),
    'publico': (
        'Amigas {plural}, confere no carrinho laranja.',
        'Pra quem {verb}, o carrinho laranja tá aí.',
    ),
    'problema': (
        'Lembra de quando nada parece certo? Confere no carrinho laranja.',
        'Lembra da dúvida do começo? Confere no carrinho laranja.',
        'Lembra do medo de {pain}? Confere no carrinho laranja.',
    ),
    'diferencial': (
        'Só por {l1}, já vale conferir no carrinho laranja.',
        'Me ganhou por {l1}: confere no carrinho laranja.',
    ),
    'experiencia': (
        'Eu mesma ficaria com {pron}: tá no carrinho laranja.',
        'Pra mim foi amor à primeira vista: tá no carrinho laranja.',
    ),
    'custo': (
        'Pra mim, por esses três motivos, vale conferir no carrinho laranja.',
        'Eu acho que esses três motivos compensam: confere no carrinho laranja.',
    ),
    'comparar': (
        'Compara com o que você já tem e confere no carrinho laranja.',
        'Compara com o que você já usa e decide no carrinho laranja.',
    ),
    'decisao': (
        'Fez sentido pra você? O carrinho laranja tá aí.',
        'A decisão é sua: o carrinho laranja tá aí.',
    ),
}

# Quais slots de cada molde precisam existir para o molde servir.
_NEEDS_SLOTS = {
    'Com receio de {pain}': ('pain',),
    'Lembra do medo de {pain}': ('pain',),
    '{Pron} já vendeu {sold}': ('sold',),
    '{Pron} tem nota {rating}': ('rating',),
    'Eu tenho {h} e peguei o {s}': ('h', 's'),
    'Eu tenho {h}:': ('h',),
    'Peguei o {s}': ('s',),
    'Amigas {plural}': ('plural',),
    'Pra quem {verb}': ('verb',),
    'Só por {l1}': ('l1',),
    'Me ganhou por {l1}': ('l1',),
}
# O molde do problema depende do arco (ou da dor): "nada parece certo" so no arco problema, "dúvida do começo" so na dúvida.
_PROBLEM_ARCS = {'Lembra de quando nada parece certo': 'problema', 'Lembra da dúvida do começo': 'questionada'}

MAX_PAIN_WORDS = 4   # a dor entra no fechamento so se for curta


def profile(offer: bool, pain: str, social: dict, size: dict, ident: dict, arc: str) -> dict:
    """O que o briefing sustenta, para escolher o tipo. ``offer``: ha oferta real; ``social``/``size``/``ident``: o que
    services/persuasion.py extraiu do briefing; ``arc``: arco da sequencia."""
    return {
        'offer': bool(offer),
        'pain': bool(pain),
        'proof': bool(social or size),
        'audience': bool(ident),
        'problem': arc in ('problema', 'questionada') or bool(pain),
    }


def available(has: dict) -> list[str]:
    """Tipos que o briefing sustenta, na ordem de rotacao."""
    return [kind for kind in ORDER if not NEEDS.get(kind) or has.get(NEEDS[kind])]


def type_for_slot(slot: int, has: dict) -> str:
    """Tipo do fechamento da cor ``slot``. A cor 0 e o fechamento validado de sempre ('' = sem tipo)."""
    if int(slot or 0) < 1:
        return ''
    kinds = available(has)
    return kinds[(int(slot) - 1) % len(kinds)]


def slot_in_type(slot: int, has: dict) -> int:
    """Qual opcao do tipo a cor usa quando as cores dao a volta nos tipos (a cor 1 e a 11 caem no mesmo tipo)."""
    return (max(1, int(slot or 1)) - 1) // len(available(has))


def label(kind: str) -> str:
    return LABELS.get(kind, '')


def _slots(forms: dict, l1: str, pain: str, social: dict, size: dict, ident: dict) -> dict:
    pron = forms.get('pron') or 'ela'
    pain_ok = pain if pain and len(pain.split()) <= MAX_PAIN_WORDS else ''
    values = {
        'pron': pron, 'Pron': pron[:1].upper() + pron[1:], 'l1': l1, 'pain': pain_ok,
        'sold': (social or {}).get('sold', ''), 'rating': (social or {}).get('rating', ''),
        'h': (size or {}).get('height', ''), 's': (size or {}).get('size', ''),
        'plural': (ident or {}).get('plural', ''), 'verb': (ident or {}).get('verb', ''),
    }
    return values


def offer_candidates(offer: dict, forms: dict) -> list[str]:
    """Fechamentos de urgencia: so o que a oferta real do briefing declara (persuasion.offer_facts), com os numeros dela."""
    if not offer:
        return []
    teu = 'a tua' if forms.get('art') == 'a' else 'o teu'
    out = []
    if offer.get('discount'):
        out.append(f'Tá com {offer["discount"]}: abre o carrinho laranja.')
    if offer.get('deadline'):
        quando = 'só hoje' if offer['deadline'] == 'hoje' else offer['deadline']
        out.append(f'A oferta vai {quando}: abre o carrinho laranja.')
    if offer.get('stock'):
        out.append('O estoque é limitado: garante ' + teu + ' no carrinho laranja.' if offer['stock'] == 'estoque limitado'
                   else f'São {offer["stock"]}: garante {teu} no carrinho laranja.')
    if offer.get('coupon'):
        out.append(f'Usa o cupom {offer["coupon"]} no carrinho laranja.')
    if offer.get('free_shipping'):
        out.append('Aproveita o frete grátis no carrinho laranja.')
    if offer.get('bundle'):
        out.append(f'Tá no {offer["bundle"]}: abre o carrinho laranja.')
    return out


def candidates(kind: str, arc: str, forms: dict, l1: str, pain: str, social: dict, size: dict, ident: dict,
               offer: dict | None = None) -> list[str]:
    """Fechamentos do tipo que o briefing sustenta, prontos para falar. 'oferta' so com a oferta real declarada."""
    if kind == 'oferta':
        return offer_candidates(offer or {}, forms)
    values = _slots(forms, l1, pain, social, size, ident)
    out = []
    for mold in MOLDS.get(kind, ()):
        if any(not values[name] for key, names in _NEEDS_SLOTS.items() if mold.startswith(key) for name in names):
            continue
        arc_of_mold = next((a for key, a in _PROBLEM_ARCS.items() if mold.startswith(key)), '')
        if arc_of_mold and arc_of_mold != arc:
            continue
        out.append(mold.format(**values))
    return out


def rule_text() -> str:
    """Regra para o pedido da IA (fechamento do ultimo clipe de uma sequencia)."""
    itens = '; '.join(f'{LABELS[k]}' for k in ORDER)
    return ('TIPO DE FECHAMENTO (regra): o último clipe fecha num destes tipos de CTA: ' + itens + '. Só os que o briefing '
            'sustenta: urgência só com a oferta real; objeção só com objeção declarada; prova só com vendas, nota, altura ou '
            'tamanho declarados; público só com a identidade declarada. Nunca invente preço, história de uso, credencial '
            'nem fale mal de outro produto. O fechamento chama o carrinho laranja.')
