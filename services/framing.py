"""Enquadramento e clima do video: que plano mostra a peca e em que clima ela e filmada.

Saiu de prompt_improve.py: prompts.py usava estas funcoes e as importava por dentro de
uma funcao, porque prompt_improve importava prompts no topo (import circular).
"""
import re

from services.formats import video_mode
from services.piece import niche_key, product_family

_FRAMING = (
    (('legging', 'calça', 'calca', 'vestido', 'macacão', 'macacao', 'conjunto', 'pijama', 'saia longa', 'jumpsuit'),
     'corpo inteiro, da cabeça aos pés'),
    (('short', 'bermuda', 'saia', 'biquíni', 'biquini', 'maiô', 'maio', 'calcinha', 'saída de praia'),
     'plano americano, dos joelhos para cima'),
    (('top', 'blusa', 'camiseta', 'camisa', 'cropped', 'regata', 'body', 'jaqueta', 'casaco', 'moletom', 'sutiã', 'sutia'),
     'plano médio, da cintura para cima'),
)

# "Reference moods, not just adjectives": uma referencia que o gerador
# reconhece rende mais que "natural" ou "bonito".
_MOOD = {
    'academia': 'fit check de academia gravado no celular, energia de manhã de treino',
    'praia': 'vlog de férias gravado no celular numa tarde de verão',
    'casual': 'fit check de provador postado no TikTok, gravado no iPhone',
    # Sem aspas: o prompt manda falar "so o que esta entre aspas".
    'dia-a-dia': 'vídeo de arrume-se comigo gravado em casa no celular',
    'intima': 'provador elegante com estética de editorial suave, nada explícito',
    'fantasia': 'vídeo de revelação de fantasia no TikTok, clima de festa',
}
_MOOD_POV = 'vídeo POV de unboxing e teste no TikTok, gravado no celular na mão'
_MOOD_OBJECT = 'review de achadinho no TikTok, gravado no celular'


def framing(c: dict) -> str:
    """Plano que mostra a peca inteira com folga (guia: mais aberto para pessoas)."""
    if product_family(c) not in ('moda', 'infantil'):
        return 'plano médio, com o produto nas mãos à altura do peito'
    text = f"{c.get('product', '')} {c.get('outfit', '')}".casefold()
    for words, shot in _FRAMING:
        if any(re.search(r'\b' + re.escape(word) + r'\b', text) for word in words):
            return shot
    return 'plano americano, dos joelhos para cima'


def speech_framing(c: dict) -> str:
    """Plano quando a modelo fala. Corpo inteiro deixa o rosto pequeno e o
    Grok erra identidade e labios: o prompt resumido com "corpo inteiro"
    rendeu 5/10 contra o completo, que pedia plano medio frontal. Com fala,
    o mais aberto e o plano americano; a aproximacao vai ao plano medio."""
    shot = framing(c)
    return 'plano americano, dos joelhos para cima' if shot.startswith('corpo inteiro') else shot


def mood(c: dict) -> str:
    if video_mode(c) == 'pov':
        return _MOOD_POV
    if product_family(c) not in ('moda', 'infantil'):
        return _MOOD_OBJECT
    return _MOOD.get(niche_key(c), _MOOD['casual'])


_PUSH = {
    'corpo inteiro, da cabeça aos pés': 'o plano americano (dos joelhos para cima)',
    'plano americano, dos joelhos para cima': 'o plano médio (da cintura para cima)',
}


def push_target(c: dict) -> str:
    return _PUSH.get(speech_framing(c), 'um plano um pouco mais fechado')
