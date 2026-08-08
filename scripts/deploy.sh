#!/usr/bin/env bash
#
# Pull, rebuild, migrate, restart. docs/DEPLOY.md 5.6.
#
#   ./scripts/deploy.sh              # pull and deploy
#   ./scripts/deploy.sh --no-pull    # rebuild what is already checked out
#   ./scripts/deploy.sh --skip-tests # skip the acceptance gate (say why)
#
# Run as the user that owns the repo and the services (bvp). It needs sudo for
# exactly one thing -- restarting the API -- and asks for nothing else.
#
# ORDER MATTERS, and not in the obvious way:
#
#   pull -> pip -> npm -> MIGRATE -> restart -> verify
#
# api/main.py never migrates. `db.migrate` is called by services/run_cycle.py
# and engine/ingest/build.py; get_conn calls db.connect alone. So after a pull
# that adds a migration, the API must not be restarted until the schema is
# current -- it would come up querying a table that does not exist.
#
# Migrate is late rather than early for the other half of the same reason: the
# window between "schema changed" and "code that expects it is running" is the
# only genuinely dangerous part of a deploy, and npm ci can take a minute. Do
# the slow work first, then move the schema and the code together.
#
# Nothing user-visible changes until the npm build. If this script fails before
# then, the running site is untouched.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PULL=1
TESTS=1
while [ $# -gt 0 ]; do
    case "$1" in
        --no-pull)    PULL=0 ;;
        --skip-tests) TESTS=0 ;;
        -h|--help)    sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "deploy.sh: unknown option '$1'" >&2; exit 64 ;;
    esac
    shift
done

PYTHON="$REPO/.venv/bin/python"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[31mdeploy.sh: %s\033[0m\n' "$*" >&2; exit 1; }

[ -x "$PYTHON" ] || die "no venv at $PYTHON -- see docs/DEPLOY.md 5.4"

# --- 0. refuse to deploy from a tree that is not what git says it is ------- #
# docs/DEPLOY.md 3.6: everything environment-specific belongs in an env var or
# a unit file outside the repo. A hand-edit here makes the next pull a conflict
# over SSH on a matchday, so it is caught now rather than then.
step "checking the working tree"
if [ -n "$(git status --porcelain)" ]; then
    git status --short
    die "working tree is dirty. Commit, stash or revert -- do not edit tracked files on the server."
fi
branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$branch" = "main" ] || die "on branch '$branch', expected main"
before="$(git rev-parse --short HEAD)"
echo "clean, on main, at $before"

# --- 1. pull -------------------------------------------------------------- #
if [ "$PULL" -eq 1 ]; then
    step "git pull"
    # --ff-only: a merge commit created on the server is a divergence nobody
    # will ever reconcile.
    git pull --ff-only
    after="$(git rev-parse --short HEAD)"
    if [ "$before" = "$after" ]; then
        echo "already at $after -- nothing new"
    else
        echo "$before -> $after"
        git --no-pager log --oneline "$before..$after"
    fi
else
    step "skipping pull (--no-pull)"
fi

# --- 2. python deps ------------------------------------------------------- #
step "python dependencies"
# -c pins versions without changing what is required; pyproject stays the
# source of truth for WHAT, requirements.lock only fixes WHICH. DEPLOY.md 3.5.
"$PYTHON" -m pip install --quiet -e ".[serve,dev]" -c requirements.lock
echo "ok"

# --- 3. frontend ---------------------------------------------------------- #
step "frontend build"
# `npm ci` not `npm install`: ci installs exactly package-lock.json and fails
# if the lock and the manifest disagree, which is the property that makes a
# deploy reproducible.
#
# Vite empties web/build before writing it, and nginx serves that directory
# live, so there is a ~2s window where the site is incomplete. At this traffic
# level that is acceptable; if it ever is not, build to a staging directory and
# swap a symlink that nginx's root points at.
( cd web && npm ci --silent && npm run build )
echo "published root:"
ls -la web/build | sed 's/^/  /'

# --- 4. migrate ----------------------------------------------------------- #
step "database migrations"
# Not `run_cycle --dry-run`, which also migrates: that would refit the artifact
# and hit the network as a side effect of asking about the schema.
"$PYTHON" -c "
from engine import db
applied = db.migrate(db.connect())
print('applied:', applied or 'none (already current)')
"

# --- 5. acceptance gate --------------------------------------------------- #
if [ "$TESTS" -eq 1 ]; then
    step "test suite"
    # 44s, and it is the only thing that proves this environment matches the
    # one the code was written against -- an unpinned transitive dependency,
    # a different Python minor, a partial pull. It runs BEFORE the restart, so
    # a failure leaves the old API serving.
    #
    # Expect one skip on a server: the real-ledger guard in test_trials.py has
    # nothing to guard where gate_ledger is empty, which it always is on a
    # rebuilt store. See DEPLOY.md 5.4.
    "$PYTHON" -m pytest -q
else
    step "SKIPPING the test suite (--skip-tests)"
fi

# --- 6. restart and verify ------------------------------------------------ #
step "restarting the API"
sudo systemctl restart bvp-api

# uvicorn takes a moment to bind; a single immediate curl reports a failure
# that is really a race. Ten tries at 1s is far longer than it needs.
for i in $(seq 1 10); do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/health >/tmp/bvp-health.$$ 2>/dev/null; then
        echo "healthy after ${i}s:"
        sed 's/^/  /' /tmp/bvp-health.$$; rm -f /tmp/bvp-health.$$
        step "deployed $(git rev-parse --short HEAD)"
        exit 0
    fi
    sleep 1
done

rm -f /tmp/bvp-health.$$
echo "--- last 40 journal lines ---" >&2
sudo journalctl -u bvp-api -n 40 --no-pager >&2 || true
die "API did not answer /health within 10s. It is DOWN -- the site will show errors."
