"""Put the rows in Postgres, and put them there only once.

The identifier the API gives is the key. Running the load again updates
the row it already has instead of adding a second one, so a run that is
interrupted can simply be run again.
"""

import os

TABLES = """
CREATE TABLE IF NOT EXISTS reclamacoes (
    id           TEXT PRIMARY KEY,
    aberto_em    TIMESTAMP,
    fechado_em   TIMESTAMP,
    tipo         TEXT,
    bairro       TEXT,
    detalhe      TEXT,
    carregado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS problemas (
    id        TEXT NOT NULL,
    problema  TEXT NOT NULL,
    visto_em  TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, problema)
);

CREATE INDEX IF NOT EXISTS reclamacoes_aberto_em ON reclamacoes (aberto_em);
CREATE INDEX IF NOT EXISTS reclamacoes_bairro ON reclamacoes (bairro);
"""

INSERT_ROW = """
INSERT INTO reclamacoes (id, aberto_em, fechado_em, tipo, bairro, detalhe)
VALUES (%(id)s, %(aberto_em)s, %(fechado_em)s, %(tipo)s, %(bairro)s, %(detalhe)s)
ON CONFLICT (id) DO UPDATE SET
    aberto_em  = EXCLUDED.aberto_em,
    fechado_em = EXCLUDED.fechado_em,
    tipo       = EXCLUDED.tipo,
    bairro     = EXCLUDED.bairro,
    detalhe    = EXCLUDED.detalhe
"""

INSERT_PROBLEM = """
INSERT INTO problemas (id, problema)
VALUES (%(id)s, %(problema)s)
ON CONFLICT (id, problema) DO NOTHING
"""


def address():
    """Where the database is, from the environment and nowhere else."""
    where = os.environ.get("DATABASE_URL")
    if not where:
        raise RuntimeError(
            "DATABASE_URL nao esta definida. "
            "Exemplo: postgresql://user:senha@localhost:5432/nyc")
    return where


class Database:
    """The table, behind the only four things the pipeline asks of it.

    The connection is handed in, so the tests run against a stand-in and
    the suite needs no Postgres.
    """

    def __init__(self, connection):
        self.connection = connection

    def prepare(self):
        with self.connection.cursor() as cursor:
            cursor.execute(TABLES)
        self.connection.commit()

    def save(self, rows, problems):
        """One batch, one transaction. A batch half written is no batch."""
        with self.connection.cursor() as cursor:
            for row in rows:
                cursor.execute(INSERT_ROW, row)
            for problem in problems:
                cursor.execute(INSERT_PROBLEM, problem)
        self.connection.commit()

    def count(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM reclamacoes")
            return cursor.fetchone()[0]

    def newest(self):
        """The most recent complaint held, so the next run starts there."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT MAX(aberto_em) FROM reclamacoes")
            return cursor.fetchone()[0]


def connect(url=None):
    """A real Postgres connection. Imported here so the tests never need it."""
    import psycopg

    return psycopg.connect(url or address())
