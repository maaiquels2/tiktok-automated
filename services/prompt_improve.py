"""Versao enxuta do prompt de video ("Melhorar prompt"), no formato do guia
oficial do Grok Imagine.

O prompt completo do app e um manual de regras (proibicoes, limites de
segundos, notas do operador). O guia do Grok pede o contrario para
imagem-para-video: o gerador ja tem a imagem como contexto, entao o texto so
descreve o que se move e como, em poucas linhas:

    sujeito/acao + clima (uma referencia, nao adjetivo) + luz + camera nomeada
    + acabamento

Outras regras do guia aplicadas aqui:
- "Go wider for people": plano mais aberto e movimento lento quando ha pessoa.
  O enquadramento sai da peca vendida -- legging pede corpo inteiro; top cabe
  da cintura para cima.
- Nomear o movimento de camera ("dolly-in lento", "camera fixa") e a luz.
- Nao redescrever a cena que ja esta na imagem.

Usa os mesmos dados da campanha e as mesmas falas, em cerca de 1.000 a 1.600
caracteres.
"""
import re
import unicodedata

from services import persuasion
from services.prompts import shows_unconfirmed_feature
from services.prompts import (
    _STAY_IN_FRAME, _body_turns, _dominant_motor, _niche_key, _piece_forms, _pov_proof_gestures,
    _product_family, _product_features, _proof_gestures, _video_mode,
)

# Quantos movimentos cabem no trecho do meio (8 segundos): cerca de 2 segundos
# para cada um. Acima disso o gerador acelera tudo ou deforma o corpo.
MAX_MOVES = 4

_BOTTOM_WORDS = ('legging', 'short', 'calça', 'calca', 'saia', 'bermuda', 'biquíni', 'biquini', 'calcinha')

# Enquadramento pela peca. A ordem importa: "saia longa" e corpo inteiro,
# "saia" sozinha cabe dos joelhos para cima.
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


def _clean(value) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _quote(value) -> str:
    return _clean(value).replace('"', "'")


def _touch_point(c: dict) -> str:
    text = f"{c.get('product', '')} {c.get('outfit', '')}".casefold()
    return 'o cós' if any(word in text for word in _BOTTOM_WORDS) else 'a peça'


def framing(c: dict) -> str:
    """Plano que mostra a peca inteira com folga (guia: mais aberto para pessoas)."""
    if _product_family(c) not in ('moda', 'infantil'):
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
    if _video_mode(c) == 'pov':
        return _MOOD_POV
    if _product_family(c) not in ('moda', 'infantil'):
        return _MOOD_OBJECT
    return _MOOD.get(_niche_key(c), _MOOD['casual'])


def size(c: dict) -> str:
    return '720 × 1280 (720p)' if _clean(c.get('generator')).casefold() == 'grok' else '1080 × 1920 (1080p)'


_IRREGULAR = {'ir': 'vai', 'vir': 'vem', 'sair': 'sai', 'subir': 'sobe', 'pôr': 'põe', 'por': 'põe'}


# Verbos que pedem objeto: "ajusta" sozinho nao diz o que ela ajusta.
_NEEDS_OBJECT = ('ajust', 'arrum', 'alis', 'pux', 'ajeit')


def _third_person(move: str) -> str:
    """'agachar devagar' -> 'agacha devagar': o briefing lista verbos no
    infinitivo e o prompt narra "Ela agacha", nao "Ela agachar". Cada acao
    ligada por "e" ("sentar e levantar") e conjugada."""
    done = ' e '.join(_conjugate(part) for part in move.split(' e '))
    if ' ' not in done.strip() and done.casefold().startswith(_NEEDS_OBJECT):
        done += ' a peça'
    return done


def _conjugate(move: str) -> str:
    first, _, rest = move.partition(' ')
    low = first.casefold()
    if low in _IRREGULAR:
        verb = _IRREGULAR[low]
    elif re.fullmatch(r'\w{3,}ar', low):
        verb = first[:-1]
    elif re.fullmatch(r'\w{3,}[ei]r', low):
        verb = first[:-2] + 'e'
    else:
        return move
    return f'{verb} {rest}'.strip()


# Acoes de quem ainda nao esta com a peca: no video ela ja aparece vestida
# (a imagem aprovada e o primeiro quadro). No primeiro video de teste, "pegar
# a peca" e "vestir" chegaram ao prompt e so gastaram espaco.
_OFF_BODY_RE = re.compile(r'^(?:peg|segur|vest|tir|coloc|troc|escolh|dobr|pendur)\w*', re.I)


def _moves(c: dict) -> list[str]:
    raw = _clean(c.get('movements'))
    items = [m.strip(' .') for m in re.split(r'[;\n]|,(?![^()]*\))', raw) if m.strip(' .')]
    # Tira pedidos de camera e giros: o giro vem da orientacao corporal.
    items = [m for m in items if not re.search(r'c[âa]mera|close|zoom|costas|gir|vir', m, re.I)]
    # Pose, sorriso e "CTA final" nao sao acao: no fluxo continuo viravam
    # parada ("emendando em seguida: pose inicial frontal"). Mostrar atributo
    # nao confirmado ("mostrar bolso") tambem sai.
    items = [m for m in items if not re.search(r'\bpose\b|\bposar\b|\bcta\b|sorri|\bolhar\b', m, re.I)
             and not shows_unconfirmed_feature(m, c)]
    moves = []
    for item in items:
        # "vestir/ajustar": fica a primeira alternativa que faz sentido vestida.
        options = [o.strip() for o in item.split('/') if o.strip()]
        keep = next((o for o in options if not _OFF_BODY_RE.match(o)), '')
        # "senta e levanta mostrando conforto": o movimento fica, a promessa
        # ("conforto" nao confirmado) sai.
        keep = re.sub(r'\s+(?:mostrando|para mostrar|pra mostrar|demonstrando)\b.*$', '', keep, flags=re.I)
        if keep:
            moves.append(_third_person(keep[0].lower() + keep[1:]))
    return moves[:MAX_MOVES]


def _turn(c: dict) -> str:
    return {
        # "Gira levemente" virou costas inteiras no primeiro teste: o limite
        # precisa estar escrito.
        'leve_lado': 'vira o corpo uns 30 graus para o lado, sem mostrar as costas, e volta de frente',
        'lado': 'vira de perfil por um instante, sem mostrar as costas, e volta de frente',
        'costas': 'vira de costas por um instante e volta de frente',
    }.get(_clean(c.get('body_turns')), '')


def _stem(label: str) -> str:
    """'sem transparência' -> 'transpa' (casa com 'transparente' na fala)."""
    word = re.sub(r'^sem\s+', '', label).split()[0]
    return unicodedata.normalize('NFKD', word.casefold()).encode('ascii', 'ignore').decode()[:7]


# Ate onde a camera aproxima sem cortar o rosto, a partir do plano inicial.
_PUSH = {
    'corpo inteiro, da cabeça aos pés': 'o plano americano (dos joelhos para cima)',
    'plano americano, dos joelhos para cima': 'o plano médio (da cintura para cima)',
}


def push_target(c: dict) -> str:
    return _PUSH.get(speech_framing(c), 'um plano um pouco mais fechado')


def closing_rules(c: dict, product: str, keeps: str, face: bool = True) -> str:
    """Linha final de travas: rosto, giro nao autorizado e opacidade no
    genero da peca ("o short ... opaco")."""
    opaque = 'opaca' if _piece_forms(c)['art'] == 'a' else 'opaco'
    parts = []
    if face:
        parts.append('mesmo rosto em todos os quadros, sempre inteiro na imagem enquanto ela fala')
    if 'costas' not in _body_turns(c):
        parts.append('ela nunca fica de costas para a câmera')
    parts.append(f'{product} continua {keeps} e totalmente {opaque}')
    parts.append('sem texto na tela')
    return 'IMPORTANTE: ' + '; '.join(parts) + '.'


def proof_gesture(c: dict, spoken: str = '') -> str:
    """O gesto que prova o fato confirmado que a fala promete ("sem
    transparência" -> agachamento de frente sob a mesma luz). Sem ele, a fala
    promete algo que nenhuma cena mostra.

    Entre varios fatos, vence o citado mais cedo nas falas: o gancho e a
    promessa, e a prova do meio tem que responder a ela."""
    features = _product_features(c, limit=6)
    text = unicodedata.normalize('NFKD', spoken.casefold()).encode('ascii', 'ignore').decode()
    cited = [(text.find(_stem(f)), i) for i, f in enumerate(features) if _stem(f) in text]
    if cited:
        features = [features[min(cited)[1]]]
    if _video_mode(c) == 'pov':
        plan = _pov_proof_gestures(features, limit=1)
        return plan[0].split(' → ', 1)[1] if plan else ''
    plan = _proof_gestures(features, limit=1, turns=_body_turns(c))
    if not plan:
        return ''
    label, gesture = plan[0].split(' → ', 1)
    return _STAY_IN_FRAME.get(label, gesture)


def movement_steps(c: dict, spoken: str = '',
                   default: str = 'caminha dois passos e ajeita a peça com uma das mãos',
                   limit: int = MAX_MOVES) -> list[str]:
    """Gesto de prova, movimentos do briefing (na ordem escrita) e o giro
    autorizado -- no maximo ``limit`` acoes no total."""
    proof = proof_gesture(c, spoken) if _video_mode(c) != 'pov' else ''
    moves = _moves(c)
    if proof:
        # "agacha" depois de "faz um agachamento" seria a mesma acao duas vezes.
        moves = [m for m in moves if m.split()[0][:5].casefold() not in proof.casefold()]
    turn = _turn(c)
    room = max(0, limit - bool(turn) - bool(proof))
    steps = ([proof] if proof else []) + moves[:room] + ([turn] if turn else [])
    return steps or [default]


def pov_hands(c: dict, spoken: str = '') -> str:
    """Trecho do meio do POV: o gesto de prova visto pelas maos, ou o manuseio
    generico quando o briefing nao confirma nenhum atributo."""
    proof = proof_gesture(c, spoken)
    if not proof:
        return 'As mãos puxam levemente o tecido e passam pelos detalhes da peça'
    if proof.startswith('a câmera'):
        return proof[0].upper() + proof[1:]
    return f'Com a mão livre, ela {proof}'


# Direcao de fala. As tres frases sao um so pensamento: sem isso o gerador
# trata cada trecho como um anuncio separado, com pausa e entonacao de
# locutor. Tom de conversa com amiga, nao de propaganda.
SPEECH = ('Fala: uma conversa só, do começo ao fim, sem pausa entre as frases, como quem conta uma descoberta para uma amiga; '
          'tom espontâneo e animado na medida, entonação que sobe e desce, sorriso na voz; nada de locução '
          'nem de anúncio. Ritmo natural, sem correr. Voz feminina em português do Brasil, lábios '
          'sincronizados; fala só o que está entre aspas, palavra por palavra; som ambiente baixo, sem música.')
# Maos vivas: no teste real, "uma mao sempre na peca" + "movimentos lentos"
# deixou a modelo dura e em camera lenta. Gente de verdade gesticula enquanto
# fala; a mao volta para a peca so para mostrar o que a fala diz.
HANDS = ('Mãos: enquanto fala, ela gesticula com naturalidade, como quem conversa com uma amiga — abre a mão, '
         'aponta para a peça, toca o tecido no momento em que fala dele e volta a mão para a peça; nada de mãos '
         'paradas nem braços duros. Gestos e expressões no ritmo das palavras, sem movimento artificial de IA.')
SPEECH_POV = ('Fala: narração de quem está testando e comentando sozinha, num tom baixo e espontâneo, '
              'como pensando em voz alta; uma conversa só, sem pausa de locutor. Voz feminina em português '
              'do Brasil, só o que está entre aspas; som ambiente baixo, sem música.')


# Conectivos entre as acoes. "Depois... depois..." fazia o Grok executar cada
# acao como uma cena: terminava, parava e recomecava -- o video saia travado
# nas emendas. Aqui cada gesto comeca enquanto o anterior termina.
_FLOW = (', e, sem parar, ', ', emendando em seguida: ', ', e no mesmo embalo ')
_CONNECTIVE = re.compile(r'^(Mas|E|Aí|Então|Só que|Porque)\b')


def flow(steps: list[str], offset: int = 0) -> str:
    """Acoes ligadas num movimento so, sem pausa entre elas. ``offset``
    escolhe o primeiro conectivo, para nao repetir o que veio antes."""
    out = ''
    for i, step in enumerate(s for s in steps if s):
        out = step if not out else out + _FLOW[(i - 1 + offset) % len(_FLOW)] + step
    return out


def one_breath(*lines: str) -> str:
    """As tres falas numa so citacao. Em tres aspas separadas, o Grok fazia
    uma pausa de locutor em cada emenda; numa so, a fala corre inteira.
    "...apertar demais" + "Mas essa aqui..." vira "...apertar demais, mas
    essa aqui..." -- sem ponto final onde a fala nao para."""
    parts = [_clean(x).rstrip(' .…') if i < 2 else _clean(x) for i, x in enumerate(lines)]
    text = ''
    for part in (p for p in parts if p):
        if not text:
            text = part
        elif _CONNECTIVE.match(part) and not text.endswith(('!', '?')):
            text += ', ' + part[0].lower() + part[1:]
        else:
            text += ('' if text.endswith(('!', '?')) else '.') + ' ' + part
    return text


def build_compact_video_prompt(c: dict, prompts: dict, color: str) -> str:
    model = _clean(c.get('model_name')) or 'a modelo'
    product = _clean(c.get('product')) or _clean(c.get('outfit')) or 'a peça'
    color = _clean(color) or _clean(c.get('color'))
    piece = f'{product} na cor {color}' if color else product
    touch = _touch_point(c)
    keeps = f'na cor {color}' if color else 'igual'
    hook, development, cta = (_quote(prompts.get(k)) for k in ('hook', 'development', 'cta'))
    mode = _video_mode(c)
    shot = framing(c)
    vibe = mood(c)
    res = size(c)

    spoken = f'{hook} {development}'
    # Com fala: no maximo 3 acoes no meio (a prova, um movimento e o giro).
    # Quatro em fila ("passa a mao, ajusta, senta e levanta, gira") deixavam
    # o video corrido.
    falando = mode not in ('pov', 'movimento')
    # Sem "devagar" no resumido: o Grok deixava tudo em camera lenta.
    steps = [re.sub(r'\s+devagar\b', '', s)
             for s in movement_steps(c, spoken, limit=3 if falando else MAX_MOVES)]
    # Motor de persuasao no corpo: expressao do gancho, arco e gesto da chamada.
    cena = persuasion.scene_direction(persuasion.script_motor(_dominant_motor(c), hook), touch)
    fala = one_breath(hook, development, cta)
    seamless = ('Cada gesto começa enquanto o anterior termina: nada de parar, posar ou recomeçar entre uma '
                'ação e outra.')

    first_frame = (
        f'A imagem anexada é o primeiro quadro: a mesma mulher ({model}); preserve 100% o mesmo rosto, '
        'cabelo, pele e corpo em todos os quadros, vestindo exatamente o que aparece nela.')
    light = 'Luz: a mesma da imagem, sem trocar a cena nem escurecer.'
    close = closing_rules(c, product, keeps)

    if mode == 'pov':
        hands = pov_hands(c, spoken)
        return '\n'.join([
            f'Vídeo vertical 9:16 em primeira pessoa (POV), 15 segundos, {res}. Clima: {vibe}.',
            'A imagem anexada é o primeiro quadro: mesmo ambiente e mesma luz do começo ao fim. '
            f'A câmera é o olhar de quem veste {piece}; aparecem só as mãos e o corpo do pescoço para baixo, nunca o rosto.',
            'Câmera: na mão, apontada para baixo, um único take contínuo com leve balanço natural, sem cortes.',
            f'Ação contínua, sem pausas: as mãos mostram {touch}{_FLOW[0]}{hands[0].lower() + hands[1:]}, em ritmo natural; '
            'no final, tilt suave para baixo mostrando a peça inteira no corpo, e o indicador aponta uma vez para a '
            f'parte de baixo da tela. {seamless}',
            f'Narração, do começo ao fim, num fôlego só: "{fala}"',
            SPEECH_POV,
            closing_rules(c, product, keeps, face=False).replace('IMPORTANTE: ', 'IMPORTANTE: o rosto nunca aparece; ', 1),
        ])

    if mode == 'movimento':
        return '\n'.join([
            f'Vídeo vertical 9:16, 15 segundos, {res}, sem fala. Clima: {vibe}.',
            first_frame, light,
            f'Câmera: fixa na altura do peito, {shot}, sem zoom, um único take contínuo, sem cortes.',
            f'Ação contínua, sem pausas: ela {cena["hook"]}{_FLOW[0]}{flow(steps, 1)}, em ritmo natural de conversa, sem câmera lenta; '
            f'no final, já de frente para a lente, ela {cena["cta"]}, com sorriso leve e confiante. {seamless}',
            f'Expressão: {cena["arc"]}.',
            'Som: sem voz e sem fala; só som ambiente discreto.',
            close,
        ])

    return '\n'.join([
        f'Vídeo vertical 9:16, 15 segundos, {res}. Clima: {vibe}.',
        first_frame, light,
        f'Câmera: na mão, estável, {speech_framing(c)}, frontal, um único take contínuo, sem cortes; dolly-in suave e '
        f'contínuo até {push_target(c)} e volta suave ao plano inicial no final. O rosto fica sempre no quadro.',
        f'Ação contínua, sem pausas: ela {cena["hook"]}{_FLOW[0]}{flow(steps, 1)}, em ritmo natural de conversa, sem câmera lenta; '
        f'no final, já de frente para a lente, ela {cena["cta"]}, sorrindo. {seamless}',
        f'O que ela diz, do começo ao fim do vídeo, num fôlego só e enquanto se move: "{fala}"',
        f'Expressão: {cena["arc"]}.',
        HANDS,
        SPEECH,
        close,
    ])
