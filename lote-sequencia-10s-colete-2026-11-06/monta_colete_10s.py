"""Sequência de 3 clipes de 10 s (30 s) para o Coletinho de courino com botões encapados, 2 cores (Preto e Caramelo; o Vinho está indisponível no anúncio), no espelho.

Reaproveita o conversor de 15 s para 10 s e as checagens de lote-sequencia-10s-top-2026-11-06/monta_top_10s.py.
Cada cor abre com uma DOR + FOMO diferente (pedido do estúdio): medo de o courino parecer plástico e look de todo dia sem
graça. A lacuna abre no clipe 1 e fecha no 3; só o 3 convida para o link.

Rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I lote-sequencia-10s-colete-2026-11-06\\monta_colete_10s.py
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

# Fatos: descrição do anúncio (courino, botões encapados frontais, modelagem ajustada que valoriza a silhueta, estruturado
# que não fica mole no corpo, não é transparente, fácil de combinar, ideal para inverno e meia estação, tamanhos P a GG).
# Não entram: forro, elasticidade, conforto, impermeabilidade, marca.
FATOS = ('courino, botões encapados na frente, modelagem ajustada, estruturado, não é transparente, '
         'ideal para inverno e meia estação, tamanhos P, M, G e GG')

FALAS = {
    'Preto': (  # dor: courino parecer plástico/barato de perto
        ('Eu sempre fugi de courino com medo de parecer plástico.',
         'Aí provei esse coletinho preto e entendi o que muda. Fica até o fim que eu te mostro três motivos.',
         'O primeiro vem agora, olha só.'),
        ('O primeiro são os botões encapados, olha o acabamento.',
         'O segundo é o caimento estruturado, ele não fica mole no corpo, e olha que não é transparente.',
         'E o terceiro é o que quase ninguém repara.'),
        ('O terceiro: combina fácil, do dia a dia ao look elegante.',
         'Tem de P a GG e serve pro inverno e pra meia estação, sempre com ar sofisticado.',
         'Corre no link aqui embaixo e garante o teu.')),
    'Caramelo': (  # dor: look de todo dia sem graça; FOMO de estar perdendo
        ('Já olhou pro armário e achou todo look sem graça?',
         'Esse coletinho caramelo resolve pra mim, e o último motivo quase ninguém conta. Fica até o fim.',
         'Já já eu te mostro o primeiro.'),
        ('O primeiro são os botões encapados, olha o acabamento.',
         'O segundo é a modelagem ajustada, que valoriza a silhueta, num courino que não é transparente.',
         'O último é o que quase ninguém conta.'),
        ('O último: combina fácil, do dia a dia ao look elegante.',
         'Tem tamanhos de P a GG e é ideal pro inverno e pra meia estação, um coringa no armário.',
         'Toca no link aqui embaixo e escolhe o teu.')),
}

POSE_IMAGEM = (' POSE DESTA SEQUÊNCIA (obrigatório): selfie no espelho, celular na altura do peito, sem cobrir o '
               'rosto; a mão livre pousada na cintura, de frente para o espelho, sorriso leve, cena '
               'casual de loja. O coletinho é {cor}, de courino, decote em V, sem mangas, com três botões encapados na '
               'frente e a barra em ponta, usado com calça jeans cinza de cintura alta, como na foto de referência do '
               'produto. Não copiar o rosto, o cabelo, as joias nem as unhas da modelo do anúncio: o rosto, o corpo e o '
               'cabelo são os da Micaela.')


def arcos_da_cor(cor):
    f1, f2, f3 = FALAS[cor]
    mao = 'começa na pose da imagem anexada (mão livre pousada na cintura), já falando, e '
    return {cor: dict(
        inicio='imagem-base',
        titulo=f'3 motivos para o coletinho {cor} (3 clipes de 10 s = 30 s, dor + FOMO)',
        capa='3 motivos pra ter esse coletinho',
        clipes=[
            dict(
                papel='Dor + gancho de FOMO; o motivo 1 (botões encapados) ainda por vir',
                falas=f1,
                abertura='sorri para o espelho, sem sair do lugar, e toca com as pontas dos dedos os botões encapados '
                         'do coletinho',
                meio='desce a mão pela frente do coletinho até a barra em ponta e volta a mão para a cintura',
                fim=t.GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='Você também fugia de courino?' if cor == 'Preto' else 'Todo look sem graça?',
                amarra='a promessa dos 3 motivos + mão parada na cintura',
            ),
            dict(
                papel='Motivos 1 e 2 (botões encapados e caimento estruturado), lacuna ainda aberta',
                falas=f2,
                abertura='começa na pose da imagem anexada, já falando, e toca o botão do meio do coletinho',
                abertura_base=mao + 'toca o botão do meio do coletinho',
                meio='passa a mão pela lateral do coletinho mostrando a modelagem e volta a mão para a cintura',
                fim=t.GESTO_FIM_ABERTO,
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='Os motivos 1 e 2',
                amarra='chamada para o terceiro motivo + mão parada na cintura',
            ),
            dict(
                papel='Motivo 3 fecha a dor (combina fácil) + tamanhos + CTA',
                falas=f3,
                abertura='começa na pose da imagem anexada, já falando, e abre a mão livre ao lado do corpo, como quem '
                         'convida',
                abertura_base=mao + 'abre a mão livre ao lado do corpo, como quem convida',
                meio='passa a mão pelos botões e pela barra e gesticula como quem conversa com uma amiga',
                fim=None,
                ultimo_quadro='',
                tela='Qual é o seu motivo?',
                amarra='',
            ),
        ])}


def main():
    from services.prompts import generate
    for cor in FALAS:
        ms.CAMPANHA.update(model_name='Micaela', product='Coletinho de courino', outfit='coletinho de courino', color=cor, details=FATOS,
                           niche='dia-a-dia', generator='flow', video_mode='espelho')
        ms.ARCOS = arcos_da_cor(cor)
        ms.main()
        imagem = generate(dict(ms.CAMPANHA), base_image=False)['image'] + POSE_IMAGEM.format(cor=cor.lower())
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
