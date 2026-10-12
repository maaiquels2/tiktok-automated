"""Monta o lote de teste real no Grok do formato "Na mesa, de perto".

Sem API e sem custo: usa o mesmo gerador do site e grava, por clipe, a imagem-base,
o prompt completo, o Guia do Grok (compacto), as falas e um "plano B" mais simples
para o caso de a cena principal falhar. As cenas sao hipotese; o lote existe para
descobrir quais o Grok aguenta.

6 clipes novos (2 por tipo de cena) + 2 controles no espelho, que ja funcionou:
  pele       creme facial (pote)        protetor solar (bisnaga)
  joia       brinco de argola           colar ponto de luz
  roupa      pijama de cetim            calca jeans

Como rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I lote-grok-2026-10-12\\monta_lote.py
"""
import io
import json
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from services import formats  # noqa: E402
from services.copywriter import audit  # noqa: E402
from services.prompt_improve import build_compact_video_prompt  # noqa: E402
from services.prompts import generate  # noqa: E402

LIMITE = 3940
BASE = dict(model_name='Micaela', audience='', benefit='', angle='', tone='', style='', movements='',
            generator='grok', objection='', offer='')

# id, tipo de cena, formato, produto, outfit, cor, fatos confirmados, nicho
CLIPES = [
    ('C1-creme-facial', 'pele', 'mesa', 'Creme hidratante facial', 'creme hidratante', 'Branco',
     'pote de vidro, textura leve', 'dia-a-dia'),
    ('C2-protetor-solar', 'pele', 'mesa', 'Protetor solar facial', 'protetor solar', 'Branco',
     'toque seco, bisnaga de 50 g', 'dia-a-dia'),
    ('C3-brinco-argola', 'joia', 'mesa', 'Brinco de argola dourada', 'brinco', 'Dourado',
     'argola média, banhado a ouro, fecho de pressão', 'casual'),
    ('C4-colar-ponto-de-luz', 'joia', 'mesa', 'Colar ponto de luz', 'colar', 'Prateado',
     'pingente de zircônia, corrente fina', 'casual'),
    ('C5-pijama-cetim', 'roupa', 'mesa', 'Pijama de cetim', 'pijama', 'Rosa claro',
     'cetim, gola e bolso', 'intima'),
    ('C6-calca-jeans', 'roupa', 'mesa', 'Calça jeans', 'calça jeans', 'Azul claro',
     'lavagem clara, cintura alta', 'dia-a-dia'),
    ('K1-pijama-cetim-espelho', 'controle', 'espelho', 'Pijama de cetim', 'pijama', 'Rosa claro',
     'cetim, gola e bolso', 'intima'),
    ('K2-calca-jeans-espelho', 'controle', 'espelho', 'Calça jeans', 'calça jeans', 'Azul claro',
     'lavagem clara, cintura alta', 'dia-a-dia'),
]

# Plano B: troca so o meio da cena por algo com menos risco para as mesmas mãos
# (sem produto no rosto, sem objeto perto da orelha, sem desdobrar a peça toda).
PLANO_B = {
    'pele': 'risca um pouco do produto no dorso da outra mão e espalha com a ponta do dedo, mostrando a '
            'textura para a lente',
    'brinco': 'segura o brinco na palma da mão aberta, bem perto da lente, e o vira devagar',
    'colar': 'segura o colar pela corrente com uma mão, deixando-o pendurado e balançando de leve, bem perto '
             'da lente',
    'roupa': 'segura a peça dobrada com as duas mãos e a abre só até a metade, mostrando a frente, e passa a '
             'mão no tecido',
}


def campanha(clipe):
    cid, _tipo, formato, produto, outfit, cor, fatos, nicho = clipe
    return {**BASE, 'product': produto, 'outfit': outfit, 'color': cor, 'details': fatos, 'niche': nicho,
            'video_mode': formato}


def pacote(c):
    pack = generate(c, audit=audit)
    return pack, audit(pack, c), build_compact_video_prompt(c, pack, c['color'])


def com_plano_b(c, kind):
    original = formats.MESA_SCENES[kind]
    try:
        formats.MESA_SCENES[kind] = {**original, 'middle': PLANO_B[kind if kind in PLANO_B else 'roupa']}
        return pacote(c)
    finally:
        formats.MESA_SCENES[kind] = original


def grava(pasta, nome, texto):
    (pasta / nome).write_text(texto.strip() + '\n', encoding='utf-8')


def main():
    manifesto = []
    for clipe in CLIPES:
        cid, tipo, formato, produto = clipe[0], clipe[1], clipe[2], clipe[3]
        c = campanha(clipe)
        pasta = PASTA / 'clipes' / cid
        pasta.mkdir(parents=True, exist_ok=True)
        pack, problemas, guia = pacote(c)
        kind = formats.mesa_kind(c) if formato == 'mesa' else ''
        falas = (f'GANCHO: {pack["hook"]}\nMEIO: {pack["development"]}\nCTA: {pack["cta"]}\n'
                 f'TEXTO NA TELA (colar no CapCut, nao vai no vídeo): {pack["screen_text"]}\n')
        grava(pasta, '1-imagem-base.txt', pack['image'])
        grava(pasta, '2-prompt-completo.txt', pack['video'])
        grava(pasta, '3-guia-grok.txt', guia)
        grava(pasta, '4-falas.txt', falas)
        linha = dict(id=cid, tipo=tipo, formato=formato, produto=produto, cena=kind or 'espelho',
                     chars_completo=len(pack['video']), chars_guia=len(guia),
                     auditoria=problemas, plano_b=False)
        if formato == 'mesa':
            packb, probb, guiab = com_plano_b(c, kind)
            grava(pasta, '5-planoB-prompt-completo.txt', packb['video'])
            grava(pasta, '6-planoB-guia-grok.txt', guiab)
            linha['plano_b'] = True
            linha['auditoria_planoB'] = probb
            linha['chars_planoB'] = len(packb['video'])
            assert len(packb['video']) <= LIMITE, (cid, 'planoB')
        assert len(pack['video']) <= LIMITE, cid
        manifesto.append(linha)
    (PASTA / 'lote.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding='utf-8')
    for m in manifesto:
        print(f"{m['id']:28} cena={m['cena']:8} completo={m['chars_completo']:4} guia={m['chars_guia']:4} "
              f"auditoria={'ok' if not m['auditoria'] else m['auditoria']}")


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
