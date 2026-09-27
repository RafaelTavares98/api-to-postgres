# An API into a database, and safe to run twice

Somebody has a public API and wants the data in Postgres, refreshed on a
schedule. The hard part is never the first run. It is the second one, the
one that must not double every row, and the one that has to survive a
server that says "not so fast".

This does both, against a real API with millions of rows.

## What it does

```
API -> every page -> check each row -> Postgres
                          |
                          problem -> its own table, never a dropped row
```

1. Walks the API page by page until a short page says the end.
2. Waits when the server says to wait, and tries again.
3. Turns each record into a row, and names what is wrong with it.
4. Writes on the API's own key, so a second run updates, never doubles.
5. Prints what it read, what it wrote, and every problem it found.

## Try it

You need Postgres running and Python 3.10 or newer.

```bash
pip install -r requirements.txt
createdb nyc311
set DATABASE_URL=postgresql://postgres:senha@localhost:5432/nyc311
python run.py load --limit 2000
```

That reads New York's 311 complaints, which need no key and no account.
Run it again and the count does not move.

```bash
python run.py load --new
```

`--new` asks the API only for what arrived after the newest row already
held, so a daily run costs a few calls rather than a full download.

## What one real run did

Against the live feed, on 2026-09-26:

| | |
| --- | --- |
| Rows read from the API | 2000 |
| Rows written | 2000 |
| Rows with a problem | 6 |
| API calls | 4 |
| Rows after running it a second time | 2000 |

The last line is the whole argument. Six problems: five complaints filed
with no borough, one closed before it was opened. All six are in the
table, flagged, because a row the software hides is a row nobody checks.

## The checks

| Check | What it catches |
| --- | --- |
| Identifier present | A record with nothing to write it against |
| Nothing invented | A gap is left empty and reported |
| Date readable | A date the API printed in a shape nobody expects |
| Closed after opened | A complaint closed before it was filed |
| Borough known | A value outside the five boroughs of New York City |
| Type present | A complaint with no kind |
| Spacing squeezed | `Noise -  Residential` vs `Noise - Residential` |

The last one matters more than it looks. Two spaces and one space are the
same thing to a person and two different rows to a `GROUP BY`.

## Two tables

`reclamacoes` is one row per complaint, keyed on the API's own identifier.

`problemas` is one row per defect, keyed on the identifier and the defect,
so re-running never writes the same complaint twice.

```sql
SELECT p.problema, COUNT(*)
FROM problemas p
GROUP BY 1 ORDER BY 2 DESC;
```

## Look at what arrived

```bash
python run.py show
```

Five summaries, printed as text: by day, by borough, by type, average
hours to close by borough, and the problems found. The queries live in
`src/queries.py`, so each one can be read and run by hand in psql.

## Tests

```bash
python -m pytest
```

38 tests, none of which open a socket or a database. The API is a
stand-in that hands out prepared pages, and Postgres is a stand-in that
records the statements it was asked to run. A test suite that needs a
server is a suite nobody runs.

What they prove: every page is read, a short page ends the walk, a busy
server is tried again, a refusal is raised rather than swallowed, a batch
is one transaction, and a flagged row is still written.

## Running it every day

There is no scheduler here on purpose. `--new` makes the job safe to run
from cron, Task Scheduler, or a GitHub Action, and those already exist on
every machine it would run on.

```bash
0 6 * * *  cd /srv/nyc && python run.py load --new
```

If the job dies halfway, the next run finds the newest row it managed to
write and carries on from there. No state is kept outside the table
itself, and nothing has to be cleaned up. A run that needs a lock file
or a marker breaks the first time a machine restarts.

## Decisions worth knowing

**The key is the API's, not ours.** `ON CONFLICT (id) DO UPDATE` is what
makes the second run safe. A row identified by its position would break
the moment the source reordered.

**Each page is written before the next is asked for.** An interrupted run
keeps what it already had, and `--new` picks up from there.

**A refusal is raised, not logged.** A half-filled table that reports
success is worse than a run that stops and says which call failed.

**429 and 5xx are tried again; 4xx is not.** Repeating a request the
server already refused on its merits will not change the answer.

**Six columns are requested, not forty.** The API returns everything it
has unless told otherwise, and the download is an order of magnitude
smaller for it.

**The network and the clock are passed in.** That is the only reason the
tests run in a fifth of a second with nothing installed.

**A row with no identifier is counted and left out.** Inventing a key
would break every run after this one.

**The problems live in their own table, not a log file.** A defect you
can query is a defect somebody will eventually fix. A defect printed to a
terminal that scrolled away last Tuesday is not one.

**Nothing is deleted, ever.** A row that arrives changed is updated where
it sits, so the table always matches the source as the source stands now,
and no history is thrown out.

**The database address comes from the environment.** There is no default
of `localhost`, so a misconfigured machine fails loudly instead of
quietly writing somewhere nobody meant.

## Layout of the code

```
run.py                 the command line
src/
  api_reader.py        paging, waiting, and giving up loudly
  row_check.py         one record turned into one row, with its faults
  database.py          the two tables and the upsert
  pipeline.py          the order the steps run in
  queries.py           the five summaries, as plain SQL
tests/
```

## Pointing it somewhere else

The source is one line in `src/pipeline.py`. Any API that pages with
`$limit` and `$offset` works as it stands; another paging style is one
change, to `ApiReader.pages`, and nothing else moves.
