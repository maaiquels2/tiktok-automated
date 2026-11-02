"""Mede a variedade das falas do gerador LOCAL (sem IA) num painel fixo: categorias x situacoes x 7 cores.

Para cada caso monta as 7 cores como o app faz (generate_variants) e conta quantos ganchos, desenvolvimentos e CTAs
distintos saem, quantas cores abrem igual (3 primeiras palavras) e quantas falas reprovam na auditoria.

    python ferramentas/medir_variedade_falas.py --saida baseline.json
    python ferramentas/medir_variedade_falas.py --comparar baseline.json     # mostra antes x depois

So leitura: nao grava nada no app nem no banco, nao chama API.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CORES = 'Preto, Marrom, Vinho, Verde claro, Off-white, Azul bebê, Amarelo'
BASE = dict(model_name='Micaela', audience='mulheres adultas', benefit='', angle='', tone='', style='', movements='',
            objection='', offer='', generator='grok', video_mode='', color=CORES)

PAINEL = {
    'blusa': dict(product='Blusa feminina de viscose', outfit='blusa', niche='casual',
                  details='viscose, decote, caimento leve', pain='ficar transparente'),
    'calca_jeans': dict(product='Calça jeans reta', outfit='calça jeans', niche='dia-a-dia',
                        details='lavagem clara, cintura alta, bolsos na frente', pain='ficar apertada'),
    'legging': dict(product='Legging cintura alta com bolso', outfit='legging', niche='academia',
                    details='cintura alta, bolso lateral, tecido grosso', pain='ficar transparente'),
    'pijama': dict(product='Pijama de cetim', outfit='pijama', niche='intima',
                   details='cetim, botões, short', pain='esquentar demais'),
    'biquini': dict(product='Biquíni cortininha', outfit='biquíni', niche='praia',
                    details='bojo, amarração ajustável', pain='sair do lugar'),
    'colete': dict(product='Colete de courino', outfit='colete', niche='casual',
                   details='courino, botões', pain='parecer barato'),
    'creme': dict(product='Creme hidratante facial', outfit='creme', niche='casual',
                  details='textura leve, pote de 50 g', pain='pesar na pele'),
    'brinco': dict(product='Brinco argola dourado', outfit='brinco', niche='casual',
                   details='acabamento dourado, argola média', pain='escurecer'),
}
SITUACOES = {
    'desejo': dict(),                                    # sem objecao nem oferta
    'necessidade': dict(objection=True),                 # com objecao
    'escassez': dict(offer='Frete grátis em compras acima de R$ 99 até domingo'),
}


def casos():
    for cat, prod in PAINEL.items():
        for nome, extra in SITUACOES.items():
            c = {**BASE, **{k: v for k, v in prod.items() if k != 'pain'}}
            if extra.get('objection'):
                c['objection'] = prod['pain']
            if extra.get('offer'):
                c['offer'] = extra['offer']
            yield f'{cat}|{nome}', c


def abre(texto, n=3):
    return ' '.join(re.sub(r'[^\wÀ-ÿ ]', '', str(texto).casefold()).split()[:n])


def medir():
    from services import copywriter
    from services.prompts import generate_variants
    out = {}
    for chave, c in casos():
        packs = [v['prompts'] for v in generate_variants(c, audit=copywriter.audit)]
        row = {}
        for campo in ('hook', 'development', 'cta'):
            textos = [p.get(campo, '') for p in packs]
            aberturas = Counter(abre(t) for t in textos)
            row[campo] = dict(distintos=len(set(textos)), abertura_repetida=max(aberturas.values()))
        frases = [f.strip().casefold() for p in packs for f in re.split(r'(?<=[.!?])\s+', p.get('development', '')) if f.strip()]
        row['frases_dev'] = dict(total=len(frases), reaproveitadas=len(frases) - len(set(frases)))
        row['reprovadas'] = sum(1 for v in generate_variants(c, audit=copywriter.audit)
                                if copywriter.audit(v['prompts'], {**c, 'color': v['color']}))
        row['ctas'] = [p.get('cta', '') for p in packs]
        out[chave] = row
    return out


def resumo(dados):
    n = len(dados)
    linhas = {}
    for campo in ('hook', 'development', 'cta'):
        linhas[campo] = (sum(r[campo]['distintos'] for r in dados.values()) / n,
                         sum(r[campo]['abertura_repetida'] for r in dados.values()) / n)
    linhas['reprovadas'] = sum(r['reprovadas'] for r in dados.values())
    total = sum(r['frases_dev']['total'] for r in dados.values())
    linhas['frases'] = sum(r['frases_dev']['reaproveitadas'] for r in dados.values()) / max(1, total)
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saida')
    ap.add_argument('--comparar')
    args = ap.parse_args()
    dados = medir()
    if args.saida:
        Path(args.saida).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding='utf-8')
    atual = resumo(dados)
    antes = resumo(json.loads(Path(args.comparar).read_text(encoding='utf-8'))) if args.comparar else None
    print(f'{len(dados)} casos x 7 cores (media por caso)')
    for campo in ('hook', 'development', 'cta'):
        distintos, repetida = atual[campo]
        extra = ''
        if antes:
            extra = f'   (antes: {antes[campo][0]:.2f} distintos, {antes[campo][1]:.2f} abrem igual)'
        print(f'  {campo:12s} distintos {distintos:.2f} de 7 | maior grupo que abre igual {repetida:.2f}{extra}')
    print(f'  frases do desenvolvimento que se repetem entre as 7 cores: {atual["frases"] * 100:.0f}%'
          + (f' (antes: {antes["frases"] * 100:.0f}%)' if antes else ''))
    print(f'  falas reprovadas na auditoria: {atual["reprovadas"]}' + (f' (antes: {antes["reprovadas"]})' if antes else ''))
    for chave, r in dados.items():
        if r['cta']['distintos'] <= 3:
            print(f'  CTA pouco variado em {chave}: {r["cta"]["distintos"]} distintos')


if __name__ == '__main__':
    main()
