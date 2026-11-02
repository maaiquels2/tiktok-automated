"""Junta os moldes finais (curadoria/finais/<categoria>.json) em services/speech_curated.py.

    python ferramentas/curadoria_falas/mesclar.py            # todas as categorias que tem arquivo final
    python ferramentas/curadoria_falas/mesclar.py --ver      # so mostra o que entraria

O modulo gerado e dado versionado (o gerador local le no import); nunca edite a mao: rode de novo.
"""
import pprint
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

BASE = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria'
DESTINO = lib.ROOT / 'services' / 'speech_curated.py'

CABECALHO = '''"""Moldes de fala curados: candidatos escritos por GPT e por agentes do Claude, aprovados pelas checagens automaticas
(espacos, atributo declarado, genero, orcamento de palavras, termos proibidos, auditoria do app, repeticao) e por pelo
menos 2 de 3 juizes (Claude Opus, Sonnet e Haiku, sem saber quem escreveu), sem nenhum alerta de risco, e pela auditoria estrita da geracao individual do app.

Mesmo formato dos moldes de services/speech_bank.py (hooks, reactions, closers, ctas). Entram INTERCALADOS com os moldes
que ja existiam (o primeiro de cada lista continua o mesmo). Gerado por ferramentas/curadoria_falas/mesclar.py: nao edite a mao.
"""
'''


def main():
    ver = '--ver' in sys.argv
    out, recusados = {}, []
    for cat in lib.speech_bank.CATEGORIES:
        dados = lib.load_json(BASE / 'finais' / f'{cat["id"]}.json')
        if not dados:
            continue
        bloco = {}
        for kind in lib.KINDS:
            itens = []
            for x in dados.get(kind, []):
                item = x['mold'] if isinstance(x['mold'], dict) else {'t': x['mold']}
                # Ultima barreira: as checagens automaticas, agora com a auditoria estrita da geracao individual.
                if lib.check(cat, item, kind) or lib.audit_in_context(cat, item, kind) or lib.check_pains(cat, item, kind):
                    recusados.append((cat['id'], kind, item['t']))
                    continue
                itens.append(x['mold'])
            if itens:
                bloco[kind] = itens
        if bloco:
            out[cat['id']] = bloco
    total = sum(len(v) for b in out.values() for v in b.values())
    print(len(out), 'categorias,', total, 'moldes;', len(recusados), 'recusados na ultima barreira')
    for item in recusados[:12]:
        print('   recusado', item)
    if ver:
        return
    texto = CABECALHO + '\nCURATED = ' + pprint.pformat(out, width=118, sort_dicts=False) + '\n'
    DESTINO.write_text(texto, encoding='utf-8')
    print('gravado', DESTINO)


if __name__ == '__main__':
    main()
