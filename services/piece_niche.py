"""Aviso peca x nicho: diz quando a peca do produto destoa do nicho escolhido.

So AVISA. Nunca impede criar, gerar ou avancar: saida de praia no casual,
legging no dia a dia e pijama na intima sao usos reais, entao a matriz so
marca o que claramente nao combina (biquini na rotina em casa, legging na
praia, fantasia na academia...).

Os nichos sao os do app, nao os do tutorial do Grok: "dia-a-dia" e rotina EM
CASA (sentar, levantar, andar pela casa), nao trabalho/escritorio; "intima" e
lingerie com tom elegante e discreto, e pijama tambem cai nela (playbook.py).

A peca vem do campo produto (o que manda, como em speech_bank.detect). A
roupa (outfit) so conta quando nao e o texto padrao de algum nicho: escolher o
nicho copia esse texto para o briefing ("Moda praia (biquini, saida de
praia...)"), e trocar de nicho depois faria o aviso acusar uma peca que nao e
a do produto.
"""
from __future__ import annotations

import re
import unicodedata

from services import speech_bank
from services.model_library import NICHE_DEFAULTS, NICHE_LABELS
from services.piece import NICHES, product_family


def _norm(text) -> str:
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ' '.join(''.join(ch for ch in text if not unicodedata.combining(ch)).split())


# Categoria do banco de falas -> grupo de peca.
_GROUP_OF_CATEGORY = {
    'biquini': 'banho', 'maio': 'banho',
    'saida_praia': 'saida_praia',
    'legging': 'treino', 'short_legging': 'treino',
    'pijama': 'dormir', 'baby_doll': 'dormir',
    'fantasia': 'fantasia',
    'calca_jeans': 'rua', 'calca_courino': 'rua', 'colete': 'rua',
    'blusa': 'basico', 'regata': 'basico',
}

# Pecas que o banco de falas nao tem como categoria. Rodam depois dele, entao
# "calcinha de praia" continua sendo biquini.
_EXTRA_GROUPS = (
    ('lingerie', re.compile(
        r'\b(?:lingerie|sutias?|calcinhas?|cuecas?|espartilhos?|corselet|corpete|cinta[ -]liga|'
        r'body (?:de )?renda|body rendado|conjunto de lingerie|camisola sensual)\b')),
    ('treino', re.compile(
        r'\b(?:top (?:fitness|de academia|de treino|esportivo)|conjunto (?:fitness|de academia|de treino)|'
        r'macaquinho (?:fitness|de academia|de treino)|macacao fitness|roupa de (?:academia|treino))\b')),
)

GROUP_LABELS = {
    'banho': 'peça de banho', 'saida_praia': 'saída de praia', 'treino': 'roupa de treino',
    'dormir': 'pijama', 'lingerie': 'lingerie', 'fantasia': 'fantasia',
    'rua': 'peça de sair', 'basico': 'peça básica',
}

# O que cada nicho do app grava (VIDEO_NICHE e NICHE_DEFAULTS).
_NICHE_SCENE = {
    'praia': 'praia ou piscina, com sol e passos na areia/deck',
    'academia': 'treino: agachamento, cós e tecido em movimento',
    'casual': 'look urbano, de rua ou café',
    'dia-a-dia': 'rotina em casa: sentar, levantar e andar pela casa',
    'intima': 'lingerie, com tom elegante e discreto',
    'fantasia': 'fantasia ou cosplay em cenário temático',
}

# grupo -> (nichos onde combina, nichos onde destoa). O que nao esta em
# nenhum dos dois fica sem aviso (ex.: calca jeans na fantasia).
MATRIX = {
    'banho': (('praia',), ('academia', 'casual', 'dia-a-dia', 'intima', 'fantasia')),
    'saida_praia': (('praia', 'casual'), ('academia', 'dia-a-dia', 'intima', 'fantasia')),
    'treino': (('academia', 'casual', 'dia-a-dia'), ('praia', 'intima', 'fantasia')),
    'dormir': (('intima', 'dia-a-dia'), ('praia', 'academia', 'casual', 'fantasia')),
    'lingerie': (('intima',), ('praia', 'academia', 'casual', 'dia-a-dia', 'fantasia')),
    'fantasia': (('fantasia',), ('praia', 'academia', 'casual', 'dia-a-dia', 'intima')),
    'rua': (('casual', 'dia-a-dia'), ('praia', 'academia', 'intima')),
    'basico': (('casual', 'dia-a-dia', 'academia', 'praia'), ('intima',)),
}

_DEFAULT_OUTFITS = {_norm(d.get('outfit')) for d in NICHE_DEFAULTS.values() if isinstance(d, dict)}


def _group_of(text: str) -> tuple[str, str]:
    """(grupo, nome da peca) do texto, ou ('', '')."""
    if not str(text or '').strip():
        return '', ''
    cat_id = speech_bank.detect({'product': text})
    if cat_id in _GROUP_OF_CATEGORY:
        cat = speech_bank.category(cat_id) or {}
        return _GROUP_OF_CATEGORY[cat_id], (cat.get('label') or GROUP_LABELS[_GROUP_OF_CATEGORY[cat_id]]).casefold()
    low = _norm(text)
    for group, pattern in _EXTRA_GROUPS:
        if pattern.search(low):
            return group, GROUP_LABELS[group]
    return '', ''


def piece_group(c: dict) -> tuple[str, str]:
    """Grupo da peca da campanha: pelo produto; pela roupa so se ela nao for texto padrao de nicho."""
    group, name = _group_of(c.get('product'))
    if group:
        return group, name
    outfit = c.get('outfit')
    if _norm(outfit) and _norm(outfit) not in _DEFAULT_OUTFITS:
        return _group_of(outfit)
    return '', ''


def _join(labels) -> str:
    labels = list(labels)
    return labels[0] if len(labels) == 1 else ', '.join(labels[:-1]) + ' ou ' + labels[-1]


def warnings(c: dict) -> list[dict]:
    """Avisos (em portugues) quando a peca destoa do nicho. Lista vazia quando combina ou nao da para saber."""
    niche = (c.get('niche') or '').strip()
    if niche not in NICHES:
        return []   # sem nicho escolhido: o prompt usa a direcao casual, nao ha escolha para questionar
    if product_family(c) != 'moda':
        return []   # beleza, acessorio, casa...: o nicho de roupa nao diz nada sobre a peca
    group, name = piece_group(c)
    if not group:
        return []
    fits, off = MATRIX[group]
    if niche not in off:
        return []
    sugestao = _join(NICHE_LABELS[n] for n in fits)
    texto = (f'A peça ({name}) destoa do nicho {NICHE_LABELS[niche]}: esse nicho grava '
             f'{_NICHE_SCENE[niche]}. {name[:1].upper() + name[1:]} costuma combinar com {sugestao}. '
             'É só um aviso: dá para seguir assim.')
    return [{'kind': 'peca_nicho', 'text': texto}]
