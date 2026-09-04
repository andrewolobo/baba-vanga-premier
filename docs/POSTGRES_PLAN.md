# POSTGRES_PLAN — moving the store from SQLite to Postgres

Written **2026-09-04**, before anything was built. Owner request: migrate
the database to Postgres to enable later features (user sign-in); recommend
an approach (ORM or not, migration scripts), name the pitfalls, and plan the
change **on the production server, carrying its data across**. This file is
the assessment and the plan; nothing in it has run.

Reading order for a thread picking this up: `STATE.md` → this file →
`engine/db.py` (the whole access layer today) → `scripts/deploy.sh` and
`deploy/systemd/` (what runs on the VM) → `DEPLOY.md` §6.1 (why the serving
database is the one irreplaceable thing there).

---

## 0. The recommendation, in one paragraph

**Do it, without an ORM.** Replace the `sqlite3` driver with **psycopg 3**,
keep raw SQL and the forward-only `.sql` migration runner that already exist,
run **Postgres on the same VM** for now, copy the production data with a
purpose-written script that **verifies what it copied**, and cut over
**between matchdays** with the SQLite file left untouched as the rollback.
Sequelize is the wrong tool for this codebase (§1.1). The work is about a
week including a full rehearsal on a copy of production, and most of it is
one mechanical pass over ~70 SQL call sites in 20 files — the access layer
was written to make this "a connection-string change rather than a rewrite"
(`engine/db.py` docstring), and that promise mostly holds, with the
exceptions catalogued in §3.

## 1. Assessment

### 1.1 Sequelize does not fit; no ORM does, yet

Every byte that touches the database is **Python**: `engine/` (ingest, eval,
serve), `services/` (the cycle, the graders, the scrapers), `api/` (FastAPI)
and `scripts/`. The web tier is a **static SvelteKit build**
(`adapter-static`, `web/svelte.config.js`) served by nginx; there is no Node
process on the server. Sequelize is a Node ORM. Adopting it would mean either
a second runtime that owns the schema while Python owns the data, or moving
the API to Node. Neither is a database migration; both are a rewrite.

An ORM on the Python side (SQLAlchemy ORM, Django, Peewee) is also not
recommended for this move:

- The queries are **analytical** — `CASE`/`SUM` aggregations over tips,
  `NOT EXISTS` anti-joins, frames read straight into pandas. An ORM adds an
  idiom to those without removing anything.
- The project's own rule (`CLAUDE.md` §2) is no abstraction for single-use
  code, and `engine/db.py` was kept thin on purpose so this move would be
  small. An ORM makes it large.
- Sign-in, the feature this is for, needs three or four tables and a dozen
  queries. If that work later wants a schema toolkit, **SQLAlchemy Core +
  Alembic** is the right shape — decide it then, on that work, not now.

**Driver: psycopg 3** (`psycopg[binary]`). Sync, DB-API, `dict_row` gives
the `row["name"]` access the code uses today, numpy scalars adapt out of the
box (which retires the `register_adapter` block in `engine/db.py`), native
`COPY` for the data load, and `psycopg_pool` is there when the API becomes a
writer. Not asyncpg: the API is sync and so is everything else.

**Migrations: keep the runner.** `db.migrate()` applies numbered `.sql`
files in order and records them in `schema_migrations`. That works verbatim
on Postgres. What changes is the *history*: 004 and 005 are SQLite-only
table rebuilds (SQLite cannot alter a CHECK constraint; Postgres can), so the
Postgres history starts at a single **`001_baseline.sql`** equal to the
current schema after 006. The six SQLite files stay in git history.

### 1.2 Is Postgres actually needed for sign-in?

Strictly, no — SQLite can hold a users table. What Postgres buys, and why it
is worth it once sign-in is committed:

- **Concurrent writers.** Today the API is read-only and one worker, and
  the WAL note in `engine/db.py` is what lets the cycle write while it
  reads. Sign-in makes the API a writer (sessions, accounts) beside the
  06:00 cycle and the two-hourly results pull. SQLite serialises writers
  and hands the loser `SQLITE_BUSY`; Postgres does not.
- **More than one API worker**, when there is a reason for one.
- **Real types and constraints** — `timestamptz`, `citext` for emails,
  `uuid`, alterable CHECKs — for the tables that do not exist yet.
- **Backups the ordinary way**: `pg_dump` instead of the WAL-aware
  `VACUUM INTO` ritual, and a path to a managed service with point-in-time
  recovery later.

What it costs: one more service on the VM and on both development
machines; a slower test suite (§3.13); every SQL site touched once. If
sign-in is still hypothetical, this can wait without penalty — the DAL is
already thin. The plan below assumes it is not.

### 1.3 Where Postgres runs

**Same VM, phase 1.** The API opens a connection per request; against a
local socket that is under a millisecond, against Azure Database for
PostgreSQL it is a TLS handshake per request and a pool becomes mandatory
before anything else works. Same-VM has one moving part, no monthly cost,
peer authentication on the socket, and the migration rehearsal is identical
to the real thing. The cost is that backups stay yours: `backup.sh` becomes a
`pg_dump -Fc` on the same timer, **and the timer gets enabled** — it is not
today (`STATE.md` ops row). Moving Postgres → managed Postgres later is a
dump and restore, trivial next to this move.

## 2. Decisions for the owner

| # | decision | recommendation |
| --- | --- | --- |
| D1 | driver and ORM | psycopg 3, raw SQL, existing `.sql` runner (§1.1) |
| D2 | where Postgres runs | same VM, `postgresql` from apt, socket auth (§1.3) |
| D3 | column types in phase 1 | **keep them** — TEXT dates and timestamps, REAL → `double precision`, INTEGER → `integer` with identity. Byte-identical API output is the acceptance test (§4.1); type conversion is a later migration once the sign-in tables show what they need |
| D4 | `matchweeks` on `/tips/record` | compute in Python (§3.4), pinned by a test on a year-boundary fixture |
| D5 | tests | every test gets a fresh database cloned from a migrated template (§3.13); Postgres becomes a development prerequisite on both machines |
| D6 | the development ledger | both development machines move too; the gate ledger crosses by the existing `export_ledger.py --restore`, not the bulk copier (§3.6) |
| D7 | cutover window | a weekday between matchdays, after the 06:00 cycle and a results pull have both completed on SQLite; the decision point for rollback is *before the first Postgres cycle writes* (§4.3) |

## 3. Pitfalls — every one grounded in this codebase

Counts are from `grep` over `engine/ api/ services/ scripts/ db/` on
2026-09-04.

1. **Placeholders.** `?` → `%s` at every call site (~70 in 20 files). Any
   literal `%` in SQL (`LIKE '%…'`) must become `%%`. Mechanical, but the
   only way to know it is complete is the suite running green on Postgres.
2. **`datetime('now')` is UTC text; `now()` is a timestamptz in the session
   zone.** 16 sites: column defaults in the DDL and three `UPDATE … SET
   settled_at=datetime('now')` (`csv_grader.py` ×2, `fixture_sync.py`).
   Under D3 the columns stay TEXT with the default
   `to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')`, so stored
   values and the JSON the site receives stay identical. **And** set the
   role's timezone to UTC (`ALTER ROLE bvp SET timezone = 'UTC'`) so
   nothing depends on the VM's zone — the same argument as `DEPLOY.md`
   §3.8.
3. **`date('now')` compared with TEXT.** `f.match_date >= date('now')` in
   `/tips`, `/tips/record` and `step_grade`. Postgres will not compare
   `text` with `date` at all (an error, not a wrong answer), and
   `CURRENT_DATE` is session-zone. Use
   `to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD')` — or a `db.today()`
   helper computed in Python, which is easier to test.
4. **`strftime('%Y-%W', …)` has no Postgres twin.** SQLite's `%W` is a
   Monday-first week number 00–53; Postgres `IW` is ISO and differs across
   the year boundary, so `matchweeks` on `/tips/record` could move by one
   for a late-December/early-January week. Python's `strftime('%Y-%W')` is
   identical to SQLite's. D4: pull the distinct dates and count in Python.
5. **Identity columns and sequences.** `INTEGER PRIMARY KEY` → `integer
   GENERATED BY DEFAULT AS IDENTITY`. Rows are copied **with their ids**
   (the docs quote ledger rows and tips by id), so after the copy every
   sequence must be advanced to `max(id)` or the first insert after cutover
   — the next cycle's first prediction, on a matchday — fails with a
   duplicate key. The copier does this and the verifier checks it.
6. **The gate ledger.** Row numbers are load-bearing (`STATE.md`,
   `DEFLATION.md`). The development machine is the authority, the server's
   ledger is empty by design (`deploy.sh` §5 comment), and the sanctioned
   way to fill an empty ledger is `scripts/export_ledger.py --restore` from
   `docs/gate_ledger.jsonl`, which preserves ids and timestamps and verifies
   itself. Use that on the development machines; the bulk copier must
   **refuse** to copy `gate_ledger` so there is one path, not two. After
   the restore, `--check` must be clean and
   `trials.count_configurations` must still read **112 / 69 / 202**.
7. **NaN.** SQLite stores a float NaN as NULL; Postgres `double precision`
   stores NaN as a value, and sorts it above every number. `build.py:45`
   already maps `pd.isna → None`; the copier and any other frame-to-table
   write must too, and the verifier scans every float column for
   `'NaN'::float8`.
8. **SQLite types are advisory, Postgres types are enforced.** A `TEXT`
   value in an `INTEGER` column copies silently into SQLite and fails into
   Postgres. Surveyed on the local database today: **zero** columns whose
   stored `typeof()` disagrees with the declared type, and every foreign
   key satisfied. The same survey runs against the production snapshot
   before anything is copied (§4.2).
9. **SQLite-only SQL.** `INSERT OR IGNORE` ×4 → `ON CONFLICT DO NOTHING`;
   `INSERT OR REPLACE` ×2 (`build.py`, teams and aliases) → `ON CONFLICT
   (…) DO UPDATE`; `cur.lastrowid` ×1 (`ledger.record`) → `RETURNING id`;
   `GROUP_CONCAT` ×1 (`stadium_coords/cli.py`) → `string_agg`;
   `executescript` ×1 (the migration runner) → plain `execute` — psycopg
   runs a multi-statement string; `VACUUM INTO` (`backup.sh`) → `pg_dump`.
10. **Row access.** `sqlite3.Row` answers both `row["n"]` and `row[0]`;
    psycopg's `dict_row` answers only the first. Seven `fetchone()[0]`
    sites (`build.py` ×3, `meta.py`, `api/main.py:83`,
    `backfill_tip_scores.py`, …) → a `db.scalar(conn, sql, params)` helper.
    `dict(row)` in the API's `_rows` keeps working.
11. **Transactions — the one behavioural change that can break a cycle.**
    Python 3.11's `sqlite3` opens a transaction only before DML; psycopg
    opens one on the first statement of any kind and holds it until
    `commit()` or `rollback()`. Three consequences:
    - `services/run_cycle.py` runs every step on **one shared connection**
      and `_guard` (line 139) catches a step's exception without rolling
      back. On Postgres a failed statement leaves the transaction
      **aborted**, and every later step then fails with *current
      transaction is aborted* — the independence of the steps, which the
      whole exit-code design rests on (`RUNBOOK.md` §1), would silently
      collapse. `_guard` gains `conn.rollback()` on the exception path, and
      a test plants a failing step and asserts the next one still runs.
    - The API's per-request connection ends every request *idle in
      transaction* after a `SELECT`. Open it with `autocommit=True`; the
      API only reads.
    - Today, if a step raises after writing and before committing, its
      writes are still pending on the connection and the **next** step's
      `commit()` lands them. That is a latent SQLite bug the move fixes;
      worth knowing so the change in behaviour is not mistaken for a
      regression.
12. **pandas.** `pd.read_sql_query` ×5 (`store.py` ×2, `cycle.py`,
    `tips.py`, `book.py`) with a non-SQLAlchemy connection routes through
    pandas' SQLite fallback and warns that it is untested. Replace with a
    `db.read_frame(conn, sql, params)` helper: cursor → `DataFrame`. No
    SQLAlchemy dependency.
13. **Tests.** 15 modules use the `conn` fixture, which today is a
    throwaway SQLite file per test — free. On Postgres: a session-scoped
    template database migrated once, and `CREATE DATABASE … TEMPLATE …`
    per test (tens of milliseconds); expect the 628-test suite to gain
    roughly a minute. `deploy.sh` runs the suite on the VM before restarting
    the API, so the VM's Postgres also carries a `bvp_test` role that may
    create databases. The real-ledger guard in `test_trials.py` and
    `test_the_ledger_export_is_current` open the *real* store through
    `db.connect()`; they follow the new setting unchanged.
14. **Collation.** SQLite orders TEXT by bytes. A Postgres database created
    under `en_US.UTF-8` orders by locale rules (case and punctuation
    differ), so any `ORDER BY canonical_name` or `ORDER BY match_id`
    changes order. Create the database with `LC_COLLATE = 'C'` and
    `LC_CTYPE = 'C.UTF-8'` so ordering is byte-identical.
15. **`AVG` and `SUM(...) * 1.0` return `numeric`, which psycopg hands back
    as `Decimal`.** `strike_rate` in `/tips/record`, the corpus checks in
    `build.py`. Register a numeric → float loader once in `db.connect()` —
    the same place, and the same reason, as today's numpy adapters.
16. **`PRAGMA foreign_keys` is not optional any more.** The copy runs in
    dependency order — `teams`, `team_aliases`, `matches`,
    `player_seasons`, `fixtures`, `model_runs`, `predictions`, `tips`,
    `paper_bets`, `clv_grades`, `serving_state` — and `PRAGMA
    foreign_key_check` on the source is part of the survey.
    **`schema_migrations` is not copied**: the SQLite rows name six files
    that no longer exist, and `db.migrate()` writes the baseline's own row
    when the copier creates the schema. And a SQLite `TEXT PRIMARY KEY`
    admits NULL (only `INTEGER PRIMARY KEY` is a real key there); Postgres
    does not, so the survey also checks `matches.match_id` and
    `model_runs.model_version` for NULLs. Local store: none.
17. **systemd hardening.** `ReadWritePaths=/srv/bvp/db` existed for the WAL
    sidecars; the cycle still needs it for `db/artifacts/` and the flock
    file, the API no longer needs write access to `db/` at all. Under
    `ProtectSystem=strict`, connecting to the socket under
    `/var/run/postgresql` must be **checked on the VM**, not assumed; if it
    is refused, `host=127.0.0.1` with a password is the fallback. The flock
    stays: it serialises the cycle against the results pull *logically*,
    which Postgres does not do for you.
18. **`check_same_thread` and the FastAPI thread hand-off.** The rationale
    in `engine/db.py` dissolves: psycopg connections are not thread-bound.
    Keep one connection per request in phase 1 (sub-millisecond on a
    socket); `psycopg_pool` when the API starts writing.
19. **Configuration.** One new setting, `BVP_DATABASE_URL`, resolved by
    `config.setting()` like everything else, and `BVP_DB_PATH` retired.
    Server: `Environment=` in the three units; development: `.env`. The
    scratch-database pattern for click-throughs (`BVP_DB_PATH` to a seeded
    file) becomes a scratch *database*, same idea.
20. **Rollback.** The SQLite file is never written after the final
    snapshot and never deleted in this plan. Until the first Postgres cycle
    writes, rollback is: previous commit, previous unit files, restart. After
    it, rollback loses that cycle's rows — hence D7.

**Surfaced, not in scope:** `cycle.py:152` formats `served_at` as
`'%Y-%m-%d %H:%M:%f'` — hour, minute, *microseconds*, no seconds
(`'2026-09-01 09:52:222281'` in the local store). It is only used inside the
uniqueness key, so nothing is wrong today, but it is not the format the
column default writes, and it will bite the moment anyone sorts or
converts that column. A separate one-line fix with its own test.

## 4. Build

### Phase A — the code, locally (~2–3 days)

Decisions D1–D7 taken as recommended, 2026-09-04. **All five steps built
the same day.** The tree speaks Postgres end to end; **645 pass, 2 skipped**
in 3 min 10 s on the owner's instance (the two skips are the real-ledger
guards in `test_trials.py`, which skip until Phase B creates the `bvp`
store — under SQLite they ran on this machine). Not one line of SQLite
remains under `engine/ api/ services/ scripts/ tests/`.

1. `engine/db.py`: `connect()` from `BVP_DATABASE_URL` (`dict_row`, the
   numeric loader, `SET timezone`), `scalar()`, `read_frame()`, `today()`;
   `migrate()` unchanged except for the runner's own DDL. Drop the numpy
   adapters and `check_same_thread`.
   → verify: `tests/test_seasons_and_db.py` green on Postgres.
   **Built.** Two things the plan did not foresee: psycopg keeps
   `executemany` on the cursor, so `db.Connection` is a one-method subclass
   that puts it back on the connection (the call sites keep their shape);
   and the timezone goes in as a libpq startup option, not a `SET`, so a
   rollback cannot undo it. The verification test pulled two more files
   forward from step 3 — `engine/ledger.py` and `engine/ingest/build.py`,
   which it exercises — and the `conn` fixture from step 4 (§3.13's
   template-and-clone, `STRATEGY FILE_COPY`, ~¼ s per test on this
   machine). `build.validate`'s BLOB check became a NaN check, which is the
   same defect under the new engine. **24 pass**, 5.8 s.
2. `db/migrations/001_baseline.sql`: the post-006 schema in Postgres DDL,
   same table and column names, identities, `double precision`, TEXT dates,
   the partial index on `tips(settled_at)`, the CHECKs.
   → verify: `\d` of every table matches the SQLite `pragma table_info`
   column for column (a script, not eyes).
   **Built.** The six SQLite files are removed (git history keeps them).
   Compared by script against the local store: 12 tables, every column's
   name, order, type, nullability and default-presence, every primary key,
   unique set, foreign key, named index and CHECK count — identical, with
   `INTEGER PRIMARY KEY` ↔ identity as the one intended mapping.

**Development Postgres on this machine:** the owner's own PostgreSQL 16.1
service on **port 5433**, as the `postgres` superuser; `.env` carries the
credentials and the two URLs composed from them (password URL-encoded).
Its server timezone is `Africa/Nairobi` and its `template0` collation is
the Windows locale — neither matters, because `db.connect()` forces UTC as
a startup option and the test fixtures create every database from
`template0` with `LC_COLLATE 'C'`; that is what pitfalls 2 and 14 are for.
Verified there 2026-09-04: 24 pass, schema comparison identical. The
`bvp` database does not exist yet; Phase B's first rehearsal creates it.
(A throwaway trust-auth cluster on port 54329 under `%LOCALAPPDATA%\bvp\pg16`
was used for the first run and is stopped; it can be deleted.)
3. Port the call sites, file by file, from the §3 list. `_guard` gains the
   rollback; `get_conn` goes autocommit; `matchweeks` moves to Python.
   → verify: full suite green; the new tests for the rollback and the
   year-boundary matchweek.
   **Built.** Twenty production files and twelve test modules, by two
   scripts of exact, asserted replacements rather than by hand. Beyond the
   §3 list: `db.NOW_TEXT` is the one place the UTC-text timestamp
   expression lives (three `settled_at`/`updated_at` writes and the
   runner's DDL); `export_ledger.py --restore` now advances the identity
   after loading rows with their ids (pitfall 5 applied to the ledger's
   own path); `string_agg(... ORDER BY)` replaces `GROUP_CONCAT` in the
   stadium tool; `WHERE 0` became `WHERE false` in `store.py`. The two
   named tests exist: `test_a_failed_step_leaves_the_connection_usable_for_the_next`
   plants a duplicate-key failure and proves the next step runs *and* the
   failed step's earlier insert is gone; `test_matchweeks_keep_the_monday_first_week_number_across_a_year_boundary`
   pins 29 Dec 2025 and 1 Jan 2026 as two matchweeks, where ISO would say
   one.
4. Test harness: template database + per-test clone in `conftest.py`;
   `BVP_TEST_DATABASE_URL`. Document the local Postgres setup for both
   development machines in `DEPLOY.md` §2.
   → verify: `pytest -q` from a clean checkout on both machines.
   **Built** on this machine (`DEPLOY.md` §2.7; the other machine is still
   to run it). `make_database` is a factory fixture for tests that need
   several stores at once; `database_url` and `conn` sit on it;
   `relative_date(n)` in `conftest.py` replaces `date('now', '+n days')`
   in test data. Two SQLite habits the tests had that Postgres refuses,
   worth knowing when writing new ones: NULL into an identity column does
   not mean "assign one" (`COALESCE(%s, nextval(...))` where a test wants
   either), and a TEXT primary key must be supplied.
5. Ops files: `backup.sh` → `pg_dump -Fc` + `pg_restore --list` as the
   read-back; the three units gain `Environment=BVP_DATABASE_URL`, the API
   loses `ReadWritePaths`; `deploy.sh` unchanged in shape.
   **Built.** `backup.sh` resolves the URL through `engine.config` so it
   cannot dump a different store from the one the cycle writes, needs
   `pg_dump`/`pg_restore`/`psql` on the VM (`postgresql-client`, which the
   server install brings), and prints the same irreplaceable-table counts
   as before. All four units carry `Environment=BVP_DATABASE_URL=postgresql:///bvp`;
   the API and backup units no longer write under `db/`, the cycle and
   results units keep it for artifacts and the lock. None of this is live
   until Phase C copies the units to the VM.

### Phase B — the copier (~1 day)

`scripts/migrate_sqlite_to_pg.py`, three sub-commands, all idempotent:

- `--survey SRC.db`: row counts, `typeof()` disagreement per column,
  `foreign_key_check`, NaN scan, `max(id)` per table. Prints; exits 1 on
  any disagreement.
- `--copy SRC.db`: runs `db.migrate()` on the empty target, then `COPY`s
  table by table in §3.16 order with ids preserved and NaN → NULL, refuses
  `gate_ledger` (§3.6), then `setval`s every identity to `max(id)`.
  Refuses a non-empty target.
- `--verify SRC.db`: for every table, row count **and** an
  order-independent checksum over every column computed the same way on
  both sides (sorted rows, canonical text rendering, sha256), NaN scan,
  sequence position ≥ `max(id)`. Exits 1 on any difference.

Rehearsal, in order: (i) the local development store, with the ledger via
`--restore`; (ii) a fresh `VACUUM INTO` snapshot of **production**, copied
to the development machine. Against (ii), start the SQLite-backed API from
the previous commit and the Postgres-backed API from the branch on the same
data and **diff the JSON** of `/health`, `/tips`, `/tips/results`,
`/tips/record`, `/parlay`, `/performance`, `/fixtures`. Byte-equal is the
bar (D3); every difference is either a bug or a documented consequence of
§3.4.

### Phase C — production cutover (~1 hour, between matchdays)

Checklist; each line has a check that must pass before the next.

1. `apt install postgresql`; create role `bvp` (peer auth) and `bvp_test`;
   `CREATE DATABASE bvp … LC_COLLATE 'C'`; `ALTER ROLE bvp SET timezone =
   'UTC'`. → `psql -c 'select now()'` as `bvp` from `/srv/bvp`.
2. `systemctl disable --now bvp-cycle.timer bvp-results.timer
   bvp-backup.timer`; confirm nothing holds `db/.cycle.lock`. **The API
   stays up on SQLite** — it only reads, so the site is unaffected until
   step 7.
3. Capture the pre-cutover JSON of the endpoints in Phase B to
   `/var/backups/bvp/cutover/`. Final `VACUUM INTO` snapshot: the copy
   source and the rollback artefact.
4. `--survey` the snapshot → clean. `--copy` → `--verify` → clean.
5. `git pull` to the release commit; install the units with the new
   `Environment=`; `daemon-reload`; `deploy.sh --no-pull` — its migrate
   step must report *none (already current)*, its `pytest` must pass
   against `bvp_test`.
6. `deploy.sh` restarts the API. `/health` row counts equal the snapshot's.
   Diff the live endpoints against step 3: identical.
7. `scripts/run_cycle.sh --dry-run` → exit 0 or 2, no traceback.
8. Re-enable the cycle and results timers; enable the **new** backup timer;
   run one backup and restore it into `bvp_restore_drill` the same day —
   the drill `STATE.md` has wanted since the ops row was written.
9. `premier.db` and the snapshot stay where they are, read-only. Retire
   after one full matchday has been served, settled and graded on Postgres.

**Rollback before step 8:** previous commit, previous units, restart the
API, re-enable the timers. SQLite has not been written since step 3.

### Phase D — documents (~½ day)

`DEPLOY.md` (§2 development setup, §3.8 now about the role's timezone,
§5 units, §6.1 backup is `pg_dump`), `RUNBOOK.md` §8, `STATE.md` server
row, `OUTSTANDING.md`, `.env.example`, `README.md`. The memory note about
the two development machines gains the setting.

## 5. Effort

| phase | days |
| --- | --- |
| A code + tests | 2–3 |
| B copier + two rehearsals + JSON diff | 1–1½ |
| C cutover | ½ (one hour of it is the cutover) |
| D documents | ½ |
| **total** | **~5–6** |

## 6. What this does not change

No rule, no engine, no cycle step, no endpoint shape, no site change. The
ledger stays **112 / 69 / 202**. Nothing is backfilled (`STATE.md` "must
never" 4): the copier moves rows, it does not regenerate them. The sign-in
tables are `002_users.sql` in a later plan, on top of this one.
