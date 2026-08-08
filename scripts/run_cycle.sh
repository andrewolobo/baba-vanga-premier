#!/usr/bin/env bash
#
# Scheduled entry point for the serving cycle. The Linux twin of
# scripts/run_cycle.ps1 (docs/DEPLOY.md 2.5).
#
#   ./scripts/run_cycle.sh
#   ./scripts/run_cycle.sh --dry-run
#   ./scripts/run_cycle.sh --refreeze
#
# Exit codes come from services.run_cycle and mean different things:
#
#     0   clean
#     2   ran, but needs a look   (empty feed, unknown club, unpriceable fixture)
#     1   a step failed
#
# Two is not a worse one. A scheduler that treats every non-zero the same will
# page someone all summer for an out-of-season feed, and they will then stop
# reading the alerts -- which is the failure the whole design is avoiding. The
# systemd unit encodes this as `SuccessExitStatus=2`; see
# deploy/systemd/bvp-cycle.service.
#
# WHAT THIS DOES NOT DO, and the PowerShell version did: write a dated log file.
# That existed because Task Scheduler reports "last run result" and discards
# output, so a run was otherwise unreconstructable. journald does not discard
# output, so writing files as well would be a second copy that ages
# independently and that nobody prunes. Read a run with:
#
#     journalctl -u bvp-cycle.service -n 200
#     journalctl -u bvp-cycle.service --since today
#
# Run by hand, output simply goes to the terminal.

# NOT `set -e`. The entire purpose of this script is to observe a non-zero exit
# and report it, which errexit would pre-empt.
set -uo pipefail

usage() {
    sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
}

args=(-m services.run_cycle)
while [ $# -gt 0 ]; do
    case "$1" in
        -d|--dry-run)  args+=(--dry-run) ;;
        -r|--refreeze) args+=(--refreeze) ;;
        -h|--help)     usage; exit 0 ;;
        *) echo "run_cycle.sh: unknown option '$1'" >&2; exit 64 ;;
    esac
    shift
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || { echo "run_cycle.sh: cannot cd to $REPO" >&2; exit 1; }

# api/ and services/ are not installed packages -- pyproject's
# packages.find includes engine* only -- so the repo root must be the working
# directory. docs/DEPLOY.md 3.4.
PYTHON="${BVP_PYTHON:-$REPO/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python3 || true)"
fi
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "run_cycle.sh: no interpreter; expected $REPO/.venv/bin/python" >&2
    exit 1
fi

# Belt and braces over systemd, which already refuses to run two instances of
# one unit. This also covers the case systemd cannot see: a hand-run cycle
# while the timer fires. Re-running is safe and idempotent (RUNBOOK.md 6), so
# an overlap is wasteful rather than dangerous -- but the timer firing while
# the previous run is still going means that run is slow or wedged, which is
# exactly "ran, but a human should look".
#
# The lock lives beside the database rather than in /tmp because the systemd
# unit sets PrivateTmp=true: a /tmp lock would be invisible between the
# service and a hand-run shell, which is precisely the overlap it is for.
#
# The `command -v` branch is not defensive padding. Without it a MISSING flock
# takes the same path as a HELD lock: `flock` fails, the script says "another
# cycle is already running", and exits 2 -- a benign-looking message for a
# cycle that never ran at all. flock ships with util-linux and is present on
# every Ubuntu, so this only fires on a minimal image; the cost of getting it
# wrong is a matchday that goes unpriced while the log looks reasonable, which
# is the exact failure services/run_cycle.py exists to prevent.
#
# When it is absent, run anyway and say so. The lock is belt and braces over
# systemd, and re-running is idempotent -- so an unguarded run is a small risk
# and a skipped run is a permanent hole.
if command -v flock >/dev/null 2>&1; then
    LOCK="$REPO/db/.cycle.lock"
    mkdir -p "$REPO/db"
    exec 9>"$LOCK" || { echo "run_cycle.sh: cannot open $LOCK" >&2; exit 1; }
    if ! flock -n 9; then
        echo "run_cycle.sh: another cycle is already running; not starting a second" >&2
        echo "cycle exit 2 (ATTENTION -- overlapping run, the previous one is still going)"
        exit 2
    fi
else
    echo "run_cycle.sh: flock not found -- running WITHOUT an overlap guard" >&2
fi

"$PYTHON" "${args[@]}"
code=$?

case "$code" in
    0) verdict="clean" ;;
    2) verdict="ATTENTION -- see the log" ;;
    1) verdict="FAILED -- see the log" ;;
    *) verdict="unexpected exit code $code" ;;
esac
echo "cycle exit $code ($verdict)"

exit "$code"
