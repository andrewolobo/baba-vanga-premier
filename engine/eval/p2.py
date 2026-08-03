"""P2: the player prior, gated.

    python -m engine.eval.p2 --stage all

Runs the hypotheses pre-registered in `docs/P2_PLAN.md`. The pre-gate there
already says stop -- the squad aggregate is 0.980 collinear with the club's own
fitted strength, and no scored match in thirteen seasons is played by a club
carrying fewer than 25.8 effective matches of evidence. This module exists to
put that conclusion on the metric that selects rather than on a proxy, and to
prove the harness could have seen a prior had there been one.

H17 is the load-bearing arm. It hands the fit the club's *realised* season-N
strength, which is unknowable at the decision moment and is never served. If a
perfect prior does not move the score, then a null from H14 says nothing about
players and everything about the ridge, and that distinction is the whole point
of running this at all.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace

import numpy as np
import pandas as pd

from engine import db, ledger, store
from engine.eval import bootstrap, metrics, sweep
from engine.eval.p1 import BASE, served
from engine.eval.walkforward import _fit_at, _index, season_day, walk_forward
from engine.ingest.players import KIND_HEX
from engine.models import squad
from engine.seasons import DEV_SEASONS, SERVED_DIVISIONS, season_code, season_start_year

#: P1's frozen head. `BASE` already carries the COVID scoring embargo, which a
#: gate keeps and serving drops.
HEAD = replace(BASE, half_life=400.0, alpha=0.1)

#: Weight on the ridge target. 0.0 is the pre-P2 model exactly, so the sweep
#: nests its own baseline.
PRIOR_GRID = [0.0, 0.25, 0.5, 0.75, 1.0]

#: The oracle is also run at stronger penalties. At alpha=0.1 the likelihood
#: swamps the ridge, so a null could mean "no signal in the prior" or "no
#: channel for any prior". These separate the two.
ORACLE_ALPHAS = [0.1, 1.0, 5.0]

#: The population SPEC 3.3 was designed for: August, newly-promoted.
EARLY_SEASON_DAYS = 45


def scoring_filter(seasons):
    """Score only the seasons a prior actually exists for.

    The coefficient map needs `MIN_TRAIN_SEASONS` of finished history, so the
    first four seasons of the corpus have no prior and both arms return
    identical lambdas there. Scoring them would dilute every delta by about a
    third while adding no information -- a paired difference of exactly zero is
    not evidence of a small effect.
    """
    allowed = set(seasons)

    def restrict(out: pd.DataFrame) -> pd.DataFrame:
        work = served(out)
        return work[work["season"].isin(allowed)].reset_index(drop=True)

    return restrict


def _log(conn, kind, name, detail, reason):
    ledger.record(conn, kind=kind, name=name, purpose="dev", seasons=DEV_SEASONS,
                  divisions=SERVED_DIVISIONS, detail=detail, reason=reason)
    print(f"  [ledger] {kind}:{name}")


def _show(result: dict, order=None) -> None:
    for name in (order or result["arms"]):
        entry = result["arms"][name]
        vs = entry.get("vs_reference")
        note = "" if not vs else (f"  {vs['delta']:+.5f} "
                                  f"[{vs['ci_low']:+.5f}, {vs['ci_high']:+.5f}]")
        print(f"  {name:22s} deviance {entry['deviance']:.5f}  "
              f"1X2 {entry['ll_1x2']:.5f}{note}")


# --- the inputs the prior is built from ------------------------------------


def load_players(conn) -> pd.DataFrame:
    """Player-seasons with a canonical club name and a start year.

    Slug ids are dropped: `players.py` records that National League ids before
    2018-19 are name slugs which collide on common names and are not stable, so
    joining on them across seasons would silently merge two people.
    """
    frame = store.read_player_seasons(conn, seasons=DEV_SEASONS).for_measurement()
    frame = frame[(frame["player_id_kind"] == KIND_HEX) & frame["team"].notna()
                  & frame["minutes"].notna() & (frame["minutes"] > 0)].copy()
    frame["year"] = frame["season"].map(season_start_year)
    frame["club"] = frame["team"]
    return frame


def boundary_strengths(matches: pd.DataFrame, cfg, years) -> dict[int, tuple[dict, dict]]:
    """One fit per 1 August, on matches strictly before it."""
    idx = _index(matches, cfg.fit_divisions)
    out = {}
    for year in years:
        model, _ = _fit_at(idx, pd.Timestamp(year, *squad.BOUNDARY_MONTH_DAY), cfg)
        if model is None:
            continue
        out[year] = ({t: float(model.att[i]) for i, t in enumerate(idx.teams)},
                     {t: float(model.dfn[i]) for i, t in enumerate(idx.teams)})
    return out


def build_history(matches: pd.DataFrame, players: pd.DataFrame, cfg) -> pd.DataFrame:
    """One row per (season, division, club): what was known, what happened.

    `att_end` for season S is the boundary fit one year later, so it needs no
    extra fitting and cannot reach past the end of the season it summarises.
    """
    years = sorted({season_start_year(s) for s in matches["season"].unique()})
    strengths = boundary_strengths(matches, cfg, [*years, years[-1] + 1])

    division = pd.concat([
        matches[["season", "division", "home_team"]].rename(columns={"home_team": "club"}),
        matches[["season", "division", "away_team"]].rename(columns={"away_team": "club"}),
    ]).drop_duplicates(["season", "club"])

    rows = []
    for year in years:
        if year not in strengths:
            continue
        att, dfn = strengths[year]
        end = strengths.get(year + 1, ({}, {}))
        levels = squad.player_levels(players, year, att, dfn)
        channels = squad.club_channels(players, year, levels)
        if channels.empty:
            continue
        channels["season"] = season_code(year)
        channels["att_pre"] = channels["club"].map(att)
        channels["dfn_pre"] = channels["club"].map(dfn)
        channels["att_end"] = channels["club"].map(end[0])
        channels["dfn_end"] = channels["club"].map(end[1])
        rows.append(channels)

    history = pd.concat(rows, ignore_index=True)
    return history.merge(division, on=["season", "club"], how="left").dropna(
        subset=["att_pre", "dfn_pre", "division"])


def oracle_priors(history: pd.DataFrame) -> squad.SquadPriors:
    """THE POSITIVE CONTROL. Illegal by construction; never served.

    The prior for season N is the club's strength as fitted *after* season N has
    been played. Nothing legal can do better, so this is the ceiling: whatever
    it scores is the most any prior could ever be worth on this head, and if it
    scores nothing then the ridge is the constraint rather than the players.
    """
    known = history.dropna(subset=["att_end", "dfn_end"])
    return squad.SquadPriors(
        label="oracle(realised season-N strength; NOT SERVABLE)",
        att={s: dict(zip(g["club"], g["att_end"])) for s, g in known.groupby("season")},
        dfn={s: dict(zip(g["club"], g["dfn_end"])) for s, g in known.groupby("season")},
    )


# --- H14: the SPEC 3.3 prior, weight swept ---------------------------------


def h14_prior_sweep(conn, frame, priors, scored) -> sweep.SweepResult:
    print("\nH14  prior-anchored ridge: squad level, weight swept")
    result = sweep.run(frame, "squad_prior", PRIOR_GRID, HEAD,
                       more_regularised=lambda v: -float(v), score_filter=scored,
                       priors=priors)
    for arm in result.arms:
        mark = " <-- chosen" if arm.value == result.chosen.value else ""
        best = " (best)" if arm.value == result.best.value else ""
        print(f"  w={arm.value:<5} deviance {arm.deviance:.5f}  "
              f"paired se {arm.paired_stderr:.5f}  1X2 {arm.ll_1x2:.5f}{best}{mark}")
    _log(conn, ledger.SWEEP, "h14_squad_prior", result.as_detail(),
         "SPEC 3.3 prior-anchored ridge, weight swept, 1-SE (paired). "
         "Predicted chosen w <= 0.25 and |delta| < 0.0005 at every weight.")
    return result


# --- H15: which channels, if any ------------------------------------------


def h15_channels(conn, frame, priors: dict, scored) -> dict:
    print("\nH15  which squad channels carry anything")
    arms = {"baseline": HEAD}
    arms |= {name: replace(HEAD, squad_prior=1.0) for name in priors}
    result = sweep.compare(frame, arms, reference="baseline", score_on=scored,
                           priors=priors)
    _show(result, order=["baseline", "control", "level", "orthogonal", "all"])
    _log(conn, ledger.GATE, "h15_channels", result,
         "Each squad channel set as the ridge target at weight 1. The control "
         "arm carries no player data at all, so anything an arm shows over it "
         "is the players and not the reshaping. Predicted all |delta| < 0.0005.")
    return result


# --- H16: the population the feature was designed for ----------------------


def _cold_population(out: pd.DataFrame, changed: set, scored) -> pd.DataFrame:
    """August matches involving a club that changed division."""
    work = scored(out)
    early = season_day(work) <= EARLY_SEASON_DAYS
    touched = [(s, h) in changed or (s, a) in changed
               for s, h, a in zip(work["season"], work["home_team"], work["away_team"])]
    return work[early & np.array(touched)].reset_index(drop=True)


def h16_cold_population(conn, frame, priors, history, scored) -> dict:
    print("\nH16  restricted to August + a club that changed division")
    div = history.set_index(["season", "club"])["division"]
    changed = set()
    for (season, club), division in div.items():
        prev = div.get((season_code(season_start_year(season) - 1), club))
        if prev is not None and prev != division:
            changed.add((season, club))

    arms = {"baseline": HEAD, "level": replace(HEAD, squad_prior=1.0)}
    result = sweep.compare(frame, arms, reference="baseline",
                           score_on=lambda out: _cold_population(out, changed, scored),
                           priors={"level": priors})
    _show(result)
    _log(conn, ledger.GATE, "h16_cold_population", result,
         f"{result['n']} matches in the first {EARLY_SEASON_DAYS} days of a season "
         "involving a club that changed division -- the population SPEC 3.3 was "
         "written for. Predicted |delta| < 0.002, CI spans zero.")
    return result


# --- H17: the positive control --------------------------------------------


def h17_oracle(conn, frame, oracle, scored) -> dict:
    print("\nH17  positive control: an oracle prior, at three ridge strengths")
    arms, priors = {}, {}
    for alpha in ORACLE_ALPHAS:
        arms[f"base a{alpha:g}"] = replace(HEAD, alpha=alpha)
        name = f"oracle a{alpha:g}"
        arms[name] = replace(HEAD, alpha=alpha, squad_prior=1.0)
        priors[name] = oracle
    result = sweep.compare(frame, arms, reference="base a0.1", score_on=scored,
                           priors=priors)
    _show(result)
    _log(conn, ledger.PROBE, "h17_oracle_control", result,
         "A prior that knows the answer, at alpha 0.1/1/5. Separates 'no signal "
         "in the squad' from 'no channel through the ridge at P1's alpha'. "
         "Predicted oracle at a0.1 <= -0.010 with CI excluding zero.")
    return result


# --- H18: per division -----------------------------------------------------


def h18_divisions(conn, frame, priors, scored) -> dict:
    print("\nH18  per division")
    base = scored(walk_forward(frame, HEAD))
    arm = scored(walk_forward(frame, replace(HEAD, squad_prior=1.0), priors))
    key = ["match_date", "home_team", "away_team"]
    merged = base.set_index(key).join(arm.set_index(key), rsuffix="_p", how="inner")

    out = {}
    for division in SERVED_DIVISIONS:
        sub = merged[merged["division"] == division]
        left = metrics.goal_deviance(sub)
        # Rebuilt rather than renamed: `sub` still carries the baseline's own
        # lam_h, so renaming lam_h_p onto it produces two columns of that name
        # and the metric silently receives a 2-D array.
        right = metrics.goal_deviance(pd.DataFrame({
            "lam_h": sub["lam_h_p"], "lam_a": sub["lam_a_p"],
            "fthg": sub["fthg"], "ftag": sub["ftag"]}))
        blocks = bootstrap.week_blocks(sub.index.get_level_values("match_date"))
        cmp = bootstrap.paired(right, left, blocks)
        out[division] = cmp.as_dict() | {"n": len(sub)}
        print(f"  {division}  n={len(sub):5,}  {cmp.delta:+.5f} "
              f"[{cmp.ci[0]:+.5f}, {cmp.ci[1]:+.5f}]  {cmp.verdict}")
    _log(conn, ledger.GATE, "h18_divisions", out,
         "The level prior per served division. Predicted |delta| < 0.001 "
         "everywhere; E3 the likeliest to move.")
    return out


# --- H19: post-hoc, and labelled as such -----------------------------------


def h19_alpha_interaction(conn, frame, priors: dict, oracle, scored) -> dict:
    """NOT PRE-REGISTERED. Asked because H17 made it well-posed.

    H17 found a perfect prior worth only −0.00018 at P1's α=0.1 but −0.00694 at
    α=5. The ridge penalty is the channel a prior travels through, and P1 chose
    α by a sweep in which the target was fixed at zero -- where weak shrinkage
    is correct, because "league average" is a bad thing to be pulled toward.
    The two parameters are coupled and were optimised as if they were not.

    So: at each α, does the player prior beat a control prior carrying no player
    data at all? The control isolates the reshaping from the players, and the
    oracle marks the ceiling on the same aligned sample.
    """
    print("\nH19  (post-hoc) prior x ridge strength")
    arms = {"base a0.1": HEAD}
    priors_by_arm = {}
    for alpha in (1.0, 2.0, 5.0):
        arms[f"base a{alpha:g}"] = replace(HEAD, alpha=alpha)
        for name in ("control", "level"):
            arm = f"{name} a{alpha:g}"
            arms[arm] = replace(HEAD, alpha=alpha, squad_prior=1.0)
            priors_by_arm[arm] = priors[name]
    arms["oracle a5"] = replace(HEAD, alpha=5.0, squad_prior=1.0)
    priors_by_arm["oracle a5"] = oracle

    result = sweep.compare(frame, arms, reference="base a0.1", score_on=scored,
                           priors=priors_by_arm)
    _show(result)
    _log(conn, ledger.PROBE, "h19_alpha_interaction", result,
         "POST-HOC, not in P2_PLAN.md. H17 showed the ridge strength gates how "
         "much any prior can matter, and P1 chose alpha with the target pinned "
         "at zero. Does the player prior beat a no-player control at an alpha "
         "where priors transmit? Ceiling marked by the oracle.")
    return result


# --- driver ----------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", default="all",
                        choices=["all", "h14", "h15", "h16", "h17", "h18", "h19"])
    parser.add_argument("--out", default="docs/p2_results.json")
    args = parser.parse_args()

    conn = db.connect()
    matches = store.read_matches(conn, seasons=DEV_SEASONS).for_measurement()
    players = load_players(conn)
    print(f"{len(matches):,} matches, {len(players):,} player-seasons")

    history = build_history(matches, players, HEAD)
    print(f"{len(history):,} club-seasons with a squad aggregate "
          f"({history['season'].nunique()} seasons)")

    built = {
        "control": squad.build(history, (), label="control (no player data)"),
        "level": squad.build(history, ("sq_att", "sq_dfn"), label="level"),
        "orthogonal": squad.build(history, ("sq_age", "sq_churn"), label="orthogonal"),
        "all": squad.build(history, squad.CHANNELS, label="all channels"),
    }
    print("  priors built for seasons: "
          + ", ".join(f"{k}={len(v.att)}" for k, v in built.items()))

    prior_seasons = sorted(built["level"].att)
    scored = scoring_filter(prior_seasons)
    print(f"  scoring {prior_seasons[0]}-{prior_seasons[-1]}, the seasons a prior exists for")

    results = {"prior_seasons": prior_seasons}
    if args.stage in ("all", "h14"):
        results["h14"] = h14_prior_sweep(conn, matches, built["level"], scored).as_detail()
    if args.stage in ("all", "h15"):
        results["h15"] = h15_channels(conn, matches, built, scored)
    if args.stage in ("all", "h16"):
        results["h16"] = h16_cold_population(conn, matches, built["level"], history, scored)
    if args.stage in ("all", "h17"):
        results["h17"] = h17_oracle(conn, matches, oracle_priors(history), scored)
    if args.stage in ("all", "h18"):
        results["h18"] = h18_divisions(conn, matches, built["level"], scored)
    if args.stage in ("all", "h19"):
        results["h19"] = h19_alpha_interaction(conn, matches, built,
                                               oracle_priors(history), scored)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
