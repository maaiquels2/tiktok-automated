"""Checagens automaticas dos candidatos: espacos, req, genero, orcamento de palavras, termos proibidos, auditoria do app e
repeticao. Le curadoria/<origem>/<categoria>.json e grava curadoria/auto/<origem>__<categoria>.json (aprovados e motivos).

    python ferramentas/curadoria_falas/verificar.py candidatas_gpt blusa calca_jeans
    python ferramentas/curadoria_falas/verificar.py candidatas_gpt --todas
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

BASE = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria'


def texto(m):
    return m['t'] if isinstance(m, dict) else m


def verificar(cat, candidatos):
    existentes = {k: [texto(m) for m in cat.get(k, [])] for k in lib.KINDS}
    ok = {k: [] for k in lib.KINDS}
    recusados = []
    for kind in lib.KINDS:
        vistos = list(existentes[kind])
        for mold in candidatos.get(kind, []):
            item = mold if isinstance(mold, dict) else {'t': mold}
            if not isinstance(item.get('t'), str):
                recusados.append((kind, str(mold)[:80], ['formato invalido']))
                continue
            clean = {k: v for k, v in item.items() if k in ('t', 'req', 'pain', 'for_pain') and v not in (None, '', False)}
            motivos = lib.check(cat, clean, kind, vistos)
            if not motivos:
                motivos = lib.audit_in_context(cat, clean, kind)
            if motivos:
                recusados.append((kind, item['t'][:90], motivos[:3]))
                continue
            ok[kind].append(clean if kind != 'closers' else clean['t'])
            vistos.append(clean['t'])
    return ok, recusados


def main():
    origem = sys.argv[1]
    nomes = sys.argv[2:]
    cats = {c['id']: c for c in lib.speech_bank.CATEGORIES}
    if '--todas' in nomes:
        nomes = [p.stem for p in sorted((BASE / origem).glob('*.json')) if '.bruto' not in p.name]
    total, aprovados, motivos = 0, 0, Counter()
    for nome in nomes:
        dados = lib.load_json(BASE / origem / f'{nome}.json')
        if not dados:
            print(nome, 'sem arquivo')
            continue
        ok, recusados = verificar(cats[nome], dados)
        n = sum(len(v) for v in dados.values())
        a = sum(len(v) for v in ok.values())
        total += n
        aprovados += a
        for _k, _t, why in recusados:
            motivos[why[0].split(':')[0][:48]] += 1
        lib.save_json(BASE / 'auto' / f'{origem}__{nome}.json', {'aprovados': ok, 'recusados': recusados})
        print(f'{nome}: {a}/{n} passaram', {k: len(v) for k, v in ok.items()})
    print(f'TOTAL {aprovados}/{total}', motivos.most_common(8))


if __name__ == '__main__':
    main()
