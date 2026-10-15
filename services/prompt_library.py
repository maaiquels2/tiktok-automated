"""Biblioteca de prompts aprovados e registro de uso da IA.

A biblioteca guarda os prompts de imagem e de video que deram certo nos
testes reais, para reaproveitar em produtos parecidos. Ela nasce com os
prompts aprovados no teste de 11 e 12/10/2026 (prompt_library_seed.json).

O registro de uso guarda os tokens de cada chamada a IA por campanha: e o
que a OpenAI cobra. O valor em dolar so aparece com a tabela de precos em
FABRICA_AI_PRICES (JSON: {"modelo": [entrada, saida]} em US$ por 1 milhao de
tokens), porque o preco muda e nao deve ser chutado no codigo.
"""
import json
import os
import uuid
from pathlib import Path

LIBRARY_SQL = ('CREATE TABLE IF NOT EXISTS prompt_library (key TEXT PRIMARY KEY, kind TEXT NOT NULL, '
               "product TEXT NOT NULL DEFAULT '', format TEXT NOT NULL DEFAULT '', "
               "version TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL, "
               'created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
USAGE_SQL = ('CREATE TABLE IF NOT EXISTS ai_usage (campaign_id INTEGER, endpoint TEXT NOT NULL, '
             'model TEXT NOT NULL, input_tokens INTEGER NOT NULL DEFAULT 0, '
             'output_tokens INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
KINDS = ('imagem', 'video')
_SEED = Path(__file__).with_name('prompt_library_seed.json')
_LIMITS = {'product': 160, 'format': 60, 'version': 40, 'note': 300, 'prompt': 12000}


def seed(conn):
    """Popula a biblioteca vazia com os prompts aprovados nos testes reais."""
    if conn.execute('SELECT 1 FROM prompt_library LIMIT 1').fetchone():
        return 0
    itens = json.loads(_SEED.read_text(encoding='utf-8')) if _SEED.exists() else []
    for item in itens:
        conn.execute('INSERT INTO prompt_library(key,kind,product,format,version,note,prompt) VALUES(?,?,?,?,?,?,?)',
                     (uuid.uuid4().hex, item['kind'], item.get('product', ''), item.get('format', ''),
                      item.get('version', ''), item.get('note', ''), item['prompt']))
    return len(itens)


def clean(data):
    """Valida o que chega da tela. Devolve (campos, erro)."""
    if not isinstance(data, dict):
        return None, 'Envie os dados do prompt.'
    kind = str(data.get('kind') or '').strip()
    if kind not in KINDS:
        return None, 'Tipo inválido: use imagem ou vídeo.'
    campos = {'kind': kind}
    for nome, limite in _LIMITS.items():
        valor = data.get(nome, '')
        if not isinstance(valor, str):
            return None, f'Campo {nome} inválido.'
        campos[nome] = valor.strip()[:limite]
    if len(campos['prompt']) < 40:
        return None, 'O prompt está vazio ou curto demais para guardar.'
    return campos, ''


def prices():
    try:
        tabela = json.loads(os.environ.get('FABRICA_AI_PRICES') or '{}')
        return {str(k): (float(v[0]), float(v[1])) for k, v in tabela.items()}
    except (ValueError, TypeError, IndexError, KeyError):
        return {}


def usage_summary(rows, tabela=None):
    """Resumo do uso da IA de uma campanha: chamadas, tokens e custo (se houver preco)."""
    tabela = prices() if tabela is None else tabela
    modelos = {}
    for row in rows:
        m = modelos.setdefault(row['model'], {'model': row['model'], 'calls': 0, 'input_tokens': 0,
                                               'output_tokens': 0})
        m['calls'] += 1
        m['input_tokens'] += int(row['input_tokens'] or 0)
        m['output_tokens'] += int(row['output_tokens'] or 0)
    custo, sem_preco = 0.0, False
    for m in modelos.values():
        preco = tabela.get(m['model'])
        if preco:
            m['cost_usd'] = round((m['input_tokens'] * preco[0] + m['output_tokens'] * preco[1]) / 1_000_000, 4)
            custo += m['cost_usd']
        else:
            sem_preco = True
    lista = sorted(modelos.values(), key=lambda m: -m['calls'])
    return {'calls': sum(m['calls'] for m in lista),
            'input_tokens': sum(m['input_tokens'] for m in lista),
            'output_tokens': sum(m['output_tokens'] for m in lista),
            'cost_usd': None if sem_preco or not lista else round(custo, 4),
            'by_model': lista}
