"""Sequência de 3 clipes de 10 s (30 s) para o Maiô Sindy (um ombro só, recorte, argolas douradas), 3 cores, no espelho.

Reaproveita o conversor de 15 s para 10 s e as checagens de lote-sequencia-10s-top-2026-11-06/monta_top_10s.py.
Cada cor abre com uma DOR + FOMO diferente (pedido do estúdio): não ir à praia por falta de roupa, não se sentir
valorizada, vergonha de se vestir na praia. A lacuna abre no clipe 1 e fecha no 3; só o 3 convida para o link.

Rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I lote-sequencia-10s-maio-2026-11-06\\monta_maio_10s.py
"""
import io
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
RAIZ = PASTA.parent
sys.path.insert(0, str(RAIZ / 'lote-sequencia-10s-top-2026-11-06'))
import monta_top_10s as t  # noqa: E402

ms = t.ms
ms.PASTA = PASTA

# O gerador de sequência supõe a expressão "encanto → orgulho → convite" (fala de desejo). Aqui os clipes 1 e 2 partem de
# uma dor (medo, vergonha): a expressão vira "preocupação → alívio → curiosidade", e o padrão tolera as variações do app.
_sub1 = ms.sub1


def _sub1_dor(pat, new, text, flags=0):
    if pat.startswith('EXPRESSÃO: encanto'):
        pat = r'EXPRESSÃO: [^.\n]*\.'
        new = 'EXPRESSÃO: preocupação → alívio → curiosidade (sem convite de compra).'
    elif pat == r'(?m)^Expressão: .*$':
        new = 'Expressão: preocupação → alívio → curiosidade (sem convite de compra).'
    return _sub1(pat, new, text, flags)


ms.sub1 = _sub1_dor

# Fatos: descrição do anúncio (design sofisticado, recorte moderno, detalhes dourados, tamanhos P, M e G) e o que as fotos
# mostram (alça em um ombro só com correntinha de argolas, argola no recorte). "Valoriza a silhueta" e "confiante e
# elegante" são da própria descrição do anúncio, ditos em primeira pessoa como opinião. Não entram: modela o corpo, barriga,
# firmeza, tecido, proteção solar, secagem.
FATOS = 'recorte moderno, argolas douradas, alça em um ombro só, tamanhos P, M e G'

FALAS = {
    'Marrom': (  # dor: não ir à praia por não ter o que vestir
        ('Já deixei de ir à praia porque não tinha o que vestir.',
         'Se acontece contigo também, olha esse maiô marrom, com esse recorte moderno, e fica até o fim.',
         'Eu te conto os três motivos já já.'),
        ('O primeiro é o recorte moderno, olha só.',
         'O segundo são as argolas douradas, olha as argolas na alça, um detalhe de luxo que a gente repara.',
         'E o terceiro é o que me fez amar.'),
        ('O terceiro: agora eu sempre tenho o que vestir pra praia.',
         'Tem nos tamanhos P, M e G, e é um modelo sofisticado, pronto pra praia e pra qualquer ocasião.',
         'Corre no link aqui embaixo e garante o teu.')),
    'Vinho': (  # dor: medo de não se sentir valorizada
        ('Eu tinha medo de vestir maiô e não me sentir valorizada.',
         'Foi aí que eu provei esse vinho e entendi o que faltava. Fica até o fim que eu te mostro.',
         'Olha o primeiro motivo agora, presta atenção.'),
        ('O primeiro é o recorte moderno, que valoriza a silhueta, olha só.',
         'O segundo são as argolas douradas, esse toque de luxo que realça o visual todo.',
         'E o terceiro quase ninguém conta.'),
        ('O terceiro: me senti confiante e elegante, como eu queria.',
         'Tem P, M e G, num modelo sofisticado, ideal pra quem quer se destacar em qualquer ocasião.',
         'Toca no link aqui embaixo e escolhe o teu.')),
    'Preto': (  # dor: vergonha de se vestir na praia
        ('Eu tinha vergonha de me vestir pra ir à praia.',
         'Se é o teu caso, olha esse maiô preto, porque o último motivo pra amar ele quase ninguém conta.',
         'Já já eu te mostro o primeiro.'),
        ('O primeiro é o recorte moderno, olha só esse detalhe.',
         'E as argolas douradas na alça dão um toque de luxo no preto, olha como brilham.',
         'O último é o que quase ninguém conta.'),
        ('Pronto, o segredo: com ele eu me sinto confiante e elegante.',
         'Tem tamanhos P, M e G, e é sofisticado pra praia ou pra qualquer ocasião, sem aquela vergonha.',
         'Abre o link aqui embaixo e garante o teu.')),
}

POSE_IMAGEM = (' POSE DESTA SEQUÊNCIA (obrigatório): selfie no espelho, celular na altura do peito, mão livre pousada na '
               'cintura, de frente para o espelho, sorriso leve, cena casual de loja ou casa de praia, sem pose sensual. O '
               'maiô é {cor}, de um ombro só, com a correntinha de argolas douradas na alça e a argola dourada no recorte '
               'da frente, como na foto de referência do produto. Não copiar o rosto, a pele, o cabelo, as joias nem as '
               'unhas da modelo do anúncio: o rosto, o corpo e o cabelo são os da Micaela.')


def arcos_da_cor(cor):
    f1, f2, f3 = FALAS[cor]
    mao = ('começa na pose da imagem anexada (mão livre pousada na cintura), já falando, e ')
    return {cor: dict(
        inicio='imagem-base',
        titulo=f'3 motivos para o maiô {cor} (3 clipes de 10 s = 30 s, dor + FOMO)',
        capa='3 motivos pra ter esse maiô',
        clipes=[
            dict(
                papel='Dor + gancho de FOMO, motivo 1 (recorte) ainda por vir',
                falas=f1,
                abertura='sorri para o espelho, sem sair do lugar, e passa a mão livre pelo ombro, tocando a '
                         'correntinha de argolas douradas da alça',
                meio='desce a mão pelo braço até a cintura, como quem mostra o detalhe, e volta a mão para a cintura',
                fim=t.GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='Você também já deixou de ir?',
                amarra='a promessa dos 3 motivos + mão parada na cintura',
            ),
            dict(
                papel='Motivos 1 e 2 (recorte moderno e argolas douradas), lacuna ainda aberta',
                falas=f2,
                abertura='começa na pose da imagem anexada, já falando, e toca a correntinha de argolas douradas no '
                         'ombro',
                abertura_base=mao + 'toca a correntinha de argolas douradas no ombro',
                meio='passa a mão pela lateral da cintura mostrando a modelagem e volta a mão para a cintura',
                fim=t.GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='Os motivos 1 e 2',
                amarra='chamada para o terceiro motivo + mão parada na cintura',
            ),
            dict(
                papel='Motivo 3 fecha a dor (confiança) + tamanhos + CTA',
                falas=f3,
                abertura='começa na pose da imagem anexada, já falando, e abre a mão livre ao lado do corpo, como quem '
                         'convida',
                abertura_base=mao + 'abre a mão livre ao lado do corpo, como quem convida',
                meio='passa a mão pelo ombro e pela cintura e gesticula como quem conversa com uma amiga',
                fim=None,
                ultimo_quadro='',
                tela='Qual é o seu motivo?',
                amarra='',
            ),
        ])}


def main():
    from services.prompts import generate
    for cor in FALAS:
        ms.CAMPANHA.update(model_name='Micaela', product='Maiô', outfit='maiô', color=cor, details=FATOS,
                           niche='praia', generator='flow', video_mode='espelho')
        ms.ARCOS = arcos_da_cor(cor)
        ms.main()
        imagem = generate(dict(ms.CAMPANHA), base_image=False)['image'] + POSE_IMAGEM.format(cor=cor.lower())
        imagem = imagem.replace('o maiô inteira', 'o maiô inteiro')
        (PASTA / f'0-imagem-base-{cor.lower()}.txt').write_text(imagem + '\n', encoding='utf-8')
    (PASTA / 'sequencia.json').unlink(missing_ok=True)
    n = 0
    for arq in sorted(PASTA.rglob('*.txt')) + sorted(PASTA.rglob('ROTEIRO.md')):
        if arq.name.startswith('0-imagem-base'):
            continue
        novo = t.para_10s(arq.read_text(encoding='utf-8'))
        t.confere(novo, arq.name)
        arq.write_text(novo, encoding='utf-8')
        n += 1
    for ext in PASTA.rglob('3-extend-video.txt'):
        ext.unlink()
    for guia in PASTA.rglob('2-guia-grok.txt'):
        guia.rename(guia.with_name('2-prompt-curto.txt'))
    print(f'{n} arquivos convertidos para 10 s e conferidos')


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
