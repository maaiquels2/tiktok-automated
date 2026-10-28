"""Formato "Recebi em casa": 2 cenas para emendar no CapCut (cerca de 20 s).

Cena 1 (6 s): a modelo em casa, de pijama, com a caixa aberta e a peca nas maos; termina tampando a lente com a
mao. Cena 2 (15 s): parte da imagem aprovada (a peca ja no corpo), comeca com a mao saindo da lente e usa as
mesmas tres falas ja auditadas da campanha. O espectador completa a troca de roupa no corte.

O que os testes reais no Grok (maio marrom de um ombro so, out/2026) ensinaram e esta aqui:
  - o Grok redesenha a peca a cada quadro; no corpo ela fica fiel, na mao ela muda. Por isso a Cena 1 e curta
    (6 s), a peca fica DOBRADA e quase parada, longe do corpo, e a prova dos detalhes fica para a Cena 2;
  - abracar a peca ou encostar no peito fez o Grok "colar" a peca na roupa que ela vestia;
  - a emocao vai no rosto e no corpo (pulinhos, olhos arregalados, risada), nao na peca;
  - tampar a lente com a MAO (nao com a peca, que se abre) no fim da Cena 1 e comecar a Cena 2 com a mao saindo
    da lente funcionou dos dois lados;
  - o Grok nunca viu a peca fora do corpo: para a imagem da Cena 1 a melhor referencia e uma foto da peca
    sozinha. Sem ela, o passo 0 cria uma a partir da imagem aprovada;
  - prompt curto, com a peca descrita pelo que ela E logo no inicio, rendeu mais que listas longas de "nunca".

Regras de honestidade do app: as falas da Cena 2 sao as do roteiro auditado; a da Cena 1 so diz que chegou,
aponta um detalhe confirmado e avisa que vai vestir (nada de "comprei", "esperei", resultado ou urgencia).
So le a campanha: nada e gravado.
"""
import re

from services import generators, persuasion
from services.piece import product_family
from services.prompts import (
    STAY_IN_FRAME, body_turns, focus_parts, piece_forms, product_features, proof_gestures, video_details,
    with_article,
)

FAMILIES = ('moda', 'infantil')
SCENE1_SECONDS = 6       # Grok: 6, 10 ou 15 s por clipe
FLOW_SCENE1_SECONDS = 8  # Flow: clipes de 8 s
SCENE2_SECONDS = 15


class RevealError(Exception):
    """Pedido que o app nao consegue atender (a mensagem e para o operador)."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def _clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _quote(value):
    return _clean(value).replace('"', "'")


def _piece_description(c, color):
    """A peca pelo que ela E: nome, cor e os detalhes do briefing, nas palavras do operador."""
    product = _clean(c.get('product')) or 'a peça'
    color = _clean(color)
    details = video_details(_clean(c.get('details')))
    text = f'{product} na cor {color}' if color and color.casefold() not in product.casefold() else product
    return f'{text}: {details}' if details else text


def scene1_line(c):
    """Fala curta da Cena 1 (cabe em 6 s): chegou, um detalhe confirmado, vou vestir."""
    forms = piece_forms(c)
    _focus, features = focus_parts(c)
    detalhe = with_article(features[0]) if features else 'esse acabamento'
    return f'CHEGOU! Olha {detalhe} d{forms["dem"]} {forms["piece"]}... vou vestir agora, já volto!'


def _scene2_gestures(c):
    gestures = proof_gestures(product_features(c, limit=2), turns=body_turns(c))
    out = []
    for item in gestures:
        label, gesture = item.split(' → ', 1)
        out.append(STAY_IN_FRAME.get(label, gesture))
    return out


def build_home_reveal(c, prompts, color):
    if product_family(c) not in FAMILIES:
        raise RevealError('O formato "Recebi em casa" é para roupa: a peça sai da caixa e depois aparece no corpo.')
    hook, development, cta = (_quote(prompts.get(k)) for k in ('hook', 'development', 'cta'))
    if not (hook and development and cta):
        raise RevealError('Conclua o hook, o desenvolvimento e o CTA antes de montar as duas cenas.')
    gen = generators.of(c)
    res = gen.resolution_label
    s1 = FLOW_SCENE1_SECONDS if gen.name == 'flow' else SCENE1_SECONDS
    a, b = (2, 4) if s1 == 6 else (3, 5)
    model = _clean(c.get('model_name')) or 'a modelo'
    color = _clean(color) or _clean(c.get('color'))
    piece = _piece_description(c, color)
    line1 = scene1_line(c)
    t1, t2 = persuasion.timeline(hook, development, cta)
    gestures = _scene2_gestures(c)
    prova = ('; depois '.join(gestures) if gestures else 'passa a mão pela peça mostrando o caimento no corpo')

    step0 = '\n'.join([
        'Foto de produto vertical 4:5, realista.',
        'A mesma peça que a modelo veste na imagem anexada, agora sem ninguém: estendida sobre um lençol bege liso, '
        'vista de cima, luz do dia suave e uniforme.',
        f'A peça: {piece}.',
        'Copie cada detalhe exatamente como na imagem: mesma cor, mesmo formato, mesma quantidade de detalhes.',
    ])
    image1 = '\n'.join([
        'Foto vertical 9:16, estilo UGC do TikTok, realista.',
        f'A mesma mulher da imagem 1 ({model}: mesmo rosto, cabelo, pele, tatuagens e unhas), sentada na cama de '
        'um quarto aconchegante, de pijama bege, com uma caixa de papelão aberta e papel de seda no colo.',
        'Ela segura a peça da imagem 2 com as duas mãos, DOBRADA, de frente para a câmera, na altura do peito e '
        'afastada do corpo.',
        f'A peça: {piece}. Copie a peça exatamente como na imagem 2.',
        'Rosto: olhos arregalados, boca aberta de surpresa feliz.',
        'Luz natural suave de uma janela à esquerda.',
    ])
    scene1 = '\n'.join([
        f'UGC TikTok Shop vertical 9:16, {s1} segundos, {res}, um único take contínuo, celular parado '
        'num tripé.',
        'Comece exatamente desta imagem. Mesma mulher, mesmo quarto, mesmo pijama.',
        f'A peça fica dobrada nas duas mãos, de frente para a lente, exatamente como no primeiro quadro ({piece}). '
        'Ela só acompanha as mãos, quase parada.',
        f'0–{a}s: ela solta um gritinho, olhos arregalados, e dá dois pulinhos sentada na cama; o cabelo balança.',
        f'{a}–{b}s: inclina a peça de leve para o detalhe pegar a luz, com uma risada larga.',
        f'{b}–{s1}s: apoia a peça no colo, ergue a mão livre e tampa a lente inteira com a palma até a tela ficar '
        'escura.',
        f'Fala (PT-BR), voz feminina animada, só estas palavras: "{line1}"',
        'Sem texto na tela, sem música, som ambiente baixo.',
    ])
    scene2 = '\n'.join([
        f'UGC TikTok Shop vertical 9:16, {SCENE2_SECONDS} segundos, {res}, um único take contínuo, câmera na mão, '
        'da cintura para cima.',
        f'Comece exatamente da imagem anexada: mesma mulher, mesmo cenário, vestindo a peça exatamente como na '
        f'imagem ({piece}).',
        '0–1s: a palma aberta dela cobre a lente e desce, revelando-a de perto, sorrindo.',
        f'0–{t1}s: enquanto a mão desce, ela já fala, olhando na lente. Fala: "{hook}"',
        f'{t1}–{t2}s: {prova}, sem parar de falar. Fala: "{development}"',
        f'{t2}–15s: uma mão na cintura; a outra aponta uma vez para baixo com o indicador e volta, sorrindo, ainda '
        f'falando. Fala: "{cta}"',
        'Corpo de frente o tempo todo. As três falas são um discurso contínuo; voz feminina em português do Brasil, '
        'espontânea, lábios sincronizados, só as palavras entre aspas.',
        'Sem texto na tela, sem música, som ambiente baixo.',
    ])

    clips = [
        {'index': 0, 'role': 'Foto da peça sozinha (se não tiver)', 'kind': 'image', 'seconds': 0,
         'attach': 'a imagem aprovada desta cor',
         'why': 'O Grok nunca viu a peça fora do corpo. Uma foto real do fornecedor é melhor; use este passo só sem ela.',
         'prompt': step0},
        {'index': 1, 'role': 'Imagem da Cena 1', 'kind': 'image', 'seconds': 0,
         'attach': 'imagem 1: a foto da modelo; imagem 2: a foto da peça sozinha',
         'why': 'Acerte a imagem antes do vídeo: confira cada detalhe da peça com lupa. Imagem é rápida; vídeo errado '
                'é tempo perdido.',
         'prompt': image1},
        {'index': 2, 'role': 'Cena 1 · Recebi em casa', 'kind': 'video', 'seconds': s1,
         'attach': 'a imagem aprovada no passo anterior',
         'why': 'Curta e com a peça quase parada: na mão a peça muda; a emoção fica no rosto e no corpo.',
         'spoken': line1, 'prompt': scene1},
        {'index': 3, 'role': 'Cena 2 · Já no corpo', 'kind': 'video', 'seconds': SCENE2_SECONDS,
         'attach': f'a imagem aprovada da cor {color}' if color else 'a imagem aprovada',
         'why': 'No corpo a peça fica fiel: é aqui que os detalhes são provados, com as falas do roteiro.',
         'spoken': ' '.join((hook, development, cta)), 'prompt': scene2},
    ]
    tips = [
        'Gere a Cena 1 duas ou três vezes e fique com a melhor: se a peça mudar num trecho, não reescreva o prompt.',
        'Na Cena 1 use só os segundos em que a peça está perfeita (2 a 4 s bastam) e o final com a mão na lente.',
        'Se a peça ainda mudar na mão, troque o trecho por 1 a 2 s da foto real da peça com zoom lento no CapCut.',
        'A Cena 2 parte da imagem aprovada da campanha. Não crie outra versão dela: cada imagem nova é mais uma '
        'chance de a peça mudar.',
    ]
    capcut = [
        'Novo projeto 9:16. Importe a Cena 1 e depois a Cena 2.',
        'Corte a Cena 1 no quadro em que a mão cobre a lente; a Cena 2 entra com corte seco, sem transição.',
        'Tire cerca de 0,2 s do começo da Cena 2 se a mão aparecer parada antes de descer.',
        'Áudio > Normalizar volume, para as duas cenas ficarem no mesmo nível. Sem música por cima da fala.',
        'Texto > Legendas automáticas (Português) e revise palavra por palavra.',
        'Exporte em 1080p e 30 fps.',
    ]
    total = s1 + SCENE2_SECONDS
    title = _clean(c.get('product')) or 'a peça'
    text = '\n\n'.join(
        [f'RECEBI EM CASA — {title}' + (f' ({color})' if color else '') + f' — cerca de {total}s']
        + [f'PASSO {clip["index"]} · {clip["role"].upper()}'
           + (f' · {clip["seconds"]}s' if clip['seconds'] else '')
           + f'\nAnexe: {clip["attach"]}\n{clip["prompt"]}' for clip in clips]
        + ['COMO GERAR NO GROK\n' + '\n'.join(f'- {tip}' for tip in tips),
           'MONTAGEM NO CAPCUT\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(capcut, 1))]
    )
    return {
        'color': color,
        'total_seconds': total,
        'clips': clips,
        'tips': tips,
        'capcut': capcut,
        'text': text,
    }
