"""Peca e nicho da campanha: familia do produto (moda, beleza, acessorio...) e nicho.

Sairam de prompts.py: formats.py e o enquadramento precisavam deles e importavam prompts
por dentro de funcoes para fugir do import circular.
"""
import re

# Os nichos com direcao de video propria (prompts._VIDEO_NICHE tem as mesmas chaves; um teste confere).
NICHES = ('praia', 'academia', 'casual', 'dia-a-dia', 'intima', 'fantasia')

FAMILY_WORDS = (
    ('beleza', ('batom', 'base', 'sérum', 'serum', 'creme', 'hidratante', 'protetor solar',
                'máscara de cílios', 'maquiagem', 'skincare', 'shampoo', 'perfume', 'esmalte', 'gloss')),
    ('casa', ('organizador', 'cesto', 'pote', 'suporte de parede', 'luminária', 'luminaria',
              'tapete', 'cortina', 'panela', 'utensílio', 'utensilio', 'almofada', 'edredom')),
    ('gadget', ('fone', 'carregador', 'cabo usb', 'smartwatch', 'caixa de som', 'teclado', 'mouse', 'power bank')),
    ('pet', ('coleira', 'comedouro', 'arranhador', 'caminha para', 'brinquedo para cachorro', 'brinquedo para gato')),
    ('infantil', ('infantil', 'bebê', 'bebe', 'criança', 'crianca', 'kids')),
)

# Acessorios (joia, bijuteria, bolsa, oculos). Palavra inteira e so no nome do
# produto: "anel" por substring casaria com "canelada", "colar" com "colarinho".
ACCESSORY_RE = re.compile(
    r'(?<!\w)(?:brincos?|colar(?:es)?|gargantilhas?|pulseiras?|braceletes?|an[eé]is|anel|alian[cç]as?|'
    r'rel[oó]gios?|[oó]culos|bolsas?|mochilas?|necessaires?|carteiras?|tiaras?|presilhas?|piercings?)(?!\w)',
    re.I)


def _phrase(value):
    return ' '.join(str(value or '').strip().rstrip('.').split())


def product_family(c):
    if ACCESSORY_RE.search(' '.join(_phrase(c.get(k)) for k in ('product', 'outfit'))):
        return 'acessorio'
    blob = ' '.join(_phrase(c.get(k)).casefold() for k in ('product', 'outfit', 'details', 'audience'))
    for family, needles in FAMILY_WORDS:
        if any(n in blob for n in needles):
            return family
    return 'moda'


def niche_key(c):
    niche = (c.get("niche") or "").strip()
    if niche in NICHES:
        return niche
    # fallback from style/outfit keywords
    blob = f"{c.get('style','')} {c.get('outfit','')} {c.get('angle','')}".casefold()
    for key, words in (
        ("praia", ("praia", "beach", "biquini", "verao")),
        ("academia", ("academia", "fitness", "legging", "treino", "active")),
        ("intima", ("intima", "íntima", "lingerie", "sensual")),
        ("fantasia", ("fantasia", "cosplay", "halloween", "personagem")),
        ("dia-a-dia", ("rotina", "dia a dia", "lounge", "casa")),
        ("casual", ("casual", "street")),
    ):
        if any(w in blob for w in words):
            return key
    return "casual"
