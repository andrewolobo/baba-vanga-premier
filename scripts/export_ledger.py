"""Export the gate ledger to a tracked text file.

    python scripts/export_ledger.py            # write docs/gate_ledger.jsonl
    python scripts/export_ledger.py --check    # verify the file matches the DB
    python scripts/export_ledger.py --restore  # load the file: empty ledger, or append what a prefix lacks

**Why this exists.** `db/premier.db` is 44 MB and all of it is reproducible from
the tracked CSVs by `engine.ingest.build` -- *except* `gate_ledger`, which is a
record of which measurements were run and therefore cannot be derived from the
data at all. It lives in one gitignored file on one machine.

`DEFLATION.md`'s multiplicity accounting reads it, `OUTSTANDING.md` §0 instructs
every future thread to re-derive the count with `trials.count_configurations`
*rather than trusting the prose* -- which makes that table the authority -- and
the pre-committed P6 read depends on it.

The whole ledger is a couple of hundred KB of text. So the honest backup is not
a 44 MB binary copied to object storage on a timer: it is a small, diffable,
sorted text file in the repository, for which git and GitHub already provide
off-machine durability and history. `docs/DEPLOY.md` §6.1 covers the server's
database, which holds a different irreplaceable thing (what was predicted, and
when).

**This is an export, and `--restore` is its one narrow inverse.** `OUTSTANDING.md`
§7.5 makes the ledger append-only and says a helper to update or delete it
"would defeat the purpose". `--restore` is neither: it **refuses unless
`gate_ledger` is empty or an exact prefix of the file**, then loads the rows
the ledger lacks with their original ids and timestamps and verifies the result
matches. The empty case is reconstitution of a store that was rebuilt from the
CSVs (`engine.ingest.build` does not load this table) -- owner decision
2026-08-15, taken when a fresh machine's first gate would otherwise have
written row 1 instead of row 105. The prefix case is a second development
machine catching up on rows that arrived by `git pull` -- owner decision
2026-08-17, when this machine held 104 rows against the file's 109. Neither is
mutation of one that has history: there is still no path that touches an
existing row.

Output is ordered by `id` with sorted keys, so an appended row is a one-line
diff and a *changed* row is visible as a change -- which is the property that
makes an append-only claim auditable rather than asserted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

# Invoked by path, as scripts/build_team_aliases.py is, so the repo root is not
# on sys.path and `engine` is not importable without this. Matches that file
# rather than requiring `python -m`, because RUNBOOK.md already documents the
# path form for the other script in this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import config, db  # noqa: E402

OUT = config.REPO_ROOT / "docs" / "gate_ledger.jsonl"

#: Every column, named rather than `SELECT *`, so a schema addition is a
#: deliberate change to this file instead of a silent change to the export.
COLUMNS = ("id", "created_at", "kind", "name", "purpose", "seasons",
           "divisions", "detail", "reason")


def rows(conn: sqlite3.Connection) -> list[dict]:
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(
        f"SELECT {','.join(COLUMNS)} FROM gate_ledger ORDER BY id")]


def render(records: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def classify(on_disk: str, text: str) -> str:
    """How the file relates to the database: MATCHES, BEHIND (the DB has
    appended rows the file lacks), AHEAD (the file has rows the DB lacks),
    or DISAGREES (a row both hold differs)."""
    if on_disk == text:
        return "MATCHES"
    had, has = on_disk.splitlines(), text.splitlines()
    if has[:len(had)] == had:
        return "BEHIND"
    if had[:len(has)] == has:
        return "AHEAD"
    return "DISAGREES"


def restore(conn: sqlite3.Connection, path: Path) -> int:
    """Load the file's rows into the ledger. Returns rows written.

    Two cases are allowed and one is refused. An EMPTY ledger takes the whole
    file (a fresh machine). A ledger whose rows are an exact PREFIX of the file
    takes only the tail -- the case where a gate ran on another machine and its
    rows arrived by `git pull` (2026-08-17: rows 105-109 were written on a
    second development machine and this one held 104). Anything else -- rows
    here the file lacks, or rows that disagree -- is refused rather than merged:
    reconciling two histories is exactly the update path the append-only
    convention forbids. Ids and timestamps are written as exported, so
    `--check` passes afterwards and the next gate lands on the next id.
    """
    records = [json.loads(line) for line in
               path.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing = rows(conn)
    if existing and render(records[:len(existing)]) != render(existing):
        raise SystemExit(f"refusing: gate_ledger holds {len(existing)} row(s) that are "
                         "not a prefix of the file; the ledger is append-only, so "
                         "investigate rather than merge")
    missing = records[len(existing):]
    conn.executemany(
        f"INSERT INTO gate_ledger ({','.join(COLUMNS)}) "
        f"VALUES ({','.join('?' for _ in COLUMNS)})",
        [tuple(r[c] for c in COLUMNS) for r in missing])
    conn.commit()
    if render(rows(conn)) != render(records):
        raise SystemExit("restore wrote rows that do not read back identically")
    return len(missing)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare the DB against the file; write nothing")
    parser.add_argument("--restore", action="store_true",
                        help="load the file into an EMPTY gate_ledger, or append "
                             "the rows an exact-prefix ledger is missing")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    if args.restore:
        conn = db.connect()
        db.migrate(conn)
        n = restore(conn, args.out)
        print(f"restored {n} row(s) from {config.relpath(args.out)}")
        return 0

    records = rows(db.connect())
    text = render(records)
    print(f"{len(records)} row(s), {len(text.encode('utf-8'))} bytes, "
          f"sha256:{digest(text)}")

    if args.check:
        if not args.out.exists():
            print(f"MISSING {config.relpath(args.out)}", file=sys.stderr)
            return 1
        on_disk = args.out.read_text(encoding="utf-8")
        shape = classify(on_disk, text)
        if shape == "MATCHES":
            print(f"{config.relpath(args.out)} matches the database")
            return 0
        # Report the shape of the difference rather than just "differs": a
        # ledger that has GAINED rows is the normal case and wants an export;
        # a file that is AHEAD means a gate ran on another machine and its rows
        # arrived by `git pull`, and wants --restore; one that has LOST or
        # CHANGED rows is the thing the append-only convention exists to
        # prevent, and the three need different reactions.
        had, has = len(on_disk.splitlines()), len(text.splitlines())
        if shape == "BEHIND":
            print(f"file is BEHIND by {has - had} appended row(s) "
                  f"-- re-run without --check")
        elif shape == "AHEAD":
            print(f"file is AHEAD by {had - has} row(s) -- the ledger was "
                  f"appended to elsewhere; re-run with --restore to load them")
        else:
            print("file DISAGREES on rows it already had -- the ledger is "
                  "append-only, so investigate before overwriting",
                  file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {config.relpath(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
