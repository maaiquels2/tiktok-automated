"""Sequencia STORYTELLING de 2 ou 3 clipes para o CapCut: arcos "Motivos" e "Questionada".

Diferente de services/story_sequence.py (que reparte as MESMAS 3 falas do roteiro de 15 s em partes curtas
para o Extend Video), aqui cada clipe traz fala NOVA e conteudo novo, e os clipes se encaixam num video so
de cerca de 30 s (2 clipes) ou 45 s (3 clipes).

  Motivos      "Tres motivos pra essa peca estar no teu guarda-roupa": um fato confirmado por motivo
  Questionada  "Sabe o que dizem por ai? Que ela nao te valoriza" e a resposta, motivo a motivo

Validado no Grok com a calca jeans no espelho (480p): identidade, roupa e cenario iguais entre os clipes.
O que o teste real ensinou e esta aqui:
  - no Grok, o clipe 2 (e o 3) parte do ULTIMO QUADRO do clipe anterior (o Grok pediu assim): o prompt dele e ENXUTO
    (_lean_prompt: sem cenario fixo, enquadramento e camera longa, que o quadro ja mostra; falas, gestos, maos e
    regras de identidade ficam inteiros). O prompt completo, que parte da MESMA imagem aprovada do clipe 1 (o que foi
    validado no espelho), continua em ``prompt_image``; o PACOTE DO AGENTE (agent_pack, experimental) usa o completo
    e o video do clipe anterior;
  - so o ultimo clipe pede a compra e aponta para o carrinho; os anteriores terminam no meio do gesto, com
    uma pergunta aberta;
  - o clipe 1 sai com o prompt original do espelho (os ajustes finos o deixaram lento);
  - fala densa (46 a 57 palavras por clipe): abaixo disso sobra silencio, acima fica "corrido".

Regras de honestidade (as mesmas do resto do app):
  - os "motivos" so podem ser fatos que o briefing confirma (campo Detalhes e atributos da peca);
  - "ja me imagino com ela..." e imaginacao em primeira pessoa, nunca promessa de resultado;
  - "Sabe o que dizem por ai..." e recurso retorico: nao cita pessoa nem comentario real;
  - toda fala passa pela auditoria do app (termos de desempenho, urgencia, direcao de cena falada).

So le a campanha: nada e gravado. As falas sao um RASCUNHO que o operador pode editar.
"""
import re
import unicodedata

from services import generators, script_budget, speech_bank
from services.copywriter import audit as honesty_audit
from services.prompt_improve import build_compact_video_prompt
from services.prompts import (
    PRODUCT_FEATURES, SPOKEN_OCCASION, back_rule, body_turns, cta_pool, pick_in_budget, piece_forms,
    product_features, proof_gestures, texture_beat, video_details, generate,
    without_niche_defaults,
)
from services.formats import SPEAKING_FRONT as FRONT_FORMATS, video_mode as _video_mode
from services.piece import product_family as _product_family
from services.script_budget import count_words as _count_words

ARCS = {
    'motivos': dict(label='Motivos', hint='"Três motivos pra essa peça estar no seu guarda-roupa", um fato por motivo'),
    'questionada': dict(label='Dúvida e resposta',
                        hint='"Será que vale a pena?": abre com a dúvida que a cliente teria e responde com 3 fatos da peça'),
    'problema': dict(label='Problema e solução',
                     hint='"Sabe aquela hora de montar o look e nada parece certo?": abre no problema e a peça responde, com 3 fatos'),
    'mito': dict(label='Mito e verdade',
                 hint='"Dizem que é tudo igual": desfaz a ideia comum com 3 verdades, um fato por vez'),
}
CLIP_COUNTS = (2, 3)
MIN_FACTS = 3            # todos os arcos usam 3 motivos
MAX_FACTS = 4
WORD_FLOOR, WORD_CEILING = script_budget.FILL[0], script_budget.CEILING   # abaixo sobra silencio no fim; acima a fala fica corrida
GROK_LIMIT = generators.GROK.prompt_target   # o Grok corta sem avisar; folga para o nome e a cor
SECONDS_PER_CLIP = 15

CONTINUITY = ('CONTINUIDADE: clipe {n} de {total} da MESMA gravação: mesma modelo, mesmo espelho, mesma roupa e '
              'mesma luz; o clipe abre na pose da imagem anexada, já falando, sem saudação e sem reapresentar a '
              'peça. ')
LAST_WORD = 'a última palavra é dita por inteiro antes do fim do clipe'
OPEN_END = ('termina de frente para o espelho, com a mão livre pousada na peça, no meio do gesto, sem apontar e '
            'sem pose de fechamento; a fala segue até o último segundo')
FINAL_END = ('no final, de frente para o espelho, a mão livre aponta uma vez para baixo com o indicador, sorrindo')
GENERIC_MOVE = 'gesticula como quem conversa com uma amiga, passando a mão pela peça enquanto fala dos looks'

# Formato de frente (a modelo fala para a lente, sem celular na mao dela): as mesmas regras do espelho, sem
# espelho e sem "mao livre". Ainda nao validado no Grok fora do espelho; a tela avisa.
CONTINUITY_FRENTE = ('CONTINUIDADE: clipe {n} de {total} da MESMA gravação: mesma modelo, mesmo cenário, mesma roupa '
                     'e mesma luz; o clipe abre na pose da imagem anexada, já falando, sem saudação e sem reapresentar '
                     'a peça. ')
OPEN_END_FRENTE = ('termina de frente para a lente, com uma das mãos pousada na peça, no meio do gesto, sem apontar e '
                   'sem pose de fechamento; a fala segue até o último segundo')
FINAL_END_FRENTE = 'no final, de frente para a lente, uma das mãos aponta uma vez para baixo com o indicador, sorrindo'


# Formatos com a modelo de frente falando para a lente (frontend: ARC_FORMATS, sem o espelho).


def _wording(espelho):
    """Os textos que mudam entre o espelho (validado) e o formato de frente."""
    if espelho:
        return dict(continuity=CONTINUITY, open_end=OPEN_END, final_end=FINAL_END, olhar='olhar na tela do celular',
                    abre='dá um passo até o espelho com sorriso confiante', mao='com a mão livre',
                    extend=('mesmo espelho e mesma luz; segue o último quadro sem pausa, o celular sempre na mão dela, '
                            'na altura do peito, sem cobrir o rosto'))
    return dict(continuity=CONTINUITY_FRENTE, open_end=OPEN_END_FRENTE, final_end=FINAL_END_FRENTE,
                olhar='olhar na lente', abre='dá um passo até a câmera com sorriso confiante', mao='com uma das mãos',
                extend=('mesmo cenário e mesma luz; segue o último quadro sem pausa, câmera na mão, estável, de frente '
                        'para ela, com o rosto inteiro no quadro'))


def _soft_sub(pattern, new, text, flags=0):
    """Troca uma ocorrencia se existir. Para blocos que o gerador pode omitir no limite do Grok (expressao, prova
    visual): faltar o bloco nao e erro, so nao ha o que trocar."""
    return re.sub(pattern, new if callable(new) else (lambda _m: new), text, count=1, flags=flags)


class ArcError(Exception):
    """Pedido que o app nao consegue atender (a mensagem e para o operador)."""

    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def _norm(text):
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def _cap(text):
    text = str(text or '').strip()
    return text[:1].upper() + text[1:]


def _low(text):
    """Minuscula no inicio, para o fato entrar no meio da frase (sigla como 'UV' fica como esta)."""
    text = str(text or '').strip()
    return text if text[:2].isupper() else text[:1].lower() + text[1:]


# Frases de enchimento: primeira pessoa, sobre o que se ve, sem nenhuma afirmacao sobre a peca. Entram no meio
# do clipe, uma de cada vez, so enquanto a fala estiver abaixo do piso de palavras.
FILLERS = (
    'Eu reparei nisso assim que coloquei.',
    'Dá pra ver direitinho aqui de pertinho.',
    'Eu mesma gostei muito de ver isso de perto.',
    'Olha só como isso aparece aqui.',
)


def _pad(trio):
    """Leva o clipe ao piso de palavras acrescentando enchimento ao trecho do meio."""
    first, middle, last = trio
    for filler in FILLERS:
        if sum(_count_words(part) for part in (first, middle, last)) >= WORD_FLOOR:
            break
        if filler not in middle:
            middle = f'{middle} {filler}'
    return first, middle, last


# ------------------------------------------------------------------------------------------------ fatos
def _feature_label(chunk):
    low = _norm(chunk)
    for label, needles in PRODUCT_FEATURES:
        if any(re.search(rf'\b{re.escape(_norm(n))}\b', low) for n in needles):
            return label
    return ''


def arc_facts(c, limit=MAX_FACTS, texture=False):
    """Os motivos: o que o briefing confirma, na ordem em que o operador escreveu (campo Detalhes), mais os
    atributos reconhecidos nos outros campos. Cada fato leva o gesto que o demonstra no espelho.
    ``texture`` (opt-in, experimental): fato que e material ou detalhe com close (courino, cetim, botoes...) ganha
    um close curto de 1 a 2 s; os outros fatos nao mudam."""
    turns = body_turns(c)
    espelho = _video_mode(c) == 'espelho'
    mao = _wording(espelho)['mao']
    facts, seen_text, seen_label = [], set(), set()

    def add(text, label):
        key = _norm(text)
        if not key or key in seen_text or (label and label in seen_label):
            return
        gesture = ''
        if label:
            plan = proof_gestures([label], turns=turns)
            gesture = plan[0].split(' → ', 1)[1] if plan else ''
        close = ''
        if texture:
            own, close = texture_beat(text, label, espelho, mao)
            if close:
                gesture = f'{gesture or own}, e {close}'
        facts.append(dict(
            text=text, label=label, texture=bool(close),
            gesture=gesture or f'mostra {mao}, bem à vista, o detalhe "{text}" e volta a mão para a peça'))
        seen_text.add(key)
        if label:
            seen_label.add(label)

    # O campo Detalhes nasce com o texto padrao da moda (direcao de cena: "Destacar textura e modelagem").
    # Teste real: ele virava "motivo" da sequencia. So conta o que a pessoa escreveu.
    details = video_details(without_niche_defaults(c.get('details') or ''))
    for chunk in re.split(r'\s*[,;]\s*|(?<=[.!?])\s+|\n+', details):
        chunk = chunk.strip(' .;')
        if not chunk or len(chunk.split()) > 5:
            continue
        if re.match(r'^(mostr|demonstr|aproxim|gir|ajust|fa[çc]a|use|destac|mant[ei]|evit|identidade|rosto)\w*\b',
                    _norm(chunk)):
            continue   # direcao de cena, nao fato
        add(chunk, _feature_label(chunk))
    for label in product_features(c, limit=50):
        add(label, label)
    return facts[:limit]


# ------------------------------------------------------------------------------------------------ falas
def _join_pt(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' e ' + items[-1]


def _style(c):
    forms = piece_forms(c)
    cat = speech_bank.category(speech_bank.detect(c))
    occasions = list(cat['occasions']) if cat else []
    if not occasions:
        fallback = SPOKEN_OCCASION.get((c.get('niche') or '').strip(), '') or 'no dia a dia'
        occasions = [fallback]
    # "com tenis ou salto" nao cabe depois de "eu ja me imagino com ela ..."
    occasions = [o for o in occasions if not o.casefold().startswith('com ')][:3] or ['no dia a dia']
    combos = speech_bank.COMBOS.get(cat['id']) if cat else None
    return forms, occasions, combos


def _cta(c, forms):
    return pick_in_budget(cta_pool(c, forms), 0, *script_budget.LOCAL_PICK['cta'], fuzzy=False)


def draft_lines(c, arc, clips, facts):
    """Rascunho das falas: lista de clipes, cada um com 3 trechos (0-4 s, 4-12 s, 12-15 s)."""
    f1, f2, f3 = (_cap(f['text']) for f in facts[:3])
    l1, l2, l3 = (_low(f['text']) for f in facts[:3])
    forms, occasions, combos = _style(c)
    dem, piece, pron = forms['dem'], forms['piece'], forms['pron']
    imagino = f'Eu já me imagino com {pron} {_join_pt(occasions)}.'
    mix = f' e já imagina com {combos[0]}, com {combos[1]}' if combos else ''
    cta = _cta(c, forms)
    if arc == 'motivos':
        abre = f'Três motivos pra {dem} {piece} estar no teu guarda-roupa, olha só.'
        if clips == 2:
            return [
                (abre,
                 f'O primeiro motivo? {f1}. Repara bem aqui nessa parte{mix}. O segundo motivo? {f2}. '
                 f'Repara nesse detalhe de pertinho.',
                 'E o terceiro motivo? Esse eu guardei pra você ver logo em seguida.'),
                (f'O terceiro motivo? {f3}. Repara bem nisso aqui, olha só.',
                 f'{imagino} É daquelas peças que dá vontade de usar a semana inteira.',
                 cta),
            ]
        return [
            (abre,
             f'O primeiro motivo? {f1}. Repara bem aqui nessa parte{mix}. Eu reparei nisso assim que coloquei.',
             'E o segundo motivo? Esse eu guardei pra você ver logo em seguida.'),
            (f'O segundo motivo? {f2}. Repara nesse detalhe de pertinho, eu já me vejo usando {pron}.',
             f'O terceiro motivo? {f3}. Olha só como isso aparece aqui, dá pra ver direitinho de pertinho.',
             'Agora vem a parte que eu mais queria te falar.'),
            (f'É que {l1}, {l2} e {l3}, tudo isso junto, resolve muito look.',
             f'{imagino} É daquelas peças que dá vontade de usar a semana inteira.',
             cta),
        ]
    if arc == 'problema':
        abre = f'Sabe aquela hora de montar o look e nada parece certo? Então olha {dem} {piece}.'
        alivio = f'Pra mim, {pron} já resolve boa parte disso.'
        if clips == 2:
            return [
                (abre,
                 f'Primeiro: {f1}. Repara bem aqui nessa parte{mix}. Segundo: {f2}. Repara nesse detalhe de pertinho.',
                 'E o terceiro motivo? Esse eu guardei pra você ver logo em seguida.'),
                (f'O terceiro: {f3}. Repara bem nisso aqui, olha só.',
                 f'{imagino} Quando faltar ideia de look, {pron} já tá ali, esperando.',
                 cta),
            ]
        return [
            (abre,
             f'{alivio} O primeiro motivo? {f1}. Eu reparei nisso assim que coloquei.',
             'E o segundo? Esse eu guardei pra você ver logo em seguida.'),
            (f'O segundo: {f2}. Repara nesse detalhe de pertinho, eu já me vejo usando {pron}.',
             f'E o terceiro: {f3}. Olha só como isso aparece aqui, dá pra ver direitinho de pertinho.',
             'Agora vem a parte que eu mais queria te falar.'),
            (f'É que {l1}, {l2} e {l3}: pra mim, esse é o fim do "não tenho o que vestir".',
             imagino,
             cta),
        ]
    if arc == 'mito':
        abre = f'Dizem que {piece} é tudo igual. Pra mim isso é mito, e eu vou te mostrar três verdades, olha só.'
        if clips == 2:
            return [
                (abre,
                 f'Primeira verdade: {f1}. Repara bem aqui nessa parte{mix}. Segunda verdade: {f2}.',
                 'A terceira verdade eu guardei pra você ver logo em seguida.'),
                (f'Terceira verdade: {f3}. Repara bem nisso aqui, olha só.',
                 f'Então, pra mim, {piece} não é tudo igual não. {imagino}',
                 cta),
            ]
        return [
            (abre,
             f'Primeira verdade: {f1}. Eu reparei nisso assim que coloquei.',
             'A segunda verdade eu guardei pra você ver logo em seguida.'),
            (f'Segunda verdade: {f2}. Repara nesse detalhe de pertinho, dá pra ver direitinho.',
             f'Terceira verdade: {f3}. Olha só como isso aparece aqui, de pertinho.',
             'Agora me diz com sinceridade: ainda parece tudo igual?'),
            (f'Pois é. {_cap(l1)}, {l2} e {l3}: pra mim, é aí que o mito cai.',
             f'{imagino} Tem peça que só parece igual de longe.',
             cta),
        ]
    # questionada (Dúvida e resposta)
    pergunta = f'Sei que dá aquela dúvida: será que {dem} {piece} vale mesmo a pena?'
    promessa = (f'Então olha comigo. Eu vou te mostrar três motivos pra {dem} {piece} '
                f'merecer um lugar no teu guarda-roupa, um por um.')
    if clips == 2:
        return [
            (pergunta, promessa,
             f'Começando pelo primeiro motivo: {l1}. Os outros eu já mostro.'),
            (f'O segundo motivo? {f2}. Repara nesse detalhe de pertinho.',
             f'O terceiro motivo? {f3}. Dúvida respondida: pra mim, {pron} vale a pena por esses três motivos. '
             f'{imagino}',
             cta),
        ]
    return [
        (pergunta, promessa,
         f'Começando pelo primeiro motivo: {l1}. Presta atenção aqui no que eu vou te mostrar.'),
        (f'O primeiro: {f1}. Olha só como aparece aqui, de pertinho.',
         f'O segundo motivo? {f2}. E o terceiro? {f3}. Repara em cada detalhe de pertinho, um de cada vez.',
         'Agora me responde com sinceridade: ainda sobrou algum motivo pra duvidar?'),
        (f'Pois é. Quando eu juntei esses três motivos, a dúvida passou pra mim.',
         f'{imagino} {_cap(l1)}, {l2}, {l3}: se faltava motivo, é esse.',
         cta),
    ]


def _clip_facts(arc, clips, index, facts):
    """Quais fatos a modelo demonstra (com gesto) em cada clipe."""
    f = facts[:3]
    if arc in ('motivos', 'problema', 'mito'):
        layout = {2: [f[:2], f[2:3]], 3: [f[:1], f[1:3], []]}
    else:
        layout = {2: [f[:1], f[1:3]], 3: [f[:1], f[:3], []]}
    return layout[clips][index]


_ROLES = {
    ('motivos', 2): ('Gancho + motivos 1 e 2', 'Motivo 3 + projeção de uso + fechamento (CTA)'),
    ('motivos', 3): ('Gancho + motivo 1', 'Motivos 2 e 3', 'Projeção de uso + fechamento (CTA)'),
    ('questionada', 2): ('A dúvida + o primeiro motivo', 'Os outros dois motivos + a dúvida respondida + fechamento (CTA)'),
    ('questionada', 3): ('A dúvida', 'A resposta: desmonta cada motivo', 'A dúvida respondida + fechamento (CTA)'),
    ('problema', 2): ('O problema + a peça + motivos 1 e 2', 'Motivo 3 + projeção de uso + fechamento (CTA)'),
    ('problema', 3): ('O problema + a peça + motivo 1', 'Motivos 2 e 3', 'O problema resolvido + fechamento (CTA)'),
    ('mito', 2): ('O mito + verdades 1 e 2', 'Verdade 3 + o mito desfeito + fechamento (CTA)'),
    ('mito', 3): ('O mito + verdade 1', 'Verdades 2 e 3', 'O mito desfeito + fechamento (CTA)'),
}
_SCREEN = {
    'motivos': ('3 motivos pra ter essa peça', 'O 2º e o 3º motivo', 'Qual é o seu motivo?'),
    'questionada': ('Vale a pena?', 'Tirando a dúvida', 'Qual peça é a sua?'),
    'problema': ('Nada pra vestir?', 'A solução em 3 motivos', 'Qual é o seu look?'),
    'mito': ('Mito ou verdade?', 'As 3 verdades', 'Ainda parece tudo igual?'),
}


# ------------------------------------------------------------------------------------------------ prompts
def _sub1(pattern, new, text, flags=0):
    """Troca exatamente uma ocorrencia. Se o gerador de prompts mudar e o padrao sumir, falha em voz alta
    (os testes pegam) em vez de entregar um prompt sem a trava."""
    result, count = re.subn(pattern, new if callable(new) else (lambda _m: new), text, count=1, flags=flags)
    if count != 1:
        raise ArcError(f'O gerador de prompts mudou e a sequência não encontrou: {pattern[:50]}', 500)
    return result


def _opening_of(text, w):
    """O que o app manda ela fazer no gancho (ex.: 'dá um passo até o espelho com sorriso confiante...')."""
    m = re.search(r'0–\d+s HOOK: [^;]*; a modelo (.*?)\. Fala \(PT-BR\):', text)
    return m.group(1) if m else w['abre']


def _moves(clip_facts):
    if not clip_facts:
        return GENERIC_MOVE
    return ' e, em seguida, '.join(f['gesture'] for f in clip_facts)


# Giro do corpo POR CLIPE (opt-in, experimental: giro do corpo no espelho nunca foi testado no Grok). '' = o giro da
# campanha (como sempre foi); os outros valem so para aquele clipe. 'costas_pausa' e o unico valor novo: parada de
# costas de 3 a 6 s com um olhar por cima do ombro; o 'costas' da campanha (no maximo 1 s, sem olhar) nao muda.
CLIP_TURNS = {
    '': dict(label='Igual à campanha', move=''),
    'frente': dict(label='Sempre de frente', move=''),
    'leve_lado': dict(label='Leve de lado (20 a 30 graus)',
                      move='inclina o corpo uma única vez, de 20 a 30 graus, e volta de frente, com o rosto e a frente '
                           'da peça sempre visíveis'),
    'lado': dict(label='De lado, até o perfil',
                 move='vira uma única vez até o perfil, sem passar dele nem mostrar as costas, e volta de frente'),
    'costas': dict(label='De costas por no máximo 1 s',
                   move='faz uma única virada contínua de costas, por no máximo 1 segundo, e volta de frente na hora, '
                        'sem pose nem olhar por cima do ombro'),
    'costas_pausa': dict(label='De costas de 3 a 6 s, olhando por cima do ombro uma vez', move=''),
}
_BACK_FACTS = ('sem transparência', 'decote nas costas')   # o que a parada de costas ja demonstra
_TURNING_GESTURE = re.compile(r'\b(?:gir\w*|vir[ao]\w*|perfil|de costas)\b', re.I)


def _clip_turn_list(clip_turns, clips):
    """Valida o giro de cada clipe. None quando nenhum clipe escolheu giro proprio (saida igual a de sempre)."""
    if clip_turns is None:
        return None
    if isinstance(clip_turns, str):
        clip_turns = clip_turns.split(',')
    if not isinstance(clip_turns, (list, tuple)) or len(clip_turns) != clips:
        raise ArcError(f'Escolha o giro do corpo de cada um dos {clips} clipes.', 400)
    values = [str(v or '').strip() if isinstance(v, (str, type(None))) else '?' for v in clip_turns]
    if any(v not in CLIP_TURNS for v in values):
        raise ArcError('Giro do clipe inválido: escolha igual à campanha, de frente, leve de lado, de lado, de costas '
                       'por 1 s ou de costas de 3 a 6 s.', 400)
    return values if any(values) else None


def _back_hold(c, espelho, light):
    """A parada de costas de 3 a 6 s, com as travas no proprio gesto (o Guia e o pacote do agente so levam as acoes)."""
    quadro = ('peça inteira no reflexo, celular na mão apontado para o espelho' if espelho
              else 'peça inteira no quadro')
    luz = ', sob a mesma luz, para a cobertura do tecido aparecer' if light else ''
    olhar = 'a tela do celular' if espelho else 'a lente'
    return (f'vira de costas uma única vez e fica assim de 3 a 6 s, de pé, {quadro}{luz}; olha UMA vez por cima do '
            f'ombro para {olhar} e volta de frente falando; nada sensualizado: sem pose, rebolado, câmera baixa ou '
            f'close no corpo; {back_rule(c)}')


def _turn_plan(value, clip_facts, c, espelho):
    """(fatos do clipe com o gesto ajustado, acao do giro a acrescentar). Uma unica virada por clipe: se um gesto de
    prova ja vira o corpo, ele e a virada; na parada de costas, o fato que ela ja prova entra nela."""
    if value in ('', 'frente'):
        return clip_facts, ''
    if value != 'costas_pausa':
        if any(_TURNING_GESTURE.search(f['gesture']) for f in clip_facts):
            return clip_facts, ''
        return clip_facts, CLIP_TURNS[value]['move']
    back = [f for f in clip_facts if f['label'] in _BACK_FACTS]
    if not back:
        return clip_facts, _back_hold(c, espelho, light=False)
    light = any(f['label'] == 'sem transparência' for f in back)
    out = []
    for f in clip_facts:
        if f is back[0]:
            out.append({**f, 'gesture': _back_hold(c, espelho, light)})
        elif f not in back:
            out.append(f)
    return out, ''


def _trim(text, limit):
    """O Grok corta em 4000 caracteres sem avisar: cortes de baixa prioridade (so frases de regra, nunca fala nem
    gesto), um de cada vez, so se passar de ``limit``."""
    for pattern in (r' Notas adicionais do operador \(não são falas\): [^.]*\. ',
                    r' Estilo visual: natural e realista\.',
                    r' Ângulo de venda \(contexto, não criar atributos\): [^.]*\.',
                    r' Com material confirmado, preservar textura e brilho\.',
                    r' Sem promessas não demonstradas no vídeo\.',
                    r'(?<=\. )Outras peças citadas na fala não entram no vídeo\. ',
                    r' Visual: [^.]*\.'):  # repete o "Produto em cena" logo antes
        if len(text) <= limit:
            break
        text = re.sub(pattern, ' ', text, count=1)
    if len(text) > limit:
        text = re.sub(r' {2,}', ' ', text)  # cada corte deixa um espaco; so aqui, para nao mexer nos que ja cabem
    return text


def _full_prompt(source, n, total, lines, clip_facts, base_image, opening=None, w=None, extra=''):
    w = w or _wording(True)
    final = n == total
    pack = generate(source, script=dict(hook=lines[0], development=lines[1], cta=lines[2]), base_image=base_image)
    text = pack['video']
    opening = opening or _opening_of(text, w)
    if n == 1:
        # o clipe 1 abre como o app ja abre o gancho do espelho e segue pelos gestos dos fatos
        abertura, meio = opening, _moves(clip_facts)
    else:
        # os seguintes partem da pose da imagem aprovada e ja entram falando, sem recomecar
        base = 'começa na pose da imagem anexada, já falando'
        if clip_facts:
            abertura, meio = f'{base}, e {clip_facts[0]["gesture"]}', _moves(clip_facts[1:]) if clip_facts[1:] else ''
        else:
            abertura, meio = base, GENERIC_MOVE
    acoes = f'{abertura}; {meio}' if meio else abertura
    if extra:
        acoes = f'{acoes}; {extra}'   # giro escolhido para este clipe (opt-in)
    # a PROVA VISUAL fixa do app e trocada pela coreografia do clipe (os gestos dos fatos)
    # (o bloco pode faltar: sem fato com gesto o gerador nao escreve PROVA VISUAL)
    text = _soft_sub(r'PROVA VISUAL — [^\n]*\n', '', text)
    start = re.search(r'ENCERRAMENTO \((\d+)–15s\)', text).group(1)
    # "AÇÕES (...)" aceita qualquer rotulo: com tecnicas (esticar, ousado) o gerador escreve "na ordem, a
    # primeira e obrigatoria" em vez de "escolha 2 a 3", e a sequencia caia com erro.
    if final:
        text = _sub1(r'AÇÕES \([^)]*\): .*?ENCERRAMENTO \(\d+–15s\):',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {acoes}. ENCERRAMENTO ({start}–15s):',
                     text, re.S)
    else:
        text = _sub1(r'AÇÕES \([^)]*\): .*?ENCERRAMENTO \(\d+–15s\): .*? (?=EXPRESSÃO:|\n)',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {acoes}. ENCERRAMENTO ({start}–15s): '
                     f'{w["open_end"]}. ', text, re.S)
        # A expressao muda com a tatica (desejo, necessidade, escassez): qualquer uma vira curiosidade aqui.
        text = _soft_sub(r'EXPRESSÃO: [^.\n]*\.', 'EXPRESSÃO: encanto → curiosidade (sem convite de compra).', text)
        text = _sub1(r'(\d+)–15s CTA: [^\n]*?Fala \(PT-BR\):',
                     lambda m: f'{m.group(1)}–15s FIM DO TRECHO (a venda NÃO fecha aqui): sem apontar para baixo e '
                               'sem pose de fechamento; segue o gesto e a fala'
                               + (f'; {LAST_WORD}' if n > 1 else '') + '. Fala (PT-BR):', text)
    if n > 1:
        text = _sub1(r'0–(\d+)s HOOK: [^\n]*?Fala \(PT-BR\):',
                     lambda m: f'0–{m.group(1)}s CONTINUAÇÃO (não é um hook novo: não recomeçar, não reapresentar '
                               f'a peça): {w["olhar"]}, já falando, na pose da imagem anexada, sem '
                               'recomeçar. Fala (PT-BR):', text)
        text = _sub1(r'(ANEXE a IMAGEM APROVADA da cor [^.]*\.)',
                     lambda m: m.group(1) + ' ' + w['continuity'].format(n=n, total=total), text)
    return _trim(text, GROK_LIMIT), opening, acoes


_LEAN_ANCHORS = (
    ('header', re.compile(r'\A(.*?)ANEXE a IMAGEM APROVADA', re.S)),
    ('identity', re.compile(r'A modelo é [^\n]*')),
    ('avoid', re.compile(r'EVITAR: [^\n]*')),
    ('orientation', re.compile(r'ORIENTAÇÃO CORPORAL[^\n]*')),
    ('actions', re.compile(r'MÃOS:.*?(?=\nSHOT LIST)', re.S)),
    ('shots', None),   # _SHOT_LIST_SPAN, definido mais abaixo
    ('tail', re.compile(r'ATRIBUTOS NÃO CONFIRMADOS.*\Z', re.S)),
)
LEAN_CAMERA_ESPELHO = ('CÂMERA: a mesma do quadro anexado: o reflexo no espelho de corpo inteiro, o celular sempre na mão '
                       'dela, na altura do peito, sem cobrir o rosto; um único take contínuo, sem cortes nem zoom.')
LEAN_CAMERA_FRENTE = ('CÂMERA: a mesma do quadro anexado: de frente para a lente, câmera estável, rosto inteiro no '
                      'quadro; um único take contínuo, sem cortes nem zoom.')


def _lean_prompt(full, n, total, w, espelho):
    """Prompt do clipe 2 e seguintes quando ele parte do ULTIMO QUADRO do clipe anterior (e nao da imagem aprovada).

    O quadro ja mostra modelo, roupa, cenario e luz, entao saem o CENARIO FIXO, o ENQUADRAMENTO e a descricao longa
    da camera (uma linha a substitui). Fica inteiro tudo o que o quadro NAO conta: identidade e fatos, o que evitar,
    orientacao do corpo, maos, cabelo, acoes, encerramento, expressao, shot list com as falas, atributos nao
    confirmados e audio. None se algum trecho nao for encontrado (o chamador usa o prompt completo e avisa)."""
    found = {}
    for name, pattern in _LEAN_ANCHORS:
        hit = (_SHOT_LIST_SPAN if name == 'shots' else pattern).search(full)
        if not hit:
            return None
        found[name] = hit.group(1) if name == 'header' else hit.group(0).strip()
    anchor = (f'ANEXE o ÚLTIMO QUADRO do clipe {n - 1} (extraído do vídeo gerado) como primeiro quadro e referência '
              'contínua: modelo, roupa, cenário e luz são os dele. ' + w['continuity'].format(n=n, total=total))
    text = '\n'.join((
        (found['header'] + anchor).strip(), found['identity'],
        LEAN_CAMERA_ESPELHO if espelho else LEAN_CAMERA_FRENTE, found['avoid'],
        found['orientation'], found['actions'], found['shots'], found['tail']))
    for old in ('da imagem anexada', 'à imagem aprovada', 'à imagem anexada', 'à imagem'):
        text = text.replace(old, 'do quadro anexado' if old.startswith('da') else 'ao quadro anexado')
    text = re.sub(r' {2,}', ' ', text)
    if re.search(r'imagem anexada|IMAGEM APROVADA|imagem aprovada', text):
        return None
    return text


def _guide(source, n, total, lines, acoes, w=None):
    w = w or _wording(True)
    final = n == total
    pack = dict(hook=lines[0], development=lines[1], cta=lines[2])
    text = build_compact_video_prompt(source, pack, source.get('color') or '')
    fim = w['final_end'] if final else w['open_end'] + (f'; {LAST_WORD}' if n > 1 else '')
    text = _sub1(r'(?m)^Ação contínua, sem pausas:.*$',
                 f'Ação contínua, sem pausas: ela {acoes}; {fim}. Cada gesto começa enquanto o anterior termina: '
                 'nada de parar, posar ou recomeçar entre uma ação e outra.', text)
    if not final:
        text = _sub1(r'(?m)^Expressão: .*$', 'Expressão: encanto → curiosidade (sem convite de compra).', text)
    if n > 1:
        text = _sub1(r'(?m)^A imagem anexada é o primeiro quadro: ',
                     w['continuity'].format(n=n, total=total) + 'A imagem anexada é o primeiro quadro: ', text)
    return text   # o Guia compacto continua partindo da imagem anexada; o operador anexa a imagem que quiser


def _extend(n, total, lines, acoes, w=None):
    w = w or _wording(True)
    final = n == total
    fim = w['final_end'] if final else w['open_end']
    return (
        f'Continuação do mesmo take, já em movimento: mesma pessoa, mesma roupa, {w["extend"]}.\n'
        f'Ela {acoes}. Ela emenda a fala no mesmo tom, como quem conta uma descoberta para uma amiga: '
        f'"{" ".join(lines)}"\n{_cap(fim)}.' + ('' if final else ' Termina em movimento, sem parar no último quadro.')
        + '\nFala: espontânea, voz feminina em português do Brasil, lábios sincronizados, só o que está entre '
          'aspas; a fala ocupa os 15 segundos até o fim, sem silêncio; som ambiente baixo, sem música. '
          'Sem texto na tela.')


# ------------------------------------------------------------------------------------------------ montagem
def _normalize_lines(clips_lines, clips):
    if not isinstance(clips_lines, (list, tuple)) or len(clips_lines) != clips:
        raise ArcError(f'Mande as falas dos {clips} clipes.', 400)
    out = []
    for index, item in enumerate(clips_lines, 1):
        if isinstance(item, str):
            item = [part for part in re.split(r'\n+', item.strip()) if part.strip()]
        item = [re.sub(r'\s+', ' ', str(part)).strip() for part in (item or [])]
        if len(item) != 3 or not all(item):
            raise ArcError(f'O clipe {index} precisa de 3 trechos de fala (um por linha): gancho, meio e fechamento.',
                           400)
        out.append(tuple(item))
    return out


def build_story_arc(c, color, arc, clips, lines=None, base_image=False, clip_turns=None, texture=False):
    """Monta a sequencia: falas (rascunho ou editadas), prompt completo, Guia do Grok e Extend Video por clipe,
    mais o passo a passo do CapCut. `c` e a campanha (como detail()); `color` a cor da variacao.
    Opt-in (experimental, so neste pedido, nada gravado): ``clip_turns`` (giro do corpo de cada clipe, chaves de
    CLIP_TURNS) e ``texture`` (close de textura nos motivos que sao material ou detalhe confirmado). Desligados, a
    saida e a de sempre."""
    if arc not in ARCS:
        raise ArcError('Escolha um dos arcos da sequência.', 400)
    if clips not in CLIP_COUNTS:
        raise ArcError('Escolha 2 ou 3 clipes.', 400)
    turns = _clip_turn_list(clip_turns, clips)
    espelho, facts = check_campaign(c)
    w = _wording(espelho)
    drafted = lines is None
    clip_lines = ([_pad(trio) for trio in draft_lines(c, arc, clips, facts)] if drafted
                  else _normalize_lines(lines, clips))
    return _assemble(c, color, arc, clips, facts, clip_lines, drafted, base_image, espelho, w,
                     turns=turns, texture=bool(texture))


def write_lines_with_ai(c, arc, clips, settings):
    """Falas da sequencia escritas pela IA, conferidas pela mesma regua do rascunho (clip_problems), e cada um
    dos 3 fatos citado. Devolve (falas, fatos, motivo_da_falha). So roda pelo botao proprio: gasta tokens."""
    from services import copywriter
    if arc not in ARCS:
        raise ArcError('Escolha um dos arcos da sequência.', 400)
    if clips not in CLIP_COUNTS:
        raise ArcError('Escolha 2 ou 3 clipes.', 400)
    espelho, facts = check_campaign(c)
    source = {**c, 'video_mode': 'espelho' if espelho else ''}
    fatos = [f['text'] for f in facts[:3]]
    roles = _ROLES[(arc, clips)]
    oferta = str(c.get('offer') or '').strip()
    system = '\n'.join([
        'Você escreve as falas de vídeos UGC do TikTok Shop em português do Brasil, em primeira pessoa, como uma '
        'cliente real' + (' gravando o próprio look no espelho com o celular na mão.' if espelho
                          else ' falando de frente para a câmera.'),
        f'É uma SEQUÊNCIA de {clips} clipes de 15 segundos, emendados no CapCut. Arco: {ARCS[arc]["hint"]}.',
        'Regras:',
        '- Cada clipe tem 3 trechos: abertura (0-4 s), meio (4-12 s) e fechamento (12-15 s).',
        f'- Cada clipe soma de {WORD_FLOOR} a {WORD_CEILING - 1} palavras: quem vende fala o clipe inteiro, e fala '
        'curta deixa silêncio no fim. Nunca passe de ' + str(WORD_CEILING) + ' palavras por clipe.',
        '- Os motivos são SÓ estes fatos da peça, nesta ordem, citados com estas palavras: '
        + '; '.join(f'{n}) {t}' for n, t in enumerate(fatos, 1)) + '.',
        '- Não invente nada fora do briefing: tecido, conforto, caimento, tamanho, transparência, durabilidade, preço, '
        'desconto, estoque ou prazo. Opinião pessoal pode ("fiquei me sentindo linda"); desempenho, não.',
        '- Papel de cada clipe: ' + '; '.join(f'clipe {n}: {r}' for n, r in enumerate(roles, 1)) + '.',
        '- Só o último clipe pede a compra, com "carrinho laranja". Os outros terminam deixando gancho para o '
        'próximo clipe, sem falar em carrinho, comprar ou garantir.',
        ('- Oferta real que pode ser citada no último clipe, com os números exatos: ' + oferta) if oferta
        else '- Não existe oferta: nada de urgência, "só hoje", "últimas peças" ou desconto.',
        '- Linguagem falada e natural, com as emendas de quem conversa ("e olha", "sério", "aí"). Nada de direção '
        'de câmera dentro da fala (câmera, close, enquadramento, "mostrando").',
        f'Responda só JSON: {{"clips": [["abertura", "meio", "fechamento"], ...]}} com exatamente {clips} clipes.',
    ])
    user = '\n'.join(x for x in (
        f'Produto: {c.get("product") or c.get("outfit") or ""}',
        f'Cor: {c.get("color") or ""}' if c.get('color') else '',
        f'Público: {c.get("audience")}' if c.get('audience') else '',
        f'Benefício que o briefing confirma: {c.get("benefit")}' if c.get('benefit') else '',
        f'O que mais segura a compra (objeção): {c.get("objection")}' if c.get('objection') else '',
        f'Prova social real: {c.get("social_proof")}' if c.get('social_proof') else '',
    ) if x)

    def validate(dados):
        lista = dados.get('clips') if isinstance(dados, dict) else None
        if not isinstance(lista, list) or len(lista) != clips:
            return None, [f'a resposta precisa ter exatamente {clips} clipes']
        falas, problemas = [], []
        for i, trio in enumerate(lista, 1):
            if (not isinstance(trio, list) or len(trio) != 3
                    or not all(isinstance(t, str) and t.strip() for t in trio)):
                return None, [f'o clipe {i} precisa ter 3 trechos de texto']
            trio = [' '.join(t.split()) for t in trio]
            problemas += [f'clipe {i}: {p}' for p in clip_problems(trio, i, clips, source)]
            falas.append(trio)
        juntos = ' '.join(' '.join(t) for t in falas).casefold()
        problemas += [f'o fato "{t}" não foi citado' for t in fatos if t.casefold() not in juntos]
        return falas, problemas

    falas, motivo = copywriter.ask_json(settings, system, user, validate)
    return falas, fatos, motivo


def sequence_problem(c):
    """Por que a campanha nao pode ser uma sequencia ('' se pode). Usado na criacao, quando o tipo de video
    escolhido e sequencia de 2 ou 3 clipes: o aviso aparece ali, e nao so na etapa de video."""
    try:
        check_campaign(c)
    except ArcError as error:
        return str(error)
    return ''


def check_campaign(c):
    """Formato, tipo de peca e os 3 fatos. Devolve (espelho, fatos) ou levanta ArcError."""
    # Espelho (validado no Grok) e os formatos com a modelo de frente falando para a lente (Com fala, Teste de
    # prova, Respondendo comentario, Troca de cor, 3 jeitos). POV e so movimento nao tem fala de frente.
    espelho = _video_mode(c) == 'espelho'
    # Lista explicita (a mesma da tela): "Na mesa" tambem cai na base de frente, mas la nao ha modelo.
    bruto = str(c.get('video_mode') or '').strip().casefold()
    de_frente = bruto in FRONT_FORMATS
    if not espelho and not de_frente:
        raise ArcError('A sequência storytelling funciona nos formatos "Celular no espelho" e com a modelo de frente '
                       'falando (Com fala, Teste de prova, Respondendo comentário, Troca de cor). Troque o formato '
                       'do vídeo e tente de novo.')
    if _product_family(c) not in ('moda', 'infantil'):
        raise ArcError('A sequência storytelling está disponível para roupas. Para creme, brinco e colar use o '
                       'formato "Na mesa, de perto".')
    facts = arc_facts(c)
    if len(facts) < MIN_FACTS:
        achados = f'Só encontrei {len(facts)}' + (f' ({", ".join(f["text"] for f in facts)})' if facts else '')
        raise ArcError(f'{achados}. A sequência usa 3 motivos, e cada um precisa ser um fato confirmado: escreva '
                       f'pelo menos 3 no campo Detalhes, separados por vírgula (ex.: cintura alta, lavagem clara, '
                       f'bolsos na frente).')
    return espelho, facts


def clip_problems(trio, index, clips, source):
    """A regua de cada clipe, igual para o rascunho e para as falas da IA: honestidade (nada fora do briefing,
    urgencia so com oferta real), so o ultimo clipe pede a compra e a fala ocupa os 15 s sem correr."""
    words = sum(_count_words(part) for part in trio)
    problems = list(honesty_audit(dict(hook=trio[0], development=trio[1], cta=trio[2]), source,
                                  require_caption=False, strict_style=False))
    if index < clips and re.search(r'carrinho|corre pro|garante', ' '.join(trio), re.I):
        problems.append('só o último clipe pode pedir a compra')
    if words < WORD_FLOOR:
        problems.append(f'fala curta ({words} palavras): pode sobrar silêncio no fim do clipe')
    elif words > WORD_CEILING:
        problems.append(f'fala longa ({words} palavras): pode ficar corrida')
    return problems


# ------------------------------------------------------------------------------------------ pacote do agente
# O agente do Grok Imagine (grok.com/imagine/agent) segue instrucoes numa conversa: as REGRAS (formato, identidade,
# cenario, camera, maos, audio) vao uma vez, na mensagem 1 com o clipe 1, e cada clipe seguinte so traz o que muda.
# Experimental: nenhuma pagina da xAI descreve o agente nem o limite dele; os 4000 caracteres sao os do campo de prompt
# do Grok e do uso relatado pelo operador. O prompt completo de cada clipe continua sendo o padrao.
AGENT_LIMIT = generators.GROK.max_prompt_chars
_CONTINUITY_SPAN = re.compile(r'CONTINUIDADE: .*?sem reapresentar a peça\.')
_ACTIONS_SPAN = re.compile(r'AÇÕES \([^)]*\): .*?ENCERRAMENTO \(\d+–15s\): [^\n]*')
_SHOT_LIST_SPAN = re.compile(r'SHOT LIST \d+s[^\n]*\n(?:\d+–\d+s [^\n]*(?:\n|$))+')


def _clip_delta(prompt, previous):
    """O que muda num clipe (continuidade, acoes e shot list com as falas), ancorado no ultimo quadro do clipe anterior.
    None se algum trecho nao for encontrado: nunca se manda um pedaco do clipe sem avisar."""
    parts = [pattern.search(prompt) for pattern in (_CONTINUITY_SPAN, _ACTIONS_SPAN, _SHOT_LIST_SPAN)]
    if not all(parts):
        return None
    text = '\n'.join(part.group(0).strip() for part in parts)
    text = text.replace('da imagem anexada', f'do último quadro do clipe {previous}')
    return None if 'imagem anexada' in text else text


def agent_pack(c, source, espelho, clips):
    """Mensagens para colar no agente do Grok, na ordem: 1 (regras + clipe 1), uma por clipe seguinte e a de unir.
    ``clips`` sao os clipes ja montados (com ``prompt``). Vazio fora do Grok: o Flow nao tem esse agente."""
    if generators.of(c) is not generators.GROK or not clips:
        return None
    total, color = len(clips), source.get('color') or ''
    messages = []

    intro = f'{total} clipes de {SECONDS_PER_CLIP} s da MESMA gravação, um por mensagem. Gere só o CLIPE 1.\n'
    first = intro + _trim(clips[0]['prompt'], AGENT_LIMIT - len(intro))
    messages.append(dict(index=1, kind='clip', optional=False, title='Mensagem 1 · regras e clipe 1',
                         attach=[f'Imagem aprovada da cor {color}' if color else 'Imagem aprovada'], text=first))

    anchor = (f'ÂNCORA: a mesma {source.get("model_name") or "modelo"}, {source.get("product") or "o mesmo produto"}'
              f'{f" na cor {color}" if color else ""}, {"o mesmo espelho" if espelho else "o mesmo cenário"} e a mesma luz.')
    for clip in clips[1:]:
        k = clip['index']
        delta = _clip_delta(clip.get('prompt_image') or clip['prompt'], k - 1)
        if delta is None:
            # Sem separar o clipe com seguranca, vale o prompt completo dele (mais longo, mas inteiro).
            body = f'Agora gere o CLIPE {k} de {total}.\n{clip.get("prompt_image") or clip["prompt"]}'
        else:
            body = (f'Agora gere o CLIPE {k} de {total}, mesmas REGRAS da mensagem 1 (formato, identidade, cenário, '
                    f'câmera, mãos, atributos não confirmados e áudio), tudo igual ao clipe {k - 1}.\n{anchor}\n'
                    f'PRIMEIRO QUADRO: o último quadro do clipe {k - 1} (vídeo anexado), e não a imagem aprovada; '
                    'se não der para usar o vídeo, use a IMAGEM APROVADA.\n'
                    f'{delta}\n'
                    + (f'Neste clipe a orientação do corpo muda e vale no lugar da do clipe {k - 1}: '
                       f'{clip["orientation"]}\n' if clip.get('orientation') else '')
                    + f'Áudio: voz feminina em português do Brasil, a mesma do clipe {k - 1}; fale só as '
                    'falas entre aspas, palavra por palavra.')
        messages.append(dict(index=k, kind='clip', optional=False, title=f'Mensagem {k} · só o clipe {k}',
                             attach=[f'Vídeo do clipe {k - 1} (o que o agente gerou)'], text=body, whole=delta is None))
    messages.append(dict(index=total + 1, kind='join', optional=True, title='Mensagem final · unir (opcional)',
                         attach=[], text=f'Pode unir os {total} clipes em um vídeo só, na ordem, sem cortar nem mudar a '
                                         'duração de nenhum e mantendo o áudio de cada um.'))
    for message in messages:
        message['chars'] = len(message['text'])
        message['problems'] = []
        if message['chars'] > AGENT_LIMIT:
            message['problems'].append(
                f'a mensagem tem {message["chars"]} caracteres e o limite é {AGENT_LIMIT:,}'.replace(',', '.')
                + '. Nenhuma fala nem gesto foi cortado: use o prompt completo do clipe.')
        if message.pop('whole', False):
            message['problems'].append('não consegui separar este clipe das regras; mandei o prompt completo dele.')
    return dict(limit=AGENT_LIMIT, messages=messages,
                notes=['Experimental: o agente do Grok (grok.com/imagine/agent) não tem página oficial de documentação; '
                       'o limite de 4.000 caracteres é o do campo de prompt do Grok.',
                       'Uma cor por conversa. Anexe a imagem aprovada na mensagem 1 e, nas seguintes, o vídeo do clipe '
                       'anterior. Se um clipe reiniciar (saudação, peça reapresentada, rosto ou cenário errado), '
                       'repita só a ÂNCORA, não o prompt inteiro.'])


def _assemble(c, color, arc, clips, facts, clip_lines, drafted, base_image, espelho, w, turns=None, texture=False):
    """Prompts de cada clipe, montagem no CapCut e o texto para copiar."""
    # De frente, a sequencia traz falas proprias: o formato da campanha (teste, comentario...) nao entra nos
    # clipes, so a base de camera de frente.
    source = {**c, 'color': color, 'video_mode': 'espelho' if espelho else ''}
    roles = _ROLES[(arc, clips)]
    screens = _SCREEN[arc] if clips == 3 else (_SCREEN[arc][0], _SCREEN[arc][2])
    result, opening = [], None
    textured = []
    for i, (trio, role, screen) in enumerate(zip(clip_lines, roles, screens), 1):
        turn = turns[i - 1] if turns else ''
        clip_source, extra = source, ''
        if turn or texture:
            # Giro e/ou close de textura deste clipe: os gestos dos fatos sao refeitos com o giro do clipe (a parada
            # de costas usa os gestos de frente e prova o que ja mostra nela). Sem opt-in nada disso roda.
            own = {'frente': '', 'costas_pausa': ''}.get(turn, turn) if turn else None
            fact_c = c if own is None else {**c, 'body_turns': own}
            if turn:
                clip_source = {**source, 'body_turns': '' if turn == 'frente' else turn}
            facts_here = _clip_facts(arc, clips, i - 1, arc_facts(fact_c, texture=texture))
            facts_here, extra = _turn_plan(turn, facts_here, clip_source, espelho)
            textured += [f['text'] for f in facts_here if f.get('texture') and f['text'] not in textured]
        else:
            facts_here = _clip_facts(arc, clips, i - 1, facts)
        full, opening, acoes = _full_prompt(clip_source, i, clips, trio, facts_here, base_image, opening, w, extra)
        words = sum(_count_words(part) for part in trio)
        problems = clip_problems(trio, i, clips, source)
        image_prompt, lean_ok = '', True
        if i > 1 and generators.of(c) is generators.GROK:
            # O Grok pediu que o clipe 2 em diante parta do ultimo quadro do clipe anterior: prompt enxuto. O completo
            # (a partir da imagem aprovada, o que foi validado) continua em ``prompt_image``.
            lean = _lean_prompt(full, i, clips, w, espelho)
            if lean is None:
                lean_ok = False
                problems.append('não consegui montar a versão enxuta deste clipe; use o prompt completo, que parte '
                                'da imagem aprovada')
            else:
                image_prompt, full = full, lean
        if generators.of(c) is generators.GROK and len(full) > GROK_LIMIT:  # o Flow nao tem limite de prompt
            problems.append(f'o prompt tem {len(full)} caracteres e o Grok corta em '
                            f'{generators.GROK.max_prompt_chars:,}'.replace(',', '.'))
        clip = dict(
            index=i, role=role, final=i == clips, seconds=SECONDS_PER_CLIP, lines=list(trio), words=words,
            spoken=' '.join(trio), screen_text=screen, problems=problems,
            prompt=full, prompt_image=image_prompt, guide=_guide(clip_source, i, clips, trio, acoes, w),
            extend=_extend(i, clips, trio, acoes, w) if i > 1 else '',
            start='imagem aprovada' if i == 1 else (f'último quadro do clipe {i - 1}' if image_prompt
                                                    else 'a mesma imagem aprovada do clipe 1'))
        if turns:
            clip['turn'] = turn
            clip['turn_label'] = CLIP_TURNS[turn]['label']
            # No agente o clipe seguinte so leva as acoes e diz "mesmas regras do clipe anterior": quando a
            # orientacao muda, a mensagem dele traz a nova, dizendo que vale no lugar da anterior.
            if i > 1 and turn != turns[i - 2]:
                found = re.search(r'ORIENTAÇÃO CORPORAL[^\n]*', full)
                clip['orientation'] = found.group(0).strip() if found else ''
        result.append(clip)
    from_last_frame = any(clip['prompt_image'] for clip in result)
    capcut = [
        'Todos os clipes na mesma resolução e fps antes de soltar na timeline.',
        'Apare 2 a 4 quadros do início e do fim de cada clipe (é onde o Grok deforma) e a última palavra do clipe.',
        ('Corte seco entre os clipes, sem transição chamativa: o clipe seguinte abre no último quadro do anterior, '
         'então o corte é quase invisível.') if from_last_frame else
        ('Corte seco entre os clipes, sem transição chamativa: os clipes partem da mesma imagem, então a pose '
         'reinicia no corte e a continuidade vem da fala.'),
        'Normalize o volume da voz (Áudio > Normalizar volume) e use o mesmo ajuste de cor nos clipes.',
        'Legendas automáticas (Português) uma vez, sobre a timeline já unida; revise palavra por palavra.',
        'O texto na tela de cada clipe é para colar no CapCut (não vai dentro do vídeo gerado). Carrinho ou seta '
        'só no trecho do CTA, no último clipe.',
        'Exporte em 1080×1920, 30 fps ou mais, H.264.',
    ]
    tips = [
        ('O clipe 1 parte da imagem aprovada desta cor. O clipe 2 em diante parte do ÚLTIMO QUADRO do clipe anterior '
         '(na etapa Criar vídeo, anexe o clipe e use "Baixar último quadro"), com o prompt enxuto. Se a peça ou o rosto '
         'derivarem, use o botão do prompt completo, que parte da imagem aprovada. Gere na mesma qualidade (480p ou 720p).')
        if from_last_frame else
        ('Todos os clipes usam a MESMA imagem aprovada desta cor como primeiro quadro: anexe a mesma imagem em cada '
         'clipe e cole o prompt do clipe. Gere na mesma qualidade (480p ou 720p) em todos.'),
        'Gere 2 ou 3 vezes cada clipe e traga o melhor. Se um clipe ficar corrido ou lento, edite as falas e '
        'gere o prompt de novo.',
        'Se preferir uma emenda invisível, use o prompt de Extend Video do clipe 2 no vídeo do clipe 1.',
    ]
    notes = ['As falas são um rascunho: leia, ajuste ao seu jeito de falar e confira se cada motivo é verdade.']
    if not espelho:
        notes.append('Com a modelo de frente, esta sequência ainda não foi testada no Grok (a validada é a do '
                     'espelho): gere o clipe 1 primeiro e confira antes de seguir. O formato da campanha (teste, '
                     'comentário...) não entra nos clipes: a sequência traz falas próprias.')
    if arc == 'questionada':
        notes.append('A dúvida é uma pergunta retórica: não cita pessoa nem comentário real. Se houver um '
                     'comentário de verdade, vale trocar pela pergunta dele.')
    if arc == 'problema':
        notes.append('O problema é uma situação comum (montar o look), não um defeito de outra peça nem uma promessa '
                     'de resultado: a peça "ajuda" só nos 3 fatos confirmados.')
    if arc == 'mito':
        notes.append('"Dizem que é tudo igual" é recurso retórico: não cita pessoa nem comentário real, e cada '
                     'verdade é um fato confirmado da peça.')
    if turns:
        notes.append('Experimental: o giro do corpo por clipe nunca foi testado no Grok (nem no espelho). Gere '
                     'primeiro o clipe com giro e confira peça, costas, rosto e mãos antes de seguir.')
    if texture:
        notes.append(('Close de textura (experimental) em: ' + ', '.join(textured) + '. Confira se o brilho e o grão '
                      'saíram iguais aos da imagem aprovada.') if textured else
                     'Close de textura: nenhum motivo desta sequência é material ou detalhe com close (courino, '
                     'cetim, malha, botões...), então os prompts não mudaram.')
    total_seconds = sum(clip['seconds'] for clip in result)
    text = '\n\n'.join(
        [f'SEQUÊNCIA STORYTELLING · {ARCS[arc]["label"]} · {clips} clipes · cerca de {total_seconds}s']
        + [f'CLIPE {clip["index"]}/{clips} · {clip["role"]}\nFalas:\n' + '\n'.join(clip['lines'])
           + f'\nTexto na tela (CapCut): {clip["screen_text"]}\n\nPROMPT COMPLETO\n{clip["prompt"]}'
           for clip in result]
        + ['MONTAGEM NO CAPCUT\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(capcut, 1))])
    return dict(arc=arc, label=ARCS[arc]['label'], clips_count=clips, color=color, drafted=drafted,
                total_seconds=total_seconds, facts=[f['text'] for f in facts[:3]], clips=result, tips=tips,
                capcut=capcut, notes=notes, notices=generators.flow_notices(c, 'Esta sequência', SECONDS_PER_CLIP),
                agent=agent_pack(c, source, espelho, result), text=text)
