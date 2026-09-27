"""Decide what each row is worth before it reaches the table.

A row that fails a check is still written, flagged. A row the software
drops in silence is a row nobody ever goes looking for.
"""

from datetime import datetime

WANTED = {
    "unique_key": "id",
    "created_date": "aberto_em",
    "closed_date": "fechado_em",
    "complaint_type": "tipo",
    "borough": "bairro",
    "descriptor": "detalhe",
}

BOROUGHS = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"}


def read_date(value):
    """A date the API printed, or None when it printed something else."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "")
    for shape in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, shape)
        except ValueError:
            continue
    return None


def clean(raw):
    """One API row turned into one table row, with what is wrong named.

    Returns the row and a list of flags. The flags are sentences a person
    can act on, not codes.
    """
    row = {ours: (raw.get(theirs) or None) for theirs, ours in WANTED.items()}
    flags = []

    if not row["id"]:
        flags.append("sem identificador")

    opened = read_date(row["aberto_em"])
    closed = read_date(row["fechado_em"])
    if row["aberto_em"] and not opened:
        flags.append("data de abertura ilegivel")
    if row["fechado_em"] and not closed:
        flags.append("data de fechamento ilegivel")
    if opened and closed and closed < opened:
        flags.append("fechado antes de abrir")
    row["aberto_em"] = opened
    row["fechado_em"] = closed

    if not row["tipo"]:
        flags.append("sem tipo de reclamacao")

    if row["bairro"]:
        bairro = str(row["bairro"]).strip().upper()
        row["bairro"] = bairro
        if bairro not in BOROUGHS:
            flags.append(f"bairro desconhecido: {bairro}")
    else:
        flags.append("sem bairro")

    for field in ("tipo", "detalhe"):
        if row[field]:
            # Two spaces and a trailing blank are the same value to a
            # person and two different values to a GROUP BY.
            row[field] = " ".join(str(row[field]).split())

    return row, flags
