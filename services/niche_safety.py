"""Seguranca da moda intima e da fantasia: so AVISA, nunca bloqueia.

Le o texto que o app ja gerou (prompt de video e de imagem, falas, legenda,
textos de tela, de cada cor) e os movimentos do briefing, e avisa quando ele
pede nudez, sexualizacao ("sensual", "sexy"...), close no corpo em vez da
peca, angulo ou pose intima, ou quando o publico do briefing inclui menores de
idade. Vale para os nichos intima e fantasia e para lingerie, pijama e
fantasia em qualquer nicho.

Pijama e lingerie sao tratados separados: o nicho intima foi escrito para
lingerie ("sensual clean"), mas pijama e baby doll tambem caem nele. Para
pijama o aviso de "sensual" explica que o tom vem do padrao da lingerie, e
deitar na cama nao conta como pose intima.

Os textos padrao do app ja trazem proibicoes ("Evitar nudez", "nada
explicito", "EVITAR: ...; nudez, zoom agressivo"). Uma palavra so conta quando
nao esta negada: nem na mesma oracao (sem, nunca, nao, nada, nem, jamais,
evitar) nem numa frase que comeca proibindo (EVITAR:, nao inventar...).

Campanhas criadas antes de 01/11/2026 guardam os textos antigos (publico "16-35" na fantasia, tom
"sensual clean" na intima) e continuam sendo avisadas; os padroes novos (18+, elegante e discreto) nao disparam o aviso.
"""
from __future__ import annotations

import re
import unicodedata

from services.piece import product_family
from services.piece_niche import piece_group

SAFETY_NICHES = ('intima', 'fantasia')
SAFETY_GROUPS = ('lingerie', 'dormir', 'fantasia')

_PROMPT_SOURCES = (
    ('video', 'prompt de vídeo'), ('image', 'prompt de imagem'),
    ('hook', 'falas'), ('development', 'falas'), ('cta', 'falas'),
    ('caption', 'legenda'), ('cover_text', 'texto da capa'), ('screen_text', 'texto na tela'),
)

_BRIEF_FIELDS = (
    ('tone', 'Tom'), ('style', 'Estilo visual'), ('audience', 'Público'), ('movements', 'Movimentos'),
    ('details', 'Detalhes'), ('angle', 'Ângulo'), ('benefit', 'Benefício'), ('outfit', 'Roupa'),
)


def _fold(text) -> str:
    """Minusculas e sem acento, mantendo pontuacao (a negacao depende dela)."""
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


_W = r'(?:\s+[\w-]+){0,3}?\s+'   # ate 3 palavras entre o verbo de camera e a regiao do corpo
_REGIAO = (r'(?:decote|seios?|peito|busto|bumbum|bunda|nadegas?|gluteos?|virilha|entre as pernas|coxas?|'
           r'quadril|barriga|umbigo|cavado|regiao intima|partes intimas)')

# (categoria, rotulo mostrado, padrao no texto ja sem acento)
_TERMS = (
    ('nudez', 'nudez', r'\bnudez\b'),
    ('nudez', 'nua', r'\b(?:semi)?nua\b'),
    ('nudez', 'pelada', r'\bpelad[ao]s?\b'),
    ('nudez', 'sem roupa', r'\bsem roupas?\b'),
    ('nudez', 'topless', r'\btopless\b'),
    ('nudez', 'seios à mostra', r'\bseios? a mostra\b'),
    ('nudez', 'mamilo', r'\bmamilos?\b'),
    ('sensual', 'sensual', r'\bsensua(?:l|is|lidade)\b'),
    ('sensual', 'sexy', r'\bsexy\b'),
    ('sensual', 'sexualizado', r'\bsexualizad[ao]s?\b|\bsexuais?\b'),
    ('sensual', 'provocante', r'\bprovoca(?:nte|ntes|tiv[ao]s?|ndo)\b'),
    ('sensual', 'sedutora', r'\bsedu(?:tor[ae]?s?|cao|zir|z)\b'),
    ('sensual', 'erótico', r'\berotic[ao]s?\b'),
    ('sensual', 'explícito', r'\bexplicit[ao]s?\b'),
    ('sensual', 'excitante', r'\bexcitante\b'),
    ('sensual', 'insinuante', r'\binsinuante\b'),
    ('sensual', 'picante', r'\bpicante\b'),
    ('close', 'close no corpo', r'\b(?:close|zoom|plano fechado|detalhe de perto|aproxima\w*)' + _W + _REGIAO + r'\b'),
    ('close', 'câmera percorrendo o corpo', r'\bcamera\s+(?:desce|sobe|percorre|passeia|desliza)\w*(?:\s+\w+){0,2}\s+(?:pelo|por todo o|no)\s+corpo\b'),
    ('angulo', 'câmera de baixo', r'\bcamera de baixo\b|\bde baixo para cima\b|\bcontra-?plonge\w*'),
    ('angulo', 'pose deitada', r'\bdeitad[ao]s?\b|\bde brucos\b'),
    ('angulo', 'de quatro', r'\bde quatro\b'),
    ('angulo', 'pernas abertas', r'\bpernas abertas\b|\babr\w+ as pernas\b'),
    ('angulo', 'empinar', r'\bempin\w+'),
    ('angulo', 'rebolar', r'\brebol\w+'),
    ('angulo', 'morder o lábio', r'\bmorde\w*\s+o\s+labio\b|\blambe\w*\s+os?\s+labios?\b'),
)
_COMPILED = tuple((cat, label, re.compile(p)) for cat, label, p in _TERMS)

_NEG_CLAUSE = re.compile(r'\b(?:sem|nunca|nao|nada|nem|jamais|evit\w*|proibid\w*|zero)\b')
_NEG_SENTENCE = re.compile(r'\b(?:evitar|avoid|proibid\w*|nao inventar|nunca)\b')


def _negated(text: str, start: int) -> bool:
    sentence_start = max(text.rfind(ch, 0, start) for ch in '.!?\n') + 1
    clause_start = max(sentence_start, max(text.rfind(ch, 0, start) for ch in ';,(') + 1)
    if _NEG_CLAUSE.search(text[clause_start:start]):
        return True
    # "EVITAR: textos...; nudez, zoom agressivo" -- a lista inteira esta proibida.
    return bool(_NEG_SENTENCE.search(text[sentence_start:start]))


def find_terms(text) -> list[tuple[str, str]]:
    """(categoria, rotulo) de cada termo de risco nao negado no texto."""
    low = _fold(text)
    found = []
    for cat, label, pattern in _COMPILED:
        for m in pattern.finditer(low):
            if not _negated(low, m.start()):
                found.append((cat, label))
                break
    return found


# Idade minima do publico: "16-35", "16 a 35", "a partir de 14", "13+", "15 anos".
_AGE_RANGE = re.compile(r'\b(\d{1,2})\s*(?:-|–|a|ate)\s*\d{1,2}\b')
_AGE_FROM = re.compile(r'\b(?:a partir d[eo]s?|acima d[eo]s?|maiores de|\+)\s*(\d{1,2})\b|\b(\d{1,2})\s*\+|\b(\d{1,2})\s*anos\b')
_MINOR_WORDS = re.compile(r'\b(?:criancas?|infantil|infantis|kids|adolescentes?|teens?|juvenil|juvenis|'
                          r'menor(?:es)? de idade|pre-?adolescentes?|meninas? de \d{1,2})\b')


def minor_audience(audience) -> str:
    """Trecho do publico que inclui menores de 18 anos, ou ''."""
    low = _fold(audience)
    for m in _AGE_RANGE.finditer(low):
        if int(m.group(1)) < 18:
            return m.group(0)
    for m in _AGE_FROM.finditer(low):
        age = next(g for g in m.groups() if g)
        if int(age) < 18:
            return m.group(0).strip()
    m = _MINOR_WORDS.search(low)
    return m.group(0) if m else ''


def _texts(c: dict):
    """(onde, texto) de tudo o que o app gerou para a campanha, mais os movimentos do briefing."""
    prompts = c.get('prompts') if isinstance(c.get('prompts'), dict) else {}
    for key, where in _PROMPT_SOURCES:
        if prompts.get(key):
            yield where, prompts[key]
    for variant in c.get('variants') or []:
        vp = variant.get('prompts') if isinstance(variant, dict) else None
        if not isinstance(vp, dict):
            continue
        cor = (variant.get('color') or '').strip()
        for key, where in _PROMPT_SOURCES:
            if vp.get(key):
                yield (f'{where} ({cor})' if cor else where), vp[key]
    if c.get('movements'):
        yield 'movimentos do briefing', c['movements']


def _join(items) -> str:
    items = list(dict.fromkeys(items))
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' e ' + items[-1]


def _origin(c: dict, label: str) -> str:
    """Campos do briefing que trazem o mesmo termo (para dizer de onde ele veio)."""
    campos = []
    for key, name in _BRIEF_FIELDS:
        if any(lab == label for _, lab in find_terms(c.get(key))):
            campos.append(name)
    return f' O termo vem do briefing (campo {_join(campos)}).' if campos else ''


def applies(c: dict) -> bool:
    niche = (c.get('niche') or '').strip()
    return niche in SAFETY_NICHES or piece_group(c)[0] in SAFETY_GROUPS


def warnings(c: dict) -> list[dict]:
    """Avisos de seguranca (em portugues). Lista vazia fora de intima, fantasia, lingerie e pijama."""
    if not applies(c):
        return []
    niche = (c.get('niche') or '').strip()
    group, name = piece_group(c)
    # A peca manda no assunto; sem peca reconhecida, o nicho.
    if group == 'dormir':
        tipo = 'pijama'
    elif group in ('lingerie', 'fantasia'):
        tipo = group
    else:
        tipo = 'lingerie' if niche == 'intima' else 'fantasia'
    pijama, fantasia = tipo == 'pijama', tipo == 'fantasia'
    assunto = (name[:1].upper() + name[1:]) if pijama else ('Fantasia' if fantasia else 'Moda íntima')

    achados: dict[tuple[str, str], list[str]] = {}
    for where, text in _texts(c):
        for cat, label in find_terms(text):
            if pijama and label == 'pose deitada':
                continue   # pijama na cama e uso normal; para lingerie e pose intima
            achados.setdefault((cat, label), []).append(where)

    out = []
    for (cat, label), onde in achados.items():
        onde_txt = _join(onde)
        if cat == 'nudez':
            texto = (f'{assunto}: o texto gerado fala em “{label}” ({onde_txt}). Nudez é proibida no TikTok '
                     'e o gerador costuma recusar; tire esse trecho.')
        elif cat == 'sensual' and pijama:
            texto = (f'{assunto}: o texto gerado pede “{label}” ({onde_txt}). Esse tom vem do padrão da moda '
                     'íntima, pensado para lingerie; pijama costuma vender com tom aconchegante (conforto, '
                     'hora de dormir). Se quiser, troque Tom e Estilo no briefing.')
        elif cat == 'sensual' and fantasia:
            texto = (f'{assunto}: o texto gerado pede “{label}” ({onde_txt}). Fantasia com apelo sexual tem '
                     'distribuição limitada no TikTok; o vídeo vende pela transformação e pelos acessórios.')
        elif cat == 'sensual':
            texto = (f'{assunto}: o texto gerado pede “{label}” ({onde_txt}). O TikTok restringe conteúdo '
                     'sexualizado em lingerie e o gerador pode recusar; o vídeo vende pelo caimento, pelo tecido '
                     'e pelo ajuste.')
        elif cat == 'close':
            texto = (f'{assunto}: o texto gerado pede {label} ({onde_txt}). Close na região do corpo em vez da '
                     'peça é lido como conteúdo sexualizado; prefira close no tecido, na renda ou no acabamento.')
        else:
            texto = (f'{assunto}: o texto gerado pede “{label}” ({onde_txt}), um ângulo ou pose íntima. '
                     'Prefira enquadramento frontal e câmera estável.')
        out.append({'kind': 'seguranca', 'text': texto + _origin(c, label)})

    menor = minor_audience(c.get('audience'))
    infantil = product_family(c) == 'infantil'
    if menor or infantil:
        trecho = f'o público do briefing inclui menores de 18 anos (“{menor}”)' if menor else 'o produto é infantil'
        if fantasia:
            texto = (f'Fantasia: {trecho}. O vídeo mostra uma modelo adulta; conteúdo de fantasia voltado a '
                     'menor de idade pede cuidado redobrado com as regras do TikTok. Revise o campo Público.')
        elif pijama:
            texto = (f'{assunto}: {trecho}. O vídeo mostra uma modelo adulta; para público infantil ou '
                     'adolescente, não use o tom nem os textos da moda íntima. Revise o campo Público.')
        else:
            texto = (f'{assunto}: {trecho}. Moda íntima e pijama não devem ser direcionados a menores de idade '
                     'nem mostrados por modelo adulta para esse público. Revise o campo Público.')
        out.append({'kind': 'seguranca', 'text': texto})
    return out
