"""Sequência de 3 clipes de 10 s (30 s no total) para o Top Tube Tomara que Caia, cor Amarelo, no espelho.

Reaproveita o gerador de sequência de lote-sequencia-2026-10-12/monta_sequencia.py (mesmo bloco de identidade,
cenário e mãos) e converte a janela de 15 s para 10 s: 0-3 s gancho, 3-8 s meio, 8-10 s fechamento.
Falas de 35 a 38 palavras por clipe (cerca de 3,6 palavras por segundo, a densidade do app).

Rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I lote-sequencia-10s-top-2026-11-06\\monta_top_10s.py
"""
import importlib.util
import io
import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
sys.path.insert(0, str(RAIZ))
# O Flow não tem limite de prompt (o teto de 3940 do script original é do Grok): abre o teto.
_fonte = (RAIZ / 'lote-sequencia-2026-10-12' / 'monta_sequencia.py').read_text(encoding='utf-8')
_fonte = _fonte.replace('3940', '9000').replace('__file__', repr(str(RAIZ / 'lote-sequencia-2026-10-12' / 'x.py')))
ms = type(sys)('ms')
ms.__dict__['__name__'] = 'ms'
exec(compile(_fonte, 'monta_sequencia_flow', 'exec'), ms.__dict__)

# Fatos: texto do anúncio (sem alças, bojo, tecido duplo, tamanho único 34 ao 42, combina com jeans/short/saia)
# e o que a foto mostra (franzido na lateral). Não entram conforto, "fica no lugar" nem "não escorrega".
# "bojo" fica de fora dos prompts de vídeo: o clipe 1 foi recusado e a palavra fica junto do busto. Só na legenda.
FATOS = 'sem alças, tecido duplo, franzido na lateral, tamanho único do 34 ao 42'
ms.PASTA = PASTA

GESTO_FIM_ABERTO = ('termina de frente para o espelho, com a mão livre pousada na cintura, no meio do gesto, sem '
                    'apontar e sem pose de fechamento; a fala segue até o último segundo')

# 4 cores x 3 clipes. Cada cor tem uma abertura de suspense e FOMO diferente (regra do estúdio: abre uma lacuna que o
# vídeo fecha; sem estoque, prazo nem preço inventados) e um convite final com abertura própria (3 primeiras palavras
# diferentes entre as cores). Cada trio: (gancho 0-3 s, meio 3-8 s, fechamento 8-10 s). O gancho do clipe 3 FECHA a lacuna.
FALAS = {
    'Amarelo': (
        ('Três motivos pra esse top, e o último quase ninguém repara.',
         'O primeiro é o tecido duplo, repara na dobra e nas duas camadas, é um detalhe que faz diferença.',
         'O segundo é o meu favorito, já te mostro.'),
        ('O segundo é o franzido na lateral, olha só como ele desce.',
         'A modelagem sem alças deixa o ombro livre e combina com jeans, com short, com saia.',
         'O terceiro, quase todo mundo passa batido.'),
        ('O último, que ninguém repara: tamanho único, veste do 34 ao 42.',
         'Dá pra usar no dia a dia, no passeio e na festa com a mesma peça.',
         'Corre no link aqui embaixo e garante o teu.')),
    'Azul': (
        ('Você pode estar perdendo esse top sem nem saber, fica até o fim.',
         'O primeiro motivo é o tecido duplo, olha a dobra e as duas camadas, esse detalhe faz diferença.',
         'O segundo vem logo em seguida, presta atenção.'),
        ('O segundo é o franzido na lateral, olha como ele desce.',
         'Sem alças, deixa o ombro livre e combina com jeans, com short e com saia.',
         'E o terceiro você não pode perder.'),
        ('O último: é tamanho único e veste do 34 ao 42.',
         'Serve pro dia a dia, pro passeio e pra festa, é a mesma peça pra tudo.',
         'Toca no link aqui embaixo e escolhe o teu.')),
    'Preto': (
        ('Não deixa passar: esse top tem um motivo que ninguém conta.',
         'Primeiro, o tecido duplo. Repara na dobra e nas duas camadas, faz muita diferença no detalhe.',
         'Já já eu te conto o segundo motivo.'),
        ('O segundo é o franzido na lateral, olha só como desce.',
         'E sem alças o ombro fica livre, e ele combina com jeans, short ou saia.',
         'O último é o que quase ninguém conta.'),
        ('Pronto, o segredo: tamanho único, veste do 34 ao 42.',
         'Usa de dia, no passeio, no encontro e na festa, sempre com a mesma peça.',
         'Abre o link aqui embaixo e garante o teu.')),
    'Branco': (
        ('Fica até o fim: o terceiro motivo eu quase deixei passar.',
         'O primeiro é o tecido duplo, olha a dobra e as duas camadas, um detalhe que conta.',
         'O segundo motivo vem agora, olha só.'),
        ('O segundo é o franzido na lateral, repara como ele cai.',
         'A modelagem sem alças deixa o ombro livre e combina com jeans, short, saia.',
         'Agora vem o terceiro, o que eu quase esqueci.'),
        ('O terceiro: tamanho único, veste do 34 ao 42.',
         'Dá pra usar no dia a dia, num passeio e numa festa, com a mesma peça.',
         'Vai no link aqui embaixo e pega o teu.')),
}


def arcos_da_cor(cor):
    f1, f2, f3 = FALAS[cor]
    return {cor: dict(
        inicio='imagem-base',
        titulo=f'3 motivos para o top tomara que caia {cor} (3 clipes de 10 s = 30 s, abertura de suspense e FOMO)',
        capa='3 motivos pra ter esse top',
        clipes=[
            dict(
                papel='Gancho de suspense e FOMO + motivo 1 (tecido duplo)',
                falas=f1,
                abertura='sorri para o espelho, sem sair do lugar, e passa a mão livre pela lateral do top, na altura da '
                         'cintura',
                meio='gesticula com a mão livre perto da cintura, como quem mostra o detalhe do tecido, e volta a '
                     'mão para a cintura',
                fim=GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='3 motivos pra ter esse top',
                amarra='a lacuna do gancho segue aberta + mão parada na cintura',
            ),
            dict(
                papel='Motivo 2 (franzido na lateral e sem alças), lacuna ainda aberta',
                falas=f2,
                abertura='começa na pose da imagem anexada, já falando, e passa a mão livre pela lateral do top, '
                         'seguindo o franzido',
                abertura_base='começa na pose da imagem anexada (mão livre pousada na cintura), já falando, e '
                              'passa a mão livre pela lateral do top, seguindo o franzido',
                meio='desce a mão pelo franzido até a barra, abre a mão mostrando o comprimento do top e volta a '
                     'mão para a cintura',
                fim=GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='O 2º motivo',
                amarra='chamada para o terceiro motivo + mão parada na cintura',
            ),
            dict(
                papel='Motivo 3 (tamanho único 34 ao 42) fecha a lacuna + CTA',
                falas=f3,
                abertura='começa na pose da imagem anexada, já falando, e abre a mão livre ao lado do corpo, '
                         'como quem mostra que a peça é para todo mundo',
                abertura_base='começa na pose da imagem anexada (mão livre pousada na cintura), já falando, e abre '
                              'a mão livre ao lado do corpo, como quem mostra que a peça é para todo mundo',
                meio='passa a mão pelo franzido da lateral e gesticula como quem conversa com uma amiga',
                fim=None,
                ultimo_quadro='',
                tela='Qual é o seu motivo?',
                amarra='',
            ),
        ])}


# Janela de 10 s
G, M, F = (0, 3), (3, 8), (8, 10)


def para_10s(texto):
    t = texto
    t = re.sub(r'exatamente 15 segundos', 'exatamente 10 segundos', t)
    t = re.sub(r'15 segundos', '10 segundos', t)
    t = re.sub(r'SHOT LIST 15s', 'SHOT LIST 10s', t)
    # Sem a palavra TikTok (o Flow desenhou o ícone/marca d'água) e com tom casual (o clipe 1 foi recusado)
    t = t.replace('UGC TikTok Shop vertical', 'UGC vertical')
    t = t.replace('Clima: fit check no espelho gravado com o celular e postado no TikTok.',
                  'Clima: fit check casual no espelho, gravado com o celular, tom leve e simpático, roupa de passeio '
                  'do dia a dia.')
    t = t.replace('EVITAR: textos, ícones, carrinho,',
                  "EVITAR: logotipo, ícone ou marca d'água de qualquer aplicativo ou rede social, textos, "
                  'ícones, carrinho,')
    t = t.replace('sem texto, ícone, carrinho,',
                  "sem logotipo nem marca d'água de aplicativo ou rede social, sem texto, ícone, carrinho,")
    t = re.sub(r'de 15s em leitura', 'de 10s em leitura', t)
    t = t.replace('1080 × 1920 (1080p)', '720 × 1280 (720p)')  # o Flow em 10 s sai em 720p
    t = re.sub(r' CONTEXTO VISUAL OPCIONAL \(não é fato do produto; não inventar\): [^.]*\.', '', t)
    t = re.sub(r'ocupa os 15 s ', 'ocupa os 10 s ', t)
    t = re.sub(r'0–\d+s (HOOK|CONTINUAÇÃO)', rf'{G[0]}–{G[1]}s \1', t)
    t = re.sub(r'\d+–\d+s DESENVOLVIMENTO', f'{M[0]}–{M[1]}s DESENVOLVIMENTO', t)
    t = re.sub(r'\d+–15s (CTA|FIM DO TRECHO)', rf'{F[0]}–{F[1]}s \1', t)
    t = re.sub(r'ENCERRAMENTO \(\d+–\d+s\)', f'ENCERRAMENTO ({F[0]}–{F[1]}s)', t)
    t = re.sub(r'(?m)^0–4s : ', f'{G[0]}–{G[1]}s : ', t)
    t = re.sub(r'(?m)^4–12s: ', f'{M[0]}–{M[1]}s: ', t)
    t = re.sub(r'(?m)^12–15s: ', f'{F[0]}–{F[1]}s: ', t)
    return t


def confere(texto, nome):
    """Toda janela de tempo tem de caber nos 10 s; nenhum 15 sobra."""
    assert not re.search(r'(?<!\d)15 ?(s|seg)', texto), (nome, 'sobrou 15 s')
    assert '1080' not in texto, (nome, 'sobrou 1080p')
    assert not re.search(r'TikTok', texto), (nome, 'sobrou TikTok')
    for a, b in re.findall(r'(\d+)–(\d+)\s?s', texto):
        assert int(b) <= 10 and int(a) < int(b), (nome, a, b)
    for a, b in re.findall(r'entre (\d+)s e (\d+)s', texto):
        assert int(b) <= 8, (nome, 'ação alcança o último trecho', a, b)


POSE_IMAGEM = (' POSE E ENQUADRAMENTO DESTA SEQUÊNCIA (obrigatório): enquadramento da cabeça até logo abaixo da barra do '
               'top, com o top inteiro no quadro; celular na altura do ombro, ao lado do rosto, sem cobrir o rosto nem a '
               'peça; a mão livre pousada na cintura; ombros e frente do top voltados ao espelho, sem perfil. O top é '
               'tomara que caia (sem alças), {cor} liso, com a dobra de tecido duplo na parte de cima e o franzido na '
               'lateral, como na foto de referência do produto. Não copiar tatuagens, unhas nem acessórios da modelo da '
               'foto do anúncio: o rosto, o corpo e o cabelo são os da Micaela.')


def main():
    from services.prompts import generate
    for cor in FALAS:
        ms.CAMPANHA.update(model_name='Micaela', product='Top tomara que caia', outfit='top tomara que caia',
                           color=cor, details=FATOS, niche='dia-a-dia', generator='flow', video_mode='espelho')
        ms.ARCOS = arcos_da_cor(cor)
        ms.main()
        imagem = generate(dict(ms.CAMPANHA), base_image=False)['image'] + POSE_IMAGEM.format(cor=cor.lower())
        (PASTA / f'0-imagem-base-{cor.lower()}.txt').write_text(imagem + '\n', encoding='utf-8')
    (PASTA / 'sequencia.json').unlink(missing_ok=True)  # o do gerador original só guardaria a última cor
    n = 0
    for arq in sorted(PASTA.rglob('*.txt')) + sorted(PASTA.rglob('ROTEIRO.md')):
        antigo = arq.read_text(encoding='utf-8')
        novo = para_10s(antigo)
        confere(novo, arq.name)
        arq.write_text(novo, encoding='utf-8')
        n += 1
    for ext in PASTA.rglob('3-extend-video.txt'):  # técnica do Grok, não vale para o Flow
        ext.unlink()
    for guia in PASTA.rglob('2-guia-grok.txt'):
        guia.rename(guia.with_name('2-prompt-curto.txt'))
    print(f'{n} arquivos convertidos para 10 s e conferidos')


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
