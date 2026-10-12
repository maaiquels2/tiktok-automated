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

FORMATS = {
    'comentario': {'label': 'Respondendo comentário', 'base': ''},
    'teste': {'label': 'Teste de prova', 'base': ''},
    'troca_cor': {'label': 'Troca de cor', 'base': ''},
    'tres_jeitos': {'label': '3 jeitos de usar', 'base': ''},
    'unboxing': {'label': 'Abrindo o pacote', 'base': 'pov'},
    'asmr': {'label': 'Close ASMR', 'base': 'movimento'},
}

TECHNIQUES = ('acao', 'aproxima', 'revela', 'loop', 'estica')
# Mais de duas tecnicas no mesmo video de 15 s viram lista de tarefas para o
# Grok (e estouram o limite de caracteres).
MAX_TECHNIQUES = 2
STYLE_TOKENS = ('closes', 'ousado') + TECHNIQUES


def video_format(c):
    value = str(c.get('video_mode') or '').strip().casefold()
    return value if value in FORMATS else ''


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
        antes.append('cobre ' + ('a câmera do celular' if espelho else 'a lente') + ' com a mão e, ao tirar, revela a peça')
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
        where = 'do espelho' if mode == 'espelho' else 'da lente'
        out.append(f'estica o tecido de leve com as duas mãos bem perto {where}, mostrando a textura, e solta')
    return out


def three_looks(c, piece):
    """Acoes do formato 3 jeitos (substituem as acoes comuns)."""
    if video_format(c) != 'tres_jeitos':
        return ''
    a, b = looks(c)
    return (f'três looks em sequência, sempre com {piece} à mostra: primeiro só como está na imagem; depois {a}; '
            f'por último {b}; em cada troca, a mão cobre a lente por meio segundo e, ao sair, ela já está no look '
            'seguinte, no mesmo lugar e na mesma luz')


def ending(c, mode=''):
    """Frase final do encerramento: transicao da troca de cor ou loop."""
    fmt, tec = video_format(c), techniques(c)
    if fmt == 'troca_cor':
        alvo = 'a câmera do celular' if mode == 'espelho' else 'a lente'
        return (f'No último segundo, depois da fala, a mão aberta vem até {alvo} e cobre o quadro inteiro '
                '(transição para a próxima cor). ')
    if 'loop' in tec:
        return 'No último quadro, volta à pose e ao enquadramento do primeiro (loop sem emenda). '
    return ''


def allows_cuts(c):
    return video_format(c) == 'tres_jeitos'


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
    return ''


def script_development(c, forms, details=()):
    """Desenvolvimento do formato, ou '' para manter o normal. `details` sao
    os fatos confirmados ja com artigo ("a cintura alta")."""
    fmt = video_format(c)
    if fmt == 'unboxing':
        # O desenvolvimento padrao parte da dor ("quem ja passou por isso...")
        # e nao combina com abrir o pacote: aqui ele narra o que aparece.
        if len(details) >= 2:
            return f'Assim que abre, já dá pra ver {details[0]}. Desdobrando, olha só {details[1]} de perto.'
        if details:
            return f'Assim que abre, já dá pra ver {details[0]}. Desdobrando, dá pra ver a peça inteira de perto.'
        return 'Assim que abre, já dá pra ver a cor. Desdobrando, dá pra ver a peça inteira de perto.'
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
}


def edit_tip(c):
    tips = [EDIT_TIPS[video_format(c)]] if video_format(c) else []
    if 'loop' in techniques(c) and video_format(c) != 'troca_cor':
        tips.append('Loop: não corte o fim do vídeo; o último quadro emenda no primeiro.')
    return ' '.join(tips)
