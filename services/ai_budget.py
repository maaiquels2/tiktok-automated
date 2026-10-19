"""Teto de gasto da IA: por dia e por mes, em dolar, contado pelos tokens gravados em ai_usage.

Com OPENAI_API_KEY definida a IA ja vem ligada, e cada roteiro, leitura de foto e criacao automatica gasta a chave.
Sem teto, um dia de muitos testes so aparecia na fatura da OpenAI.

O preco de cada modelo (US$ por 1 milhao de tokens de entrada e de saida) vem da tela (Identidade -> Escrita das
falas) ou da variavel FABRICA_AI_PRICES. O preco muda e nao e chutado no codigo: modelo sem preco cadastrado e
contado pelo SAFETY_PRICE, alto de proposito, para o teto disparar cedo e nunca tarde. Um modelo a US$ 0 faria o
teto nunca disparar, entao preco zero tambem conta como "sem preco".
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

DEFAULT_DAILY_USD = 2.0
DEFAULT_MONTHLY_USD = 20.0
SAFETY_PRICE = (5.0, 20.0)
MAX_CAP_USD = 10000.0
MAX_PRICE_USD = 1000.0
# O dia e o mes do estudio sao os de Brasilia (sem horario de verao desde 2019).
BRT = timezone(timedelta(hours=-3))


def _number(value, maximo):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= maximo else None


def clean(values: dict) -> tuple[dict, str]:
    """Valida teto e precos vindos da tela. Devolve (campos validos, erro)."""
    out = {}
    for campo in ('cap_daily_usd', 'cap_monthly_usd'):
        if campo in values:
            n = _number(values[campo], MAX_CAP_USD)
            if n is None:
                return {}, 'Teto inválido: use um valor em dólar entre 0 e 10000 (0 desliga o teto).'
            out[campo] = round(n, 2)
    if 'prices' in values:
        tabela = values['prices']
        if not isinstance(tabela, dict) or len(tabela) > 20:
            return {}, 'Preços inválidos.'
        precos = {}
        for modelo, par in tabela.items():
            if not isinstance(modelo, str) or not modelo.strip() or len(modelo) > 80:
                return {}, 'Nome de modelo inválido nos preços.'
            if not isinstance(par, (list, tuple)) or len(par) != 2:
                return {}, f'Informe o preço de entrada e de saída de {modelo}.'
            entrada, saida = _number(par[0], MAX_PRICE_USD), _number(par[1], MAX_PRICE_USD)
            if entrada is None or saida is None:
                return {}, f'Preço inválido para {modelo}: use dólar por 1 milhão de tokens.'
            precos[modelo.strip()] = [entrada, saida]
        out['prices'] = precos
    return out, ''


def caps(settings: dict) -> tuple[float, float]:
    diario = _number(settings.get('cap_daily_usd', DEFAULT_DAILY_USD), MAX_CAP_USD)
    mensal = _number(settings.get('cap_monthly_usd', DEFAULT_MONTHLY_USD), MAX_CAP_USD)
    return (DEFAULT_DAILY_USD if diario is None else diario, DEFAULT_MONTHLY_USD if mensal is None else mensal)


def price_table(settings: dict | None = None) -> dict:
    """Precos por modelo: a variavel FABRICA_AI_PRICES e, por cima, o que foi salvo na tela."""
    tabela = {}
    try:
        for k, v in json.loads(os.environ.get('FABRICA_AI_PRICES') or '{}').items():
            tabela[str(k)] = (float(v[0]), float(v[1]))
    except (ValueError, TypeError, IndexError, KeyError, AttributeError):
        tabela = {}
    for k, v in ((settings or {}).get('prices') or {}).items():
        try:
            tabela[str(k)] = (float(v[0]), float(v[1]))
        except (ValueError, TypeError, IndexError):
            continue
    return {k: v for k, v in tabela.items() if v[0] > 0 or v[1] > 0}


def period_starts(now: datetime | None = None) -> tuple[str, str]:
    """Inicio do dia e do mes de Brasilia, em UTC, no formato que o banco grava em created_at."""
    agora = (now or datetime.now(timezone.utc)).astimezone(BRT)
    dia = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    mes = dia.replace(day=1)
    fmt = lambda d: d.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')  # noqa: E731
    return fmt(dia), fmt(mes)


def cost(model: str, tokens_in: int, tokens_out: int, tabela: dict) -> tuple[float, bool]:
    """Custo em dolar e se o preco e o real (False: contado pelo preco de seguranca)."""
    preco = tabela.get(model)
    entrada, saida = preco or SAFETY_PRICE
    return (int(tokens_in or 0) * entrada + int(tokens_out or 0) * saida) / 1_000_000, bool(preco)


def status(conn, settings: dict, now: datetime | None = None) -> dict:
    inicio_dia, inicio_mes = period_starts(now)
    tabela = price_table(settings)
    rows = conn.execute('SELECT model,input_tokens,output_tokens,created_at FROM ai_usage WHERE created_at>=?',
                        (inicio_mes,)).fetchall()
    hoje = mes = 0.0
    sem_preco = set()
    for r in rows:
        valor, real = cost(r['model'], r['input_tokens'], r['output_tokens'], tabela)
        mes += valor
        if str(r['created_at']) >= inicio_dia:
            hoje += valor
        if not real:
            sem_preco.add(r['model'] or '(sem nome)')
    diario, mensal = caps(settings)
    motivo = ''
    if diario and hoje >= diario:
        motivo = (f'teto de gasto da IA de hoje atingido (US$ {hoje:.2f} de US$ {diario:.2f}). '
                  'Aumente o teto em Identidade → Escrita das falas, ou continue com o texto local.')
    elif mensal and mes >= mensal:
        motivo = (f'teto de gasto da IA do mês atingido (US$ {mes:.2f} de US$ {mensal:.2f}). '
                  'Aumente o teto em Identidade → Escrita das falas, ou continue com o texto local.')
    return {'today_usd': round(hoje, 4), 'month_usd': round(mes, 4), 'cap_daily_usd': diario,
            'cap_monthly_usd': mensal, 'unpriced_models': sorted(sem_preco),
            'prices': {k: list(v) for k, v in sorted(tabela.items())}, 'safety_price': list(SAFETY_PRICE),
            'blocked': motivo}
