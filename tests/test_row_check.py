"""Every check is proved on a row that fails it and one that does not."""

from datetime import datetime

from src.row_check import clean, read_date

GOOD = {
    "unique_key": "12345",
    "created_date": "2026-09-01T10:00:00.000",
    "closed_date": "2026-09-03T14:30:00.000",
    "complaint_type": "Noise -  Residential",
    "borough": "brooklyn",
    "descriptor": "Loud Music",
}


def test_a_good_row_carries_no_flag():
    row, flags = clean(GOOD)
    assert flags == []
    assert row["id"] == "12345"
    assert row["bairro"] == "BROOKLYN"


def test_repeated_spaces_are_squeezed_out():
    row, _ = clean(GOOD)
    assert row["tipo"] == "Noise - Residential"


def test_a_missing_identifier_is_named():
    _, flags = clean({**GOOD, "unique_key": ""})
    assert "sem identificador" in flags


def test_a_date_the_api_mangled_is_named_not_guessed():
    row, flags = clean({**GOOD, "created_date": "01/09/2026"})
    assert "data de abertura ilegivel" in flags
    assert row["aberto_em"] is None


def test_closing_before_opening_is_caught():
    _, flags = clean({**GOOD, "closed_date": "2026-08-01T00:00:00.000"})
    assert "fechado antes de abrir" in flags


def test_an_open_complaint_is_not_a_fault():
    row, flags = clean({**GOOD, "closed_date": None})
    assert flags == []
    assert row["fechado_em"] is None


def test_an_unknown_borough_is_named_with_its_value():
    _, flags = clean({**GOOD, "borough": "Unspecified"})
    assert "bairro desconhecido: UNSPECIFIED" in flags


def test_a_missing_borough_is_its_own_flag():
    _, flags = clean({**GOOD, "borough": ""})
    assert "sem bairro" in flags


def test_a_missing_type_is_named():
    _, flags = clean({**GOOD, "complaint_type": None})
    assert "sem tipo de reclamacao" in flags


def test_a_flagged_row_is_still_a_row():
    row, flags = clean({**GOOD, "borough": "", "complaint_type": ""})
    assert len(flags) == 2
    assert row["id"] == "12345"


def test_read_date_takes_the_three_shapes_the_api_uses():
    assert read_date("2026-09-01") == datetime(2026, 9, 1)
    assert read_date("2026-09-01T10:00:00") == datetime(2026, 9, 1, 10)
    assert read_date("2026-09-01T10:00:00.000") == datetime(2026, 9, 1, 10)
    assert read_date("") is None
