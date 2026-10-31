"""Adaptador do Postgres (Supabase) para a "linguagem" SQLite que o app fala.

Faz uma conexao psycopg2 responder a .execute(sql, params) com '?' no lugar de '%s', .commit()/.rollback()/.close() e
linhas que aceitam row['coluna'] e row[0]. BEGIN vira no-op: o Postgres ja abre a transacao sozinho.
Fica fora de create_app para o teste de contrato da Gravacao da Campanha poder usar os dois bancos.
"""
import re


class CloudRow(dict):
    """Uma linha vinda do Postgres que aceita tanto row['coluna'] quanto
    row[0], do jeito que o sqlite3.Row ja se comportava no app local."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return dict.__getitem__(self, key)

def adapt_sql(query):
    text = query.strip()
    upper = text.upper()
    if upper.startswith('BEGIN'):
        return 'BEGIN', False
    if 'INSERT OR IGNORE INTO' in upper:
        text = re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', text, flags=re.IGNORECASE)
        text = text.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    want_id = bool(re.match(r'insert\s+into\s+(campaigns|users)\b', text, re.IGNORECASE)) and 'RETURNING' not in text.upper()
    # As colunas de data/hora do schema sao TEXT (formato 'YYYY-MM-DD HH24:MI:SS'),
    # mas o CURRENT_TIMESTAMP puro do Postgres retorna timestamptz, o que quebra
    # COALESCE(coluna_text, CURRENT_TIMESTAMP) com erro de tipo incompativel.
    text = re.sub(
        r'\bCURRENT_TIMESTAMP\b',
        "to_char(now() at time zone 'utc','YYYY-MM-DD HH24:MI:SS')",
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace('?', '%s')
    if want_id:
        text = text.rstrip().rstrip(';') + ' RETURNING id'
    return text, want_id

class CloudCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.lastrowid = None
    def execute(self, query, params=()):
        text, want_id = adapt_sql(query)
        if text == 'BEGIN':
            return self
        self._cursor.execute(text, tuple(params))
        if want_id:
            row = self._cursor.fetchone()
            self.lastrowid = row['id'] if row else None
        return self
    def fetchone(self):
        row = self._cursor.fetchone()
        return CloudRow(row) if row is not None else None
    def fetchall(self):
        return [CloudRow(r) for r in self._cursor.fetchall()]
    def __iter__(self):
        return iter(self.fetchall())
    @property
    def rowcount(self):
        return self._cursor.rowcount

class CloudConnection:
    """Faz uma conexao psycopg2 (Postgres/Supabase) responder a mesma
    'linguagem' que o resto do app ja fala com sqlite3: .execute(sql,params)
    com '?' no lugar de '%s', .commit()/.rollback()/.close(), e cursores que
    aceitam tanto row['coluna'] quanto row[0]."""
    def __init__(self, pg_conn):
        self._conn = pg_conn
    def execute(self, query, params=()):
        cursor = CloudCursor(self._conn.cursor())
        return cursor.execute(query, params)
    def commit(self):
        self._conn.commit()
    def rollback(self):
        self._conn.rollback()
    def close(self):
        self._conn.close()
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
