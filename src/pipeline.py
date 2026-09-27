"""The order the steps run in: read, check, write, report.

Nothing here knows how an API paginates or how Postgres upserts. Those
live in their own files, and are handed in, so this file can be read in
one sitting and tested without either.
"""

import json

SOURCE = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"

# The API returns every column it has unless told otherwise. Asking for
# six instead of forty cuts the download by an order of magnitude.
COLUMNS = "unique_key,created_date,closed_date,complaint_type,borough,descriptor"


def parse(body):
    return json.loads(body.decode("utf-8"))


class Report:
    """What one run did, in numbers a person can check against the source."""

    def __init__(self):
        self.read = 0
        self.written = 0
        self.flagged = 0
        self.problems = {}
        self.calls = 0

    def add(self, flags):
        if flags:
            self.flagged += 1
        for flag in flags:
            # The flag carries the offending value, so "bairro desconhecido:
            # FOO" and "... BAR" are counted as the same kind of problem.
            kind = flag.split(":")[0]
            self.problems[kind] = self.problems.get(kind, 0) + 1

    def lines(self):
        out = [
            f"linhas lidas da API: {self.read}",
            f"linhas gravadas:     {self.written}",
            f"linhas com problema: {self.flagged}",
            f"chamadas a API:      {self.calls}",
        ]
        if self.problems:
            out.append("")
            out.append("problemas encontrados:")
            for kind, count in sorted(self.problems.items(), key=lambda kv: -kv[1]):
                out.append(f"  {count:>6}  {kind}")
        return out


def run(reader, database, clean, since=None, limit=None, batch=500):
    """Walk the API once, writing as it goes.

    Writing per page rather than at the end means an interrupted run keeps
    what it already had, and the next run picks up from the same key.
    """
    report = Report()
    params = {"$select": COLUMNS, "$order": "created_date DESC"}
    if since:
        params["$where"] = f"created_date > '{since:%Y-%m-%dT%H:%M:%S}'"

    rows, problems = [], []
    for page in reader.pages(params, parse, limit=limit):
        for raw in page:
            report.read += 1
            row, flags = clean(raw)
            report.add(flags)
            if not row["id"]:
                # Without a key there is nothing to write it against, and
                # a made-up key would break the second run.
                continue
            rows.append(row)
            problems.extend({"id": row["id"], "problema": f} for f in flags)
        if len(rows) >= batch:
            database.save(rows, problems)
            report.written += len(rows)
            rows, problems = [], []

    if rows or problems:
        database.save(rows, problems)
        report.written += len(rows)

    report.calls = reader.calls
    return report
