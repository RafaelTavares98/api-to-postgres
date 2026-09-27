"""The command line: load the table, then look at it.

    python run.py prepare          create the tables
    python run.py load             fetch and write, newest first
    python run.py load --new       only what arrived since the last run
    python run.py load --limit 500 stop after this many rows
    python run.py show             print the five summaries
"""

import argparse
import sys

from src.api_reader import ApiReader, ApiRefused
from src.database import Database, connect
from src.pipeline import SOURCE, run
from src.queries import TODAS, ask
from src.row_check import clean


def table(names, rows, width=22):
    out = ["  ".join(str(n)[:width].ljust(width) for n in names)]
    out.append("  ".join("-" * width for _ in names))
    for row in rows:
        out.append("  ".join(str(v)[:width].ljust(width) for v in row))
    return "\n".join(out)


def cmd_prepare(args):
    with connect() as connection:
        Database(connection).prepare()
    print("tabelas criadas")


def cmd_load(args):
    with connect() as connection:
        database = Database(connection)
        database.prepare()
        since = database.newest() if args.new else None
        if args.new and since is None:
            print("a tabela esta vazia, carregando tudo")
        reader = ApiReader(SOURCE, page_size=args.page)
        try:
            report = run(reader, database, clean, since=since, limit=args.limit)
        except ApiRefused as refusal:
            # The rows already written stay written. Saying which call
            # failed is the difference between a retry and a guess.
            print(f"a API recusou: {refusal}", file=sys.stderr)
            return 1
        print("\n".join(report.lines()))
        print(f"\nlinhas na tabela agora: {database.count()}")
    return 0


def cmd_show(args):
    with connect() as connection:
        for title, statement in TODAS.items():
            names, rows = ask(connection, statement)
            print(f"\n== {title} ==")
            print(table(names, rows[:12]))
            if len(rows) > 12:
                print(f"... e mais {len(rows) - 12} linhas")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    jobs = parser.add_subparsers(dest="job", required=True)

    jobs.add_parser("prepare").set_defaults(go=cmd_prepare)

    load = jobs.add_parser("load")
    load.add_argument("--new", action="store_true",
                      help="so o que chegou depois da ultima carga")
    load.add_argument("--limit", type=int, default=5000,
                      help="para depois de tantas linhas")
    load.add_argument("--page", type=int, default=1000,
                      help="linhas por chamada a API")
    load.set_defaults(go=cmd_load)

    jobs.add_parser("show").set_defaults(go=cmd_show)

    args = parser.parse_args(argv)
    return args.go(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
