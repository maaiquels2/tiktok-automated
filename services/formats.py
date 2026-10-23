"""Formatos de video e tecnicas de retencao.

Formato e a estrutura do video (responder comentario, teste de prova, troca de
cor...). Cada um roda sobre uma das bases que ja existem -- modelo falando,
POV ou so movimento -- e muda so o que precisa: a abertura, as acoes do meio,
o encerramento e o gancho do roteiro. Tecnica e um recurso de retencao que
vale para qualquer formato (comecar em movimento, loop...).

Os textos entram DENTRO das frases que o prompt ja tem, em vez de virar bloco
novo: o prompt do Grok esta a ~70 caracteres do limite, e bloco extra
empurraria para fora as acoes do meio.

A regra de honestidade do projeto vale aqui tambem: nenhum formato afirma
resultado, compra ou historia que o briefing nao sustenta. O teste mostra o
movimento, nao diz que "passou"; o "abrindo o pacote" nao diz que comprou.
"""
import re

from services.piece import product_family

FORMATS = {
    'comentario': {'label': 'Respondendo comentário', 'base': ''},
    'teste': {'label': 'Teste de prova', 'base': ''},
    'troca_cor': {'label': 'Troca de cor', 'base': ''},
    'tres_jeitos': {'label': '3 jeitos de usar', 'base': ''},
    'unboxing': {'label': 'Abrindo o pacote', 'base': 'pov'},
    'asmr': {'label': 'Close ASMR', 'base': 'movimento'},
    'mesa': {'label': 'Na mesa, de perto', 'base': ''},
}

# "Na mesa" e o formato padrao das familias sem corpo a vestir (beleza e
# acessorios): fit check, provador e barra da peca nao fazem sentido num creme
# nem num brinco. Teste de prova e 3 jeitos sao falas de roupa; nessas
# familias viram "Na mesa".
MESA_FAMILIES = ('beleza', 'acessorio')
APPAREL_ONLY = ('teste', 'tres_jeitos')

TECHNIQUES = ('acao', 'aproxima', 'revela', 'loop', 'estica')
# Mais de duas tecnicas no mesmo video de 15 s viram lista de tarefas para o
# Grok (e estouram o limite de caracteres).
MAX_TECHNIQUES = 2
STYLE_TOKENS = ('closes', 'ousado') + TECHNIQUES


def _sem_corpo(c):
    return product_family(c) in MESA_FAMILIES


VIDEO_MODE_ALIASES = {
    'pov': 'pov', 'pov_produto': 'pov', 'pov-produto': 'pov', 'pov produto': 'pov',
    'produto': 'pov',
    'movimento': 'movimento', 'movimentos': 'movimento', 'so_movimento': 'movimento',
    'so-movimento': 'movimento', 'só movimento': 'movimento', 'so movimento': 'movimento',
    'fit': 'movimento', 'fit_check': 'movimento', 'fit check': 'movimento',
    'espelho': 'espelho', 'celular': 'espelho', 'selfie': 'espelho', 'selfie_espelho': 'espelho',
    'celular no espelho': 'espelho',
    # Formatos que rodam sobre outra base (unboxing, asmr) vem de FORMATS.
    **{k: v['base'] for k, v in FORMATS.items() if v['base']},
}


def video_mode(c):
    """Base do video escolhida pelo operador (pov, movimento, espelho), ou ''."""
    value = ' '.join(str(c.get('video_mode') or '').strip().rstrip('.').split()).casefold()
    return VIDEO_MODE_ALIASES.get(value, '')


# Formatos com a modelo de frente falando para a lente: onde cabe a sequencia storytelling.
SPEAKING_FRONT = ('', 'comentario', 'teste', 'troca_cor', 'tres_jeitos')
ARC_FORMATS = ('espelho',) + SPEAKING_FRONT
# Formatos que usam outra imagem-base (primeira pessoa ou selfie no espelho):
# trocar para eles ou sair deles passa por Definir look.
NEW_BASE_FORMATS = ('pov', 'espelho') + tuple(k for k, v in FORMATS.items() if v['base'] in ('pov', 'espelho'))


def rules():
    """O que a tela precisa (frontend/src/formatRules.json; um teste confere)."""
    return dict(max_techniques=MAX_TECHNIQUES, arc_formats=list(ARC_FORMATS),
                new_base_formats=list(NEW_BASE_FORMATS))


def video_format(c):
    value = str(c.get('video_mode') or '').strip().casefold()
    if value in FORMATS:
        return 'mesa' if value in APPAREL_ONLY and _sem_corpo(c) else value
    # Sem escolha do operador, beleza e acessorios vao para a mesa. Base
    # explicita (espelho, pov, movimento) continua valendo como antes.
    return 'mesa' if not value and _sem_corpo(c) else ''


def techniques(c):
    raw = {p.strip() for p in str(c.get('video_style') or '').split(',') if p.strip()}
    return [t for t in TECHNIQUES if t in raw]


def _text(c):
    return ' '.join(str(c.get(k) or '') for k in ('product', 'outfit')).casefold()


# (palavras da peca, nome do teste, o que ela faz)
_TESTS = (
    (('legging', 'short', 'bermuda', 'top', 'conjunto fitness', 'macaquinho'),
     'do agachamento', 'agacha fundo e levanta devagar, com a peça à mostra o tempo todo'),
    (('biquíni', 'biquini', 'maiô', 'maio'),
     'do pulo', 'dá dois pulinhos e levanta os braços, mexendo o corpo'),
    (('vestido', 'saia', 'macacão', 'macacao', 'kimono'),
     'da passada', 'caminha com passos largos e dá uma voltinha, deixando a peça se mexer'),
    (('calça', 'calca', 'jeans', 'courino'),
     'do agachamento', 'agacha e levanta a perna como quem sobe um degrau alto'),
    (('blusa', 'regata', 'camisa', 'body', 'cropped', 'colete', 'jaqueta', 'blazer'),
     'dos braços', 'levanta os braços e gira o tronco para os dois lados'),
)


def test_move(c):
    text = _text(c)
    for words, name, action in _TESTS:
        if any(w in text for w in words):
            return name, action
    return 'do movimento', 'levanta os braços, agacha e gira o tronco'


# Complementos dos 3 jeitos: pecas comuns que nao sao vendidas junto.
_LOOKS = {
    'praia': ('com a saída de praia amarrada na cintura', 'com short jeans e camisa aberta por cima'),
    'academia': ('com uma jaqueta de moletom aberta por cima', 'com uma camiseta larga amarrada na cintura'),
    'intima': ('com um robe leve aberto por cima', 'com um cardigã fino por cima'),
    # Fantasia costuma ja vir com capa ou chapeu: o complemento vai na mao.
    'fantasia': ('com um acessório na cabeça', 'com uma cestinha na mão'),
}
_DEFAULT_LOOKS = ('com uma jaqueta jeans por cima', 'com uma camisa aberta e um cinto')


def looks(c):
    return _LOOKS.get(str(c.get('niche') or '').strip().casefold(), _DEFAULT_LOOKS)


def _clean_pain(pain):
    return re.sub(r'^(tenho\s+)?medo\s+de\s+', '', (pain or '').strip(), flags=re.I)


# --------------------------------------------------------------- video
def opening(c, abre, mode=''):
    """Abertura do video com fala ou so movimento (mode '', 'espelho' ou
    'movimento'): o formato pode trocar a acao do gancho e as tecnicas entram
    antes dela."""
    fmt, tec = video_format(c), techniques(c)
    espelho = mode == 'espelho'
    if fmt == 'comentario':
        abre = ('começa lendo uma pergunta na tela do celular (a tela não aparece), ergue os olhos para o reflexo '
                'e responde' if espelho else
                'começa olhando o celular na mão, como quem lê uma pergunta (a tela não aparece), abaixa o celular '
                'e responde para a lente')
    antes = []
    if 'acao' in tec:
        antes.append('começa já em movimento, nunca parada no primeiro quadro')
    if 'revela' in tec:
        # O 1o quadro e a imagem aprovada, ja com a peca: sem mudanca depois da mao, o "revelar" mostrava o mesmo quadro.
        antes.append('tampa ' + ('toda a câmera do celular' if espelho else 'toda a lente')
                     + ' com a palma aberta e, ao tirar, surge mais perto e em outra pose')
    if 'aproxima' in tec:
        antes.append('dá dois passos rápidos até bem perto ' + ('do espelho' if espelho else 'da lente')
                     + ' e para de repente')
    return '; '.join(antes + [abre]) if abre else '; '.join(antes)


def lead_moves(c, mode=''):
    """Acoes que abrem o meio do video: o teste do formato e o esticar."""
    out = []
    if video_format(c) == 'teste':
        name, action = test_move(c)
        out.append(f'o teste {name}: {action}')
    if 'estica' in techniques(c):
        # No espelho uma mao segura o celular: esticar com as duas criaria a
        # terceira mao que o Grok inventou no teste real.
        if mode == 'espelho':
            out.append('com a mão livre, estica o tecido de leve bem perto do espelho, mostrando a textura, e solta')
        else:
            out.append('estica o tecido de leve com as duas mãos bem perto da lente, mostrando a textura, e solta')
    return out


def three_looks(c, piece):
    """Acoes do formato 3 jeitos (substituem as acoes comuns)."""
    if video_format(c) != 'tres_jeitos':
        return ''
    a, b = looks(c)
    return (f'três looks em sequência, sempre com {piece} à mostra: primeiro só como está na imagem; depois {a}; '
            f'por último {b}; a cada novo look citado, a palma aberta vem e tampa toda a lente por meio segundo e, '
            'ao sair, ela já está no look seguinte, no mesmo lugar e luz')


def ending(c, mode=''):
    """Frase final do encerramento: transicao da troca de cor ou loop."""
    fmt, tec = video_format(c), techniques(c)
    if fmt == 'troca_cor':
        alvo = 'da câmera do celular' if mode == 'espelho' else 'da lente'
        return (f'No último segundo, depois da última palavra, ela aproxima a palma aberta {alvo} até tampar o '
                'quadro inteiro, tela toda escura (transição para a próxima cor). ')
    if 'loop' in tec:
        return 'No último quadro, volta à pose e ao enquadramento do primeiro (loop sem emenda). '
    return ''


def allows_cuts(c):
    return video_format(c) == 'tres_jeitos'


def hand_covers(c):
    """Formatos em que a mão tampa a lente: o rosto sai do quadro nesse instante."""
    return video_format(c) in ('troca_cor', 'tres_jeitos') or 'revela' in techniques(c)


def speech_until(c, text):
    """Na troca de cor o último segundo é da mão na lente: "a fala ocupa os 15 s até o fim" disputava esse
    segundo e a transição sumia."""
    if video_format(c) != 'troca_cor':
        return text
    return (text.replace('15 segundos até o fim, sem silêncio no final', '14 segundos; o último é só da mão na lente')
                .replace('15 s até o fim, sem silêncio', '14 s, sem silêncio; o último segundo é só da mão na lente'))


def _lower_first(text):
    return text[:1].lower() + text[1:] if text else text


def pov_opening(c, product):
    """Abertura do POV: tirar da embalagem no "abrindo o pacote" e as
    tecnicas vistas pelas maos."""
    tec = techniques(c)
    product = _lower_first(product)
    if video_format(c) == 'unboxing':
        base = (f'as duas mãos já tiram {product} da caixa aberta e seguram a peça aberta, de frente para a '
                'lente, com curiosidade genuína')
    else:
        base = 'a mão pega ou revela o produto pela primeira vez, com curiosidade genuína'
    antes = []
    if 'acao' in tec:
        antes.append('as mãos já começam em movimento')
    if 'revela' in tec:
        antes.append('a mão cobre a lente e, ao sair, revela o produto')
    if 'aproxima' in tec:
        antes.append('a mão traz o produto rápido até bem perto da lente e afasta')
    return '; '.join(antes + [base])


def pov_lead_moves(c):
    if 'estica' in techniques(c):
        return ['as mãos esticam o tecido de leve bem na frente da lente, mostrando textura e espessura, e soltam']
    return []


def asmr(c):
    return video_format(c) == 'asmr'


ASMR_CAMERA = ('closes bem próximos do tecido, da costura e dos detalhes, alternados com o plano inteiro da peça '
               'no corpo')
ASMR_AUDIO = ('ÁUDIO (é o conteúdo do vídeo): sons nítidos e próximos da peça — o roçar do tecido, a amarração ou '
              'o zíper, os passos; nenhuma voz, nenhuma narração e nenhuma música. ')

UNBOXING_VIEW = ('uma embalagem aberta (saco ou caixa lisa, sem marca nem texto) sobre a superfície, com {piece} '
                 'dentro e uma das mãos puxando a peça para fora')


# --------------------------------------------------------------- na mesa
# Tipo de produto -> palavras. Vale a palavra que aparece PRIMEIRO no nome
# ("pulseira de corrente" e pulseira, nao colar).
_MESA_KINDS = (
    ('pele', ('creme', 'hidratante', 'sérum', 'serum', 'protetor solar', 'protetor facial', 'loção', 'locao',
              'esfoliante', 'skincare', 'máscara facial', 'mascara facial', 'gel facial', 'tônico', 'tonico')),
    ('labios', ('batom', 'gloss', 'tint labial', 'lip tint')),
    ('unhas', ('esmalte',)),
    ('perfume', ('perfume', 'colônia', 'colonia', 'body splash')),
    ('brinco', ('brinco', 'brincos')),
    ('colar', ('colar', 'gargantilha')),
    ('pulso', ('pulseira', 'bracelete', 'anel', 'aliança', 'alianca', 'relógio', 'relogio')),
    ('oculos', ('óculos', 'oculos')),
    ('bolsa', ('bolsa', 'mochila', 'necessaire', 'carteira')),
)

# Cena de cada tipo: o que aparece no primeiro quadro e as tres batidas de 15 s.
# Licoes dos testes reais com o Grok, que valem aqui: exatamente duas maos,
# uma acao por vez, o produto nunca troca de forma nem sai do quadro, e nada
# que exija as duas maos atras do pescoco (fecho) ou prender na orelha.
MESA_SCENES = {
    'pele': dict(
        start='sentada a uma mesa, rosto limpo e voltado para a lente, o pote (ou frasco) aberto à frente, sobre a mesa',
        open='pega um pouco do produto com a ponta de um dedo e mostra a textura em cima do dedo, bem perto da lente',
        middle='passa o produto na bochecha com toques curtos e leves e depois na testa, sempre com uma mão só, '
               'enquanto a outra descansa na mesa',
        close='pega o pote ou frasco com uma mão e o traz até bem perto da lente, de frente, e sustenta por um '
              'instante, sorrindo',
        avoid='mão cobrindo a boca, esfregar com força, produto escorrendo, letras legíveis inventadas no rótulo, '
              'pele mudando de cor ou de textura',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'labios': dict(
        start='sentada a uma mesa, lábios sem batom, o batom fechado numa das mãos',
        open='abre o batom e mostra o bastão bem perto da lente',
        middle='risca a cor no dorso da outra mão e vira a mão devagar para a lente mostrar o tom',
        close='aproxima o batom aberto da lente, ao lado do rosto, e sorri',
        avoid='passar o batom nos lábios, mão cobrindo a boca, bastão mudando de forma ou de cor',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'unhas': dict(
        start='sentada a uma mesa, uma mão apoiada na mesa com as unhas já pintadas, o frasco aberto ao lado',
        open='levanta a mão com as unhas pintadas até perto da lente e a vira devagar para mostrar a cor',
        middle='pega o frasco com a outra mão e o mostra ao lado dos dedos para comparar o tom',
        close='aproxima as unhas da lente e abre os dedos devagar, sorrindo',
        avoid='pintar as unhas durante o vídeo, dedos a mais ou deformados, cor mudando',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'perfume': dict(
        start='sentada a uma mesa, o frasco fechado sobre a mesa à frente',
        open='pega o frasco com as duas mãos e o mostra de frente, bem perto da lente',
        middle='tira a tampa e borrifa uma vez no pulso, longe do rosto, e mostra o frasco ao lado',
        close='aproxima o frasco da lente, ao lado do rosto, e sorri',
        avoid='borrifar perto do rosto, névoa exagerada, letras legíveis inventadas no frasco',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    # Teste real: o numero de brincos mudava ao longo do video (um saia da caixa, outro
    # aparecia na orelha, a caixa esvaziava sozinha). Agora ela ja usa o par e a caixa
    # tem OUTRO par igual: tira um e o outro fica na caixa, sempre a vista.
    'brinco': dict(
        start='sentada a uma mesa, já usando o par de brincos nas orelhas (as duas orelhas à vista, cabelo preso '
              'atrás), uma caixinha aberta à frente com outro par igual dentro',
        open='pega UM brinco da caixinha com a ponta de dois dedos e o traz até bem perto da lente, girando devagar '
             'para o brilho aparecer; o outro continua parado dentro da caixinha, à vista',
        middle='segura esse brinco ao lado do rosto, junto ao que já está na orelha, e vira o rosto de leve para um '
               'lado e para o outro',
        close='estende o brinco de novo para a lente, bem perto, e sustenta por um instante, sorrindo; o outro '
              'continua na caixinha',
        avoid='mais de um brinco na mão, brinco saindo da caixinha sozinho, o número de brincos mudando, prender o '
              'brinco na orelha, brinco mudando de forma ou de tamanho, orelha deformada',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    # Teste real: a modelo da foto ja usava um colar fino, que disputava com o do produto, e a
    # corrente sumia quando o colar balancava perto da lente. Agora o pescoco fica livre e o
    # colar fica esticado em V entre as duas maos, sem balancar, o pingente pendurado no meio.
    'colar': dict(
        start='sentada a uma mesa, sem nenhum outro colar no pescoço (pescoço e colo livres), o colar estendido '
              'sobre a mesa à frente',
        open='pega o colar pelas duas pontas da corrente, uma em cada mão, e o estica em V diante do peito, com o '
             'pingente pendurado no meio, bem visível',
        middle='sustenta o colar esticado em V e o aproxima do pescoço, sem fechar o fecho e sem soltar as pontas',
        close='afasta o colar até perto da lente, ainda esticado em V, e sustenta parado por um instante, sorrindo',
        avoid='balançar ou soltar o colar, corrente sumindo ou engrossando, pingente mudando de forma, outro colar '
              'no pescoço, colar aparecendo no pescoço sem ela o ter colocado, fechar o fecho atrás do pescoço',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'pulso': dict(
        start='sentada a uma mesa, a peça já no pulso ou no dedo, a mão apoiada na mesa',
        open='levanta a mão com a peça até perto da lente e a vira devagar',
        middle='toca a peça com a ponta do dedo da outra mão e gira o pulso para mostrar de todos os lados',
        close='aproxima a mão da lente, com a peça em destaque, e sorri',
        avoid='tirar ou colocar a peça durante o vídeo, dedos a mais ou deformados, peça mudando de forma',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'oculos': dict(
        start='sentada a uma mesa, os óculos fechados sobre a mesa à frente',
        open='pega os óculos pelas hastes e os mostra de frente, bem perto da lente',
        middle='abre as hastes, coloca os óculos no rosto com as duas mãos e solta devagar, olhando para a lente',
        close='inclina o rosto de leve para um lado, mostrando a armação de perfil, e sorri',
        avoid='reflexo nas lentes que esconda os olhos, armação mudando de forma, mão cobrindo o rosto',
        frame='plano médio fechado (cabeça, ombros e a mesa)'),
    'bolsa': dict(
        start='sentada a uma mesa, a bolsa fechada sobre a mesa à frente',
        open='puxa a bolsa para perto da lente, segurando pela alça, e a vira de frente',
        middle='abre o fecho com uma mão, mostra o interior para a lente e fecha de novo',
        close='segura a bolsa pela alça, junto ao corpo, de frente, e sorri',
        avoid='objetos inventados dentro da bolsa, bolsa mudando de forma ou de cor, alça que muda',
        frame='plano médio (da cabeça até a mesa)'),
    'roupa': dict(
        start='sentada a uma mesa, a peça dobrada sobre a mesa à frente',
        open='pega a peça dobrada e a levanta devagar, segurando pelas laterais, de frente para a lente',
        middle='desdobra a peça aos poucos, passa a mão no tecido e traz a costura (ou o detalhe) bem perto da lente',
        close='sustenta a peça aberta, de frente, junto ao corpo, sem vestir, e sorri',
        avoid='vestir a peça, girar ou mostrar o verso, peça mudando de forma ou de cor, a peça saindo do quadro',
        frame='plano médio (da cabeça até a mesa)'),
}

_BELEZA_KINDS = ('pele', 'labios', 'unhas', 'perfume')
_ACESSORIO_KINDS = ('brinco', 'colar', 'pulso', 'oculos', 'bolsa')

# Atributos que cada grupo NAO pode inventar (sai da lista o que o briefing
# confirma). Sao as promessas que mais aparecem em video de creme e de joia.
_MESA_UNCONFIRMED = {
    'beleza': (
        ('hidratação', ('hidrat',)),
        ('resultado na pele', ('resultado', 'viço', 'vico', 'mancha', 'ruga')),
        ('cheiro', ('cheiro', 'perfum', 'aroma', 'fragr')),
        ('proteção solar', ('fps', 'protetor', 'proteção', 'protecao')),
        ('duração e fixação', ('dura', 'horas', 'fixação', 'fixacao')),
    ),
    'acessorio': (
        ('material', ('ouro', 'prata', 'aço', 'aco', 'zircônia', 'zirconia', 'pérola', 'perola', 'couro',
                      'acetato', 'metal', 'cristal')),
        ('banho ou garantia', ('banhad', 'garantia', 'hipoalerg')),
        ('resistência', ('resist', 'água', 'agua', 'não escurece', 'nao escurece')),
        ('medidas', ('mm', 'cm', 'tamanho')),
    ),
}


def mesa_kind(c):
    """Tipo de produto para a cena "Na mesa" ('roupa' quando nada casa)."""
    text = _text(c)
    best = None
    for kind, words in _MESA_KINDS:
        for word in words:
            hit = re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', text)
            if hit and (best is None or hit.start() < best[0]):
                best = (hit.start(), kind)
    return best[1] if best else 'roupa'


def mesa_scene(c):
    return MESA_SCENES[mesa_kind(c)]


def mesa_unconfirmed(c, confirmed_text=''):
    """Frase "ATRIBUTOS NAO CONFIRMADOS" do grupo do produto, sem o que o
    briefing confirma. '' para roupa (ai vale a lista de roupa do prompt)."""
    kind = mesa_kind(c)
    group = 'beleza' if kind in _BELEZA_KINDS else 'acessorio' if kind in _ACESSORIO_KINDS else ''
    if not group:
        return ''
    low = str(confirmed_text or '').casefold()
    banned = [name for name, keys in _MESA_UNCONFIRMED[group] if not any(k in low for k in keys)]
    lista = ', '.join(banned[:-1]) + (' ou ' + banned[-1] if len(banned) > 1 else (banned[0] if banned else ''))
    return ((f'ATRIBUTOS NÃO CONFIRMADOS: não inventar {lista} — ' if banned else 'ATRIBUTOS: ')
            + 'nada fora dos FATOS CONFIRMADOS. ')


def mesa(c):
    return video_format(c) == 'mesa'


# --------------------------------------------------------------- roteiro
def script_hook(c, forms, pain=''):
    """Gancho do formato, ou '' para manter o gancho normal."""
    fmt = video_format(c)
    dem, piece = forms['dem'], forms['piece']
    if fmt == 'comentario':
        dor = _clean_pain(pain)
        if dor:
            return f'Respondendo quem tem medo d{dem} {piece} {dor}.'
        return f'Respondendo quem perguntou como {dem} {piece} fica no corpo.'
    if fmt == 'teste':
        return f'Fiz o teste {test_move(c)[0]} com {dem} {piece}, repara no que acontece.'
    if fmt == 'tres_jeitos':
        return f'Três jeitos de usar {dem} {piece}, do mais simples ao mais arrumado.'
    if fmt == 'unboxing':
        return f'Vamos abrir {dem} {piece} juntas e ver tudo de perto.'
    if fmt == 'mesa' and mesa_kind(c) == 'roupa':
        return f'Vem ver {dem} {piece} de pertinho, que eu separei aqui na mesa.'
    return ''


def script_development(c, forms, details=()):
    """Desenvolvimento do formato, ou '' para manter o normal. `details` sao
    os fatos confirmados ja com artigo ("a cintura alta")."""
    fmt = video_format(c)
    if fmt == 'mesa' and mesa_kind(c) == 'roupa':
        # A peca fica FORA do corpo na mesa: a fala de roupa ("olha como ela
        # veste, bem certinha no corpo") mandava o Grok vestir a peca, a falha
        # do "abrindo o pacote". Aqui o meio narra o que as maos mostram.
        if len(details) >= 2:
            return f'Assim que desdobro, já dá pra ver {details[0]}. Olha só {details[1]} de perto.'
        if details:
            return f'Assim que desdobro, já dá pra ver {details[0]}. Dá pra ver tudo de perto.'
        return 'Assim que desdobro, já dá pra ver a cor e tudo de perto.'
    if fmt == 'unboxing':
        # O desenvolvimento padrao parte da dor ("quem ja passou por isso...")
        # e nao combina com abrir o pacote: aqui ele narra o que aparece.
        if len(details) >= 2:
            return f'Assim que abre, já dá pra ver {details[0]}. Desdobrando, olha só {details[1]} de perto.'
        if details:
            return f'Assim que abre, já dá pra ver {details[0]}. Desdobrando, dá pra ver tudo de perto.'
        return 'Assim que abre, já dá pra ver a cor. Desdobrando, dá pra ver tudo de perto.'
    if fmt != 'tres_jeitos':
        return ''
    a, b = looks(c)
    # Curto de proposito: acima de 50 palavras o roteiro corta a ultima frase
    # e o terceiro look sumia.
    return f'Primeiro, só {forms["art"]} {forms["piece"]}. Depois, {a}. E por último, {b}.'


def screen_text(c, forms, pain=''):
    """Texto na tela (0-3 s) do formato, ou '' para manter o normal."""
    fmt = video_format(c)
    dem, piece = forms['dem'], forms['piece']
    if fmt == 'comentario':
        dor = _clean_pain(pain)
        return f'Medo de {dor}?' if dor else f'Como {dem} {piece} fica no corpo?'
    if fmt == 'teste':
        return f'Fiz o teste {test_move(c)[0]}'
    if fmt == 'troca_cor':
        return 'Qual cor é a sua?'
    if fmt == 'tres_jeitos':
        return f'3 jeitos de usar {dem} {piece}'
    if fmt == 'unboxing':
        return f'Abrindo {dem} {piece}'
    if fmt == 'asmr':
        return 'Aumenta o som'
    return ''


def brief_lines(c, pain=''):
    """Linhas do briefing da IA de escrita para o formato escolhido."""
    fmt = video_format(c)
    if fmt == 'comentario':
        duvida = _clean_pain(pain) or 'como a peça fica no corpo'
        return [f'FORMATO: resposta a comentário. O HOOK começa com "Respondendo quem..." e repete a dúvida '
                f'do cliente ({duvida}); o desenvolvimento responde mostrando no corpo, sem afirmar o que não '
                'está nos fatos confirmados.']
    if fmt == 'teste':
        name, action = test_move(c)
        return [f'FORMATO: teste de prova (o teste {name}: {action}). O HOOK anuncia o teste; o desenvolvimento '
                'narra o que a câmera mostra durante o teste, sem afirmar resultado que não esteja nos fatos '
                'confirmados.']
    if fmt == 'troca_cor':
        return ['FORMATO: troca de cor. Este vídeo é um trecho de uma sequência com as outras cores; o CTA '
                'convida a escolher a cor.']
    if fmt == 'tres_jeitos':
        a, b = looks(c)
        return [f'FORMATO: 3 jeitos de usar — só a peça; {a}; {b}. O desenvolvimento cita os três looks nessa '
                'ordem. Os complementos não são vendidos: não diga que vêm junto.']
    if fmt == 'unboxing':
        return ['FORMATO: abrindo o pacote em primeira pessoa. O vídeo mostra só as mãos com a peça FORA do '
                'corpo: não fale em vestir, no corpo, em caimento, em treino nem em "contra a luz"; fale só do que '
                'as mãos mostram (estampa, tecido, costura, botões, bolsos, elástico, detalhes). Não diga que '
                'comprou, que chegou pelo correio nem há quanto tempo tem a peça.']
    if fmt == 'asmr':
        return ['FORMATO: close ASMR, sem fala no vídeo (as falas servem só para a legenda).']
    if fmt == 'mesa':
        return ['FORMATO: na mesa, de perto. A pessoa está sentada à mesa e mostra o produto com as mãos, bem '
                'perto da câmera. Fale só do que a câmera mostra (textura, brilho, cor, acabamento). Não fale em '
                'vestir, caimento, corpo, provador nem em resultado na pele; não diga que comprou, nem há quanto '
                'tempo usa.']
    return []


EDIT_TIPS = {
    'comentario': 'Publique pelo botão "Responder com vídeo" no comentário (o TikTok coloca o balão sozinho) '
                  'ou cole o texto na tela como balão no CapCut.',
    'teste': 'Deixe o teste inteiro no corte final; o texto na tela anuncia o teste nos primeiros 3 s.',
    'troca_cor': 'Gere o vídeo de cada cor e junte em sequência no CapCut, cortando no instante em que a mão '
                 'cobre a lente: o vídeo seguinte começa já na nova cor.',
    'tres_jeitos': 'Formato experimental: o Grok pode errar a troca de look. Se errar, gere de novo ou use só '
                   'os trechos bons.',
    'unboxing': 'A imagem-base mostra as mãos tirando a peça da embalagem: aprove-a antes de gerar o vídeo.',
    'asmr': 'Publique com o som original, sem música por cima: o som do tecido é o conteúdo.',
    'mesa': 'Formato experimental: mãos perto do rosto e objeto pequeno são o que o Grok mais erra. Gere duas '
            'vezes e fique com a melhor; se o produto mudar de forma no meio, corte antes disso.',
}


def edit_tip(c):
    tips = [EDIT_TIPS[video_format(c)]] if video_format(c) else []
    if 'loop' in techniques(c) and video_format(c) != 'troca_cor':
        tips.append('Loop: não corte o fim do vídeo; o último quadro emenda no primeiro.')
    return ' '.join(tips)
