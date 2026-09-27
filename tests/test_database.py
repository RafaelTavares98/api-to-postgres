"""The database is driven through a stand-in that records what it was asked.

Postgres itself is proved by `python run.py load`, which needs a server.
These tests prove the pipeline asks the right things of it, and they run
on a machine with no database at all.
"""

import pytest

from src.database import Database, INSERT_PROBLEM, INSERT_ROW, address


class Cursor:
    def __init__(self, log, answers):
        self.log = log
        self.answers = answers

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, values=None):
        self.log.append((statement, values))

    def fetchone(self):
        return self.answers.pop(0)


class Connection:
    """Remembers every statement, and how many times it was committed."""

    def __init__(self, answers=None):
        self.log = []
        self.answers = answers or []
        self.commits = 0

    def cursor(self):
        return Cursor(self.log, self.answers)

    def commit(self):
        self.commits += 1


ROW = {"id": "1", "aberto_em": None, "fechado_em": None,
       "tipo": "Noise", "bairro": "QUEENS", "detalhe": "Loud"}


def test_prepare_creates_the_tables_once():
    connection = Connection()
    Database(connection).prepare()
    assert "CREATE TABLE IF NOT EXISTS reclamacoes" in connection.log[0][0]
    assert connection.commits == 1


def test_a_row_is_written_as_an_upsert():
    connection = Connection()
    Database(connection).save([ROW], [])
    statement, values = connection.log[0]
    assert statement == INSERT_ROW
    assert "ON CONFLICT (id) DO UPDATE" in statement
    assert values == ROW


def test_the_same_row_twice_is_still_one_statement_per_row():
    connection = Connection()
    Database(connection).save([ROW, ROW], [])
    assert len(connection.log) == 2
    assert connection.commits == 1


def test_a_problem_is_written_and_never_doubled():
    connection = Connection()
    Database(connection).save([], [{"id": "1", "problema": "sem bairro"}])
    statement, values = connection.log[0]
    assert statement == INSERT_PROBLEM
    assert "DO NOTHING" in statement
    assert values["problema"] == "sem bairro"


def test_a_batch_is_one_transaction():
    connection = Connection()
    Database(connection).save([ROW, ROW, ROW], [{"id": "1", "problema": "x"}])
    assert connection.commits == 1


def test_an_empty_batch_touches_nothing_but_still_closes():
    connection = Connection()
    Database(connection).save([], [])
    assert connection.log == []
    assert connection.commits == 1


def test_count_and_newest_read_what_they_say_they_read():
    connection = Connection(answers=[(7,), ("2026-09-01",)])
    database = Database(connection)
    assert database.count() == 7
    assert database.newest() == "2026-09-01"
    assert "COUNT(*)" in connection.log[0][0]
    assert "MAX(aberto_em)" in connection.log[1][0]


def test_a_missing_address_fails_loudly_with_an_example(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError) as failure:
        address()
    assert "postgresql://" in str(failure.value)


def test_the_address_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://a:b@c/d")
    assert address() == "postgresql://a:b@c/d"
