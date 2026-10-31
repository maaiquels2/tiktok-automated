"""Contrato da Gravacao da Campanha, o mesmo para o SQLite do computador e o Postgres da nuvem.

O SQLite roda sempre. O Postgres so roda com FABRICA_TEST_DATABASE_URL apontando para um Postgres DESCARTAVEL
(um container local, por exemplo); endereco que nao seja da propria maquina e recusado, a menos que
FABRICA_TEST_ALLOW_REMOTE=1 diga que e um banco de teste. Cada execucao cria e apaga um schema proprio.
"""
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import urlparse

from services.campaign_write import CONFLICT, CampaignWriter
from services.cloud_db import CloudConnection


class Refused(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


class Contract:
    """Os testes; cada banco entrega connect() e prepara o schema em setUp."""

    def connect(self):
        raise NotImplementedError

    def writer(self, conn):
        return CampaignWriter(lambda: conn, Refused)

    def seed(self):
        conn = self.connect()
        cid = conn.execute("INSERT INTO campaigns(name,status) VALUES('Original','briefing')").lastrowid
        conn.commit()
        conn.close()
        return cid

    def peek(self, cid):
        conn = self.connect()
        try:
            row = conn.execute('SELECT name,version FROM campaigns WHERE id=?', (cid,)).fetchone()
            notes = [r['text'] for r in conn.execute('SELECT text FROM notes WHERE campaign_id=?', (cid,)).fetchall()]
            return row['name'], row['version'], notes
        finally:
            conn.close()

    def test_write_raises_the_version_once_and_commits_what_the_route_wrote(self):
        cid = self.seed()
        conn = self.connect()
        with self.writer(conn).write(cid, {'version': 1}) as campaign:
            self.assertEqual((campaign['name'], campaign['version']), ('Original', 1))
            conn.execute('UPDATE campaigns SET name=? WHERE id=?', ('Novo', cid))
            conn.execute('INSERT INTO notes(campaign_id,text) VALUES(?,?)', (cid, 'nota'))
        conn.close()
        self.assertEqual(self.peek(cid), ('Novo', 2, ['nota']))

    def test_an_error_inside_the_block_undoes_everything_including_the_version(self):
        cid = self.seed()
        conn = self.connect()
        with self.assertRaises(Refused):
            with self.writer(conn).write(cid, {'version': 1}):
                conn.execute('UPDATE campaigns SET name=? WHERE id=?', ('Novo', cid))
                conn.execute('INSERT INTO notes(campaign_id,text) VALUES(?,?)', (cid, 'nota'))
                raise Refused('falhou no meio')
        conn.close()
        self.assertEqual(self.peek(cid), ('Original', 1, []))

    def test_a_stale_version_in_the_payload_is_refused_before_the_block_runs(self):
        cid = self.seed()
        conn = self.connect()
        ran = []
        with self.assertRaises(Refused) as caught:
            with self.writer(conn).write(cid, {'version': 7}):
                ran.append(True)
        self.assertEqual((caught.exception.status, caught.exception.message), (409, CONFLICT))
        self.assertEqual(ran, [])
        conn.close()
        self.assertEqual(self.peek(cid), ('Original', 1, []))

    def test_a_payload_without_version_is_accepted_and_a_bad_version_is_a_400(self):
        cid = self.seed()
        conn = self.connect()
        with self.writer(conn).write(cid, {}):
            pass
        with self.assertRaises(Refused) as caught:
            with self.writer(conn).write(cid, {'version': 'abc'}):
                pass
        self.assertEqual(caught.exception.status, 400)
        conn.close()
        self.assertEqual(self.peek(cid)[1], 2)

    def test_a_missing_campaign_is_a_404_for_read_and_for_write(self):
        conn = self.connect()
        writer = self.writer(conn)
        with self.assertRaises(Refused) as caught:
            writer.read(999)
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(Refused) as caught:
            with writer.write(999, expected_version=1):
                pass
        self.assertEqual(caught.exception.status, 404)
        conn.close()

    def test_read_does_not_open_a_transaction_or_change_anything(self):
        cid = self.seed()
        conn = self.connect()
        campaign = self.writer(conn).read(cid, {'version': 1})
        self.assertEqual(campaign['version'], 1)
        conn.close()
        self.assertEqual(self.peek(cid), ('Original', 1, []))

    def test_two_phase_write_after_a_long_call_refuses_when_someone_else_wrote_meanwhile(self):
        cid = self.seed()
        slow = self.connect()
        campaign = self.writer(slow).read(cid, {'version': 1})
        # Uma edicao termina enquanto a rota esperava a IA.
        other = self.connect()
        with self.writer(other).write(cid, {'version': 1}):
            other.execute('UPDATE campaigns SET name=? WHERE id=?', ('Mudou no meio', cid))
        other.close()
        # A rota lenta ja tinha gravado algo antes de abrir a gravacao: isso tambem some no 409.
        slow.execute('INSERT INTO notes(campaign_id,text) VALUES(?,?)', (cid, 'escrita antes do 409'))
        ran = []
        with self.assertRaises(Refused) as caught:
            with self.writer(slow).write(cid, expected_version=campaign['version']):
                ran.append(True)
        self.assertEqual((caught.exception.status, caught.exception.message), (409, CONFLICT))
        self.assertEqual(ran, [])
        # A propria conexao da rota ja nao enxerga a escrita feita antes do 409 (o rollback foi dado na hora).
        self.assertEqual(slow.execute('SELECT COUNT(*) AS n FROM notes WHERE campaign_id=?', (cid,)).fetchone()['n'], 0)
        self.assertFalse(getattr(slow, 'in_transaction', False))
        slow.close()
        self.assertEqual(self.peek(cid), ('Mudou no meio', 2, []))

    def test_two_writers_with_the_same_version_only_one_wins(self):
        cid = self.seed()
        first_inside, release = threading.Event(), threading.Event()
        results = {}

        def first():
            conn = self.connect()
            try:
                with self.writer(conn).write(cid, {'version': 1}):
                    conn.execute('UPDATE campaigns SET name=? WHERE id=?', ('primeiro', cid))
                    first_inside.set()
                    release.wait(10)
                results['first'] = 'ok'
            except Refused as error:
                results['first'] = error.status
            finally:
                conn.close()

        def second():
            conn = self.connect()
            try:
                with self.writer(conn).write(cid, {'version': 1}):
                    conn.execute('UPDATE campaigns SET name=? WHERE id=?', ('segundo', cid))
                results['second'] = 'ok'
            except Refused as error:
                results['second'] = error.status
            finally:
                conn.close()

        one = threading.Thread(target=first)
        one.start()
        self.assertTrue(first_inside.wait(10))
        two = threading.Thread(target=second)
        two.start()
        release.set()
        one.join(30)
        two.join(30)
        self.assertEqual(results, {'first': 'ok', 'second': 409})
        self.assertEqual(self.peek(cid), ('primeiro', 2, []))


SQLITE_SCHEMA = (
    'CREATE TABLE campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,status TEXT,'
    'version INTEGER NOT NULL DEFAULT 1,updated_at TEXT)',
    'CREATE TABLE notes(campaign_id INTEGER,text TEXT)',
)
POSTGRES_SCHEMA = (
    'CREATE TABLE campaigns(id SERIAL PRIMARY KEY,name TEXT,status TEXT,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT)',
    'CREATE TABLE notes(campaign_id INTEGER,text TEXT)',
)


class SqliteContract(Contract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'contract.db'
        with closing(sqlite3.connect(self.path)) as conn:
            for statement in SQLITE_SCHEMA:
                conn.execute(statement)
            conn.commit()

    def tearDown(self):
        self.temp.cleanup()

    def connect(self):
        # Igual ao connect() do app: linhas por nome e espera de ate 20 s pelo lock de escrita.
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def test_write_takes_the_write_lock_before_it_reads(self):
        # So no SQLite: la o lock vem do BEGIN IMMEDIATE. Outra gravacao muda a campanha sem subir a versao (como as
        # falas da sequencia no checklist); quem abre a Gravacao depois tem de ler o que ela deixou, nao a copia
        # de antes do lock. No Postgres o BEGIN nao faz nada e essa janela continua existindo.
        cid = self.seed()
        holder = self.connect()
        holder.execute('BEGIN IMMEDIATE')
        holder.execute('UPDATE campaigns SET name=? WHERE id=?', ('Mudou sem subir a versao', cid))
        seen = {}

        def open_write():
            conn = self.connect()
            try:
                with self.writer(conn).write(cid, {}) as campaign:
                    seen['name'] = campaign['name']
            finally:
                conn.close()

        thread = threading.Thread(target=open_write)
        thread.start()
        time.sleep(0.3)
        holder.commit()
        holder.close()
        thread.join(30)
        self.assertEqual(seen.get('name'), 'Mudou sem subir a versao')


def _postgres_url():
    url = os.environ.get('FABRICA_TEST_DATABASE_URL', '').strip()
    if not url:
        return ''
    host = (urlparse(url).hostname or '').lower()
    if host not in {'localhost', '127.0.0.1', '::1'} and os.environ.get('FABRICA_TEST_ALLOW_REMOTE') != '1':
        raise RuntimeError(
            'FABRICA_TEST_DATABASE_URL aponta para fora desta maquina. Use so um banco descartavel e defina '
            'FABRICA_TEST_ALLOW_REMOTE=1 para confirmar; nunca o banco de producao.')
    return url


@unittest.skipUnless(os.environ.get('FABRICA_TEST_DATABASE_URL', '').strip(),
                     'defina FABRICA_TEST_DATABASE_URL (Postgres descartavel) para rodar o contrato no Postgres')
class PostgresContract(Contract, unittest.TestCase):
    def setUp(self):
        import psycopg2
        self.psycopg2 = psycopg2
        self.url = _postgres_url()
        self.schema = 'contrato_' + uuid.uuid4().hex[:10]
        admin = psycopg2.connect(self.url)
        admin.autocommit = True
        admin.cursor().execute(f'CREATE SCHEMA {self.schema}')
        admin.close()
        conn = self.connect()
        for statement in POSTGRES_SCHEMA:
            conn.execute(statement)
        conn.commit()
        conn.close()

    def tearDown(self):
        admin = self.psycopg2.connect(self.url)
        admin.autocommit = True
        admin.cursor().execute(f'DROP SCHEMA {self.schema} CASCADE')
        admin.close()

    def connect(self):
        from psycopg2.extras import RealDictCursor
        raw = self.psycopg2.connect(self.url, cursor_factory=RealDictCursor, options=f'-c search_path={self.schema}')
        return CloudConnection(raw)


if __name__ == '__main__':
    unittest.main()
