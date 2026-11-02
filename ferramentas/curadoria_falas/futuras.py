"""Frases de "imaginacao de uso" (services/prompts.py: _FUTURE_LINES e _FUTURE_BY_FAMILY): checagens, pacote dos juizes e juncao.

Cada grupo (nicho ou familia) tinha so 3 frases; com 7 cores elas se repetiam (3 de 7 cores com "Já tô pensando em sair com ela
no fim de semana..."). Aqui ficam as candidatas, a checagem e o resultado.

    python ferramentas/curadoria_falas/futuras.py verificar      # candidatas -> auto.json
    python ferramentas/curadoria_falas/futuras.py pacote         # monta o pacote dos juizes
    python ferramentas/curadoria_falas/futuras.py consolidar     # vereditos -> finais.json
"""
import difflib
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from services import prompts  # noqa: E402

BASE = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria' / 'futuras'
MODELOS = ('opus', 'sonnet', 'haiku')
GRUPOS = {**{k: v for k, v in prompts._FUTURE_LINES.items()}, **{k: v for k, v in prompts._FUTURE_BY_FAMILY.items()}}
EXTRA_BANIDO = r'(todo mundo|todos|todas|pergunt\w+|elogi\w+|inveja|assunto da|de onde é|amigas? (aprovou|amou))'


def verificar():
    cand = lib.load_json(BASE / 'candidatas.json') or {}
    saida, recusados = {}, []
    for grupo, linhas in cand.items():
        existentes = [t.replace('{com}', 'com ela') for t in GRUPOS.get(grupo, ())]
        ok = []
        for t in linhas:
            motivos = []
            texto = str(t).strip()
            if set(re.findall(r'\{(\w+)\}', texto)) - {'com'}:
                motivos.append('espaco desconhecido')
            cheio = texto.replace('{com}', 'com ela')
            n = lib.words(cheio)
            if not 7 <= n <= 18:
                motivos.append(f'{n} palavras (7-18)')
            if not re.search(r'[.!]$', cheio):
                motivos.append('sem ponto final')
            for pat in lib.BANNED:
                hit = re.search(pat if not pat.startswith('\b') else lib.norm(pat), lib.norm(cheio))
                if hit:
                    motivos.append(f'termo proibido: {hit.group(0)}')
            if re.search(EXTRA_BANIDO, lib.norm(cheio)):
                motivos.append('reacao de terceiros / prova social inventada')
            for label in lib.FEATURES:
                if re.search(rf'(?<!\w){re.escape(label.casefold())}(?!\w)', cheio.casefold()):
                    motivos.append(f'cita atributo: {label}')
            for outra in existentes + ok:
                if difflib.SequenceMatcher(None, lib.norm(cheio), lib.norm(outra.replace('{com}', 'com ela'))).ratio() >= 0.75:
                    motivos.append(f'quase igual a: {outra[:40]}')
                    break
            (recusados.append((grupo, texto, motivos)) if motivos else ok.append(texto))
        saida[grupo] = ok
    lib.save_json(BASE / 'auto.json', {'aprovados': saida, 'recusados': recusados})
    print({g: len(v) for g, v in saida.items()}, 'recusados:', len(recusados))
    for r in recusados[:10]:
        print('  ', r)


def pacote():
    auto = lib.load_json(BASE / 'auto.json')
    itens, controle = [], {}
    n = 0
    for grupo, linhas in auto['aprovados'].items():
        for t in linhas:
            n += 1
            ident = f'fu{n:03d}'
            itens.append({'id': ident, 'grupo': grupo, 'filled': t.replace('{com}', 'com ela')})
            controle[ident] = {'grupo': grupo, 'texto': t}
    random.Random('futuras').shuffle(itens)
    lib.save_json(BASE / 'pacote.json', {'itens': itens})
    lib.save_json(BASE / 'controle.json', controle)
    print(len(itens), 'frases para julgar')


def consolidar():
    controle = lib.load_json(BASE / 'controle.json')
    ver = {m: lib.load_json(BASE / f'veredito_{m}.json') for m in MODELOS}
    if any(not v for v in ver.values()):
        print('faltam vereditos:', [m for m, v in ver.items() if not v])
        return
    finais = {}
    for ident, info in controle.items():
        notas = [ver[m].get(ident) for m in MODELOS]
        if any(x is None for x in notas):
            continue
        scores = [int(x.get('score') or 0) for x in notas]
        if any(bool(x.get('risco')) for x in notas) or sum(1 for s in scores if s >= 4) < 2:
            continue
        finais.setdefault(info['grupo'], []).append((sum(scores) / 3, info['texto']))
    saida = {}
    for grupo, lista in finais.items():
        lista.sort(key=lambda x: -x[0])
        saida[grupo] = [t for _s, t in lista[:7]]
    lib.save_json(BASE / 'finais.json', saida)
    print({g: len(v) for g, v in saida.items()})


def mesclar():
    import pprint
    finais = lib.load_json(BASE / 'finais.json') or {}
    cab = ('"""Frases de imaginacao de uso curadas (candidatas do Claude, checagens automaticas e 3 juizes sem risco).'
           + ' Entram DEPOIS das 3 originais de cada grupo (as 3 primeiras cores continuam iguais).'
           + ' Gerado por ferramentas/curadoria_falas/futuras.py: nao edite a mao."""')
    texto = cab + chr(10) + 'FUTURE = ' + pprint.pformat(finais, width=118, sort_dicts=False) + chr(10)
    (lib.ROOT / 'services' / 'speech_future.py').write_text(texto, encoding='utf-8')
    print('gravado services/speech_future.py:', {g: len(v) for g, v in finais.items()})


if __name__ == '__main__':
    {'verificar': verificar, 'pacote': pacote, 'consolidar': consolidar, 'mesclar': mesclar}[sys.argv[1]]()
