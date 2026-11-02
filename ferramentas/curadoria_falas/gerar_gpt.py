"""Pede candidatos de moldes ao ChatGPT, uma categoria por chamada, e grava em curadoria/candidatas_gpt/<categoria>.json.

    set OPENAI_API_KEY (variavel de ambiente; nunca vai para arquivo)
    python ferramentas/curadoria_falas/gerar_gpt.py blusa calca_jeans          # piloto
    python ferramentas/curadoria_falas/gerar_gpt.py --todas --teto 0.9         # o resto

O gasto e somado pelos tokens que a API devolve, ao preco de seguranca do app (US$ 5 entrada / US$ 20 saida por 1M:
alto de proposito). O script para antes de passar do --teto.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

SAIDA = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria' / 'candidatas_gpt'
LEDGER = lib.ROOT / 'testes-estresse-2026-11-02' / 'curadoria' / 'gasto_gpt.json'
PRECO = (5.0, 20.0)


def gasto_total():
    return float((lib.load_json(LEDGER, {}) or {}).get('usd', 0.0))


def anotar(model, tin, tout):
    dados = lib.load_json(LEDGER, {}) or {}
    dados['usd'] = round(float(dados.get('usd', 0.0)) + tin * PRECO[0] / 1e6 + tout * PRECO[1] / 1e6, 4)
    dados['tokens_in'] = int(dados.get('tokens_in', 0)) + tin
    dados['tokens_out'] = int(dados.get('tokens_out', 0)) + tout
    dados['chamadas'] = int(dados.get('chamadas', 0)) + 1
    dados['model'] = model
    lib.save_json(LEDGER, dados)
    return dados['usd']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('categorias', nargs='*')
    ap.add_argument('--todas', action='store_true')
    ap.add_argument('--teto', type=float, default=0.9, help='gasto maximo deste script (US$, preco de seguranca)')
    ap.add_argument('--refazer', action='store_true')
    args = ap.parse_args()
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    if not key:
        sys.exit('Defina OPENAI_API_KEY no ambiente.')
    settings = {'provider': 'openai', 'api_key': key, 'model': lib.copywriter.DEFAULT_MODELS['openai'], 'enabled': True,
                '_request_timeout': 150}
    caller = lib.copywriter.CALLERS['openai']
    cats = {c['id']: c for c in lib.speech_bank.CATEGORIES}
    nomes = list(cats) if args.todas else args.categorias
    inicio = gasto_total()
    for nome in nomes:
        destino = SAIDA / f'{nome}.json'
        if destino.exists() and not args.refazer:
            print(nome, 'ja existe, pulando')
            continue
        if gasto_total() - inicio >= args.teto:
            print('TETO atingido:', gasto_total() - inicio)
            break
        system, user = lib.pedido_geracao(cats[nome])
        lista = lib.copywriter.usage_start()
        t0 = time.monotonic()
        try:
            texto = caller(settings, system, user)
        except Exception as exc:  # noqa: BLE001
            print(nome, 'ERRO', type(exc).__name__, str(exc)[:200])
            if '401' in str(exc):
                sys.exit('Chave recusada (401): pare e peca outra.')
            continue
        for uso in lista:
            anotar(uso['model'], uso['input_tokens'], uso['output_tokens'])
        dados = lib.parse_candidatos(texto)
        if dados is None:
            print(nome, 'resposta ilegivel')
            lib.save_json(SAIDA / f'{nome}.bruto.json', {'texto': texto})
            continue
        lib.save_json(destino, dados)
        print(nome, {k: len(v) for k, v in dados.items()}, f'{time.monotonic() - t0:.0f}s', 'gasto acumulado US$', gasto_total())


if __name__ == '__main__':
    main()
