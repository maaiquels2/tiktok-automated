"""Sequencia STORYTELLING de 2 ou 3 clipes para o CapCut: arcos "Motivos" e "Questionada".

Diferente de services/story_sequence.py (que reparte as MESMAS 3 falas do roteiro de 15 s em partes curtas
para o Extend Video), aqui cada clipe traz fala NOVA e conteudo novo, e os clipes se encaixam num video so
de cerca de 30 s (2 clipes) ou 45 s (3 clipes).

  Motivos      "Tres motivos pra essa peca estar no teu guarda-roupa": um fato confirmado por motivo
  Questionada  "Sabe o que dizem por ai? Que ela nao te valoriza" e a resposta, motivo a motivo

Validado no Grok com a calca jeans no espelho (480p): identidade, roupa e cenario iguais entre os clipes.
O que o teste real ensinou e esta aqui:
  - o clipe 2 (e o 3) parte da MESMA imagem aprovada do clipe 1; o prompt diz isso em vez de pedir para
    "retomar o ultimo quadro", que o Grok nao recebe;
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

from services import speech_bank
from services.copywriter import audit as honesty_audit
from services.prompt_improve import build_compact_video_prompt
from services.prompts import (
    _PRODUCT_FEATURES, _SPOKEN_OCCASION, _body_turns, _count_words, _cta_pool, _pick_in_budget, _piece_forms,
    _product_family, _product_features, _proof_gestures, _video_details, _video_mode, generate,
)

ARCS = {
    'motivos': dict(label='Motivos', hint='"Três motivos pra essa peça estar no seu guarda-roupa", um fato por motivo'),
    'questionada': dict(label='Questionada',
                        hint='"Sabe o que dizem por aí? Que ela não te valoriza", e a resposta, motivo a motivo'),
}
CLIP_COUNTS = (2, 3)
MIN_FACTS = 3            # os dois arcos usam 3 motivos
MAX_FACTS = 4
WORD_FLOOR, WORD_CEILING = 46, 57   # abaixo sobra silencio no fim; acima a fala fica corrida
GROK_LIMIT = 3940        # o Grok corta em 4000 caracteres sem avisar; margem para o nome e a cor
SECONDS_PER_CLIP = 15

CONTINUITY = ('CONTINUIDADE: clipe {n} de {total} da MESMA gravação: mesma modelo, mesmo espelho, mesma roupa e '
              'mesma luz; o clipe abre na pose da imagem anexada, já falando, sem saudação e sem reapresentar a '
              'peça. ')
LAST_WORD = 'a última palavra é dita por inteiro antes do fim do clipe'
OPEN_END = ('termina de frente para o espelho, com a mão livre pousada na peça, no meio do gesto, sem apontar e '
            'sem pose de fechamento; a fala segue até o último segundo')
FINAL_END = ('no final, de frente para o espelho, a mão livre aponta uma vez para baixo com o indicador, sorrindo')
GENERIC_MOVE = 'gesticula como quem conversa com uma amiga, passando a mão pela peça enquanto fala dos looks'


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
    for label, needles in _PRODUCT_FEATURES:
        if any(re.search(rf'\b{re.escape(_norm(n))}\b', low) for n in needles):
            return label
    return ''


def arc_facts(c, limit=MAX_FACTS):
    """Os motivos: o que o briefing confirma, na ordem em que o operador escreveu (campo Detalhes), mais os
    atributos reconhecidos nos outros campos. Cada fato leva o gesto que o demonstra no espelho."""
    turns = _body_turns(c)
    facts, seen_text, seen_label = [], set(), set()

    def add(text, label):
        key = _norm(text)
        if not key or key in seen_text or (label and label in seen_label):
            return
        gesture = ''
        if label:
            plan = _proof_gestures([label], turns=turns)
            gesture = plan[0].split(' → ', 1)[1] if plan else ''
        facts.append(dict(
            text=text, label=label,
            gesture=gesture or f'mostra com a mão livre, bem à vista, o detalhe "{text}" e volta a mão para a peça'))
        seen_text.add(key)
        if label:
            seen_label.add(label)

    details = _video_details(c.get('details') or '')
    for chunk in re.split(r'\s*[,;]\s*|(?<=[.!?])\s+|\n+', details):
        chunk = chunk.strip(' .;')
        if not chunk or len(chunk.split()) > 5:
            continue
        if re.match(r'^(mostr|demonstr|aproxim|gir|ajust|fa[çc]a|use)\w*\b', _norm(chunk)):
            continue   # direcao de cena, nao fato
        add(chunk, _feature_label(chunk))
    for label in _product_features(c, limit=50):
        add(label, label)
    return facts[:limit]


# ------------------------------------------------------------------------------------------------ falas
def _join_pt(items):
    items = [i for i in items if i]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' e ' + items[-1]


def _style(c):
    forms = _piece_forms(c)
    cat = speech_bank.category(speech_bank.detect(c))
    occasions = list(cat['occasions']) if cat else []
    if not occasions:
        fallback = _SPOKEN_OCCASION.get((c.get('niche') or '').strip(), '') or 'no dia a dia'
        occasions = [fallback]
    # "com tenis ou salto" nao cabe depois de "eu ja me imagino com ela ..."
    occasions = [o for o in occasions if not o.casefold().startswith('com ')][:3] or ['no dia a dia']
    combos = speech_bank._COMBOS.get(cat['id']) if cat else None
    return forms, occasions, combos


def _cta(c, forms):
    return _pick_in_budget(_cta_pool(c, forms), 0, 6, 10, fuzzy=False)


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
    # questionada
    pergunta = f'Sabe o que dizem por aí de {piece}? Que {pron} não te valoriza.'
    promessa = (f'Pode ser que você pense assim também. Mas eu vou te mostrar três motivos pra {dem} {piece} '
                f'merecer um lugar no teu guarda-roupa, um por um, olha comigo.')
    if clips == 2:
        return [
            (pergunta, promessa,
             f'Começando pelo primeiro motivo: {l1}. Os outros eu já mostro.'),
            (f'O segundo motivo? {f2}. Repara nesse detalhe de pertinho.',
             f'O terceiro motivo? {f3}. Então a pergunta nunca foi se {piece} valoriza ou não, foi qual {piece}. '
             f'{imagino}',
             cta),
        ]
    return [
        (pergunta, promessa,
         f'Começando pelo primeiro motivo: {l1}. Presta atenção aqui no que eu vou te mostrar.'),
        (f'O primeiro: {f1}. Olha só como aparece aqui, de pertinho.',
         f'O segundo motivo? {f2}. E o terceiro? {f3}. Repara em cada detalhe de pertinho, um de cada vez.',
         'Agora me responde com sinceridade: ainda sobrou algum motivo pra duvidar?'),
        (f'Pois é. No fundo, a pergunta nunca foi se {piece} valoriza ou não.',
         f'Foi qual {piece}. {imagino} {_cap(l1)}, {l2}, {l3}: se faltava motivo, é esse.',
         cta),
    ]


def _clip_facts(arc, clips, index, facts):
    """Quais fatos a modelo demonstra (com gesto) em cada clipe."""
    f = facts[:3]
    if arc == 'motivos':
        layout = {2: [f[:2], f[2:3]], 3: [f[:1], f[1:3], []]}
    else:
        layout = {2: [f[:1], f[1:3]], 3: [f[:1], f[:3], []]}
    return layout[clips][index]


_ROLES = {
    ('motivos', 2): ('Gancho + motivos 1 e 2', 'Motivo 3 + projeção de uso + fechamento (CTA)'),
    ('motivos', 3): ('Gancho + motivo 1', 'Motivos 2 e 3', 'Projeção de uso + fechamento (CTA)'),
    ('questionada', 2): ('A pergunta + o primeiro motivo', 'Os outros dois motivos + a resposta + fechamento (CTA)'),
    ('questionada', 3): ('A pergunta', 'A resposta: desmonta cada motivo', 'A resposta final + fechamento (CTA)'),
}
_SCREEN = {
    'motivos': ('3 motivos pra ter essa peça', 'O 2º e o 3º motivo', 'Qual é o seu motivo?'),
    'questionada': ('Não te valoriza?', 'Desmontando cada motivo', 'A pergunta é qual peça'),
}


# ------------------------------------------------------------------------------------------------ prompts
def _sub1(pattern, new, text, flags=0):
    """Troca exatamente uma ocorrencia. Se o gerador de prompts mudar e o padrao sumir, falha em voz alta
    (os testes pegam) em vez de entregar um prompt sem a trava."""
    result, count = re.subn(pattern, new if callable(new) else (lambda _m: new), text, count=1, flags=flags)
    if count != 1:
        raise ArcError(f'O gerador de prompts mudou e a sequência não encontrou: {pattern[:50]}', 500)
    return result


def _opening_of(text):
    """O que o app manda ela fazer no gancho (ex.: 'dá um passo até o espelho com sorriso confiante...')."""
    m = re.search(r'0–\d+s HOOK: [^;]*; a modelo (.*?)\. Fala \(PT-BR\):', text)
    return m.group(1) if m else 'dá um passo até o espelho com sorriso confiante'


def _moves(clip_facts):
    if not clip_facts:
        return GENERIC_MOVE
    return ' e, em seguida, '.join(f['gesture'] for f in clip_facts)


def _full_prompt(source, n, total, lines, clip_facts, base_image, opening=None):
    final = n == total
    pack = generate(source, script=dict(hook=lines[0], development=lines[1], cta=lines[2]), base_image=base_image)
    text = pack['video']
    opening = opening or _opening_of(text)
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
    # a PROVA VISUAL fixa do app e trocada pela coreografia do clipe (os gestos dos fatos)
    text = _sub1(r'PROVA VISUAL — [^\n]*\n', '', text)
    start = re.search(r'ENCERRAMENTO \((\d+)–15s\)', text).group(1)
    if final:
        text = _sub1(r'AÇÕES \(escolha 2 a 3[^)]*\): .*?ENCERRAMENTO \(\d+–15s\):',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {acoes}. ENCERRAMENTO ({start}–15s):',
                     text, re.S)
    else:
        text = _sub1(r'AÇÕES \(escolha 2 a 3[^)]*\): .*? EXPRESSÃO:',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {acoes}. ENCERRAMENTO ({start}–15s): '
                     f'{OPEN_END}. EXPRESSÃO:', text, re.S)
        text = _sub1(r'EXPRESSÃO: encanto → orgulho → convite sorridente\.',
                     'EXPRESSÃO: encanto → curiosidade (sem convite de compra).', text)
        text = _sub1(r'(\d+)–15s CTA: [^\n]*?Fala \(PT-BR\):',
                     lambda m: f'{m.group(1)}–15s FIM DO TRECHO (a venda NÃO fecha aqui): sem apontar para baixo e '
                               'sem pose de fechamento; segue o gesto e a fala'
                               + (f'; {LAST_WORD}' if n > 1 else '') + '. Fala (PT-BR):', text)
    if n > 1:
        text = _sub1(r'0–(\d+)s HOOK: [^\n]*?Fala \(PT-BR\):',
                     lambda m: f'0–{m.group(1)}s CONTINUAÇÃO (não é um hook novo: não recomeçar, não reapresentar '
                               'a peça): olhar na tela do celular, já falando, na pose da imagem anexada, sem '
                               'recomeçar. Fala (PT-BR):', text)
        text = _sub1(r'(ANEXE a IMAGEM APROVADA da cor [^.]*\.)',
                     lambda m: m.group(1) + ' ' + CONTINUITY.format(n=n, total=total), text)
    # O Grok corta em 4000 caracteres sem avisar: cortes de baixa prioridade, um de cada vez, so se passar.
    for pattern in (r' Notas adicionais do operador \(não são falas\): [^.]*\. ',
                    r' Estilo visual: natural e realista\.',
                    r' Ângulo de venda \(contexto, não criar atributos\): [^.]*\.',
                    r' Com material confirmado, preservar textura e brilho\.',
                    r' Sem promessas não demonstradas no vídeo\.',
                    r'(?<=\. )Outras peças citadas na fala não entram no vídeo\. ',
                    r' Visual: [^.]*\.'):  # repete o "Produto em cena" logo antes
        if len(text) <= GROK_LIMIT:
            break
        text = re.sub(pattern, ' ', text, count=1)
    if len(text) > GROK_LIMIT:
        text = re.sub(r' {2,}', ' ', text)  # cada corte deixa um espaco; so aqui, para nao mexer nos que ja cabem
    return text, opening, acoes


def _guide(source, n, total, lines, acoes):
    final = n == total
    pack = dict(hook=lines[0], development=lines[1], cta=lines[2])
    text = build_compact_video_prompt(source, pack, source.get('color') or '')
    fim = FINAL_END if final else OPEN_END + (f'; {LAST_WORD}' if n > 1 else '')
    text = _sub1(r'(?m)^Ação contínua, sem pausas:.*$',
                 f'Ação contínua, sem pausas: ela {acoes}; {fim}. Cada gesto começa enquanto o anterior termina: '
                 'nada de parar, posar ou recomeçar entre uma ação e outra.', text)
    if not final:
        text = _sub1(r'(?m)^Expressão: .*$', 'Expressão: encanto → curiosidade (sem convite de compra).', text)
    if n > 1:
        text = _sub1(r'(?m)^A imagem anexada é o primeiro quadro: ',
                     CONTINUITY.format(n=n, total=total) + 'A imagem anexada é o primeiro quadro: ', text)
    return text


def _extend(n, total, lines, acoes):
    final = n == total
    fim = FINAL_END if final else OPEN_END
    return (
        'Continuação do mesmo take, já em movimento: mesma pessoa, mesma roupa, mesmo espelho e mesma luz; segue o '
        'último quadro sem pausa, o celular sempre na mão dela, na altura do peito, sem cobrir o rosto.\n'
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


def build_story_arc(c, color, arc, clips, lines=None, base_image=False):
    """Monta a sequencia: falas (rascunho ou editadas), prompt completo, Guia do Grok e Extend Video por clipe,
    mais o passo a passo do CapCut. `c` e a campanha (como detail()); `color` a cor da variacao."""
    if arc not in ARCS:
        raise ArcError('Escolha o arco Motivos ou Questionada.', 400)
    if clips not in CLIP_COUNTS:
        raise ArcError('Escolha 2 ou 3 clipes.', 400)
    if _video_mode(c) != 'espelho':
        raise ArcError('A sequência storytelling está validada para o formato "Celular no espelho". Troque o '
                       'formato do vídeo e tente de novo.')
    if _product_family(c) not in ('moda', 'infantil'):
        raise ArcError('A sequência storytelling está disponível para roupas. Para creme, brinco e colar use o '
                       'formato "Na mesa, de perto".')
    facts = arc_facts(c)
    if len(facts) < MIN_FACTS:
        achados = f'Só encontrei {len(facts)}' + (f' ({", ".join(f["text"] for f in facts)})' if facts else '')
        raise ArcError(f'{achados}. A sequência usa 3 motivos, e cada um precisa ser um fato confirmado: escreva '
                       f'pelo menos 3 no campo Detalhes, separados por vírgula (ex.: cintura alta, lavagem clara, '
                       f'bolsos na frente).')
    drafted = lines is None
    clip_lines = ([_pad(trio) for trio in draft_lines(c, arc, clips, facts)] if drafted
                  else _normalize_lines(lines, clips))
    source = {**c, 'color': color, 'video_mode': 'espelho'}
    roles = _ROLES[(arc, clips)]
    screens = _SCREEN[arc] if clips == 3 else (_SCREEN[arc][0], _SCREEN[arc][2])
    result, opening = [], None
    for i, (trio, role, screen) in enumerate(zip(clip_lines, roles, screens), 1):
        facts_here = _clip_facts(arc, clips, i - 1, facts)
        full, opening, acoes = _full_prompt(source, i, clips, trio, facts_here, base_image, opening)
        words = sum(_count_words(part) for part in trio)
        problems = list(honesty_audit(dict(hook=trio[0], development=trio[1], cta=trio[2]), source,
                                      require_caption=False, strict_style=False))
        if i < clips and re.search(r'carrinho|corre pro|garante', ' '.join(trio), re.I):
            problems.append('só o último clipe pode pedir a compra')
        if words < WORD_FLOOR:
            problems.append(f'fala curta ({words} palavras): pode sobrar silêncio no fim do clipe')
        elif words > WORD_CEILING:
            problems.append(f'fala longa ({words} palavras): pode ficar corrida')
        if len(full) > GROK_LIMIT:
            problems.append(f'o prompt tem {len(full)} caracteres e o Grok corta em 4.000')
        result.append(dict(
            index=i, role=role, final=i == clips, seconds=SECONDS_PER_CLIP, lines=list(trio), words=words,
            spoken=' '.join(trio), screen_text=screen, problems=problems,
            prompt=full, guide=_guide(source, i, clips, trio, acoes),
            extend=_extend(i, clips, trio, acoes) if i > 1 else '',
            start='imagem aprovada' if i == 1 else 'a mesma imagem aprovada do clipe 1'))
    capcut = [
        'Todos os clipes na mesma resolução e fps antes de soltar na timeline.',
        'Apare 2 a 4 quadros do início e do fim de cada clipe (é onde o Grok deforma) e a última palavra do clipe.',
        'Corte seco entre os clipes, sem transição chamativa: os clipes partem da mesma imagem, então a pose '
        'reinicia no corte e a continuidade vem da fala.',
        'Normalize o volume da voz (Áudio > Normalizar volume) e use o mesmo ajuste de cor nos clipes.',
        'Legendas automáticas (Português) uma vez, sobre a timeline já unida; revise palavra por palavra.',
        'O texto na tela de cada clipe é para colar no CapCut (não vai dentro do vídeo gerado). Carrinho ou seta '
        'só no trecho do CTA, no último clipe.',
        'Exporte em 1080×1920, 30 fps ou mais, H.264.',
    ]
    tips = [
        'Todos os clipes usam a MESMA imagem aprovada desta cor como primeiro quadro: anexe a mesma imagem em cada '
        'clipe e cole o prompt do clipe. Gere na mesma qualidade (480p ou 720p) em todos.',
        'Gere 2 ou 3 vezes cada clipe e traga o melhor. Se um clipe ficar corrido ou lento, edite as falas e '
        'gere o prompt de novo.',
        'Se preferir uma emenda invisível, use o prompt de Extend Video do clipe 2 no vídeo do clipe 1.',
    ]
    notes = ['As falas são um rascunho: leia, ajuste ao seu jeito de falar e confira se cada motivo é verdade.']
    if arc == 'questionada':
        notes.append('"Sabe o que dizem por aí..." é recurso retórico: não cita pessoa nem comentário real. Se '
                     'houver um comentário de verdade, vale trocar pela pergunta dele.')
    total_seconds = sum(clip['seconds'] for clip in result)
    text = '\n\n'.join(
        [f'SEQUÊNCIA STORYTELLING · {ARCS[arc]["label"]} · {clips} clipes · cerca de {total_seconds}s']
        + [f'CLIPE {clip["index"]}/{clips} · {clip["role"]}\nFalas:\n' + '\n'.join(clip['lines'])
           + f'\nTexto na tela (CapCut): {clip["screen_text"]}\n\nPROMPT COMPLETO\n{clip["prompt"]}'
           for clip in result]
        + ['MONTAGEM NO CAPCUT\n' + '\n'.join(f'{i}. {step}' for i, step in enumerate(capcut, 1))])
    return dict(arc=arc, label=ARCS[arc]['label'], clips_count=clips, color=color, drafted=drafted,
                total_seconds=total_seconds, facts=[f['text'] for f in facts[:3]], clips=result, tips=tips,
                capcut=capcut, notes=notes, text=text)
