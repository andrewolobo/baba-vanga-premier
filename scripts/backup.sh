#!/usr/bin/env bash
#
# Back up the serving database. docs/DEPLOY.md 6.1.
#
#   ./scripts/backup.sh
#   ./scripts/backup.sh --dir /var/backups/bvp --keep 7
#
# WHY NOT `cp premier.db`. The database runs in WAL mode (engine/db.py), so
# committed transactions can still be sitting in premier.db-wal. A plain copy
# can therefore silently lose the most recent cycle -- the one you most wanted.
# `VACUUM INTO` writes a consistent snapshot and is safe to run while the API is
# up and while the cycle is writing. A VM-level disk snapshot has the same defect
# as `cp` at a different layer.
#
# WHY A SEPARATE TIMER, not ExecStartPost on bvp-cycle. ExecStartPost does not
# run when ExecStart fails, and the cycle's steps are deliberately independent:
# a run that failed at `grade` may still have written predictions at `serve`.
# The backup should not inherit the cycle's verdict.
#
# WHAT THIS PROTECTS. `predictions`, `tips`, `clv_grades` and `serving_state` --
# what was predicted and when. Everything else in the file is reproducible from
# the tracked CSVs by engine.ingest.build. The DEVELOPMENT machine holds a
# different irreplaceable thing, `gate_ledger`, and that is handled by
# scripts/export_ledger.py rather than here.

set -uo pipefail

DIR="/var/backups/bvp"
KEEP=7

while [ $# -gt 0 ]; do
    case "$1" in
        --dir)  DIR="$2"; shift ;;
        --keep) KEEP="$2"; shift ;;
        -h|--help) sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "backup.sh: unknown option '$1'" >&2; exit 64 ;;
    esac
    shift
done

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

PYTHON="${BVP_PYTHON:-$REPO/.venv/bin/python}"
[ -x "$PYTHON" ] || { echo "backup.sh: no interpreter at $PYTHON" >&2; exit 1; }

mkdir -p "$DIR" || { echo "backup.sh: cannot create $DIR" >&2; exit 1; }

# Full UTC timestamp, not just the date: two runs in one day must not collide,
# because `VACUUM INTO` refuses to overwrite an existing file and the retention
# below prunes by count rather than by name.
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$DIR/premier-$STAMP.db"

# The snapshot and its verification are one step. A backup that has never been
# read back is a belief rather than a backup -- the same argument as
# OUTSTANDING.md 7.8, that a null without a positive control is not a result.
"$PYTHON" - "$TARGET" <<'PY'
import sqlite3, sys, os
sys.path.insert(0, os.getcwd())
from engine import db

target = sys.argv[1]
db.connect().execute("VACUUM INTO ?", (target,))

copy = sqlite3.connect(target)
ok = copy.execute("PRAGMA integrity_check").fetchone()[0]
if ok != "ok":
    print(f"integrity_check FAILED on the snapshot: {ok}", file=sys.stderr)
    raise SystemExit(1)

# Row counts of the things that cannot be rebuilt from the CSVs. Printed rather
# than asserted: zero is correct out of season, and a threshold here would
# either fire all summer or be set so low it never fires.
counts = {t: copy.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
          for t in ("predictions", "tips", "clv_grades", "serving_state",
                    "gate_ledger")}
size = os.path.getsize(target)
print(f"snapshot ok  {size/1e6:.1f} MB  " +
      "  ".join(f"{k}={v}" for k, v in counts.items()))
PY
code=$?
if [ "$code" -ne 0 ]; then
    echo "backup.sh: snapshot failed; leaving $TARGET for inspection" >&2
    exit 1
fi
echo "wrote $TARGET"

# Retention. Newest KEEP survive. `ls -1t` orders by mtime, which is the same as
# the name order here but does not depend on the name format staying parseable.
mapfile -t old < <(ls -1t "$DIR"/premier-*.db 2>/dev/null | tail -n +$((KEEP + 1)))
if [ "${#old[@]}" -gt 0 ]; then
    printf 'pruning %d old snapshot(s)\n' "${#old[@]}"
    for f in "${old[@]}"; do rm -f -- "$f" && echo "  removed $(basename "$f")"; done
fi

# Off-machine copy. Local snapshots survive a mistake; they do not survive the
# VM. This stays OPT-IN rather than silently skipped: a backup script that
# appears to work while keeping every copy on the machine it is protecting is
# worse than one that says it is not finished.
if [ -n "${BVP_BACKUP_CONTAINER:-}" ]; then
    if ! command -v az >/dev/null 2>&1; then
        echo "backup.sh: BVP_BACKUP_CONTAINER is set but the az CLI is absent" >&2
        exit 1
    fi
    az storage blob upload --container-name "$BVP_BACKUP_CONTAINER" \
        --file "$TARGET" --name "$(basename "$TARGET")" --only-show-errors \
        || { echo "backup.sh: upload FAILED -- the snapshot is local only" >&2; exit 1; }
    echo "uploaded to $BVP_BACKUP_CONTAINER"
else
    echo "NOTE: BVP_BACKUP_CONTAINER unset -- snapshots are on this VM ONLY," \
         "which does not survive losing it (docs/DEPLOY.md 6.1)" >&2
fi
