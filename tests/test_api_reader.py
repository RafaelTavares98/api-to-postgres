"""The reader is driven against a stand-in server, never the internet."""

import json

import pytest

from src.api_reader import ApiReader, ApiRefused


def rows_of(body):
    return json.loads(body.decode("utf-8"))


class Server:
    """A server that hands out a fixed set of rows, page by page."""

    def __init__(self, rows, fail_with=None, fail_times=0):
        self.rows = rows
        self.fail_with = fail_with
        self.fail_times = fail_times
        self.seen = []

    def __call__(self, url):
        self.seen.append(url)
        if self.fail_times:
            self.fail_times -= 1
            return self.fail_with, b""
        limit = int(url.split("%24limit=")[1].split("&")[0])
        offset = int(url.split("%24offset=")[1].split("&")[0])
        page = self.rows[offset:offset + limit]
        return 200, json.dumps(page).encode("utf-8")


def reader(server, **kwargs):
    kwargs.setdefault("page_size", 2)
    return ApiReader("https://example.test/data", opener=server,
                     sleep=lambda _: None, **kwargs)


def test_reads_every_row_across_pages():
    server = Server([{"n": i} for i in range(5)])
    got = [row for page in reader(server).pages({}, rows_of) for row in page]
    assert [row["n"] for row in got] == [0, 1, 2, 3, 4]


def test_stops_on_a_short_page_without_asking_again():
    server = Server([{"n": 0}])
    list(reader(server).pages({}, rows_of))
    assert len(server.seen) == 1


def test_an_empty_first_page_yields_nothing():
    server = Server([])
    assert list(reader(server).pages({}, rows_of)) == []


def test_a_busy_server_is_tried_again():
    server = Server([{"n": 0}], fail_with=429, fail_times=2)
    got = list(reader(server).pages({}, rows_of))
    assert got == [[{"n": 0}]]
    assert len(server.seen) == 3


def test_a_refusal_is_raised_not_swallowed():
    server = Server([], fail_with=404, fail_times=1)
    with pytest.raises(ApiRefused) as failure:
        list(reader(server).pages({}, rows_of))
    assert "404" in str(failure.value)


def test_giving_up_says_how_many_tries_it_took():
    server = Server([], fail_with=503, fail_times=99)
    with pytest.raises(ApiRefused) as failure:
        list(reader(server).pages({}, rows_of))
    assert "failed 4 times" in str(failure.value)


def test_the_limit_stops_the_walk_early():
    server = Server([{"n": i} for i in range(10)])
    got = list(reader(server).pages({}, rows_of, limit=4))
    assert sum(len(page) for page in got) == 4
