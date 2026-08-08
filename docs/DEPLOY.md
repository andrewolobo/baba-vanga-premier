# Deployment — Azure, Ubuntu 24.04 LTS, single VM

Plan for hosting the application on one Azure VM, updated by `git pull`.
Companion to `RUNBOOK.md` (how the cycle is operated) and `OUTSTANDING.md` §4.3
(what was left undone when the runbook was written).

Written **2026-08-08**. Nothing here has been executed.

> **The fault-tolerance step this plan is built around.** Taken to mean
> `RUNBOOK.md` §8's *Known gaps* — **no alerting, no hosting, no backup, no
> lock file** — which `OUTSTANDING.md` §4.3 carries as the outstanding item.
> §6 below builds all four. If a different piece of work was meant, say so;
> §6 is the only section that changes.

---

## 1. What is being deployed

Three pieces with different lifecycles. Getting this distinction right is most
of the deployment.

| piece | what it is | how it runs |
| --- | --- | --- |
| `services.run_cycle` | a **batch job that exits** — sync → serve → tips → grade | systemd **timer**, daily |
| `api.main:app` | a read-only FastAPI over what the cycle wrote | systemd **service**, always up |
| `web/build` | a **static SPA** (SvelteKit `adapter-static`, `ssr: false`) | files served by nginx |

Nothing daemonises itself and nothing retries itself, by design
(`services/run_cycle.py` docstring). The scheduler owns recurrence; the
application owns one run.

### 1.1 Measured cost — the VM can be small

Timed on this machine, 2026-08-08, against the live 44 MB database:

| | measured |
| --- | --- |
| full artifact refit (`cycle.build_artifact`) | **1.5 s**, 13,973 training matches, 151 clubs |
| peak process RSS during the refit | **167 MB** |
| test suite | **437 passed in 44 s** |
| `db/premier.db` | 44 MB |
| `data/` (tracked CSV corpus) | 59 MB |

**The weekly refit is not a sizing constraint.** The heaviest thing this
application will do on the server is `npm run build`, and that happens only on
deploy.

---

## 2. Blockers — none of this can be deployed today

Ordered. Each one stops the deployment dead, not degrades it.

### 2.1 The entire customer-facing product is uncommitted — **RESOLVED 2026-08-08**

Closed by `ccb6f8e`, pushed to `origin/main`. Kept in full because the shape of
it is the reason the other blockers were worth looking for.

`git status` carried **16 modified and 20 untracked paths**. And `origin/main`
was at **`244ca18` — the first commit** — five behind local `main`, not level
with it as this section first said. GitHub was missing P2, the runbook and
scheduling, all of the controls, and the entire customer surface. **A `git pull`
on a fresh server would have fetched the data spine and nothing else.** The
error came from reading `git branch -a` and assuming the remote tracked the
local; `git status -sb` says `ahead 5` and was never consulted.

So a `git pull` on a fresh server would have fetched a tree with:

- no `engine/serve/tips.py` — the tip rule
- no `db/migrations/003_tips.sql`, `004_tips_double_chance.sql` — the `tips` table
- no `engine/eval/{tips,selection,meta}.py`
- no `web/src/lib/badge.js`, no `web/static/` — the page will not render
- the **pre-fix** `api/main.py` and `engine/db.py`, i.e. without
  `check_same_thread=False` and without WAL — the two fixes of 2026-08-07 that
  make the site work at all under concurrent fetches and make the API and the
  cycle coexist

The published site is `+page.svelte`, which fetches `/tips`, `/tips/results`
and `/tips/record` in one `Promise.all`. That is exactly the concurrency case
`OUTSTANDING.md` §1.11 records as **500ing on every load** before the fix.

**One thing this turned up that belongs in the runbook, not here.**
`git push` over SSH fails from this machine — `github.com:22` times out, the
network blocks it. GitHub's port-443 endpoint works and authenticates, so
`origin` is now `ssh://git@ssh.github.com:443/...`. **The server will need the
same treatment if its egress is filtered**, and it is worth checking during
§5.4 rather than discovering it mid-deploy. The permanent, repo-independent
form is a `~/.ssh/config` block:

```
Host github.com
    Hostname ssh.github.com
    Port 443
    User git
```

**Action: commit and push before anything else.** Two care points when doing so:

- `web/static/player.rar` (756 KB) sits beside `player.png` and is not
  referenced by anything. Committing `web/static/` wholesale publishes it at
  `https://<host>/player.rar`. **Done 2026-08-08 — moved to `docs/ui/`**, plus a
  `.gitignore` rule for `web/static/*.rar` as a standing guard.

  **Gitignoring it alone was not enough, and that is the point worth keeping.**
  `.gitignore` governs what reaches git; `npm run build` copies whatever is on
  disk in `web/static/` into the published root. The server would have been
  safe — `git pull` never carries the file there — but every local build kept
  publishing it. **`web/static/` is a publication list, not a folder**, and the
  only reliable way to keep something out of it is for the file not to be in it.
  Design source lives in `docs/ui/`, which is never served.
- `web/static/player.png` is the hero image on the one public page and is
  therefore the largest thing this VM will ever serve. See §2.6 — it also
  carries a defect worth fixing before it is published.

### 2.2 The database is gitignored and must be built on the server

`.gitignore:11` excludes `db/*.db`. `git pull` will never carry `premier.db`.

It does not need to: `data/play_history/` and `data/player-stats/` **are**
tracked, so the store is rebuildable on the server from the repo alone:

```bash
python -m engine.ingest.build          # runs migrations, loads, then validates
```

Expect `integrity checks: all passed` and exit 0. Anything else, stop —
`OUTSTANDING.md` §7.6 is the convention: *no number is trusted before
`build.validate()` passes*, and both defects it has caught left row counts
perfect.

`db/artifacts/` is gitignored too. The first cycle freezes its own artifact, so
this needs no action — but note the served `model_version` on the server will
**not** be `p1-3a38e9d6ef1ca7ee`. It will be a fresh hash at the server's own
cutoff, which is correct and expected (the runner refreezes past
`REFIT_AFTER_DAYS`). The version string is a derivation of the training data
and cutoff, so it is *supposed* to differ.

### 2.3 The frontend build output is gitignored

`.gitignore:5` is `build/`, which matches `web/build`. So **Node must be
installed on the server** and `npm ci && npm run build` must run as part of
every deploy. `package-lock.json` is committed, so the install is reproducible.

The alternative — un-ignoring `web/build` and committing the compiled output —
is not recommended: it makes every deploy a merge conflict on minified files.

### 2.4 The `/api` proxy exists only in Vite dev

`web/src/lib/api.js` sets `const BASE = '/api'` and every call is
origin-relative. In development `web/vite.config.js` proxies `/api` → the
uvicorn port **and rewrites the prefix away**. In production there is no Vite.

nginx must reproduce that rewrite exactly (§5.3). If it is missed, the failure
is the one `vite.config.js` already documents in a comment: every page reads as
**an empty week rather than as a misconfiguration**. It will look like the feed
is out of season.

### 2.5 All operational scripting is PowerShell — **RESOLVED 2026-08-08**

`scripts/run_cycle.ps1` (the logging wrapper that preserves the exit code) and
`scripts/dev.ps1` are Windows-only — `RUNBOOK.md` §0.2 says so in as many
words. `RUNBOOK.md` §2's whole scheduling section is Task Scheduler.

Now shipped: `scripts/run_cycle.sh`, `scripts/deploy.sh`, and
`deploy/systemd/{bvp-api.service,bvp-cycle.service,bvp-cycle.timer}`.

**`run_cycle.sh` does not write a dated log file, and that is the one place it
deliberately differs from the `.ps1`.** The PowerShell version wrote one
because Task Scheduler reports "last run result" and discards output, so a run
was otherwise unreconstructable. journald does not discard output; a second
copy on disk would only age independently and go unpruned.

**Two defects found by running it rather than reading it:**

- **A missing `flock` took the same branch as a held lock** — the script
  reported "another cycle is already running" and exited 2, which is a
  benign-looking message for a cycle that never ran at all. `flock` ships with
  util-linux and is on every Ubuntu, so this would only fire on a minimal
  image — but the cost is a matchday going unpriced while the log reads fine,
  which is the precise failure `services/run_cycle.py` exists to prevent. It
  now detects absence separately, says so, and runs anyway: the lock is belt
  and braces over systemd, re-running is idempotent, and a skipped run is
  permanent where an unguarded one is merely wasteful.
- **The lock cannot live in `/tmp`.** The units set `PrivateTmp=true`, so a
  `/tmp` lock is invisible between the service and a hand-run shell — which is
  exactly the overlap it exists to catch. It lives at `db/.cycle.lock`, inside
  the one path `ReadWritePaths` grants.

Verified against the live feed: `exit 2`, `NO ENGLISH ROWS` — `RUNBOOK.md` §3's
T-7 check, now passing through the Linux script.

**Still open: `RUNBOOK.md` §0.2 and §2 still document Task Scheduler**, so an
operator following it against the Ubuntu VM finds half its commands do not
exist. §7 step 9.

### 2.6 The hero image carries a green matte fringe

Measured 2026-08-08 on `web/static/player.png` (2540×992 RGBA, 2.72 MB):
**54,696 pixels — 2.17% of the image — are green**, and every one of them is
**semi-transparent**. Not one opaque pixel is green.

That is the signature of a green background keyed out without de-fringing: the
anti-aliased edge kept the old background's colour. It is invisible against
white, which is why it survived review, and `.hero` in `+page.svelte:350` has
`background: var(--accent)` — **orange**. A pixel of `rgba(33,239,31,168)`
composited over `#ff6b1a` lands near `rgb(108,198,41)`, a strong lime. The
figure will be published with a green halo around it.

**Fixed by** carrying the nearest opaque pixel's colour into the fringe and
keeping its alpha — a standard matte de-fringe, 54,696 → 107 green pixels — then
downscaling to 2000 px and quantising. `.art` is `width: min(64%, 1000px)`, so
2000 px is exactly 2× and nothing visible is lost.

| | bytes |
| --- | --- |
| as found | 2.72 MB |
| de-fringed, 2000 px, 256-colour PNG | **127 KB** |

A 95% reduction with the defect removed, and it stays a PNG, so
`+page.svelte:104` does not change. WebP was 145 KB — larger here, because a
low-poly illustration is exactly what palette quantisation is good at.

**An earlier figure in this document was wrong.** This file first quoted the
hero at 7.8 MB, read from a `ls -la` before the asset was replaced mid-session.
2.72 MB is the measured size of the file as committed.

---

## 3. What does not conform to this deployment type

Real conflicts between the application as built and a single public VM.
Mitigation given for each.

### 3.1 `/performance` publishes ROI, and the honesty rule does not cover it

**This is the most consequential item in this section.**

`BACKLOG.md` B7 and `api/main.py`'s docstring establish that no profit figure
reaches the wire, and `test_the_record_publishes_no_profit_figure` enforces it
— **on `/tips/record` only**. `/performance` returns `pnl`, `roi` and
`hit_rate`, and `/book` returns `paper_bets.*` including `pnl`. Both are linked
from the public footer in `+layout.svelte:59`.

Today they return nothing, because the book is off and `paper_bets` is empty.
The exposure is conditional but real: the moment anything is ever written to
`paper_bets`, a **public** URL publishes a return, through a page the honesty
test does not cover, on a product whose entire regulatory position is that it
does not claim one (`OUTSTANDING.md` §1.10).

**Mitigation, in the deployment:** basic-auth `/api/book` and
`/api/performance` at nginx (§5.3) and delete the two footer links. Both are
small.

**Mitigation, in the application (recommended follow-up, not deployment
work):** invert B7's test from "this endpoint has no P&L" to "these endpoints
are public, and no public endpoint has P&L". The current test passes while the
hole exists, which is the same shape as `step_grade`'s short-circuit in
`OUTSTANDING.md` §1.10 — a check that was correct until a second thing needed
covering.

### 3.2 The database cannot go on Azure Files

`engine/db.py:66` puts the database in WAL mode, and WAL needs shared memory.
`RUNBOOK.md` §8 already flags it and names the Ubuntu move as the reason:
**local disk or a bind-mount from local disk only**.

So: `premier.db` lives on the VM's OS disk or an attached **managed disk**
(a block device with ext4). **Not** an Azure Files SMB share, **not** NFS.
Backups may live in Blob storage — they are files, not a live database — but
the working copy may not.

This also rules out, without further work, any design where two VMs share the
database. Single VM is the shape this application fits.

### 3.3 CORS is hardcoded in application code

`api/main.py:48` allows `http://localhost:5173` and `http://127.0.0.1:5173`,
which is a code constant, not configuration.

Under §5.3's same-origin nginx layout **this is not a problem and needs no
change** — the browser sees one origin and never issues a preflight. That is
the reason to proxy rather than to split hosts.

It becomes a problem the moment anyone wants `api.<domain>` separate from the
site: that would require editing a file on the server, which breaks `git pull`
as a deployment mechanism (§3.6). If a split origin is ever wanted, the fix is
to read the allowlist from an env var — a two-line change made *before* the
split, not during it.

### 3.4 `api`, `services` and `scripts` are not installed packages

`pyproject.toml` has `include = ["engine*"]`, so `pip install -e .` installs
`engine` and nothing else. `python -m services.run_cycle` and
`uvicorn api.main:app` work **only with the repo root as the working
directory**.

Not a defect — but it means every systemd unit must set
`WorkingDirectory=/srv/bvp`, and a shell that has `pip install -e .` in it will
give a false impression that the cycle can be invoked from anywhere.

### 3.5 Python dependencies are unpinned and there is no lockfile

`pyproject.toml` asks for `pandas>=2.0`, `numpy>=1.24`, `scipy>=1.10`. This
machine is running **pandas 3.0.3 / numpy 2.2.6 / scipy 1.15.3** on Python
3.11. A fresh `pip install` on the server resolves to whatever is current on
that day, which is not necessarily what 437 tests passed against.

It matters more than usual here because `pyproject.toml` sets
`filterwarnings = ["error::FutureWarning"]`: a pandas release that deprecates
something this code uses turns a warning into a **test failure**, and possibly
into a behaviour change in the fit.

**Mitigation:** generate a constraints file from this machine's environment,
commit it, and install against it on the server:

```powershell
python -m pip freeze > requirements.lock     # here, once
```

```bash
pip install -e ".[serve]" -c requirements.lock   # on the server
```

Then run `pytest -q` **on the server** as an acceptance gate (§5.6). 437 green
on Ubuntu/Python 3.12 is the only thing that proves the environment
transferred; the test suite takes 44 s, so there is no reason not to.

Ubuntu 24.04 also ships Python **3.12** as `python3` and is
**PEP 668 externally-managed** — `pip install` outside a virtualenv is refused.
A venv is mandatory, not optional. `requires-python = ">=3.11"` is satisfied.

### 3.6 `git pull` deployment requires the server working tree to stay clean

Any hand-edit on the server — a CORS origin, a port, a threshold — makes the
next `git pull` a conflict, on a matchday, over SSH.

**Rule: everything environment-specific goes in an env var or a systemd unit
outside the repo, and no tracked file is edited on the server.** The overridable
settings today are `BVP_DB_PATH`, `BVP_DATA_DIR`, `BVP_REFERENCE_DIR`
(`engine/config.py`) and `BVP_API_URL` / `BVP_API_PORT` (Vite dev only).

Note `DB_DIR`, `MIGRATIONS_DIR` and `ARTIFACT_DIR` are **not** overridable —
artifacts always land in `<repo>/db/artifacts`. So the repo directory itself
must be writable by the service user, and the deploy user and the service user
should be the same account.

### 3.7 The API never runs migrations

`db.migrate` is called by `services/run_cycle.py:330` and
`engine/ingest/build.py`, but `api/main.py`'s `get_conn` calls `db.connect`
alone.

So after a pull that adds a migration, **migrate before restarting the API**,
or the API queries a table that does not exist. §5.6 fixes the deploy order
around this. It is why `deploy.sh` is a script and not four commands typed from
memory.

### 3.8 Timezone: SQLite is UTC, pandas is local

`date('now')` in SQL is **UTC**; `pd.Timestamp.now()` in `run_cycle.run` and
`cycle.build_artifact` is **local**. They agree only if the machine is on UTC.

Azure Linux VMs default to UTC. **Keep it that way** and schedule the cycle at
06:00 UTC. Setting the VM to `Europe/London` would put the two a day apart
between 00:00 and 01:00 BST, which would silently move which fixtures
`step_grade`'s `match_date <= date('now')` bound and `/tips`' `match_date >=
date('now')` filter consider live.

### 3.9 Two runtime dependencies on the public internet

Outbound HTTPS to `football-data.co.uk` for both `fixtures.csv` (sync) and
`mmz4281/{season}/{division}.csv` (grade). No inbound requirement beyond the
web ports. Azure NSGs allow outbound by default; nothing to configure, but it
is what the VM must be able to reach.

`web/src/app.html` also pulls Barlow from Google Fonts at page load. It
degrades to a narrow system fallback by design, so it is not a hosting
dependency — noted only so nobody treats a blocked font request as a fault.

### 3.10 `.env` should not travel to the server

It holds `LOCATIONIQ_API_KEY`, used only by `services/stadium_coords`, which is
a one-off table builder that already produced `reference/stadiums.csv` (tracked
and complete at 151/151 clubs). **The serving path never reads it.**

It is gitignored, so it has not leaked through git. Do not copy it to a public
VM; there is nothing there that needs it.

---

## 4. Azure shape

| | choice | why |
| --- | --- | --- |
| VM | **2 vCPU / 4 GiB burstable** (B2s or the current v2 equivalent) | runtime needs ~200 MB; the 4 GiB is for `npm run build` and headroom |
| image | Ubuntu Server **24.04 LTS**, Gen2 | as specified |
| OS disk | 30 GiB Standard SSD, ext4 | repo 130 MB + DB 44 MB + `node_modules`; no IOPS pressure at this size |
| data disk | none | see §3.2 — if one is added it must be a managed disk, never Azure Files |
| public IP | static | needed for a stable DNS A record and TLS |
| NSG inbound | 22 from your address only; 80 and 443 from anywhere | 80 exists to redirect to 443 and for the ACME challenge |
| NSG outbound | default (allow) | §3.9 |
| backups | Blob container, versioning on, lifecycle rule | §6.1 |

**A 1 vCPU / 2 GiB B1ms would run the application fine** — the measured
footprint is 167 MB. It is tight for the Node build. If cost matters more than
convenience, take B1ms and either add 2 GiB of swap or build `web/` locally and
`rsync` the output; the plan below assumes building on the server.

Azure Backup on the VM is **optional and not the recovery story**. Everything
except `premier.db` is reconstructible from git in minutes; `premier.db` holds
the one irreplaceable thing — what was predicted, and when — and §6.1 backs it
up properly. A VM-level snapshot of a live WAL database is exactly the
`cp premier.db` mistake at a different layer.

---

## 5. The deployment, in order

Each step has a verification. Do not proceed past a failed one.

### 5.1 Commit and push — *verify:* `git status` clean, `origin/main` moved

Blocker §2.1. Handle `player.rar` and `player.png` (§2.6) at the same time.
Generate and commit `requirements.lock` (§3.5) in the same push.

A **read-only deploy key** on the server for the private repo — not a personal
SSH key, and not a token in a URL.

### 5.2 Provision and harden the VM — *verify:* `ssh` in, `sudo` works

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx sqlite3 git ufw
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
timedatectl                                  # expect: UTC  (§3.8)
```

Node from NodeSource, matching this machine's major (24):

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
sudo apt install -y nodejs
```

A dedicated unprivileged user owning both the repo and the services (§3.6):

```bash
sudo adduser --disabled-password --gecos "" --home /srv/bvp bvp
```

**Not `adduser --system`, which is what this section said until 2026-08-08.**
A system user gets `/usr/sbin/nologin` and is not in `sudo`, and
`scripts/deploy.sh` runs *as* `bvp` and needs exactly two privileged calls:
restarting the API and reading its journal when the health check fails. The
narrow grant, rather than putting `bvp` in the `sudo` group:

```bash
printf '%s\n' \
  'bvp ALL=(root) NOPASSWD: /usr/bin/systemctl restart bvp-api' \
  'bvp ALL=(root) NOPASSWD: /usr/bin/journalctl -u bvp-api *' \
  | sudo tee /etc/sudoers.d/bvp
sudo chmod 440 /etc/sudoers.d/bvp
sudo visudo -c        # expect: /etc/sudoers.d/bvp: parsed OK
```

`bvp` has no password and cannot log in; reach it with `sudo -u bvp -H bash`.

`sqlite3` is installed for the backup in §6.1, and for the ad-hoc queries
`RUNBOOK.md` §3 and §7 tell you to run.

### 5.3 nginx — *verify:* `nginx -t`, then curl each of the three shapes

Three jobs: serve the SPA, reproduce Vite's `/api` rewrite (§2.4), and fence
off the internal views (§3.1).

**Committed as `deploy/nginx/bvp.conf.template`** (2026-08-08), with
`bvp-bootstrap.conf.template` for the first certificate. They are templates
rendered by `envsubst` into `/etc/nginx/sites-available/bvp` rather than
finished files, for two §3.6 reasons: the domain is environment, and
`certbot --nginx` **rewrites the site file it manages** — so certificates are
issued with `certonly --webroot`, which touches no tracked file. The abridged
shape:

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name <domain>;

    root /srv/bvp/web/build;
    index index.html;

    # adapter-static with fallback: 'index.html'. Without this, /book and
    # /performance 404 on refresh -- the SPA routes do not exist as files.
    location / {
        try_files $uri $uri/ /index.html;
    }

    # The trailing slash on proxy_pass is what strips /api. This is the exact
    # rewrite web/vite.config.js performs in development; without it every page
    # renders as an empty week rather than as an error.
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Internal views. Exact-match locations outrank the /api/ prefix above, so
    # each needs its own proxy_pass. See DEPLOY.md 3.1 -- these are the two
    # endpoints that would publish a return.
    location = /api/book {
        auth_basic "internal"; auth_basic_user_file /etc/nginx/.htpasswd-bvp;
        proxy_pass http://127.0.0.1:8000/book;
    }
    location = /api/performance {
        auth_basic "internal"; auth_basic_user_file /etc/nginx/.htpasswd-bvp;
        proxy_pass http://127.0.0.1:8000/performance;
    }

    # Long-lived hashed assets; index.html must not be cached.
    location /_app/ { expires 1y; add_header Cache-Control "public, immutable"; }
}
```

TLS via `certbot --nginx` once the DNS A record resolves. Certbot writes the
port-80 redirect itself.

**Verify all three shapes, not just the homepage:**

```bash
curl -sI  https://<domain>/                    # 200, text/html
curl -sI  https://<domain>/book                # 200 (SPA fallback, not 404)
curl -s   https://<domain>/api/health          # {"status":"ok",...}
curl -sI  https://<domain>/api/performance     # 401
```

`/api/health` returning JSON is the one that proves §2.4 is right.

### 5.4 The application — *verify:* `build.validate()` passes, 437 tests green

```bash
sudo -u bvp git clone git@github.com:andrewolobo/baba-vanga-premier.git /srv/bvp
cd /srv/bvp
sudo -u bvp python3 -m venv .venv
sudo -u bvp .venv/bin/pip install -e ".[serve,dev]" -c requirements.lock

sudo -u bvp .venv/bin/python -m engine.ingest.build   # expect: all passed, exit 0
sudo -u bvp .venv/bin/python -m pytest -q             # expect: 437 passed
```

The build step runs migrations, loads 16 seasons from the tracked CSVs, and
runs the integrity checks. `pytest` on the server is the §3.5 acceptance gate.

**Expect `436 passed, 1 skipped` on the server, not 437 passed.** This was
measured on 2026-08-08 by pointing `BVP_DB_PATH` at a freshly built store, and
it failed before it skipped.
`test_trials.py::test_the_real_ledger_holds_more_configurations_than_rows`
opens the **real** `db/premier.db` and asserts `configurations >= 133`; the
store the server builds has `gate_ledger` **empty**, because
`engine.ingest.build` loads `matches` and `player_seasons` and nothing else.
The test now skips where there is no ledger to guard, because an acceptance
gate that is known to fail is not a gate — and a tolerated failure becomes an
ignored one, on the same argument `RUNBOOK.md` §7 makes about warnings.

**The reason it is a skip and not a deletion is §6.1.** The empty ledger is not
a server problem to fix; it is a fact about where the measurement history
lives, and that fact turns out to matter more on the *development* machine than
on the server.

Then a dry cycle, which is `RUNBOOK.md` §3's T-7 check:

```bash
sudo -u bvp .venv/bin/python -m services.run_cycle --dry-run
```

**Expect exit 2 and `NO ENGLISH ROWS`** while out of season. That is the
correct answer, and confirming the empty-feed detector while the feed is
genuinely empty is the only cheap opportunity to confirm it.

### 5.5 systemd — *verify:* API answers after a reboot; timer shows a next run

**Committed at `deploy/systemd/`** — `bvp-api.service`, `bvp-cycle.service`,
`bvp-cycle.timer`. Each carries its reasoning inline; only the decisions are
repeated here, because a unit duplicated into prose is a unit that will
disagree with itself, which is this project's recorded failure mode
(`OUTSTANDING.md` §8).

```bash
sudo cp deploy/systemd/bvp-*.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bvp-api bvp-cycle.timer   # the TIMER, not the service
```

**Copied, not symlinked into the repo.** A `git pull` that changed a unit under
systemd's nose would leave the running service and the file on disk disagreeing
with nothing to say so. Copy, then `daemon-reload`, deliberately.

Four decisions worth stating outside the files:

- **The API binds `127.0.0.1`, one worker.** nginx is the only thing that
  should reach it, and nginx is what enforces basic auth on `/api/book` and
  `/api/performance` (§3.1) — an API on `0.0.0.0` lets anyone bypass that by
  going straight to the port. One worker because the API is read-only and there
  is no load here that needs more.
- **`ReadWritePaths=/srv/bvp/db` is not optional.** `ProtectSystem=strict`
  makes the hierarchy read-only, and **WAL is not a read-only mode**: opening
  the database creates and writes `premier.db-wal` and `premier.db-shm` even
  for a pure reader. Without it the API fails its first query with *attempt to
  write a readonly database*, which reads as a permissions bug rather than as
  WAL.
- **`bvp-cycle.service` has no `[Install]` section.** It is started by the
  timer. Enabling it directly would also run it at every boot — a fixture sync
  and a results fetch on each reboot, for nothing.
- **`OnFailure` is commented out until §6.2 exists.** Naming a unit that is not
  installed makes the service fail to load, and shipping a stub alert that
  quietly does nothing would be worse than shipping none.

Three things this buys, mapped to what the Windows setup did:

| Task Scheduler | systemd | note |
| --- | --- | --- |
| `-StartWhenAvailable` | `Persistent=true` | catches up a run missed while the VM was down |
| `-MultipleInstances IgnoreNew` | **free** | systemd will not run two instances of one unit — this closes `RUNBOOK.md` §8's "no lock file" gap at no cost |
| `LastTaskResult` | `systemctl status` / `journalctl -u` | plus §6.2's alerting, which Task Scheduler never had |

`SuccessExitStatus=2` is load-bearing and is the direct translation of
`RUNBOOK.md` §1. Without it systemd marks the unit **failed** every day of the
close season, `OnFailure` pages every day, and the alerts stop being read —
which is the exact failure the three-code design exists to prevent.

### 5.6 The deploy script — *verify:* run it once with no changes to pull

**Committed as `scripts/deploy.sh`.** Run it as the `bvp` user; it needs `sudo`
for exactly one thing, restarting the API, and asks for nothing else.

```
0. refuse if the working tree is dirty or the branch is not main
1. git pull --ff-only
2. pip install -e ".[serve,dev]" -c requirements.lock
3. npm ci && npm run build
4. migrate                       <-- BEFORE the API restarts
5. pytest -q                     <-- before the restart, so a failure changes nothing
6. systemctl restart bvp-api
7. curl /health, retrying        <-- and fail loudly, with the journal, if it never answers
```

**Migrate moved from step 3 to step 4, and the order is the point.** The hard
constraint is §3.7: `api/main.py` never migrates, so the schema must be current
before the API restarts. But the window between *schema changed* and *code that
expects it is running* is the only genuinely dangerous stretch of a deploy, and
`npm ci` can take a minute. Do the slow work first, then move the schema and
the code together.

Migrate is a one-liner rather than `run_cycle --dry-run`, which also migrates:
that would refit the artifact and hit the network as a side effect of asking
about the schema.

**Step 0 enforces §3.6.** A tracked file edited on the server makes the next
pull a conflict over SSH on a matchday. Catching it at deploy time is cheaper
than catching it then.

**Nothing user-visible changes until step 3.** A failure before it leaves the
running site untouched. Step 3 itself writes into `web/build`, which nginx
serves directly, so there is a ~2 s window mid-build where the site is
incomplete; at this traffic level that is acceptable, and if it ever is not,
build to a staging directory and swap a symlink that `root` points at.

---

## 6. Fault tolerance — `RUNBOOK.md` §8's four gaps

The gaps are *no backup, no alerting, no lock file, no hosting*. §5 closes
hosting, and §5.5 closes the lock file for free. The two that need building are
backup and alerting.

### 6.1 Backup — the only irreplaceable thing

`premier.db` holds what was predicted and when. Everything else on the VM is
reconstructible from git in minutes.

#### The development machine needs this more than the server does

**Found 2026-08-08, while working out why one test fails on a fresh store.**
The gate ledger — **90 rows**, the `87 runs / 45 questions / 167 configurations`
`OUTSTANDING.md` §0 quotes — lives in `db/premier.db` on the development
machine and **nowhere else**. It is gitignored. `engine.ingest.build` rebuilds
`matches` and `player_seasons` from the tracked CSVs and **does not rebuild the
ledger**, because nothing could: it is a record of measurements that were run,
not a derivation of the corpus.

`DEFLATION.md`'s entire multiplicity accounting reads it, `OUTSTANDING.md` §0
instructs every future thread to re-derive the count with
`trials.count_configurations(conn)` **rather than trusting the prose** — which
makes that file the authority — and the pre-committed P6 read depends on it.
There is no backup of any kind.

So §6.1's scope is wider than "back up the server":

| machine | holds | irreplaceable because |
| --- | --- | --- |
| server | `predictions`, `tips`, `clv_grades`, `serving_state` | opening-weekend predictions cannot be recovered afterwards |
| **development** | **`gate_ledger`** | **a record of what was measured, not a function of the data** |

The server's backup is not yet built and the machine does not yet exist. The
development machine exists now, and the same `VACUUM INTO` works on it today.
**Do that before the VM, not after** — it is the cheaper half of §6.1 and it
protects the older asset.

**`cp premier.db` is not a backup** and neither is a VM snapshot of it. Under
WAL, committed transactions can still be sitting in `premier.db-wal`, so a
plain copy can silently lose the most recent cycle — the one you most wanted.
`RUNBOOK.md` §8 already states this.

`bvp-backup.service` + `.timer`, 06:30 UTC — **a separate timer, not an
`ExecStartPost` on the cycle.** `ExecStartPost` does not run when `ExecStart`
fails, and a cycle that failed at `grade` may still have written predictions at
`serve`; the steps are independent by design and the backup should be too.

```bash
sqlite3 /srv/bvp/db/premier.db "VACUUM INTO '/var/backups/bvp/premier-$(date -u +%F).db'"
```

`VACUUM INTO` is safe to run while the API is up. Then:

1. upload to an Azure Blob container with **versioning on** and a lifecycle
   rule — 30 daily, 12 monthly is generous for a 44 MB file;
2. keep the last 7 locally so a mistake can be undone without a network round
   trip;
3. **restore drill, quarterly, written down when done.** Pull the newest blob,
   `PRAGMA integrity_check`, and compare `COUNT(*)` on `predictions` and `tips`
   against production. A backup that has never been restored is a belief, not a
   backup — and this project's own convention (§7.8: *a null needs a positive
   control*) is the same argument in a different domain.

### 6.2 Alerting — and the failure that alerting structurally cannot catch

Today nothing pushes. Failures are visible in the exit code, the log and
`serving_state`, all of which need someone to look.

**Three channels, because the three exit codes mean different things.** This is
`RUNBOOK.md` §1 turned into wiring, and collapsing them re-creates the problem
that section exists to prevent.

| condition | channel | urgency |
| --- | --- | --- |
| exit **1** — a step raised | `OnFailure=bvp-alert@.service` → push (email/webhook) | same day |
| exit **2** — ran, needs a look | append to a digest; one message Monday morning | weekly, unless it repeats into matchday |
| **no run at all** | **dead-man's switch** — see below | same day |

The third is the one that matters most and the one `OnFailure` **cannot**
provide: if the VM is off, or the timer got disabled, or systemd never started
it, there is no failure to hook. Nothing fires, and the first symptom is a
weekend of missing predictions — which `RUNBOOK.md` opens by naming as the
permanent, unrecoverable loss.

So `run_cycle.sh` pings a monitored URL on **every** completion, exit 0 or 2
alike, and the monitor alerts on **absence** past ~26 hours. Any of
healthchecks.io, Better Stack, or an Azure Monitor custom metric with a
"no data" alert rule will do; the mechanism matters less than the polarity —
**it must alert on silence, not on noise.**

`scripts/run_cycle.sh` is therefore the Linux twin of `run_cycle.ps1` with one
addition: run the module, tee to journald, ping the switch, and **propagate the
exit code unchanged**. Swallowing it is what the PowerShell version was written
to prevent.

### 6.3 What the fault tolerance does not cover, honestly

- **Single VM, single region.** A VM failure is a restore-and-rebuild, not a
  failover. At 44 MB and a 1.5 s refit, rebuild-from-git plus a blob restore is
  well under an hour. Multi-region is not worth its cost here and §3.2 would
  make it real work rather than configuration.
- **The upstream feed is a single point of failure with no fallback.**
  football-data.co.uk down on a matchday is `RUNBOOK.md` §5.5's playbook —
  a **manual** insert into `fixtures`, which is the interface. Nothing about
  moving to Azure improves that, and the FBref alternative is shelved and needs
  a headed browser (`OUTSTANDING.md` §4.1), which does not compose with an
  unattended VM at all.
- **Unattended security upgrades will eventually want a reboot.** Enable
  `unattended-upgrades`, set the reboot window well away from 06:00 UTC, and
  rely on `Persistent=true` to catch up any run it displaces.

---

## 7. Sequence

| # | step | gate |
| --- | --- | --- |
| 1 | Commit + push everything; fix `player.rar` / `player.png`; add `requirements.lock` | `git status` clean, `origin/main` moved |
| 2 | Provision VM, harden, UTC confirmed | ssh + `timedatectl` |
| 3 | Clone, venv, `ingest.build`, `pytest -q` | `all passed`; **437 passed** |
| 4 | systemd units for API and cycle | API answers after `reboot`; `systemctl list-timers` shows the next run |
| 5 | nginx + TLS + basic auth on the two internal endpoints | all four curls in §5.3 |
| 6 | `deploy.sh`, run once against no changes | `/api/health` answers afterwards |
| 7 | Backup timer + first restore drill | a restored copy passes `integrity_check` and matches row counts |
| 8 | Alerting: `OnFailure` + dead-man's switch | **test all three** — break the cycle on purpose, and stop the timer for a day |
| 9 | `RUNBOOK.md` gains an Ubuntu column; §8's gaps struck | the runbook describes the machine that is serving |

Steps 1–6 are the deployment. **7 and 8 are the fault-tolerance step and are
not optional extras** — until they are done, the system is hosted but silent,
and silence is the failure `services/run_cycle.py` was written to make
impossible.

Step 9 matters more than it looks. `RUNBOOK.md` is the operational authority
and it currently documents Task Scheduler on Windows. An operator following it
against an Ubuntu VM will find that half its commands do not exist — and this
project's recorded failure mode is documents drifting from what they describe
(`OUTSTANDING.md` §8).
