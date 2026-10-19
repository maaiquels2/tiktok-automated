"""Sequencia de 3 partes (gancho -> prova -> fechamento) para o Extend Video
do Grok Imagine, com o checklist de montagem no CapCut.

Por que existe
--------------
Um clipe so de 15s precisa fazer tudo ao mesmo tempo: prender, provar e
chamar para a compra. O guia oficial do Grok mostra o caminho para ir alem:
gerar a primeira parte a partir da imagem e "estender" o video, escrevendo
para cada extensao so o que acontece DEPOIS -- nunca a cena inteira de novo
("She stands up slowly, grabs her coat... The camera follows").

Cada parte tem um trabalho na historia de venda e carrega uma das falas ja
auditadas da campanha (hook, desenvolvimento, CTA). Nada novo e afirmado
aqui: a sequencia so reorganiza o que o roteiro ja aprovou.
"""
import math
import re

from services.prompt_improve import (
    clean, quote, touch_point, flow, framing, mood, movement_steps, pov_hands, push_target, size, speech_framing,
)
from services import formats, persuasion, script_budget
from services.formats import video_mode as _video_mode
from services.prompts import (
    light_scene, bold_move, close_target, dominant_motor, focus_parts, mirror_hands, video_style, with_em,
)
from services.script_budget import count_words as _count_words

# Ritmo de fala do orcamento do roteiro, mais um respiro para a acao antes e
# depois da frase.
_WORDS_PER_SECOND = script_budget.WORDS_PER_SECOND

_ROLES = (
    ('Gancho', 'Prende o dedo: a dúvida ou descoberta que faz a pessoa ficar.'),
    ('Prova', 'Mostra no corpo o detalhe que derruba a objeção.'),
    ('Fechamento', 'Uma ação só: levar a pessoa ao carrinho laranja.'),
)


def _seconds(line: str, silent: bool) -> int:
    if silent:
        return 5
    return max(5, min(10, math.ceil(_count_words(line) / _WORDS_PER_SECOND) + 2))


def _short_cta(cta: str) -> str:
    return cta if 0 < _count_words(cta) <= 8 else 'Toca no carrinho laranja'


def build_story_sequence(c: dict, prompts: dict, color: str) -> dict:
    model = clean(c.get('model_name')) or 'a modelo'
    product = clean(c.get('product')) or clean(c.get('outfit')) or 'a peça'
    color = clean(color) or clean(c.get('color'))
    keeps = f'{product} na cor {color}' if color else product
    hook, development, cta = (quote(prompts.get(k)) for k in ('hook', 'development', 'cta'))
    mode = _video_mode(c)
    silent = mode == 'movimento'
    touch = touch_point(c)
    touch_em = 'no cós' if touch == 'o cós' else 'na peça'
    shot = framing(c) if mode == 'movimento' else speech_framing(c)
    spoken = f'{hook} {development}'
    # Com fala, o mesmo teto do prompt resumido: 3 acoes no meio.
    lista = movement_steps(c, spoken, limit=3 if not silent else 4)[:3]
    # Formato e tecnicas (services/formats.py) valem tambem na sequencia:
    # antes, quem escolhia closes ou "respondendo comentario" perdia isso aqui.
    lugar = 'espelho' if mode == 'espelho' else ('movimento' if silent else '')
    estilo = video_style(c)
    extra = formats.lead_moves(c, lugar if lugar != 'movimento' else '')
    if 'ousado' in estilo and mode != 'pov':
        extra.append(bold_move(c, espelho=mode == 'espelho')[0])
    luz = '' if silent else light_scene((hook, development, cta), mode == 'espelho')
    if luz:
        extra.insert(0, luz)
    jeitos = formats.three_looks(c, 'a peça')
    lista = [jeitos] if jeitos else (extra + lista)[:4]
    if mode == 'espelho':
        lista = [mirror_hands(s) for s in lista]
    steps = flow(lista)
    closes = ''
    if 'closes' in estilo and mode != 'pov':
        alvo = close_target(c)
        closes = (f' No meio, ela aproxima o celular da peça para um close curto (1 a 2 s) {alvo} e volta ao reflexo.'
                  if mode == 'espelho' else
                  f' No meio, a câmera faz um close curto (1 a 2 s) {alvo}, com a voz continuando, e volta ao rosto.')
    fim = formats.ending(c, lugar)
    head = f'Vídeo vertical 9:16, {size(c)}. Clima: {mood(c)}.'
    cena = persuasion.scene_direction(persuasion.script_motor(dominant_motor(c), hook), touch)
    abre = formats.opening(c, cena['hook'], lugar)
    if mode == 'espelho':
        abre = abre.replace('em direção à câmera', 'em direção ao espelho').replace('até a câmera', 'até o espelho')
    keep_line = 'Continuação do mesmo take, já em movimento: mesma pessoa, roupa e luz; segue o último quadro sem pausa.'
    # Emenda das partes: quem para no ultimo quadro faz o Extend recomecar
    # do zero, e o video final trava na juncao.
    ends_moving = 'Termina em movimento, sem parar no último quadro.'
    voice = ('Fala: espontânea, como quem conta uma descoberta para uma amiga; tom animado na medida, '
             'entonação natural e sorriso na voz, nada de locução. Voz feminina em português do Brasil, lábios '
             'sincronizados, só o que está entre aspas; som ambiente baixo, sem música. Sem texto na tela.')

    if mode == 'pov':
        first = '\n'.join([
            f'Vídeo vertical 9:16 em primeira pessoa (POV), {size(c)}. Clima: {mood(c)}.',
            'A imagem anexada é o primeiro quadro: mesmo ambiente e mesma luz. '
            f'A câmera é o olhar de quem veste {keeps}; aparecem só as mãos e o corpo do pescoço para baixo, nunca o rosto.',
            'Câmera: na mão, apontada para baixo, take contínuo com leve balanço natural.',
            (f'{formats.pov_opening(c, product)}. Narração: "{hook}"' if formats.video_format(c) == 'unboxing'
             else f'A mão aparece e mostra {touch} pela primeira vez, com curiosidade. Narração: "{hook}"'),
            ends_moving,
            'Som: voz feminina natural em português do Brasil, só a frase entre aspas; som ambiente baixo, '
            'sem música. Sem texto na tela.',
        ])
        middle = '\n'.join([
            f'{keep_line} O rosto nunca aparece.',
            f'{pov_hands(c, spoken)}, em ritmo natural; a câmera acompanha as mãos. Narração: "{development}"',
            ends_moving,
        ])
        last = '\n'.join([
            f'{keep_line} O rosto nunca aparece.',
            f'Tilt lento para baixo mostrando a peça inteira no corpo, mãos paradas {touch_em}. Narração: "{cta}"',
        ])
    elif silent:
        first = '\n'.join([
            f'{head} Sem fala.',
            f'A imagem anexada é o primeiro quadro: a mesma mulher ({model}), mesmo rosto, cabelo e corpo, '
            'vestindo exatamente o que aparece nela. Luz: a mesma da imagem.',
            (f'Câmera: na mão, {formats.ASMR_CAMERA}, take contínuo.' if formats.asmr(c)
             else f'Câmera: fixa na altura do peito, {shot}, sem zoom, take contínuo.'),
            f'Ela {abre}.',
            ends_moving,
            ('Som (é o conteúdo): sons nítidos do tecido, da amarração ou do zíper e dos passos; sem voz e sem '
             'música. Sem texto na tela.' if formats.asmr(c)
             else 'Som: sem voz e sem fala; só som ambiente discreto. Sem texto na tela.'),
        ])
        middle = '\n'.join([
            keep_line,
            f'Ela {steps}, em ritmo natural de conversa, sem câmera lenta. Câmera fixa, sem zoom. Sem fala.',
            ends_moving,
        ])
        last = '\n'.join([
            keep_line,
            f'Ela volta de frente para a lente e {cena["cta"]}; corpo parado, sorriso leve e confiante. '
            f'Câmera fixa. Sem fala. {fim}'.strip(),
        ])
    else:
        first = '\n'.join([
            head,
            f'A imagem anexada é o primeiro quadro: a mesma mulher ({model}), mesmo rosto, cabelo e corpo, '
            'vestindo exatamente o que aparece nela. Luz: a mesma da imagem.',
            ('Câmera: o celular dela grava o reflexo no espelho de corpo inteiro, sempre na mão, na altura do peito, '
             'sem cobrir o rosto; take contínuo, sem cortes.' if mode == 'espelho'
             else f'Câmera: na mão, estável, {shot}, take contínuo, sem cortes.'),
            f'Ela {abre}. Ela diz: "{hook}"',
            f'Expressão: {cena["arc"].split(" → ")[0]}.',
            ends_moving,
            voice,
        ])
        middle = '\n'.join([
            keep_line,
            # No espelho a camera e o celular dela: "dolly-in" nao existe ali.
            (f'Ela {steps}, gesticulando com a mão livre enquanto fala.{closes} '
             if mode == 'espelho' else
             f'Ela {steps}, gesticulando enquanto fala; '
             + (closes.strip() + ' ' if closes else f'dolly-in suave até {push_target(c)} e volta. '))
            + f'Ela emenda a fala, no mesmo tom: "{development}"',
            ends_moving,
        ])
        last = '\n'.join([
            keep_line,
            (f'Ela termina de frente para o espelho e {cena["cta"]}; sorriso confiante. '
             if mode == 'espelho' else
             f'Ela termina de frente para a lente e {cena["cta"]}; sorriso confiante, a câmera fica parada. ')
            + f'E fecha, sorrindo: "{cta}" {fim}'.rstrip(),
        ])

    _focus, features = focus_parts(c)
    screen = [
        clean(prompts.get('screen_text')) or hook,
        f'Repara {with_em(features[0])}' if features else 'Repara no caimento',
        _short_cta(cta),
    ]
    lines = (hook, development, cta)
    clips = []
    for index, (prompt, (role, why)) in enumerate(zip((first, middle, last), _ROLES)):
        clips.append({
            'index': index + 1,
            'role': role,
            'why': why,
            'kind': 'image' if index == 0 else 'extend',
            'seconds': _seconds(lines[index], silent),
            'spoken': '' if silent else lines[index],
            'screen_text': screen[index] if silent else '',
            'prompt': prompt,
        })

    if silent:
        audio_steps = [
            'Silencie o áudio original de todas as partes.',
            'O som entra na publicação: escolha um áudio em alta no TikTok (ou na biblioteca do CapCut para Reels e Shopee).',
            'Texto na tela de cada parte: ' + ' / '.join(
                f'{clip["index"]}. "{clip["screen_text"]}"' for clip in clips if clip['screen_text']) + '.',
        ]
    else:
        audio_steps = [
            'Mantenha a voz original. Use Áudio > Normalizar volume para as partes ficarem no mesmo nível.',
            'Sem música por cima da fala; se quiser trilha, deixe em 10–15% do volume.',
            'Texto > Legendas automáticas (Português) e revise palavra por palavra.',
        ]
    capcut = [
        'Novo projeto 9:16. Se usou Extend Video, o Grok entrega um vídeo contínuo: importe só o final.',
        'Se gerou as partes separadas: importe na ordem 1, 2, 3 e corte seco, sem transição. '
        'Tire cerca de 0,2s do começo da parte 2 e da 3 para não repetir o quadro de emenda.',
        *audio_steps,
        f'Capa: "{clean(prompts.get("cover_text")) or hook}" no primeiro quadro.',
        'Exporte em 1080p e 30 fps. O mesmo MP4 9:16 serve para TikTok, Reels e Shopee Vídeo.',
    ]
    tips = [
        'Parte 1: anexe a imagem aprovada desta cor e gere com o prompt da parte 1.',
        'Partes 2 e 3: no vídeo gerado, escolha um quadro em que ela está de frente e nítida '
        '(perto do fim) e use Extend Video com o prompt da parte seguinte. O prompt diz só o que acontece depois: '
        'o Grok já carrega cena, luz e pessoa.',
        'Se uma parte sair ruim, gere de novo com o mesmo prompt antes de reescrever: '
        'o Grok varia a cada tentativa. Guarde os prompts que funcionaram.',
    ]
    total = sum(clip['seconds'] for clip in clips)
    text = '\n\n'.join(
        [f'SEQUÊNCIA STORYTELLING — {keeps} — cerca de {total}s']
        + [f'PARTE {clip["index"]} · {clip["role"].upper()} · '
           f'{"imagem → vídeo" if clip["kind"] == "image" else "Extend Video"} · cerca de {clip["seconds"]}s\n'
           f'{clip["prompt"]}' + (f'\nTexto na tela: {clip["screen_text"]}' if clip['screen_text'] else '')
           for clip in clips]
        + ['COMO GERAR NO GROK\n' + '\n'.join(f'- {tip}' for tip in tips),
           'MONTAGEM NO CAPCUT\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(capcut, 1))]
    )
    return {
        'color': color,
        'mode': mode or 'fala',
        'total_seconds': total,
        'clips': clips,
        'tips': tips,
        'capcut': capcut,
        'text': re.sub(r'[ \t]+\n', '\n', text),
    }
