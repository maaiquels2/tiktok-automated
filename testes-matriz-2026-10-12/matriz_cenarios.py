"""Matriz de cenarios sem custo: produtos que NAO sao roupa x bases/formatos x tecnicas.

Roda o mesmo gerador do site (services.prompts.generate), sem API e sem rede.
Mede tres coisas por combinacao:
  1. se o pacote sai (sem excecao), dentro do limite do Grok (3940) e aprovado
     pela auditoria de honestidade do app;
  2. vazamento de vocabulario de roupa (caimento, veste, barra, tecido, agachar,
     provador...) no que a modelo FALA, no que aparece na TELA e no PROMPT do
     video/imagem -- palavras erradas para creme, brinco, colar etc.;
  3. quais frases de roupa aparecem em cada formato.
As 2 roupas de controle mostram o que e esperado (la o vocabulario e correto).

Como rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I testes-matriz-2026-10-12\\matriz_cenarios.py
Gera resultados.json e relatorio.md ao lado deste arquivo.
"""
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from services import formats  # noqa: E402
from services.copywriter import audit as copywriter_audit  # noqa: E402
from services.prompts import _product_family, generate  # noqa: E402

LIMITE_VIDEO = 3940

BASE = dict(model_name='Micaela', color='', audience='', benefit='', angle='', tone='', style='',
            movements='', generator='grok', niche='casual', objection='', offer='')

# (id, grupo, produto, outfit, cor, detalhes confirmados)
PRODUTOS = [
    ('creme-facial', 'beleza', 'Creme hidratante facial', 'creme hidratante', 'Branco',
     'pote de vidro, textura leve, perfume suave'),
    ('serum', 'beleza', 'Sérum vitamina C', 'sérum facial', 'Âmbar',
     'frasco conta-gotas, textura fluida'),
    ('batom', 'beleza', 'Batom matte', 'batom', 'Vermelho',
     'acabamento matte, bastão giratório'),
    ('protetor-solar', 'beleza', 'Protetor solar facial FPS 50', 'protetor solar', 'Branco',
     'toque seco, bisnaga de 50 g'),
    ('perfume', 'beleza', 'Perfume floral', 'perfume', 'Rosa',
     'frasco de vidro, borrifador'),
    ('esmalte', 'beleza', 'Esmalte cremoso', 'esmalte', 'Nude',
     'pincel largo, acabamento cremoso'),
    ('brinco-argola', 'acessorio', 'Brinco de argola dourada', 'brinco', 'Dourado',
     'argola média, banhado a ouro, fecho de pressão'),
    ('colar-ponto-de-luz', 'acessorio', 'Colar ponto de luz', 'colar', 'Prateado',
     'pingente de zircônia, corrente fina'),
    ('pulseira', 'acessorio', 'Pulseira de pérolas', 'pulseira', 'Branco',
     'pérolas cultivadas, elástico'),
    ('anel', 'acessorio', 'Anel solitário', 'anel', 'Prateado',
     'pedra central, aro ajustável'),
    ('oculos-sol', 'acessorio', 'Óculos de sol quadrado', 'óculos de sol', 'Preto',
     'armação acetato, lente com proteção UV'),
    ('bolsa', 'acessorio', 'Bolsa de ombro', 'bolsa', 'Caramelo',
     'alça regulável, zíper, forro interno'),
    # controles: roupa, onde o vocabulario de roupa e o correto
    ('controle-legging', 'roupa', 'Legging cintura alta', 'legging', 'Preto',
     'tecido grosso, cintura alta'),
    # cor 'Laranja' de proposito: bate com o 'carrinho laranja' fixo do CTA (falso positivo da auditoria)
    ('controle-vestido', 'roupa', 'Vestido midi de cetim', 'vestido', 'Laranja',
     'cetim, fenda, alça ajustável'),
]

MODOS = ['', 'espelho', 'pov', 'movimento'] + list(formats.FORMATS)
ESTILOS = ['', 'closes,ousado,acao,loop', 'aproxima,estica']

# Vocabulario de roupa que denuncia produto errado. (rotulo, regex)
ROUPA = [
    ('caimento', r'caimento'),
    ('veste/vestir', r'\bveste\b|\bvestir\b|\bvestindo\b|\bvestid[ao]s?\b'),
    ('barra', r'\bbarra\b'),
    ('tecido', r'\btecidos?\b'),
    ('costura', r'\bcostura'),
    ('no corpo', r'\bno corpo\b'),
    ('blusinha', r'blusinha|blusa'),
    ('agachar', r'agach'),
    ('provador/fit check', r'provador|fit check'),
    ('cintura/cós', r'cintura|\bcós\b'),
    ('looks/jaqueta', r'jaqueta|cinto|camisa aberta|saída de praia|\blooks?\b'),
    ('giro/voltinha', r'voltinha|\bgiro\b|\bgira(r|ndo)? (o )?(corpo|tronco)'),
    ('peça vestida/inteira', r'peça (inteira|vestida)'),
]
ROUPA_RE = [(nome, re.compile(rx, re.I)) for nome, rx in ROUPA]
# 'no corpo' e 'tecido' podem ser ambiguos (joia usa-se no corpo): ficam fora da contagem FORTE.
AMBIGUOS = {'no corpo', 'tecido'}
# Trecho fixo de todos os prompts: lista do que NAO inventar. Fala em tecido/
# compressao por ser texto de seguranca, nao descricao deste produto.
NEGATIVA = re.compile(r'ATRIBUTOS NÃO CONFIRMADOS:.*?FATOS CONFIRMADOS\.', re.S)


def fortes(termos):
    return [t for t in termos if t not in AMBIGUOS]


def vazamentos(texto):
    texto = NEGATIVA.sub(' ', texto or '')
    return sorted({nome for nome, rx in ROUPA_RE if rx.search(texto)})


def rodar():
    linhas = []
    for (pid, grupo, produto, outfit, cor, detalhes), modo, estilo in itertools.product(PRODUTOS, MODOS, ESTILOS):
        campanha = {**BASE, 'product': produto, 'outfit': outfit, 'color': cor, 'details': detalhes,
                    'video_mode': modo, 'video_style': estilo}
        linha = dict(produto=pid, grupo=grupo, modo=modo or 'com fala', estilo=estilo or '-')
        try:
            pacote = generate(campanha, audit=copywriter_audit)
            linha['familia'] = _product_family(campanha)
            linha['video_chars'] = len(pacote.get('video') or '')
            linha['cabe_no_grok'] = linha['video_chars'] <= LIMITE_VIDEO
            linha['auditoria'] = copywriter_audit(pacote, campanha)
            fala = ' '.join(str(pacote.get(k) or '') for k in ('hook', 'development', 'cta'))
            linha['vaza_fala'] = vazamentos(fala)
            linha['vaza_tela'] = vazamentos(pacote.get('screen_text'))
            linha['vaza_video'] = vazamentos(pacote.get('video'))
            linha['vaza_imagem'] = vazamentos(pacote.get('image'))
            linha['hook'] = pacote.get('hook')
        except Exception as erro:  # a matriz mede, nao esconde falha
            linha['erro'] = f'{type(erro).__name__}: {erro}'
        linhas.append(linha)
    return linhas


def relatorio(linhas):
    ok = [l for l in linhas if 'erro' not in l]
    out = ['# Matriz de cenários — produtos que não são roupa', '',
           'Gerado sem API: o mesmo gerador do site (`generate`), com a auditoria de honestidade do app.', '',
           f'- Combinações: **{len(linhas)}** ({len(PRODUTOS)} produtos × {len(MODOS)} bases/formatos × {len(ESTILOS)} estilos)',
           f'- Geraram pacote sem erro: **{len(ok)}**',
           f'- Cabem no limite do Grok ({LIMITE_VIDEO}): **{sum(1 for l in ok if l["cabe_no_grok"])}**',
           f'- Aprovadas pela auditoria de honestidade: **{sum(1 for l in ok if not l["auditoria"])}**', '']
    erros = Counter(l['erro'] for l in linhas if 'erro' in l)
    if erros:
        out += ['## Erros', ''] + [f'- {n}× {e}' for e, n in erros.most_common(10)] + ['']

    out += ['## Vocabulário de roupa em produto que não é roupa', '',
            'Cada célula: combinações com pelo menos uma palavra inequívoca de roupa (caimento, veste, blusinha, barra, agachar, provador, cintura, jaqueta, girar...) naquele campo. "No corpo" e "tecido" ficam de fora por serem ambíguos. Na roupa de controle essas palavras estão certas.', '',
            '| Grupo | Combinações | Na fala | Na tela | No prompt do vídeo | No prompt da imagem |',
            '|---|---|---|---|---|---|']
    for grupo in ('beleza', 'acessorio', 'roupa'):
        g = [l for l in ok if l['grupo'] == grupo]
        n = len(g)
        cel = [sum(1 for l in g if fortes(l[k])) for k in ('vaza_fala', 'vaza_tela', 'vaza_video', 'vaza_imagem')]
        rotulo = {'beleza': 'Beleza', 'acessorio': 'Acessórios', 'roupa': 'Roupa (controle)'}[grupo]
        out.append(f'| {rotulo} | {n} | ' + ' | '.join(f'{c} ({100 * c // max(n, 1)}%)' for c in cel) + ' |')
    out.append('')

    out += ['## Por base/formato (beleza + acessórios)', '',
            '| Base / formato | Combinações | Com palavra de roupa na fala | No prompt do vídeo | Palavras mais frequentes (vídeo) |',
            '|---|---|---|---|---|']
    for modo in [m or 'com fala' for m in MODOS]:
        g = [l for l in ok if l['modo'] == modo and l['grupo'] != 'roupa']
        termos = Counter(t for l in g for t in fortes(l['vaza_video']))
        top = ', '.join(f'{t} ({c})' for t, c in termos.most_common(5)) or '-'
        out.append(f'| {modo} | {len(g)} | {sum(1 for l in g if fortes(l["vaza_fala"]))} | '
                   f'{sum(1 for l in g if fortes(l["vaza_video"]))} | {top} |')
    out.append('')

    out += ['## Por produto (todas as bases e estilos)', '',
            '| Produto | Família detectada | Fala com palavra de roupa | Vídeo com palavra de roupa | Reprovados na auditoria |',
            '|---|---|---|---|---|']
    for pid, grupo, *_ in PRODUTOS:
        g = [l for l in ok if l['produto'] == pid]
        fam = Counter(l['familia'] for l in g).most_common(1)[0][0] if g else '?'
        out.append(f'| {pid} | {fam} | {sum(1 for l in g if fortes(l["vaza_fala"]))}/{len(g)} | '
                   f'{sum(1 for l in g if fortes(l["vaza_video"]))}/{len(g)} | {sum(1 for l in g if l["auditoria"])} |')
    out.append('')

    por_prod = defaultdict(set)
    for l in ok:
        if l['grupo'] != 'roupa' and l['vaza_fala']:
            por_prod[l['produto']].add(l['hook'])
    out += ['## Exemplos de gancho gerado para produto que não é roupa (modo com fala, sem técnica)', '']
    for l in ok:
        if l['grupo'] != 'roupa' and l['modo'] == 'com fala' and l['estilo'] == '-':
            out.append(f'- **{l["produto"]}** (família `{l["familia"]}`): "{l["hook"]}"')
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    linhas = rodar()
    (PASTA / 'resultados.json').write_text(json.dumps(linhas, ensure_ascii=False, indent=1), encoding='utf-8')
    (PASTA / 'relatorio.md').write_text(relatorio(linhas), encoding='utf-8')
    print(f'{len(linhas)} combinacoes; erros: {sum(1 for l in linhas if "erro" in l)}')
