#!/usr/bin/env bash
#
# One command for the whole local stack: cycle once, then API and frontend.
# The Linux/Mac twin of dev.ps1 -- runs the three pieces of README.md's
# "Run it locally" in one shell instead of three.
#
#   ./scripts/dev.sh                 # cycle once, then API + frontend
#   ./scripts/dev.sh --skip-cycle    # servers only
#   ./scripts/dev.sh --api-port 8001 --web-port 5174
#
# The cycle runs first and to completion, never alongside the servers, so its
# exit code is one you actually read instead of losing in request logs. A
# non-zero cycle exit is reported but does not stop the servers -- empty
# pages are a documented, correct state (README.md "Empty pages").
#
# Ctrl-C stops both. Each server starts in its own session (setsid) so its
# child processes (uvicorn's workers, vite's esbuild) die with it too --
# `kill` alone would leave them holding the port.

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

API_PORT=8000
WEB_PORT=5173
SKIP_CYCLE=0
while [ $# -gt 0 ]; do
    case "$1" in
        --skip-cycle) SKIP_CYCLE=1 ;;
        --api-port)   API_PORT="$2"; shift ;;
        --web-port)   WEB_PORT="$2"; shift ;;
        -h|--help)    sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "dev.sh: unknown option '$1'" >&2; exit 64 ;;
    esac
    shift
done

PYTHON="$REPO/.venv/bin/python"
step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[31mdev.sh: %s\033[0m\n' "$*" >&2; exit 1; }

# --- preflight -------------------------------------------------------------
# Each of these is a failure that otherwise surfaces as an unrelated traceback
# several seconds later, once two other processes are already running.

[ -x "$PYTHON" ] || die "no venv at $PYTHON -- see README.md"

"$PYTHON" -c "import fastapi, uvicorn" >/dev/null 2>&1 || \
    die "the API's dependencies are an extra, not a base dependency: pip install -e \".[serve]\""

[ -d "$REPO/web/node_modules" ] || die "web/node_modules is missing: cd web && npm install"

port_in_use() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3<&- 3>&-; }
for p in "$API_PORT" "$WEB_PORT"; do
    port_in_use "$p" && die "port $p is already in use -- is the stack already running?"
done

# --- 1. the cycle ------------------------------------------------------- #
if [ "$SKIP_CYCLE" -eq 0 ]; then
    step "running the cycle"
    "$REPO/scripts/run_cycle.sh" || echo "cycle exit $? -- starting the servers anyway; see the log"
else
    step "skipping the cycle (--skip-cycle)"
fi

# --- 2 and 3. the servers ------------------------------------------------ #
# No --reload: uvicorn's reloader watches the working directory, and the cycle
# writes db/premier.db inside it. Reloading on your own database is a loop.
step "starting API on :$API_PORT and web on :$WEB_PORT"

setsid "$PYTHON" -m uvicorn api.main:app --port "$API_PORT" &
api_pid=$!

# vite proxies /api to the API; BVP_API_PORT keeps that pointed at the right
# place instead of the hardcoded default. See web/vite.config.js.
export BVP_API_PORT="$API_PORT"
(cd "$REPO/web" && exec setsid npm run dev -- --port "$WEB_PORT") &
web_pid=$!

cleanup() {
    for pid in "$api_pid" "$web_pid"; do
        kill -TERM "-$pid" 2>/dev/null
    done
}
trap cleanup EXIT INT TERM

echo ""
echo "  app  http://localhost:$WEB_PORT   <- use localhost, not 127.0.0.1 (see README)"
echo "  api  http://127.0.0.1:$API_PORT/health"
echo "  Ctrl-C to stop both."
echo ""

# If one server dies, stop the other: half a stack looks like a working one
# right up until the page is blank for a reason nobody can see.
wait -n "$api_pid" "$web_pid"
if kill -0 "$api_pid" 2>/dev/null; then
    echo "Frontend exited."
else
    echo "API exited."
fi
