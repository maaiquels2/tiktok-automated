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


# Enquadramento escolhido na criacao (fichas em "Camera e tecnicas", guardado em video_style). Sem escolha, vale a peca.
FRAME_TOKENS = {'enq_inteiro': 'inteiro', 'enq_joelhos': 'joelhos', 'enq_cintura': 'cintura'}
_SHOT_BY_FRAME = {'inteiro': 'corpo inteiro, da cabeça aos pés', 'joelhos': 'plano americano, dos joelhos para cima',
                  'cintura': 'plano médio, da cintura para cima'}


def frame_override(c: dict) -> str:
    """'inteiro', 'joelhos' ou 'cintura' quando o estudio escolheu o enquadramento; '' deixa a peca decidir."""
    for part in str(c.get('video_style') or '').split(','):
        frame = FRAME_TOKENS.get(part.strip())
        if frame:
            return frame
    return ''


def framing(c: dict) -> str:
    """Plano que mostra a peca inteira com folga (guia: mais aberto para pessoas)."""
    if product_family(c) not in ('moda', 'infantil'):
        return 'plano médio, com o produto nas mãos à altura do peito'
    chosen = frame_override(c)
    if chosen:
        return _SHOT_BY_FRAME[chosen]
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


# ---------------------------------------------------------------------------------------------- selfie no espelho
# O espelho validado no Grok e o de corpo inteiro. Para peca de cima (blusa, regata, casaco...) o detalhe que vende fica no peito e
# em corpo inteiro vira uma fracao pequena do quadro: o quadro fechado vai da cabeca ate logo abaixo da barra DA PECA (nao
# "ate a cintura": a barra de uma blusa assimetrica passa do quadril e seria cortada) e o celular sobe para o lado do rosto, para
# nao tapar o decote.
_TIGHT = {'cintura': 'da cabeça até logo abaixo da barra da peça, com a peça inteira no quadro',
          'joelhos': 'da cabeça até os joelhos'}


def mirror_frame(c: dict) -> str:
    """'' = espelho de corpo inteiro (o validado); 'cintura' ou 'joelhos' = quadro mais fechado na peca."""
    if product_family(c) not in ('moda', 'infantil'):
        return ''
    chosen = frame_override(c)
    if chosen:
        return '' if chosen == 'inteiro' else chosen
    return 'cintura' if framing(c).startswith('plano médio, da cintura') else ''


def mirror_scope(c: dict) -> str:
    """Complemento de 'o celular dela grava ...': onde e como o espelho e enquadrado."""
    frame = mirror_frame(c)
    if not frame:
        return 'no espelho de corpo inteiro'
    return (f'no espelho, no mesmo enquadramento do primeiro quadro ({_TIGHT[frame]}), sem abrir para corpo inteiro '
            'nem se afastar do espelho')


def mirror_phone(c: dict) -> str:
    return 'na altura do peito' if not mirror_frame(c) else 'na altura do ombro, ao lado do rosto'


def mirror_cover(c: dict) -> str:
    return 'sem cobrir o rosto' if not mirror_frame(c) else 'sem cobrir o rosto nem a peça'


def mirror_image_rules(c: dict, piece_ref: str) -> str:
    """O trecho do prompt de IMAGEM que descreve a selfie no espelho (celular, corpo e enquadramento)."""
    frame = mirror_frame(c)
    if not frame:
        return (
            "SELFIE NO ESPELHO: a imagem é o reflexo num espelho de corpo inteiro. Ela segura o próprio celular com "
            "uma das mãos, na altura do peito, com a câmera traseira voltada para o espelho; o celular aparece no "
            "reflexo sem cobrir o rosto, que fica inteiro e visível acima do aparelho. A outra mão toca a peça. "
            f"Corpo de frente para o espelho, com {piece_ref} inteira visível no reflexo. "
        )
    return (
        "SELFIE NO ESPELHO: a imagem é o reflexo no espelho. Ela segura o próprio celular com uma das mãos, na altura do "
        "ombro, ao lado do rosto, com a câmera traseira voltada para o espelho; o celular aparece no reflexo sem cobrir "
        "o rosto nem a peça. A outra mão toca a peça. Corpo de frente para o espelho. "
        f"ENQUADRAMENTO: plano fechado na peça; o quadro vai {_TIGHT[frame]}; {piece_ref} fica grande no quadro, com os "
        "detalhes nítidos; a peça de baixo e os sapatos só aparecem se couberem no fim do quadro, sem protagonismo. "
    )
