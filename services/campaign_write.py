"""Gravacao da Campanha: um bloco de escrita que so vale se ninguem mudou a Campanha nesse meio tempo.

Todas as rotas que mudam uma Campanha seguiam o mesmo roteiro, escrito a mao em cada uma: ler a Campanha, conferir a
versao que a tela mandou, trabalhar, subir a versao e confirmar. Aqui esse roteiro vive num lugar so, igual para o
SQLite do computador e para o Postgres da nuvem:

    with writer.write(cid, payload) as campanha:
        ...grava o que a rota precisa...          # a versao sobe uma vez, ao abrir
                                                   # saiu sem erro: confirma; levantou erro: desfaz tudo

Rotas que chamam a IA (segundos) nao podem segurar a gravacao durante a chamada. Elas leem antes, sem abrir nada, e
so abrem a gravacao depois, com a versao que leram:

    campanha = writer.read(cid, payload)           # nao abre transacao
    ...chamada longa...
    with writer.write(cid, expected_version=campanha['version']):
        ...

Regra de concorrencia, a mesma nos dois bancos: ao abrir, um UPDATE ... WHERE version=? "reivindica" a versao. Quem
chega depois nao encontra a versao esperada e recebe 409 antes de gravar qualquer coisa. No SQLite o arquivo serializa
os gravadores (o BEGIN IMMEDIATE sai do roteiro das rotas e fica aqui); no Postgres o UPDATE espera a linha da outra
gravacao e, depois do commit dela, nao acha mais a versao.

O modulo nao importa o Flask: recebe a funcao que devolve a conexao do pedido e a fabrica do erro da aplicacao.
Arquivos gravados em disco fora do banco nao entram na transacao.
"""
from contextlib import contextmanager

CONFLICT = 'A campanha mudou em outra janela. Recarregue antes de salvar.'
NOT_FOUND = 'Campanha não encontrada.'


class CampaignWriter:
    def __init__(self, db, error):
        """``db()`` devolve a conexao do pedido; ``error(mensagem, status)`` devolve a excecao da aplicacao."""
        self._db = db
        self._error = error

    def read(self, cid, payload=None):
        """A Campanha como dict, conferida contra a versao de ``payload`` (se houver). Nao abre transacao."""
        row = self._db().execute('SELECT * FROM campaigns WHERE id=?', (cid,)).fetchone()
        if not row:
            raise self._error(NOT_FOUND, 404)
        campaign = dict(row)
        if payload and 'version' in payload:
            try:
                version = int(payload['version'])
            except (TypeError, ValueError):
                raise self._error('Versão inválida.', 400)
            if version != campaign['version']:
                raise self._error(CONFLICT, 409)
        return campaign

    @contextmanager
    def write(self, cid, payload=None, expected_version=None):
        """Abre a gravacao, entrega a Campanha lida e confirma ao sair; qualquer erro desfaz tudo o que ela gravou.

        Sem ``expected_version``, le a Campanha agora e confere ``payload``. Com ele (rotas de IA), usa a versao que a
        rota leu antes da chamada longa.
        """
        campaign = None
        if expected_version is None:
            # Pega o lock de escrita (SQLite) antes de ler: outras gravacoes mexem no checklist sem subir a versao,
            # e uma leitura feita antes do lock podia ser apagada pela rota. No Postgres o BEGIN nao faz nada.
            self._begin()
            try:
                campaign = self.read(cid, payload)
            except BaseException:
                self._db().rollback()
                raise
            expected_version = campaign['version']
        self._claim(cid, expected_version)
        db = self._db()
        try:
            yield campaign
        except BaseException:
            db.rollback()
            raise
        db.commit()

    def _begin(self):
        db = self._db()
        # SQLite: pega o lock de escrita agora, nao na primeira escrita que sobrar. Na nuvem BEGIN e no-op.
        if not getattr(db, 'in_transaction', False):
            db.execute('BEGIN IMMEDIATE')

    def _claim(self, cid, expected_version):
        db = self._db()
        self._begin()
        claimed = db.execute(
            'UPDATE campaigns SET updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE id=? AND version=?',
            (cid, expected_version))
        if claimed.rowcount == 0:
            exists = db.execute('SELECT 1 FROM campaigns WHERE id=?', (cid,)).fetchone()
            # Desfaz tambem o que a rota ja gravou antes de abrir a gravacao (um 409 tardio nao deixa meia operacao).
            db.rollback()
            if not exists:
                raise self._error(NOT_FOUND, 404)
            raise self._error(CONFLICT, 409)
