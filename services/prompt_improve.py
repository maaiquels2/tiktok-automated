"""Versao enxuta e descritiva do prompt de video ("Melhorar prompt").

O prompt completo do app e um manual de regras (proibicoes, limites de
segundos, notas do operador). Geradores de video seguem melhor uma descricao
do que a camera ve, cena por cena, com poucas acoes. Esta versao usa os mesmos
dados da campanha e as mesmas falas, em cerca de 1.000 a 1.500 caracteres.
"""
import re

from services.prompts import _video_mode

_BOTTOM_WORDS = ('legging', 'short', 'calça', 'calca', 'saia', 'bermuda', 'biquíni', 'biquini', 'calcinha')


def _clean(value) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _quote(value) -> str:
    return _clean(value).replace('"', "'")


def _touch_point(c: dict) -> str:
    text = f"{c.get('product', '')} {c.get('outfit', '')}".casefold()
    return 'o cós' if any(word in text for word in _BOTTOM_WORDS) else 'a peça'


def _moves(c: dict) -> list[str]:
    raw = _clean(c.get('movements'))
    items = [m.strip(' .') for m in re.split(r'[;\n]|,(?![^()]*\))', raw) if m.strip(' .')]
    # Tira pedidos de camera e giros: o giro vem da orientacao corporal.
    items = [m for m in items if not re.search(r'c[âa]mera|close|zoom|costas|gir|vir', m, re.I)]
    return [m[0].lower() + m[1:] for m in items[:2]]


def _turn(c: dict) -> str:
    return {
        'leve_lado': 'gira levemente de lado e volta de frente',
        'lado': 'vira de perfil por um instante e volta de frente',
        'costas': 'vira de costas por um instante e volta de frente',
    }.get(_clean(c.get('body_turns')), '')


def build_compact_video_prompt(c: dict, prompts: dict, color: str) -> str:
    grok = _clean(c.get('generator')).casefold() == 'grok'
    size = '720 × 1280 (720p)' if grok else '1080 × 1920 (1080p)'
    model = _clean(c.get('model_name')) or 'a modelo'
    product = _clean(c.get('product')) or _clean(c.get('outfit')) or 'a peça'
    color = _clean(color) or _clean(c.get('color'))
    piece = f'{product} na cor {color}' if color else product
    touch = _touch_point(c)
    touch_em = 'no cós' if touch == 'o cós' else 'na peça'
    keeps = f'na cor {color}' if color else 'igual'
    hook, development, cta = (_quote(prompts.get(k)) for k in ('hook', 'development', 'cta'))
    mode = _video_mode(c)

    moves = _moves(c)
    turn = _turn(c)
    steps = moves[:1 if turn else 2] + ([turn] if turn else [])
    if not steps:
        steps = ['caminha dois passos e ajeita a peça com uma das mãos']
    middle = 'Ela ' + ', depois '.join(steps) + ', devagar e com naturalidade'

    first_frame = (
        f'A imagem anexada é o primeiro quadro: a mesma mulher ({model}), com o mesmo rosto, '
        'cabelo, pele e corpo, no mesmo ambiente e com a mesma luz do começo ao fim.')
    wearing = f'Ela veste {piece}, exatamente como na imagem, sem mudar cor nem estampa.'
    close = f'IMPORTANTE: mesmo rosto em todos os quadros; {product} continua {keeps} e totalmente opaca; termina de frente para a câmera.'

    if mode == 'pov':
        return '\n'.join([
            f'Vídeo vertical 9:16 em primeira pessoa (POV), estilo UGC do TikTok Shop, 15 segundos, {size}.',
            'A imagem anexada é o primeiro quadro: mesmo ambiente e mesma luz do começo ao fim. '
            f'A câmera é o olhar de quem veste {piece}; aparecem só as mãos e o corpo do pescoço para baixo, nunca o rosto.',
            'Câmera na mão, um único take contínuo, leve balanço natural.',
            f'[0–4s] A câmera olha para baixo e as mãos mostram {touch}. Narração: "{hook}"',
            f'[4–12s] As mãos puxam levemente o tecido e passam pelos detalhes da peça. Narração: "{development}"',
            f'[12–15s] A câmera se afasta um pouco e mostra a peça inteira no corpo. Narração: "{cta}"',
            'Áudio: voz feminina clara em português do Brasil, ritmo natural, só as frases entre aspas. Sem música e sem texto na tela.',
            f'IMPORTANTE: o rosto nunca aparece; {product} continua {keeps} e totalmente opaca.',
        ])

    if mode == 'movimento':
        return '\n'.join([
            f'Vídeo vertical 9:16 estilo UGC do TikTok Shop, 15 segundos, {size}, sem fala.',
            first_frame, wearing,
            'Câmera: plano médio na altura do peito, um único take contínuo, leve movimento de mão.',
            f'[0–4s] Ela olha para a lente e ajusta {touch} com as duas mãos.',
            f'[4–12s] {middle}.',
            f'[12–15s] De frente para a lente, mãos apoiadas {touch_em}, corpo parado, sorriso leve e confiante.',
            'Áudio: sem voz e sem fala; só som ambiente. Sem texto na tela.',
            close,
        ])

    return '\n'.join([
        f'Vídeo vertical 9:16 estilo UGC do TikTok Shop, 15 segundos, {size}.',
        first_frame, wearing,
        'Câmera: plano médio na altura do peito, um único take contínuo, leve movimento de mão.',
        f'[0–4s] Ela dá um passo em direção à câmera, olha para a lente e toca {touch}. Ela diz: "{hook}"',
        f'[4–12s] {middle}. Ela diz: "{development}"',
        f'[12–15s] De frente para a lente, as duas mãos apoiadas {touch_em}, corpo parado, sorriso leve e confiante. Ela diz: "{cta}"',
        'Áudio: voz feminina clara em português do Brasil, ritmo natural, só as frases entre aspas. Sem música e sem texto na tela.',
        close,
    ])
