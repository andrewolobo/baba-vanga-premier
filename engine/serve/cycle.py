"""The weekly serving cycle: freeze, predict, write.

    python -m engine.serve.cycle                 # predict pending fixtures
    python -m engine.serve.cycle --refreeze      # refit the artifact first
    python -m engine.serve.cycle --dry-run

The head is refit *weekly* rather than per request, matching what P1 measured:
H1 found day-frozen refits worth 0.00007 nats over weekly, so the serving
cadence and the evaluation cadence are the same thing and the base score
transfers directly to what is served.

Serving reads sealed seasons under `Purpose.LIVE`. That is not a hole in the
holdout: pricing an August 2026 fixture needs 2023-26 results to know where
clubs currently stand, and `Corpus.for_measurement()` refuses a LIVE frame, so
the same data cannot be used to score a model.

Predictions are append-only. Re-running a cycle does not overwrite: it skips
fixtures already priced by this artifact at this information set, unless asked
otherwise. What was served, and when, has to stay true afterwards.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import replace
from pathlib import Path

import pandas as pd

from engine import config, db, store
from engine.eval import metrics
from engine.eval.p1 import BASE
from engine.ingest.holdout import Purpose
from engine.serve.artifact import Artifact, freeze

#: The frozen head. Not swept here and not swept again without a ledger entry.
#:
#: Re-frozen 2026-08-04 to adopt the shots-on-target channel: goal deviance
#: −0.00422 [−0.00535, −0.00307], negative in all four served divisions with
#: every interval excluding zero, pooled deficit to market +0.01410 → +0.01230
#: (`SHOTS_TARGET.md`). The base score was re-issued at the same time
#: (`BASELINE.md`); the two move together or neither moves.
#:
#: The evaluation modules deliberately do NOT import this. `p2.py`, `p3.py` and
#: `p4_shots.py` each pin the head as it stood when they ran, so re-running them
#: still reproduces the documents they produced. Serving moves forward; history
#: does not.
SERVING_CONFIG = replace(BASE, half_life=400.0, alpha=0.1, embargo_regimes=(),
                         shots_blend=0.3)

ARTIFACT_DIR = config.DB_DIR / "artifacts"
INFORMATION_SET = "pre_close"


def latest_artifact(directory: Path = ARTIFACT_DIR) -> Artifact | None:
    paths = sorted(Path(directory).glob("*.json"), key=lambda p: p.stat().st_mtime)
    return Artifact.load(paths[-1]) if paths else None


def build_artifact(conn: sqlite3.Connection, cutoff=None,
                   directory: Path = ARTIFACT_DIR) -> tuple[Artifact, Path]:
    """Refit and freeze at `cutoff` (default today)."""
    cutoff = pd.Timestamp(cutoff or pd.Timestamp.now().normalize())
    frame = store.read_matches(conn, purpose=Purpose.LIVE).frame
    frame["match_date"] = pd.to_datetime(frame["match_date"])
    artifact = freeze(frame, cutoff, SERVING_CONFIG)
    return artifact, artifact.save(directory)


def register(conn: sqlite3.Connection, artifact: Artifact, path: Path | None = None) -> None:
    """Record the artifact so a stored prediction can be traced to a real fit."""
    conn.execute(
        "INSERT OR IGNORE INTO model_runs (model_version, fitted_at, config_label,"
        " n_train, n_teams, corpus_digest, artifact_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (artifact.version, artifact.fitted_at, SERVING_CONFIG.label(),
         artifact.n_train, len(artifact.teams), artifact.corpus_digest,
         str(path) if path else None),
    )
    conn.commit()


def pending_fixtures(conn: sqlite3.Connection, version: str,
                     *, information_set: str = INFORMATION_SET,
                     force: bool = False) -> pd.DataFrame:
    """Fixtures with no prediction yet from this artifact at this information set."""
    clause = "" if force else (
        " AND NOT EXISTS (SELECT 1 FROM predictions p WHERE p.fixture_id = f.fixture_id"
        "                 AND p.model_version = ? AND p.information_set = ?)"
    )
    params = [] if force else [version, information_set]
    return pd.read_sql_query(
        "SELECT f.*, h.canonical_name AS home_team, a.canonical_name AS away_team "
        "FROM fixtures f "
        "JOIN teams h ON h.team_id = f.home_team_id "
        "JOIN teams a ON a.team_id = f.away_team_id "
        f"WHERE 1=1{clause} ORDER BY f.match_date, f.fixture_id",
        conn, params=params,
    )


def servable(fixtures: pd.DataFrame, artifact: Artifact) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split pending fixtures into (can price, cannot).

    `Artifact.predict` raises on a club it has never seen, deliberately, so that
    a cold start is never hidden behind a silent league average. That is right
    for a single call and wrong for a scheduled run: the corpus gains a club
    almost every season and every one of them arrives in the National League, so
    one newly-promoted side would otherwise take the whole matchday down with
    it -- Premier League fixtures included.

    Splitting keeps both properties. Unknown clubs are still never averaged over;
    they are reported by name and left unpriced.
    """
    known = set(artifact.teams)
    ok = fixtures["home_team"].isin(known) & fixtures["away_team"].isin(known)
    return (fixtures[ok].reset_index(drop=True),
            fixtures[~ok].reset_index(drop=True))


def unknown_clubs(fixtures: pd.DataFrame, artifact: Artifact) -> list[str]:
    """The club names in `fixtures` the artifact has never seen, sorted."""
    named = set(fixtures["home_team"]) | set(fixtures["away_team"])
    return sorted(named - set(artifact.teams))


def serve(conn: sqlite3.Connection, artifact: Artifact, *,
          information_set: str = INFORMATION_SET, force: bool = False,
          dry_run: bool = False) -> pd.DataFrame:
    """Price every pending fixture the artifact knows. Returns what was written."""
    fixtures = pending_fixtures(conn, artifact.version,
                               information_set=information_set, force=force)
    if fixtures.empty:
        return fixtures
    fixtures, _ = servable(fixtures, artifact)
    if fixtures.empty:
        return fixtures

    lam_h, lam_a = artifact.predict(list(fixtures["home_team"]), list(fixtures["away_team"]))
    probs = metrics.model_probs(lam_h, lam_a)
    out = pd.concat([fixtures.reset_index(drop=True), probs], axis=1)
    out["lam_h"], out["lam_a"] = lam_h, lam_a

    if not dry_run:
        # served_at is supplied explicitly at microsecond resolution rather than
        # left to the column default, which is `datetime('now')` and therefore
        # only accurate to the second. Two deliberate re-serves inside one
        # second are rare in production but routine in tests, and they would
        # collide on the uniqueness key -- turning an intended append into a
        # crash. The timestamp is part of the key, so it has to be able to tell
        # two serves apart.
        served_at = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%f")
        conn.executemany(
            "INSERT INTO predictions (fixture_id, model_version, information_set,"
            " served_at, lam_h, lam_a, p_home, p_draw, p_away, p_over25, p_under25,"
            " calibrated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            [(int(r.fixture_id), artifact.version, information_set, served_at,
              float(r.lam_h), float(r.lam_a), float(r.p_h), float(r.p_d),
              float(r.p_a), float(r.p_over), float(r.p_under))
             for r in out.itertuples()],
        )
        conn.commit()
        out["served_at"] = served_at
    return out


def snapshot(conn: sqlite3.Connection, *, cycle_label: str, version: str,
             artifact_path, fixtures_seen: int, predictions_written: int,
             bets_written: int, rule_version: str, notes: str | None = None) -> None:
    conn.execute(
        "INSERT INTO serving_state (cycle_label, model_version, artifact_path,"
        " fixtures_seen, predictions_written, bets_written, rule_version, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (cycle_label, version, str(artifact_path) if artifact_path else None,
         fixtures_seen, predictions_written, bets_written, rule_version, notes),
    )
    conn.commit()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refreeze", action="store_true", help="refit before serving")
    parser.add_argument("--cutoff", help="training cutoff for --refreeze (default today)")
    parser.add_argument("--force", action="store_true", help="re-price already-priced fixtures")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    conn = db.connect()
    db.migrate(conn)

    path = None
    artifact = None if args.refreeze else latest_artifact()
    if artifact is None:
        artifact, path = build_artifact(conn, args.cutoff)
        print(f"froze {artifact.version} ({SERVING_CONFIG.label()}, "
              f"n_train={artifact.n_train}, cutoff={artifact.fitted_at[:10]})")
    else:
        print(f"using {artifact.version} (cutoff {artifact.fitted_at[:10]})")
    if not args.dry_run:
        register(conn, artifact, path)

    _, unknown = servable(
        pending_fixtures(conn, artifact.version, force=args.force), artifact)
    if not unknown.empty:
        print(f"skipping {len(unknown)} fixture(s); artifact has never seen: "
              f"{', '.join(unknown_clubs(unknown, artifact))}")

    served = serve(conn, artifact, force=args.force, dry_run=args.dry_run)
    print(f"priced {len(served)} fixture(s)")
    for row in served.itertuples():
        print(f"  {row.match_date} {row.division} {row.home_team} v {row.away_team}: "
              f"H {row.p_h:.3f} D {row.p_d:.3f} A {row.p_a:.3f} | O2.5 {row.p_over:.3f}")
    if args.dry_run:
        print("(dry run -- nothing written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
