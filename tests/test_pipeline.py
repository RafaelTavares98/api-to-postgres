"""The whole walk, from a stand-in API to a stand-in database."""

import json
from datetime import datetime

from src.pipeline import Report, parse, run
from src.row_check import clean


class Reader:
    """Hands out prepared pages and counts how often it was asked."""

    def __init__(self, pages):
        self.given = pages
        self.calls = 0
        self.params = None

    def pages(self, params, parse_fn, limit=None):
        self.params = params
        for page in self.given:
            self.calls += 1
            yield parse_fn(json.dumps(page).encode("utf-8"))


class Store:
    def __init__(self):
        self.rows = []
        self.problems = []
        self.saves = 0

    def save(self, rows, problems):
        self.rows.extend(rows)
        self.problems.extend(problems)
        self.saves += 1


def raw(key, **over):
    row = {
        "unique_key": key,
        "created_date": "2026-09-01T10:00:00.000",
        "closed_date": "2026-09-02T10:00:00.000",
        "complaint_type": "Noise",
        "borough": "QUEENS",
        "descriptor": "Loud",
    }
    row.update(over)
    return row


def test_every_row_reaches_the_database():
    store = Store()
    report = run(Reader([[raw("1"), raw("2")], [raw("3")]]), store, clean)
    assert report.read == 3
    assert report.written == 3
    assert [r["id"] for r in store.rows] == ["1", "2", "3"]


def test_a_flagged_row_is_written_with_its_problem():
    store = Store()
    report = run(Reader([[raw("1", borough="")]]), store, clean)
    assert report.written == 1
    assert report.flagged == 1
    assert store.problems == [{"id": "1", "problema": "sem bairro"}]


def test_a_row_with_no_key_is_left_out_but_still_counted():
    store = Store()
    report = run(Reader([[raw(""), raw("2")]]), store, clean)
    assert report.read == 2
    assert report.written == 1
    assert report.flagged == 1


def test_the_batch_is_written_before_the_walk_ends():
    store = Store()
    pages = [[raw(str(i)) for i in range(3)] for _ in range(3)]
    run(Reader(pages), store, clean, batch=2)
    # Three pages of three rows, written in batches of two, is more than
    # one save. An interrupted run therefore keeps something.
    assert store.saves > 1


def test_nothing_read_means_nothing_written():
    store = Store()
    report = run(Reader([]), store, clean)
    assert report.read == 0
    assert store.saves == 0


def test_since_becomes_a_filter_the_api_understands():
    reader = Reader([])
    run(reader, Store(), clean, since=datetime(2026, 9, 1, 10))
    assert reader.params["$where"] == "created_date > '2026-09-01T10:00:00'"


def test_without_since_no_filter_is_sent():
    reader = Reader([])
    run(reader, Store(), clean)
    assert "$where" not in reader.params


def test_only_the_six_columns_are_asked_for():
    reader = Reader([])
    run(reader, Store(), clean)
    assert reader.params["$select"].count(",") == 5


def test_the_report_groups_a_problem_by_its_kind_not_its_value():
    report = Report()
    report.add(["bairro desconhecido: FOO"])
    report.add(["bairro desconhecido: BAR"])
    assert report.problems == {"bairro desconhecido": 2}


def test_the_report_prints_the_worst_problem_first():
    report = Report()
    report.add(["sem bairro"])
    report.add(["sem bairro"])
    report.add(["sem tipo de reclamacao"])
    printed = "\n".join(report.lines())
    assert printed.index("sem bairro") < printed.index("sem tipo")


def test_parse_reads_what_the_api_sends():
    assert parse(b'[{"a": 1}]') == [{"a": 1}]
