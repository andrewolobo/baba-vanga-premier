# baba.vanga.premier

Match prediction engine for the English professional divisions (E0–E3, plus EC
in the corpus but not served). It fits a Poisson head on a sealed corpus, prices
each week's fixtures once, stores what it said, and grades itself on CLV.

Predictions are **append-only**. A fixture missed on Saturday stays missed —
pricing it on Sunday with Sunday's information would make the record a lie.

---

## The three pieces

Getting this distinction right is most of operating it.

| piece | what it is | how it runs |
| --- | --- | --- |
| `services.run_cycle` | a **batch job that exits** — sync → calendar → serve → tips → grade | systemd **timer**, daily 06:00 UTC |
| `api.main:app` | a read-only FastAPI over what the cycle wrote | systemd **service**, always up |
| `web/build` | a **static SPA** (SvelteKit `adapter-static`, `ssr: false`) | files served by nginx |

Nothing daemonises itself and nothing retries itself, by design. The scheduler
owns recurrence; the application owns one run.

**Exit codes are three, not two.** `0` clean, `2` ran but a human should look
(empty feed, unknown club, unpriceable fixture), `1` a step failed. Do not
collapse them — `SuccessExitStatus=2` in the systemd unit is load-bearing, or
the alerts fire every day of the close season and stop being read.

---

## Run it locally

Requires Python ≥3.11 and Node 24. The API's dependencies are an extra:

```bash
pip install -e ".[serve,dev]"
cd web && npm ci && cd ..
```

**Windows** — one command for the whole stack:

```powershell
.\scripts\dev.ps1              # cycle once, then API + frontend
.\scripts\dev.ps1 -SkipCycle   # servers only
```

**Any platform** — the three pieces by hand:

```bash
python -m services.run_cycle          # batch job; it exits
uvicorn api.main:app --port 8000      # terminal 1
cd web && npm run dev                 # terminal 2
```

Then open **`http://localhost:5173`** — not `127.0.0.1`, which Vite refuses.
Vite proxies `/api` → the API and strips the prefix; nginx reproduces that
rewrite in production.

On a clean checkout the database does not exist. Build it from the tracked CSVs:

```bash
python -m engine.ingest.build         # migrates, loads, validates
```

Expect `integrity checks: all passed`. Anything else, stop — no number is
trusted before `build.validate()` passes.

**Empty pages are the correct state out of season**, and the book is off by
decision, so `/book` and `/performance` stay empty regardless.

---

## Deploy

The server is one Azure VM running Ubuntu 24.04 at `/srv/bvp`, owned by an
unprivileged `bvp` user, updated by `git pull`.

**Routine deploy** — as `bvp`, from `/srv/bvp`:

```bash
./scripts/deploy.sh                # pull, install, build, migrate, test, restart, verify
./scripts/deploy.sh --no-pull      # rebuild what is already checked out
```

It refuses to run from a dirty tree or off `main`, and it **migrates before
restarting the API** — `api/main.py` never migrates, so a restart against a
stale schema queries a table that does not exist.

**First-time provisioning is `docs/DEPLOY.md` §5** and is not repeated here.
Read it before touching a new machine; it carries the post-mortems for the parts
that have already gone wrong once.

Three constraints that bite if forgotten:

- **The database must be on local disk.** WAL needs shared memory — not Azure
  Files, not NFS, not SMB.
- **Keep the VM on UTC.** SQLite's `date('now')` is UTC and pandas' is local;
  they agree only on a UTC machine.
- **Never edit a tracked file on the server.** Everything environment-specific
  goes in an env var or a systemd unit. The overridable settings are
  `BVP_DB_PATH`, `BVP_DATA_DIR`, `BVP_REFERENCE_DIR`, `BVP_BBC_CALENDAR`, and
  `BVP_API_URL` / `BVP_API_PORT` for Vite dev.

---

## Operating the server

```bash
systemctl status bvp-api                    # the API
systemctl list-timers bvp-cycle.timer       # next scheduled run
journalctl -u bvp-cycle -n 50               # what the last cycle did
./scripts/run_cycle.sh --dry-run            # write nothing
./scripts/backup.sh --dir /var/backups/bvp --keep 7
```

**`cp premier.db` is not a backup** and neither is a VM snapshot. Under WAL,
committed transactions can still be in `premier.db-wal`. Use `backup.sh`, which
uses `VACUUM INTO` and reads the copy back.

The **development** machine holds its own irreplaceable thing — the gate ledger,
a record of which measurements were run, derivable from nothing. It is backed up
as tracked text:

```bash
python scripts/export_ledger.py             # write docs/gate_ledger.jsonl
python scripts/export_ledger.py --check     # verify it matches the DB
```

Day-to-day operations, failure playbooks and the pre-launch checklist are
`docs/RUNBOOK.md`.

---

## Where things are documented

| file | authority on |
| --- | --- |
| `docs/RUNBOOK.md` | operating the cycle: exit codes, failure playbooks, weekly review |
| `docs/DEPLOY.md` | the server: provisioning, nginx, systemd, backup, alerting |
| `docs/SPEC.md` | what the system is and what it measures |
| `docs/OUTSTANDING.md` | **read first in a new thread** — what is still open |
| `docs/CALIBRATION.md` | why the betting book is off |
| `docs/BACKLOG.md`, `docs/PRODUCT.md` | product surface and what is deferred |

Measurement plans and results live in `docs/P*_PLAN.md` and `docs/*_results.json`.

---

## Current state

The site is deployed and serving. Honest list of what is not done:

- **HTTP only.** No domain yet, so no TLS and no basic auth; internal endpoints
  are fenced by source IP instead. This is a staging posture, not a launch one —
  with no `server_name`, nginx answers any Host header pointing at that address.
- **Backup is written but not installed.** `scripts/backup.sh` and the timer
  units exist; the timer is not enabled and no restore drill has been run.
- **No alerting.** Nothing pushes. A cycle that never runs at all is the failure
  that matters most, and only a dead-man's switch catches it.
- **`docs/RUNBOOK.md` still documents Task Scheduler**, so an operator following
  it against the Ubuntu VM finds half its commands do not exist.

## What must never happen

1. **Do not turn the betting book on.** It is measured-negative; it needs a new
   measurement, not a flag.
2. **Do not measure on a serving corpus.** Serving reads sealed seasons under
   `Purpose.LIVE`.
3. **Do not unseal the holdout** to explain a bad week. One pre-committed read,
   with the deflation scheme written down first.
4. **Do not backfill predictions.** They are append-only.
