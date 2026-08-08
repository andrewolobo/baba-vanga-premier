# Runbook — launch and the weekly cycle

Operational doctrine for the serving loop. Written 2026-08-03, before launch.
Companion to `OUTSTANDING.md` §1 (what is still pending) and `CALIBRATION.md`
§5 (why the book is off).

**The one thing to keep in mind.** Opening-weekend predictions cannot be
recovered afterwards. A fixture that goes unpriced on the day is a permanent
hole in the CLV series — the instrument that is the entire point of launching.
Everything below is arranged around not losing a matchday.

---

## 0. What runs

```
python -m services.run_cycle          # sync -> serve -> tips -> grade -> record
```

Four independent steps. Each records its own outcome; the cycle reports the
worst one and always writes a `serving_state` row, including when it failed.

| step | does | needs the network? |
| --- | --- | --- |
| `sync` | pull the rolling fixtures feed, upsert fixtures + prices | yes |
| `serve` | refit if stale, price every pending fixture it can | no |
| `tips` | publish one recommendation per priced fixture | no |
| `grade` | settle played fixtures, write CLV, settle tips | yes |

**The book does not run.** It is measured-negative and absent from the runner
rather than disabled by a flag.

**The tip list does run, and it is not the book.** `tips` stakes nothing and
places nothing. It publishes **one recommendation per fixture**: the outright
favourite when it clears `TIP_FLOOR` (0.55), otherwise the likeliest double
chance under `TIP_CEILING` (0.85). The argument for keeping the book out of a
scheduled job — one typo from placing bets — does not apply.

> **What the tip list may and may not be presented as.** Measured over eleven
> dev seasons: the strike rate is **honest** — **72.5% at floor 0.55, on 100%
> of matches** (`engine/eval/selection.py`), and the head is under-confident
> rather than over. A **return** is not: at prices a customer without a dozen
> accounts gets, nothing resolves and the sellable settings are negative
> (`engine/eval/tips.py`). And the model is not the source of either — it names
> the market favourite and the paired difference against backing that favourite
> is ~0.00%.
>
> **The published mix at floor 0.55 is 65% `12`, 17.6% `1X`, 11.8% `H`, 3.0%
> `X2`, 2.5% `A`** — the product names a team in 14.3% of matches. Owner
> decision of 2026-08-06.
>
> Re-run `python -m engine.eval.tips` and `python -m engine.eval.selection`
> after any head change; both end with a block stating which claims hold.

Changing `TIP_FLOOR` or `TIP_CEILING` means bumping
`engine.serve.tips.RULE_VERSION`, or the published history mixes two products
under one strike rate. It is at `confidence-v2`.

### 0.1 Starting it by hand

Three independent pieces. The cycle is a **batch job that exits**, not a server;
the other two are servers. Verified working 2026-08-04.

```powershell
# one-off: the API's dependencies are an extra, not a base dependency
pip install -e ".[serve]"

# 1. the cycle -- run it, it exits. Nothing else needs it running.
python -m services.run_cycle

# 2. the API (terminal 1)
uvicorn api.main:app --port 8000 --reload

# 3. the frontend (terminal 2)
cd web
npm install        # first time only
npm run dev
```

Then open **`http://localhost:5173`**.

> **Use `localhost`, not `127.0.0.1`, for the frontend.** Vite 5 binds to
> `localhost`, which resolves to IPv6 `::1` here; `http://127.0.0.1:5173`
> refuses the connection while `http://localhost:5173` serves normally. The API
> answers on both.

Check the API alone without the frontend:

```powershell
curl.exe http://127.0.0.1:8000/health
```

**What you will see today: empty pages.** That is correct, not a fault:

| you see | because |
| --- | --- |
| no fixtures | the feed carries no English rows yet (§5.1) |
| no predictions | nothing to price until fixtures exist |
| **empty book, always** | the betting rule is **off by decision** — `CALIBRATION.md` §5 |
| `"model": null` on `/health` | no non-dry-run cycle has been run yet |
| `calibrated: false` | flagged on the wire on purpose — P3 found calibration null/harmful |

**"Off" refers to the book, not the application.** The engine, API and frontend
all run. The betting rule is the only thing deliberately disabled, and the
`/book` and `/performance` pages will stay empty for as long as that holds.

### 0.2 Starting it with one command

```powershell
.\scripts\dev.ps1              # cycle once, then API + frontend
.\scripts\dev.ps1 -SkipCycle   # servers only
```

Same three pieces as §0.1, one shell. Ctrl-C stops both servers. Output from
the two interleaves — use §0.1 when you need to read one of them cleanly.

**It runs the cycle once and does not schedule it.** Recurring runs stay with
Task Scheduler (§2); the launcher is not a substitute for registering the task.
The cycle finishes before the API binds — not for locking reasons any more
(§5.6), but so its exit code is readable before request logs bury it.

**Windows only.** It uses `npm.cmd`, `taskkill` and `Get-NetTCPConnection`; it
will not run as-is on the Ubuntu target.

## 1. Exit codes — and why 2 is not worse than 1

```
0    clean
2    ran, but a human should look
1    a step failed
```

**Do not collapse these.** `2` fires on things that neither raise nor succeed:
an empty feed, a club the alias table does not know, a fixture the artifact
cannot price, an artifact too old to serve. If a scheduler pages someone for
every non-zero, they will be paged all summer for an out-of-season feed, and
they will stop reading the alerts — which is the exact failure this design is
built to avoid.

Treat `1` as *broken*, `2` as *unattended and drifting*.

## 2. Scheduling it

Daily, not weekly. The feed is a rolling ~7-day window that republishes prices,
so a daily run picks up each fixture the first time it appears and prices it at
its earliest observed price — which is what `first_seen_at` exists to record.
The **weekly refit happens by itself**: the runner refreezes whenever the
artifact is more than `REFIT_AFTER_DAYS` (7) old, so a missed run cannot leave a
stale head pricing this weekend.

Register the task (adjust the path; run the shell as the user who owns the repo):

```powershell
$repo   = "C:\Users\olobo\Documents\BIZ\baba.vanga.premier"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\run_cycle.ps1`"" `
    -WorkingDirectory $repo
$trigger  = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "bvp-cycle" -Action $action -Trigger $trigger `
    -Settings $settings -Description "baba.vanga.premier serving cycle"
```

`-StartWhenAvailable` catches up after the machine was asleep. `IgnoreNew`
prevents two overlapping runs — re-running is safe (§6) but pointless.

Check on it:

```powershell
Get-ScheduledTaskInfo -TaskName "bvp-cycle" | Select LastRunTime, LastTaskResult
Get-Content .\logs\cycle-$(Get-Date -Format 'yyyy-MM-dd').log -Tail 30
```

`LastTaskResult` is the exit code above.

## 3. Pre-launch checklist

Work down this list. Every step is a command with an expected answer.

**T-7 — prove the machinery, before the data exists**

```powershell
python -m pytest -q                              # expect: all green
python -m services.run_cycle --dry-run           # expect: exit 2, "NO ENGLISH ROWS"
.\scripts\run_cycle.ps1 -DryRun                  # expect: same code, a log file appears
```

Exit 2 with `NO ENGLISH ROWS` is the **correct** answer out of season. It
confirms the empty-feed detector works while the feed is genuinely empty —
which is the only time it can be confirmed cheaply.

**T-3 — the feed is the launch risk**

```powershell
python -m services.fixture_sync --dry-run
```

English rows should now appear. If they do not, see §5.1 — this is the single
item most likely to stop launch, tracked as `OUTSTANDING.md` §1.2.

**T-1 — dress rehearsal, writing for real**

```powershell
python -m services.run_cycle                     # expect: exit 0
python -c "from engine import db; c=db.connect(); print(*c.execute('select cycle_label, model_version, fixtures_seen, predictions_written from serving_state order by state_id desc limit 3'))"
python -m api.main                               # or however the API is served
```

Confirm on the site: fixtures listed, probabilities present, `/performance`
renders with an empty book (expected — no bets exist).

**T-0, matchday morning**

```powershell
.\scripts\run_cycle.ps1
```

Then verify **every** fixture kicking off today has a prediction:

```sql
SELECT f.division, COUNT(*) AS fixtures,
       SUM(CASE WHEN p.prediction_id IS NULL THEN 1 ELSE 0 END) AS unpriced
FROM fixtures f
LEFT JOIN predictions p ON p.fixture_id = f.fixture_id
WHERE f.match_date = date('now')
GROUP BY f.division;
```

`unpriced` must be 0 for E0–E3. Anything else, go to §5.3 **before kickoff** —
after kickoff the pre-close information set is gone for good.

## 4. What must never happen

1. **Do not turn the book on.** `CALIBRATION.md` §5. It needs a new measurement,
   not a flag.
2. **Do not measure on a serving corpus.** Serving reads sealed seasons under
   `Purpose.LIVE`; `Corpus.for_measurement()` refuses such a frame. If you find
   yourself wanting to bypass that, stop.
3. **Do not unseal the holdout** to explain a bad week. One pre-committed read
   at P6, and the deflation scheme is written down *first* (`OUTSTANDING.md` §3.2).
4. **Do not backfill predictions.** They are append-only. A fixture missed on
   Saturday stays missed; pricing it on Sunday with Sunday's information would
   make the CLV series a lie.
5. **Do not enable the FBref scraper** without a decision recorded. Shelved
   2026-08-03 (`OUTSTANDING.md` §1.9).

## 5. Failure playbooks

### 5.1 `sync` says NO ENGLISH ROWS

Expected out of season. A problem from roughly T-7.

```powershell
curl.exe -s https://www.football-data.co.uk/fixtures.csv | Select-Object -First 3
```

- **Rows exist but are all Scottish** → the publisher has not posted English
  fixtures yet. Recheck daily. This is normal until about a week out.
- **The file is empty or 404** → the publisher is down. Predictions can still be
  made from any other source that writes a `fixtures` row (§5.5).

### 5.2 `sync` says unbridged club name(s)

A club is playing in E0–E3 that the alias table does not know.

```powershell
python scripts\build_team_aliases.py
python -m services.fixture_sync --dry-run     # expect: clean
```

If the name is genuinely new to the corpus, it also needs to reach the artifact
before it can be priced — see §5.3.

### 5.3 `serve` says fixtures unpriced, artifact never saw X

The artifact has no history for that club. It is skipped by design rather than
given a silent league average.

Expect this **only in the National League** — the corpus has gained 1–3 clubs
almost every season and every one arrived in EC, promoted from a tier the
corpus does not cover. No club has ever entered E0–E3 this way.

- **If it is an EC club:** nothing to do. EC is not a served market.
- **If it is E0–E3:** this has never happened and something is wrong. Check the
  alias table first (§5.2) — a misspelling presents identically to a new club.
  A genuinely new club cannot be priced until it has played matches in the
  corpus; do not invent a prior for it.

### 5.4 `serve` failed outright

Read the traceback in the log. Then:

```powershell
python -m services.run_cycle --refreeze
```

A corrupt or truncated artifact is the usual cause and a refit fixes it. The
old artifact stays on disk; nothing is destroyed by refitting.

### 5.5 The feed is down and there are matches today

The `fixtures` table is the interface, not the feed. Anything that inserts a row
with `division`, `match_date`, and bridged `home_team_id`/`away_team_id` will be
priced by the next `serve` — odds are **not** required to predict (they are
required only to grade CLV later). Insert by hand, then:

```powershell
python -m engine.serve.cycle
```

Add the prices later when the feed recovers; `sync` upserts on
`(division, date, home, away)` and preserves `first_seen_at`.

### 5.6 The database is locked

**This should no longer happen.** The database runs in WAL mode as of
2026-08-07 (`engine/db.py`), so a read in progress no longer blocks the cycle's
write. Before that it did: an open read made the cycle fail with `database is
locked` after the full 5s busy timeout, which is why this section used to say
"stop the API, re-run, restart it".

WAL still allows only **one writer at a time**. So if you see it now, it is two
*writers* — two cycles overlapping, which nothing in the application prevents
(§8). Check for a second `python -m services.run_cycle`, and re-run once it is
gone; re-running is safe (§6).

## 6. Re-running is safe

Every write path is idempotent, which is what makes an unattended retry
tolerable:

| table | behaviour |
| --- | --- |
| `fixtures` | upsert on (division, date, home, away); `first_seen_at` preserved |
| `predictions` | append-only, skips fixtures already priced by this artifact |
| `model_runs` | `INSERT OR IGNORE` on version |
| `clv_grades` | `INSERT OR IGNORE`, unique per bet |
| `serving_state` | one row per run, deliberately — the audit trail |

Asserted in `tests/test_run_cycle.py::test_rerunning_is_idempotent`.

## 7. Weekly review

Monday, five minutes:

```sql
SELECT cycle_label, model_version, fixtures_seen, predictions_written, notes
FROM serving_state ORDER BY state_id DESC LIMIT 10;
```

Look for: a run every day; `predictions_written` > 0 on matchday weeks;
`ATTENTION` in notes explained rather than tolerated. A tolerated warning
becomes an ignored warning within about three weeks.

## 8. Known gaps

Honest list of what this runbook does not yet cover, tracked in
`OUTSTANDING.md` §1:

- **No alerting.** Failures are visible in `LastTaskResult`, the log, and
  `serving_state` — all of which require someone to look. Nothing pushes.
- **No hosting.** API and frontend run locally; there is no deployment.
- **No backup.** `db/premier.db` is not backed up anywhere. It holds the
  irreplaceable part: what was predicted, and when.

  When one is written: **copying `premier.db` alone is not a backup.** Under WAL
  (§5.6) committed transactions can still be sitting in `premier.db-wal`, so a
  plain `cp` can silently lose the most recent cycle — the one you most wanted.
  Use `VACUUM INTO 'backup.db'` or `sqlite3 premier.db ".backup ..."`, either of
  which is safe to run while the API is up.

  WAL also needs shared memory, so **the database cannot live on NFS or SMB.**
  Relevant to the Ubuntu move: local disk or a bind-mount from local disk only.
- **No lock file.** Overlapping runs are prevented by the scheduler's
  `IgnoreNew`, not by the application. Safe if it happens (§6), just wasteful.
