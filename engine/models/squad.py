"""Squad priors: the P2 ridge target, refreshed at season boundaries only.

SPEC §3.3 wants player aggregates entering as a **prior on the team's
`att`/`dfn`**, not as a competing additive term. This module builds that prior.

Three constraints shape everything here, and none of them is optional.

**The as-of rule.** `asof.PLAYER_SEASON_RULE`: a prediction in season N may read
player files for seasons ≤ N−1, and season N's own file is embargoed entire.
Knowing who plays for a club in season N requires reading that file, and doing
so encodes both the transfer and the survivorship. So the roster is the club's
**N−1** roster, refreshed once a year, and never the actual squad.

**The prior is a prediction, not a restatement.** The naive aggregate --
minutes-weighted strength of the clubs a squad has played for -- came back 0.980
collinear with the club's own fitted `att` (`P2_PLAN.md` §1.1), because the N−1
roster plays 52-75% of the club's own N−1 minutes. So the prior is instead the
**out-of-sample fitted prediction of where the club's strength ends up**, with
the squad channels as candidate regressors alongside what the GLM already knows.
A channel that carries nothing gets a coefficient near zero and the arm degrades
to the control rather than to noise.

**Nothing is fitted on the season it is applied to.** The coefficient map for
season N is fitted on seasons strictly earlier, and needs a realised endpoint,
so it uses seasons ≤ N−1. `att_end` for season S is simply `att_pre` at the S+1
boundary -- the same fits, read one boundary later -- so this costs no extra
fitting and cannot reach forward by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from engine.seasons import season_code, season_start_year

#: How fast a player's older seasons stop describing him. Swept in P2 rather
#: than asserted; 0.5 per season is the starting point.
SEASON_DECAY = 0.5

#: The boundary at which the player layer refreshes. Inside the dormant window
#: (`walkforward.OFFSEASON_*`), after the transfer window opens, before any
#: match of season N is played.
BOUNDARY_MONTH_DAY = (8, 1)

#: Seasons of history before a coefficient map is fitted at all. Below this the
#: prior stays at zero, which is the pre-P2 cold-start behaviour.
MIN_TRAIN_SEASONS = 3

#: Squad channels available to the map. `att`/`dfn` are club-strength by
#: association and are near-collinear with the GLM; the rest are not.
CHANNELS = ("sq_att", "sq_dfn", "sq_age", "sq_churn", "sq_ga90", "sq_top11")


@dataclass(frozen=True)
class SquadPriors:
    """Per-club ridge targets, keyed by season code.

    The scaling weight lives on `WalkForwardConfig.squad_prior`, not here, so
    the sweep has one source of truth and an arm at weight 0 is bit-for-bit the
    pre-P2 model rather than approximately it.
    """

    label: str
    att: dict[str, dict[str, float]]
    dfn: dict[str, dict[str, float]]

    def at(self, cutoff: pd.Timestamp, teams: tuple[str, ...]):
        """(prior_att, prior_dfn) aligned to `teams`, or None if unavailable.

        Aligned on demand rather than stored positionally: the caller's team
        ordering is not this module's business, and a silent mismatch would
        assign one club's prior to another.
        """
        season = season_at(cutoff)
        att = self.att.get(season)
        if att is None:
            return None
        dfn = self.dfn[season]
        return (np.array([att.get(t, 0.0) for t in teams]),
                np.array([dfn.get(t, 0.0) for t in teams]))


def season_at(cutoff: pd.Timestamp) -> str:
    """The season a fit cutoff belongs to. Boundary is 1 August, not 1 July.

    `walkforward.SEASON_BOUNDARY` is 1 July because it only has to separate
    matches, and nothing is played in July. The player layer refreshes later,
    once the transfer window has been open a month, so the two boundaries are
    deliberately different dates.
    """
    day = pd.Timestamp(cutoff)
    month, dom = BOUNDARY_MONTH_DAY
    year = day.year if (day.month, day.day) >= (month, dom) else day.year - 1
    return season_code(year)


# --- the aggregates --------------------------------------------------------


def player_levels(players: pd.DataFrame, year: int, att: dict[str, float],
                  dfn: dict[str, float], season_decay: float = SEASON_DECAY) -> pd.DataFrame:
    """One row per player: what his career to season N−1 says about him.

    `att`/`dfn` are the *current* strengths of the clubs he played for, which is
    a deliberate simplification -- a player at Wolves in 2015 is scored against
    Wolves as they are now, not as they were. The alternative needs a strength
    estimate per club per season, and the pre-gate says the whole channel is
    worth ~0.01 R², which does not justify it.
    """
    hist = players[players["year"] < year]
    hist = hist[hist["minutes"].notna() & (hist["minutes"] > 0)]
    if hist.empty:
        return pd.DataFrame(columns=["p_att", "p_dfn", "p_age", "p_ga90"])

    unmapped = hist.loc[~hist["club"].isin(att), "club"].unique()
    if len(unmapped):
        # Left alone this is silent rather than wrong-looking: the weighted sums
        # below skip NaN while the divisor does not, so an unmapped club would
        # drag its players' level toward zero and read as a weak squad.
        raise ValueError(
            f"{len(unmapped)} clubs have player rows but no fitted strength "
            f"({sorted(unmapped)[:5]}); their players' level would be biased "
            "toward zero rather than dropped")

    w = hist["minutes"].to_numpy(dtype=float) * np.power(
        season_decay, year - hist["year"].to_numpy() - 1)
    work = pd.DataFrame({
        "player_id": hist["player_id"].to_numpy(),
        "w": w,
        "w_att": w * hist["club"].map(att).to_numpy(dtype=float),
        "w_dfn": w * hist["club"].map(dfn).to_numpy(dtype=float),
        "minutes": hist["minutes"].to_numpy(dtype=float),
        "age": hist["age"].to_numpy(dtype=float),
        "ga": (hist["goals_non_pk"].fillna(0) + hist["assists"].fillna(0)).to_numpy(dtype=float),
    })
    g = work.groupby("player_id")
    total = g["w"].sum()
    out = pd.DataFrame({
        "p_att": g["w_att"].sum() / total,
        "p_dfn": g["w_dfn"].sum() / total,
        # Age at N−1, not a weighted average: a player has one age.
        "p_age": g["age"].max(),
        "p_ga90": 90.0 * g["ga"].sum() / g["minutes"].sum().clip(lower=1.0),
    })
    return out


def club_channels(players: pd.DataFrame, year: int, levels: pd.DataFrame) -> pd.DataFrame:
    """One row per club: its season N−1 roster, weighted by minutes played for it.

    Weighted by minutes *for that club*, so a player who arrived in January
    counts for the half-season he was actually there.
    """
    prev = players[(players["year"] == year - 1) & players["minutes"].notna()]
    prev = prev[prev["minutes"] > 0]
    if prev.empty:
        return pd.DataFrame(columns=["club", *CHANNELS])

    two_back = set(zip(*(players.loc[players["year"] == year - 2, c]
                         for c in ("club", "player_id"))))
    rows = []
    for club, r in prev.groupby("club"):
        w = r["minutes"].to_numpy(dtype=float)
        ids = r["player_id"]

        def weighted(column: str) -> float:
            v = ids.map(levels[column]).to_numpy(dtype=float) if len(levels) else np.array([])
            ok = np.isfinite(v)
            return float(np.average(v[ok], weights=w[ok])) if ok.any() else np.nan

        held = np.array([(club, p) in two_back for p in ids])
        rows.append({
            "club": club,
            "sq_att": weighted("p_att"),
            "sq_dfn": weighted("p_dfn"),
            "sq_age": weighted("p_age"),
            "sq_ga90": weighted("p_ga90"),
            # Share of last season's minutes played by someone who was NOT at
            # the club the season before: how much this club churns.
            "sq_churn": 1.0 - float(w[held].sum() / w.sum()),
            # Minutes concentration: reliance on a settled first eleven.
            "sq_top11": float(np.sort(w)[::-1][:11].sum() / w.sum()),
        })
    return pd.DataFrame(rows)


# --- the coefficient map ---------------------------------------------------


def _zscore(frame: pd.DataFrame, columns, by) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        g = out.groupby(by)[column]
        sd = g.transform("std").replace(0.0, np.nan)
        out[column] = (out[column] - g.transform("mean")) / sd
    return out.fillna(dict.fromkeys(columns, 0.0))


def _lstsq_predict(train_x, train_y, apply_x):
    beta, *_ = np.linalg.lstsq(train_x, train_y, rcond=None)
    return apply_x @ beta, beta


def build(history: pd.DataFrame, channels: tuple[str, ...], *, label: str,
          min_train_seasons: int = MIN_TRAIN_SEASONS) -> SquadPriors:
    """Fit the map season by season and emit the priors it implies.

    `history` carries one row per (season, division, club) with `att_pre`,
    `dfn_pre`, `att_end`, `dfn_end` and the channels. For season N the map is
    fitted on every row whose season is strictly earlier and whose endpoint is
    known, then applied to season N's rows.

    With `channels=()` this is the control arm: a prior built only from what the
    GLM already knows. Any effect an arm shows over that control is the players'
    contribution and not the reshaping's.
    """
    work = _zscore(history, channels, ["season", "division"]) if channels else history.copy()
    work = work.sort_values("season").reset_index(drop=True)
    seasons = sorted(work["season"].unique())

    att_out: dict[str, dict[str, float]] = {}
    dfn_out: dict[str, dict[str, float]] = {}
    features = ["att_pre", "dfn_pre", *channels]

    for season in seasons:
        train = work[(work["season"] < season) & work["att_end"].notna()]
        if train["season"].nunique() < min_train_seasons:
            continue
        train = train.dropna(subset=features)
        target = work[work["season"] == season].dropna(subset=features)
        if len(train) < 50 or target.empty:
            continue

        design = np.column_stack([np.ones(len(train))] + [train[f].to_numpy(float)
                                                          for f in features])
        applied = np.column_stack([np.ones(len(target))] + [target[f].to_numpy(float)
                                                            for f in features])
        att_hat, _ = _lstsq_predict(design, train["att_end"].to_numpy(float), applied)
        dfn_hat, _ = _lstsq_predict(design, train["dfn_end"].to_numpy(float), applied)
        clubs = target["club"].to_numpy()
        att_out[season] = dict(zip(clubs, att_hat))
        dfn_out[season] = dict(zip(clubs, dfn_hat))

    return SquadPriors(label=label, att=att_out, dfn=dfn_out)
