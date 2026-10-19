"""Motor de persuasao: necessidade, desejo e escassez -- sempre com fato.

Tres motores, cada um com a sua formula de venda:

- NECESSIDADE (dor -> agitacao -> prova): o gancho nomeia a dor; o meio
  agita em uma frase curta (o incomodo real de quem passa por isso) e entra
  na prova que o video mostra; a chamada oferece a saida.
- DESEJO (encanto -> imaginacao -> posse): o meio faz quem assiste se ver
  usando a peca numa ocasiao concreta ("imagina...").
- ESCASSEZ (novidade -> prova rapida -> prazo/estoque): so existe com
  OFERTA REAL. O texto livre da oferta ("20% ate domingo, ultimas 30 pecas,
  frete gratis") vira fatos separados, e cada fala de urgencia usa um fato
  com o numero exato. Sem prazo declarado nao existe "so hoje"; sem estoque
  declarado nao existe "ultimas pecas".

Prova social ("2 mil vendidos", "nota 4,8") segue a mesma regra: so quando o
operador declara no campo proprio.

Escassez inventada e propaganda enganosa (CDC, art. 37) e motivo de
derrubada de video no TikTok Shop. Por isso a regra aqui nao e enfeite:
a auditoria (services/copywriter.audit) usa as mesmas funcoes para recusar
qualquer urgencia sem o fato correspondente.

Tambem mora aqui a direcao de cena que acompanha cada motor no video do Grok
(expressao no gancho, arco emocional, gesto da chamada) e a linha do tempo
proporcional as falas.
"""
from __future__ import annotations

import re
import unicodedata

from services import script_budget

_WEEKDAYS = r'(?:segunda|terça|terca|quarta|quinta|sexta|sábado|sabado|domingo)(?:-feira)?'


def _norm(text) -> str:
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _clean(text) -> str:
    return ' '.join(str(text or '').split()).strip(' .;,')


# --------------------------------------------------------------------------
# Fatos da oferta e da prova social
# --------------------------------------------------------------------------
def offer_facts(raw) -> dict:
    """Separa a oferta escrita pelo operador em fatos que a fala pode usar.

    >>> offer_facts('20% até domingo · últimas 30 peças · frete grátis')['deadline']
    'até domingo'
    """
    text = _clean(raw)
    if not text:
        return {}
    low = text.casefold()
    facts: dict = {'raw': text}

    m = re.search(r'(\d{1,2})\s*%', low)
    if m:
        facts['discount'] = f'{m.group(1)}% de desconto'
        facts['discount_n'] = m.group(1)
    m = re.search(r'de\s+r\$\s*([\d.,]+)\s+(?:por|a)\s+r\$\s*([\d.,]+)', low)
    if m:
        facts['price_from'], facts['price_to'] = f'R$ {m.group(1)}', f'R$ {m.group(2)}'

    m = re.search(r'\bs[óo]\s+hoje\b|\baté\s+hoje\b|\bate\s+hoje\b|\bhoje\s+s[óo]\b', low)
    if m:
        facts['deadline'] = 'hoje'
    else:
        m = re.search(r'\baté\s+(?:o\s+|a\s+)?((?:meia[- ]noite)|amanhã|amanha|' + _WEEKDAYS
                      + r'|\d{1,2}/\d{1,2}|fim de semana|final de semana|fim do mês|fim do mes|\d{1,2}\s*h(?:\d{2})?)',
                      low)
        if m:
            facts['deadline'] = f'até {m.group(1)}'
        elif re.search(r'\b(?:esse|este|neste|nesse)\s+(?:fim|final)\s+de\s+semana\b', low):
            facts['deadline'] = 'esse fim de semana'
        elif (m := re.search(r'\bpr[óo]xim[ao]s\s+(\d{1,2})\s*h', low)):
            facts['deadline'] = f'nas próximas {m.group(1)} horas'
    if re.search(r'rel[âa]mpago', low):
        facts['flash'] = True

    m = re.search(r'\b(?:últim[oa]s|ultim[oa]s|restam|sobraram)\s+(\d{1,4})\b', low) \
        or re.search(r'\bs[óo]\s+(\d{1,4})\s+(?:peças|pecas|unidades|kits|conjuntos)\b', low)
    if m:
        facts['stock_n'] = m.group(1)
        facts['stock'] = f'as últimas {m.group(1)} peças'
    else:
        m = re.search(r'\b(?:últimas|ultimas)\s+(?:peças|pecas|unidades)(?:\s+(?:do|da|no|na)\s+[a-z0-9]{1,3}\b)?', low)
        if m:
            facts['stock'] = 'as ' + text[m.start():m.end()]
        elif re.search(r'estoque\s+limitado|lote\s+limitado|poucas\s+unidades|edição\s+limitada|edicao\s+limitada', low):
            facts['stock'] = 'estoque limitado'
    if re.search(r'frete\s+gr[áa]tis', low):
        facts['free_shipping'] = True
    m = re.search(r'cupom\s*:?\s*([A-Za-z0-9]{3,20})', text, re.I)
    if m and not m.group(1).isdigit():
        facts['coupon'] = m.group(1).upper()
    m = re.search(r'leve\s+(\d)\s+pague\s+(\d)', low)
    if m:
        facts['bundle'] = f'leve {m.group(1)} pague {m.group(2)}'
    return facts


def social_facts(raw) -> dict:
    """'mais de 2 mil vendidos · nota 4,8' -> fatos de prova social."""
    text = _clean(raw)
    if not text:
        return {}
    low = text.casefold()
    facts: dict = {'raw': text}
    m = re.search(r'((?:mais\s+de\s+)?\d+(?:[.,]\d+)?(?:\s*mil)?)\s*\+?\s*(?:vendid|vendas|pedidos|compras|clientes)', low)
    if m:
        facts['sold'] = m.group(1).strip()
    m = re.search(r'(?:nota|avaliação|avaliacao)\s*:?\s*(\d[.,]\d)|(\d[.,]\d)\s*(?:estrelas|★)', low)
    if m:
        facts['rating'] = (m.group(1) or m.group(2)).replace('.', ',')
    m = re.search(r'(\d+(?:[.,]\d+)?(?:\s*mil)?)\s*avalia', low)
    if m:
        facts['reviews'] = m.group(1)
    return facts if len(facts) > 1 else {}


def _deadline_cta(deadline: str) -> str:
    return 'ainda hoje' if deadline == 'hoje' else deadline


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------
# Falas por motor. Todas recebem as formas da peca do gerador
# (dem/piece/de/prep/pron/teu) e devolvem (molde, texto).
# --------------------------------------------------------------------------
def scarcity_hooks(f: dict, forms: dict) -> list[tuple[str, str]]:
    dem, piece, de, prep = forms['dem'], forms['piece'], forms['de'], forms['prep']
    out = []
    d, dl, st = f.get('discount'), f.get('deadline'), f.get('stock')
    when = 'hoje' if dl == 'hoje' else dl
    if d and dl:
        out.append(('esc-desc-prazo', f'Gente, {dem} {piece} tá com {d} só {when}, olha isso.'))
    if f.get('price_from'):
        out.append(('esc-preco', f'{_cap(piece)} de {f["price_from"]} por {f["price_to"]}? Eu precisei te mostrar isso.'))
    if st == 'estoque limitado':
        out.append(('esc-estoque', f'{_cap(dem)} {piece} tá com estoque limitado, então olha isso agora.'))
    elif st:
        out.append(('esc-estoque', f'{_cap(dem)} {piece} tá acabando: são {st}, olha.'))
    if d and not dl:
        out.append(('esc-desc', f'Achei {dem} {piece} com {d} e precisava te mostrar logo.'))
    if dl and not d:
        out.append(('esc-prazo', f'A oferta {de} {piece} vai só {when}, então olha isso rápido.'))
    if f.get('flash'):
        out.append(('esc-relampago', f'Tá rolando oferta relâmpago {prep} {piece} e eu vim correndo te mostrar.'))
    if f.get('free_shipping') and not out:
        out.append(('esc-frete', f'Achei {dem} {piece} com frete grátis e precisava te mostrar.'))
    if f.get('bundle') and not out:
        out.append(('esc-leve', f'{_cap(dem)} {piece} tá no {f["bundle"]} e eu precisava te mostrar.'))
    return out


def scarcity_closers(f: dict, forms: dict) -> list[tuple[str, str]]:
    out = []
    if f.get('deadline'):
        when = 'hoje' if f['deadline'] == 'hoje' else f['deadline']
        out.append(('fe-prazo', f'Mas a oferta vai só {when}, então eu não deixaria pra depois.'))
    if f.get('stock'):
        if f['stock'] == 'estoque limitado':
            out.append(('fe-estoque', 'E o estoque é limitado, quando acabar, acabou.'))
        else:
            out.append(('fe-estoque', f'E são {f["stock"]}, por isso eu vim te avisar.'))
    if f.get('free_shipping'):
        out.append(('fe-frete', 'E ainda tá com frete grátis, eu amei.'))
    if f.get('coupon'):
        out.append(('fe-cupom', f'E com o cupom {f["coupon"]} fica ainda melhor.'))
    if f.get('bundle'):
        out.append(('fe-leve', f'E tá no {f["bundle"]}, vale muito a pena.'))
    return out


def scarcity_ctas(f: dict, forms: dict) -> list[tuple[str, str]]:
    teu = forms['teu']
    out = []
    if f.get('stock'):
        out.append(('cta-estoque', f'Garante {teu} no carrinho laranja antes que acabe.'))
    if f.get('deadline'):
        out.append(('cta-prazo', f'Corre pro carrinho laranja e garante {teu} {_deadline_cta(f["deadline"])}.'))
    if f.get('coupon'):
        out.append(('cta-cupom', f'Usa o cupom {f["coupon"]} no carrinho laranja.'))
    if f.get('discount'):
        out.append(('cta-desc', f'Corre pro carrinho laranja e garante com {f["discount"]}.'))
    if f.get('free_shipping'):
        out.append(('cta-frete', 'Aproveita o frete grátis e corre pro carrinho laranja.'))
    return out


def social_hooks(s: dict, forms: dict) -> list[tuple[str, str]]:
    dem, piece = forms['dem'], forms['piece']
    out = []
    if s.get('sold'):
        out.append(('sp-vendeu', f'{_cap(dem)} {piece} já vendeu {s["sold"]}, e agora eu entendi por quê.'))
    if s.get('rating'):
        out.append(('sp-nota', f'{_cap(dem)} {piece} tem nota {s["rating"]}, e eu fui ver se era isso tudo.'))
    return out


def social_reactions(s: dict, forms: dict) -> list[tuple[str, str]]:
    out = []
    if s.get('sold'):
        out.append(('re-social', f'E olha, já vendeu {s["sold"]}.'))
    if s.get('rating'):
        out.append(('re-nota', f'E tem nota {s["rating"]} de quem já comprou.'))
    return out


# Agitacao: uma frase curta sobre o incomodo da dor declarada. Fala de
# sentimento comum, nunca de fato do produto.
# Varredura de 144 roteiros: com 3 frases, "quem ja passou por isso sabe
# como e chato" saia em 15% deles. Oito frases, escolhidas pelo indice.
AGITATION = (
    'E quem já passou por isso sabe como é chato.',
    'Ninguém merece ficar pensando nisso o dia inteiro.',
    'E é horrível perceber isso na hora errada, né?',
    'Sério, isso tira a vontade de usar a peça.',
    'E aí você passa o dia todo se ajeitando.',
    'Eu já deixei de usar peça por causa disso.',
    'E a gente só descobre quando já está na rua.',
    'Dá até preguiça de arriscar, né?',
)


def future_pacing(occasion: str, forms: dict) -> list[tuple[str, str]]:
    if not occasion:
        return []
    pron = forms['pron']
    return [('fe-imagina', f'Imagina {forms["dem"]} {forms["piece"]} {occasion}.')]


# --------------------------------------------------------------------------
# Auditoria: cada tipo de urgencia precisa do seu fato.
# --------------------------------------------------------------------------
_CLAIMS = (
    ('estoque', r'\búltim[ao]s\b|\bultim[ao]s\b|\besgot\w*|\bestoque\b|\brestam\b|\bsobra(?:m|ram|ndo)?\b',
     ('stock',)),
    ('prazo', r'\bs[óo]\s+hoje\b|\bacaba\s+hoje\b|\baté\s+(?:hoje|amanhã|amanha|meia|' + _WEEKDAYS
     + r'|o\s+fim|\d)|\bpor\s+tempo\s+limitado\b|\bpr[óo]xim[ao]s\s+\d+\s*h', ('deadline', 'flash')),
    ('fim da oferta', r'\bacab(?:a|e|em|ou|ando|ar)\b', ('stock', 'deadline', 'flash')),
    ('desconto', r'\bdesconto\w*|\d{1,2}\s*%|\bpromo(?:ção|cao|ções|coes)\b|\bde\s+r\$', ('discount', 'price_from')),
    ('relâmpago', r'\brel[âa]mpago\b', ('flash',)),
    ('frete grátis', r'\bfrete\s+gr[áa]tis\b', ('free_shipping',)),
    ('cupom', r'\bcupom\b', ('coupon',)),
)
_SOCIAL = r'\bvend(?:eu|idos?|as)\b|\bavalia(?:ção|cao|ções|coes)\b|\bestrelas\b|\bnota\s+\d'


def urgency_problems(spoken: str, offer_raw, social_raw='') -> list[str]:
    """Urgencia ou prova social sem o fato declarado que a sustente."""
    low = str(spoken or '').casefold()
    f = offer_facts(offer_raw)
    s = social_facts(social_raw)
    problems = []
    if f:
        for label, pattern, needs in _CLAIMS:
            hit = re.search(pattern, low)
            if hit and not any(f.get(n) for n in needs):
                problems.append(f'"{hit.group(0)}" fala de {label}, mas a oferta declarada não tem esse fato')
        for n in re.findall(r'(\d{1,2})\s*%', low):
            if n != f.get('discount_n'):
                problems.append(f'"{n}%" não bate com o desconto declarado')
        for n in re.findall(r'\búltim[ao]s\s+(\d{1,4})\b', low):
            if n != f.get('stock_n'):
                problems.append(f'"últimas {n}" não bate com o estoque declarado')
        if re.search(r'\b(?:s[óo]|acaba)\s+hoje\b', low) and f.get('deadline') and f['deadline'] != 'hoje':
            problems.append(f'"hoje" não bate com o prazo declarado ({f["deadline"]})')
    if s:
        for n in re.findall(r'\bnota\s+(\d[.,]\d)', low):
            if n.replace('.', ',') != s.get('rating'):
                problems.append(f'"nota {n}" não bate com a prova social declarada')
    hit = re.search(_SOCIAL, low)
    if hit and not s:
        problems.append(f'"{hit.group(0)}" é prova social e não foi declarada no briefing')
    return problems


def brief_lines(motor: str, offer_raw, social_raw, has_pain: bool) -> list[str]:
    """O que o pedido para a IA leva sobre o motor e os fatos de urgencia."""
    f = offer_facts(offer_raw)
    s = social_facts(social_raw)
    lines = []
    formula = {
        'necessidade': ('FÓRMULA DO MOTOR (dor → agitação → prova → saída): o hook nomeia a dor em primeira pessoa; '
                        'o desenvolvimento abre com UMA frase curta de agitação (o incômodo real de quem passa por isso, '
                        'sem exagero) e entra na prova que o vídeo mostra; o CTA é a saída para essa dor.'),
        'desejo': ('FÓRMULA DO MOTOR (encanto → imaginação → posse): o hook mostra o que encantou; o desenvolvimento '
                   'faz quem assiste se imaginar usando a peça numa ocasião concreta ("imagina...", "já pensou..."); '
                   'o CTA convida a ter a sua.'),
        'escassez': ('FÓRMULA DO MOTOR (novidade → prova rápida → prazo/estoque): o hook traz a novidade com o fato '
                     'da oferta; o desenvolvimento prova em uma frase e lembra do prazo ou do estoque; o CTA fecha '
                     'com a perda real ("antes que acabe", "ainda hoje") — só com o fato declarado.'),
    }.get(motor)
    if formula:
        lines.append(formula)
    if f:
        partes = []
        if f.get('discount'):
            partes.append(f.get('discount'))
        if f.get('price_from'):
            partes.append(f'de {f["price_from"]} por {f["price_to"]}')
        if f.get('deadline'):
            partes.append(f'prazo: {f["deadline"]}')
        if f.get('flash'):
            partes.append('oferta relâmpago')
        if f.get('stock'):
            partes.append(f'estoque: {f["stock"]}')
        if f.get('free_shipping'):
            partes.append('frete grátis')
        if f.get('coupon'):
            partes.append(f'cupom {f["coupon"]}')
        if f.get('bundle'):
            partes.append(f['bundle'])
        if partes:
            lines.append('FATOS DE URGÊNCIA PERMITIDOS (use exatamente estes números; nenhum outro): '
                         + ' · '.join(partes) + '.')
        sem = [nome for chave, nome in (('deadline', 'prazo'), ('stock', 'estoque'), ('discount', 'desconto'))
               if not f.get(chave) and not (chave == 'discount' and f.get('price_from'))]
        if sem:
            lines.append('A oferta NÃO declara ' + ', '.join(sem) + ': não fale disso.')
    if s:
        partes = [x for x in (f'já vendeu {s["sold"]}' if s.get('sold') else '',
                              f'nota {s["rating"]}' if s.get('rating') else '',
                              f'{s["reviews"]} avaliações' if s.get('reviews') else '') if x]
        lines.append('PROVA SOCIAL DECLARADA (pode citar, com estes números): ' + ' · '.join(partes) + '.')
    else:
        lines.append('PROVA SOCIAL: não declarada — proibido citar vendas, avaliações, estrelas ou nota.')
    return lines


# --------------------------------------------------------------------------
# Direcao de cena por motor (video do Grok)
# --------------------------------------------------------------------------
_PAIN_HOOK = re.compile(r'\b(?:medo|problema|desisti|receio|segurava|odiava|cansei|sofria|chato)\b')
_SCARCITY_HOOK = re.compile(r'desconto|\d\s*%|\boferta\b|acabando|\búltimas\b|frete grátis|\bcupom\b|só hoje|rel[âa]mpago')


def script_motor(motor: str, hook: str) -> str:
    """Motor da cena pelo que o gancho realmente diz. A IA pode abrir com
    uma dor mesmo com o motor "desejo"; a expressao da modelo tem que
    acompanhar a fala ("tinha medo" com sorriso confiante nao convence)."""
    low = str(hook or '').casefold()
    if _PAIN_HOOK.search(low):
        return 'necessidade'
    if _SCARCITY_HOOK.search(low):
        return 'escassez'
    return motor


def scene_direction(motor: str, touch: str) -> dict:
    """Expressao no gancho, arco emocional e gesto da chamada.

    O gesto da chamada aponta para baixo, onde o TikTok Shop mostra o
    carrinho laranja de verdade. O prompt nao cita "tela" nem "carrinho" no
    gesto: com essas palavras o Grok desenhava um icone de carrinho no video.
    Uma mao continua na peca; a outra aponta uma vez e volta.
    """
    # Curto de proposito: o Grok tem limite de caracteres e o prompt corta
    # primeiro o que e menos essencial.
    em = re.sub(r'^o\s', 'no ', re.sub(r'^a\s', 'na ', touch))
    hooks = {
        'necessidade': f'franze de leve a testa, como quem lembra de um problema, toca {touch} e abre um sorriso de alívio',
        'escassez': f'dá um passo rápido até a câmera, sobrancelhas erguidas, como quem traz novidade, e toca {touch}',
        'desejo': f'dá um passo até a câmera com sorriso confiante e passa a mão {em}',
    }
    arcs = {
        'necessidade': 'preocupação → alívio → convite tranquilo',
        'escassez': 'animação → certeza → pressa gentil',
        'desejo': 'encanto → orgulho → convite sorridente',
    }
    cta = 'aponta uma vez para baixo com o indicador, com a outra mão na peça'
    if motor == 'escassez':
        cta += ', num gesto rápido'
    return {'hook': hooks.get(motor, hooks['desejo']), 'arc': arcs.get(motor, arcs['desejo']), 'cta': cta}


def timeline(hook: str, development: str, cta: str, total: int = 15) -> tuple[int, int]:
    """Fim do gancho e inicio da chamada, proporcionais as palavras.

    Com o roteiro padrao (~11/20/8 palavras) da 4s e 12s, os tempos de
    sempre; com um meio mais longo, o meio ganha tempo em vez de a fala
    correr dentro de uma janela fixa.
    """
    # Ritmo de script_budget.WORDS_PER_SECOND, mais meio segundo de respiro.
    # O meio fica com o resto da janela.
    rate = script_budget.WORDS_PER_SECOND
    words = [len(str(x or '').split()) for x in (hook, development, cta)]
    if not sum(words):
        return 4, 12
    end_hook = min(max(3, round(words[0] / rate + 0.5)), 6)
    cta_len = min(max(3, round(words[2] / rate + 0.5)), 5)
    return end_hook, max(end_hook + 5, total - cta_len)
