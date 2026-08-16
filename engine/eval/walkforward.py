"""The walk-forward harness: day-frozen refits, regime embargo, arms.

Every lambda this produces comes from a fit that saw only matches strictly
earlier than its own cutoff, and the harness asserts that rather than trusting
it. Fitting costs 25 ms on a typical window, so nothing here is compromised for
speed -- the cadence is chosen to match how the engine will actually serve, not
to fit in a coffee break.

Three arms are configurable, each corresponding to an open decision:

  `fit_divisions`          NEW-1. Whether National League matches enter the
                           joint fit. They are never scored either way.
  `season_boundary_shrink` OPEN-3 (c). Pull strengths toward league average in
                           proportion to how much of the training weight
                           predates the current season's start.
  `offseason_gap_days`     OPEN-3 (b). Count the summer as `k` days rather than
                           its calendar length. Expected to hurt; kept as a
                           control that moves the opposite way.
  `squad_prior`            P2. Weight on the squad-derived ridge target passed
                           in as `priors`. At 0, or with no `priors`, the fit
                           is bit-for-bit the pre-P2 one.

`embargo_regimes` removes matches from *scoring*, never from training. Dropping
the COVID window from training would leave a fifteen-month hole for decay to
bridge, so 2021-22 would be predicted from February 2020 form -- a worse
distortion than the one being repaired, and one the live model never faces,
since a fit made in 2026 does not reach back that far.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from typing import Protocol

import numpy as np
import pandas as pd

from engine.models import poisson as poisson_model
from engine.seasons import REGIMES, ALL_DIVISIONS


class RidgeTarget(Protocol):
    """What the P2 arm needs from a prior. `engine.models.squad.SquadPriors`
    satisfies it; stated as a protocol so this module keeps no dependency on
    the player layer."""

    def at(self, cutoff: pd.Timestamp,
           teams: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray] | None: ...

#: Calendar window treated as the off-season by the `offseason_gap_days` arm.
#: English football is dormant across it in every season on the corpus. The end
#: is exclusive (1 August, not 31 July) so that the window's length and the
#: difference between its endpoints are the same number -- they are not, if the
#: end is inclusive, and the resulting one-day error would be silent.
OFFSEASON_START = (6, 1)   # 1 June
OFFSEASON_END = (8, 1)     # 1 August, exclusive
_OFFSEASON_LENGTH = 61

#: A season is taken to begin on 1 July, which is division-agnostic and sits
#: inside the dormant window, so no match is ever assigned to the wrong side.
SEASON_BOUNDARY = (7, 1)

CADENCES = ("daily", "weekly", "fortnightly")


@dataclass(frozen=True)
class WalkForwardConfig:
    half_life: float = poisson_model.DEFAULT_HALF_LIFE_DAYS
    alpha: float = poisson_model.DEFAULT_ALPHA
    cadence: str = "weekly"
    burn_in_days: int = 365
    min_train_matches: int = 200
    horizon_half_lives: float = poisson_model.DECAY_HORIZON_HALF_LIVES
    fit_divisions: tuple[str, ...] = ALL_DIVISIONS
    season_boundary_shrink: float | None = None
    offseason_gap_days: float | None = None
    squad_prior: float | None = None
    #: P4-shots. Weight on a shots-on-target strength fit, blended into the
    #: goal-fitted strengths. None or 0.0 leaves the head bit-for-bit unchanged.
    shots_blend: float | None = None
    #: Which coefficients the blend touches: "both", "att" or "dfn" (H21).
    shots_blend_sides: str = "both"
    embargo_regimes: tuple[str, ...] = ()

    def label(self) -> str:
        bits = [f"H{self.half_life:g}", f"a{self.alpha:g}", self.cadence,
                "+".join(self.fit_divisions)]
        if self.season_boundary_shrink is not None:
            bits.append(f"shrink{self.season_boundary_shrink:g}")
        if self.offseason_gap_days is not None:
            bits.append(f"gap{self.offseason_gap_days:g}")
        if self.squad_prior is not None:
            bits.append(f"prior{self.squad_prior:g}")
        if self.shots_blend:
            bits.append(f"sot{self.shots_blend:g}"
                        + ("" if self.shots_blend_sides == "both"
                           else f"-{self.shots_blend_sides}"))
        return "/".join(bits)


#: Auxiliary channels the blend uses when nothing says otherwise -- the shipped
#: head. Each name resolves to the `home_<name>` / `away_<name>` column pair.
DEFAULT_BLEND_CHANNELS: tuple[str, ...] = ("sot",)


@dataclass(frozen=True)
class ChannelBlendConfig(WalkForwardConfig):
    """B12. `WalkForwardConfig` plus the list of channels the blend averages.

    **A subclass rather than a field on the parent, and that is load-bearing.**
    `serve.artifact.freeze` hashes `cfg.__dict__` into the artifact version, so
    adding even a defaulted field to `WalkForwardConfig` would change the
    version string of a head whose coefficients had not moved -- retiring
    `p1-3a38e9d6ef1ca7ee`, which the documents cite and which `p2.py`, `p3.py`
    and `p4_shots.py` pin. Commit `0c9eb06` declined to do that for a better
    reason than this one. Promoting the field is part of adopting the channel,
    not part of measuring it.
    """

    blend_channels: tuple[str, ...] = DEFAULT_BLEND_CHANNELS

    def label(self) -> str:
        base = super().label()
        if self.shots_blend and tuple(self.blend_channels) != DEFAULT_BLEND_CHANNELS:
            return base + "/" + "+".join(self.blend_channels)
        return base


def _channels_of(cfg: WalkForwardConfig) -> tuple[str, ...]:
    return tuple(getattr(cfg, "blend_channels", DEFAULT_BLEND_CHANNELS))


# --- effective time --------------------------------------------------------


def season_start_of(day: pd.Timestamp) -> pd.Timestamp:
    """The 1 July at or before `day`."""
    month, dom = SEASON_BOUNDARY
    year = day.year if (day.month, day.day) >= (month, dom) else day.year - 1
    return pd.Timestamp(year, month, dom)


def _offseason_days_between(earlier: pd.Series, later: pd.Timestamp) -> np.ndarray:
    """Calendar days of off-season lying strictly between each date and `later`.

    Counted year by year rather than with a closed form, because the arm is
    only meaningful if the count is right at the boundaries and a clever
    expression here would be the kind of thing that is wrong by a day forever.
    """
    out = np.zeros(len(earlier), dtype=float)
    values = earlier.to_numpy()
    for year in range(pd.Timestamp(values.min()).year, later.year + 1):
        lo = pd.Timestamp(year, *OFFSEASON_START)
        hi = pd.Timestamp(year, *OFFSEASON_END)
        overlap_start = np.maximum(values, np.datetime64(lo))
        overlap_end = np.minimum(np.datetime64(later), np.datetime64(hi))
        days = (overlap_end - overlap_start) / np.timedelta64(1, "D")
        out += np.clip(days, 0.0, None)
    return out


def effective_ages(dates: pd.Series, cutoff: pd.Timestamp,
                   offseason_gap_days: float | None) -> np.ndarray:
    """Age in days, optionally re-clocking the summer to `offseason_gap_days`."""
    ages = (cutoff - dates).dt.days.to_numpy().astype(float)
    if offseason_gap_days is None:
        return ages
    summer = _offseason_days_between(dates, cutoff)
    scale = offseason_gap_days / _OFFSEASON_LENGTH
    return ages - summer + summer * scale


# --- a single fit ----------------------------------------------------------


#: Decayed shots-on-target matches a club needs before the shots channel is
#: allowed to move its strength. Below this the ridge would hand it `att_s ~ 0`,
#: which is not "average" but fabricated -- and the National League has no shot
#: statistics at all from 2016-17, so promoted clubs would carry that
#: fabrication into E3. A club we cannot measure is left alone.
MIN_SOT_EVIDENCE = 10.0


@dataclass(frozen=True)
class _Channel:
    """One auxiliary count channel, and where it is actually observed."""
    home: np.ndarray
    away: np.ndarray
    present: np.ndarray


@dataclass
class _Indexed:
    """Team indices and arrays, built once and reused across every refit."""
    teams: tuple[str, ...]
    home_idx: np.ndarray
    away_idx: np.ndarray
    goals_h: np.ndarray
    goals_a: np.ndarray
    dates: pd.Series
    in_fit_divisions: np.ndarray
    channels: dict[str, _Channel] = field(default_factory=dict)


def _index(frame: pd.DataFrame, fit_divisions: tuple[str, ...],
           channels: tuple[str, ...] = DEFAULT_BLEND_CHANNELS) -> _Indexed:
    teams = tuple(sorted(set(frame["home_team"]) | set(frame["away_team"])))
    lookup = {name: i for i, name in enumerate(teams)}
    columns = set(frame.columns)
    built = {}
    for name in channels:
        home_col, away_col = f"home_{name}", f"away_{name}"
        if {home_col, away_col} <= columns:
            raw_h = pd.to_numeric(frame[home_col], errors="coerce")
            raw_a = pd.to_numeric(frame[away_col], errors="coerce")
            built[name] = _Channel(
                home=raw_h.fillna(0).to_numpy(dtype=float),
                away=raw_a.fillna(0).to_numpy(dtype=float),
                present=(raw_h.notna() & raw_a.notna()).to_numpy(),
            )
    return _Indexed(
        teams=teams,
        home_idx=frame["home_team"].map(lookup).to_numpy(),
        away_idx=frame["away_team"].map(lookup).to_numpy(),
        goals_h=frame["fthg"].astype(int).to_numpy(),
        goals_a=frame["ftag"].astype(int).to_numpy(),
        dates=frame["match_date"],
        in_fit_divisions=frame["division"].isin(fit_divisions).to_numpy(),
        channels=built,
    )


def _channel_fits(idx: _Indexed, rows: np.ndarray, weights: np.ndarray,
                  cfg: WalkForwardConfig):
    """One Poisson fit per requested channel, and the clubs all of them measure.

    Returns `(fits, measured)`, or `(None, None)` if any channel is absent or
    too thin -- in which case the caller leaves the goal fit alone rather than
    blending a partial set, since which channels went in would otherwise vary
    silently by cutoff.
    """
    fits, measured = [], None
    for name in _channels_of(cfg):
        channel = idx.channels.get(name)
        if channel is None:
            return None, None
        usable = rows & channel.present
        if usable.sum() < cfg.min_train_matches:
            return None, None

        # `weights` is ordered by the True positions of `rows`, so the same
        # boolean restricted to those positions selects exactly the usable
        # ones, in order.
        w_channel = weights[channel.present[rows]]
        fits.append(poisson_model.fit(
            idx.home_idx[usable], idx.away_idx[usable],
            channel.home[usable], channel.away[usable],
            w_channel, len(idx.teams), alpha=cfg.alpha,
        ))
        evidence = (np.bincount(idx.home_idx[usable], w_channel, minlength=len(idx.teams))
                    + np.bincount(idx.away_idx[usable], w_channel, minlength=len(idx.teams)))
        seen = evidence >= MIN_SOT_EVIDENCE
        measured = seen if measured is None else (measured & seen)
    return fits, measured


def auxiliary_term(base: np.ndarray, others: list[np.ndarray],
                   measured: np.ndarray, weight: float) -> np.ndarray:
    """The term `w · C` of the blend: the channels on `base`'s scale, averaged.

    Module-level and tested directly, because what it has to get right is not
    visible through a fit. **The single-channel branch reproduces the shipped
    expression down to its association order** -- `w * att_c * scale` and
    `w * (att_c * scale)` differ by one ulp, the served head must not move at
    all, and whether a synthetic corpus exposes that is luck, since the
    discrepancy is usually absorbed by the `(1-w)·base` term it is added to.

    Above one channel the average is **renormalised**. Averaging k
    imperfectly-correlated vectors shrinks the result, and shrinkage alone
    moves deviance; without this a real k-channel arm and a noise control would
    carry different auxiliary dispersion and so would differ in two ways rather
    than one. `OUTSTANDING.md` 9.6 records a control that failed exactly that
    test.
    """
    base_sd = base[measured].std()
    scales = [(base_sd / sd if (sd := other[measured].std()) else 0.0)
              for other in others]
    if len(others) == 1:
        return weight * others[0][measured] * scales[0]
    agg = np.mean([other[measured] * scale
                   for other, scale in zip(others, scales)], axis=0)
    spread = agg.std()
    return weight * (agg * (base_sd / spread) if spread else agg)


def _blend_channels(model, idx: _Indexed, rows: np.ndarray, weights: np.ndarray,
                    cfg: WalkForwardConfig):
    """Fold auxiliary count-channel strength fits into the goal-fitted ones.

    One further Poisson per channel on the identical design matrix, with that
    channel's count instead of goals. All are log-link over the same teams at
    the same cutoff, so the coefficients share a scale up to the intercept --
    were conversion constant, log E[goals] = log(conv) + log E[sot] exactly.
    They differ in magnitude because the auxiliary counts are several times
    higher and so take relatively less shrinkage from the same ridge, which the
    sd ratio in `composite` removes.

    Blended per team and only where the club has real evidence in **every**
    requested channel. The National League has no shot statistics from 2016-17,
    and the ridge would hand those clubs `att_s ~ 0` -- not "average" but
    fabricated -- which a promoted club would then carry into E3. See
    `MIN_SOT_EVIDENCE`.
    """
    fits, measured = _channel_fits(idx, rows, weights, cfg)
    if measured is None or not measured.any():
        return model

    def fold(base, others):
        out = base.copy()
        out[measured] = (1.0 - cfg.shots_blend) * base[measured] + \
            auxiliary_term(base, others, measured, cfg.shots_blend)
        return out

    att = (fold(model.att, [f.att for f in fits])
           if cfg.shots_blend_sides in ("both", "att") else model.att)
    dfn = (fold(model.dfn, [f.dfn for f in fits])
           if cfg.shots_blend_sides in ("both", "dfn") else model.dfn)
    return poisson_model.PoissonFit(model.intercept, model.home, att, dfn, model.n_train)


def _fit_at(idx: _Indexed, cutoff: pd.Timestamp, cfg: WalkForwardConfig,
            priors: RidgeTarget | None = None):
    """Fit on everything strictly before `cutoff`. None if too little history."""
    horizon = pd.Timedelta(days=cfg.half_life * cfg.horizon_half_lives)
    train = ((idx.dates < cutoff) & (idx.dates >= cutoff - horizon)
             & pd.Series(idx.in_fit_divisions, index=idx.dates.index))
    if int(train.sum()) < cfg.min_train_matches:
        return None, 0.0
    rows = train.to_numpy()
    ages = effective_ages(idx.dates[train], cutoff, cfg.offseason_gap_days)
    weights = poisson_model.decay_weights(ages, cfg.half_life)

    prior_att = prior_dfn = None
    if priors is not None and cfg.squad_prior:
        target = priors.at(cutoff, idx.teams)
        if target is not None:
            prior_att, prior_dfn = (cfg.squad_prior * target[0],
                                    cfg.squad_prior * target[1])

    model = poisson_model.fit(
        idx.home_idx[rows], idx.away_idx[rows], idx.goals_h[rows], idx.goals_a[rows],
        weights, len(idx.teams), alpha=cfg.alpha,
        prior_att=prior_att, prior_dfn=prior_dfn,
    )

    if cfg.shots_blend:
        model = _blend_channels(model, idx, rows, weights, cfg)

    stale_share = 0.0
    if cfg.season_boundary_shrink is not None:
        boundary = season_start_of(cutoff)
        pre = (idx.dates[train] < boundary).to_numpy()
        total = weights.sum()
        stale_share = float(weights[pre].sum() / total) if total > 0 else 0.0
        # Full shrink when every training match predates the season boundary,
        # fading to none as in-season matches accumulate. Continuous, so no
        # discontinuity on the first matchday.
        factor = 1.0 - (1.0 - cfg.season_boundary_shrink) * stale_share
        model = poisson_model.PoissonFit(
            model.intercept, model.home,
            model.att * factor, model.dfn * factor, model.n_train,
        )
    return model, stale_share


def lambdas_at(frame: pd.DataFrame, cutoff, cfg: WalkForwardConfig | None = None,
               *, targets: pd.Series | None = None,
               priors: RidgeTarget | None = None) -> pd.DataFrame:
    """One fit at `cutoff`, predicting the matches selected by `targets`.

    This is the serving operation, isolated so the leak canary has something to
    corrupt around. Everything the walk-forward does is repeated calls to it.
    """
    cfg = cfg or WalkForwardConfig()
    cutoff = pd.Timestamp(cutoff)
    work = frame.reset_index(drop=True)
    idx = _index(work, cfg.fit_divisions, _channels_of(cfg))
    if targets is None:
        selected = (work["match_date"] >= cutoff).to_numpy()
    else:
        selected = np.asarray(targets)[: len(work)]

    model, _ = _fit_at(idx, cutoff, cfg, priors)
    out = work.loc[selected].copy()
    if model is None:
        out["lam_h"] = np.nan
        out["lam_a"] = np.nan
    else:
        out["lam_h"], out["lam_a"] = model.predict(idx.home_idx[selected], idx.away_idx[selected])
    out["fit_cutoff"] = cutoff
    return out.reset_index(drop=True)


# --- cutoff schedule -------------------------------------------------------


def _cutoffs(dates: pd.Series, cfg: WalkForwardConfig) -> list[pd.Timestamp]:
    start = dates.min() + pd.Timedelta(days=cfg.burn_in_days)
    end = dates.max()
    if cfg.cadence == "fortnightly":
        # Anchored on `start` and stepped by 14 days, matching the P0 harness
        # exactly so its results stay reproducible.
        return list(pd.date_range(start, end, freq="14D"))
    if cfg.cadence == "weekly":
        first_monday = start + pd.Timedelta(days=(7 - start.weekday()) % 7)
        return list(pd.date_range(first_monday, end, freq="7D"))
    if cfg.cadence == "daily":
        return sorted(d for d in dates.unique() if d >= start)
    raise ValueError(f"unknown cadence {cfg.cadence!r}; expected one of {CADENCES}")


def _step(cfg: WalkForwardConfig) -> pd.Timedelta:
    return pd.Timedelta(days={"daily": 1, "weekly": 7, "fortnightly": 14}[cfg.cadence])


# --- the harness -----------------------------------------------------------


def walk_forward(frame: pd.DataFrame, cfg: WalkForwardConfig | None = None,
                 priors: RidgeTarget | None = None) -> pd.DataFrame:
    """Out-of-sample lambdas for every match with enough history behind it.

    Returns the frame with `lam_h`, `lam_a`, `fit_cutoff`, `n_train` and
    `stale_share` attached, embargoed rows already removed.
    """
    cfg = cfg or WalkForwardConfig()
    work = frame.sort_values("match_date").reset_index(drop=True)
    idx = _index(work, cfg.fit_divisions, _channels_of(cfg))

    n = len(work)
    lam_h = np.full(n, np.nan)
    lam_a = np.full(n, np.nan)
    cutoff_of = np.full(n, np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    n_train = np.zeros(n, dtype=int)
    stale = np.full(n, np.nan)

    cutoffs = _cutoffs(work["match_date"], cfg)
    step = _step(cfg)
    for position, cutoff in enumerate(cutoffs):
        window_end = cutoffs[position + 1] if position + 1 < len(cutoffs) else cutoff + step
        target = ((work["match_date"] >= cutoff) & (work["match_date"] < window_end)).to_numpy()
        if not target.any():
            continue
        model, stale_share = _fit_at(idx, cutoff, cfg, priors)
        if model is None:
            continue
        lam_h[target], lam_a[target] = model.predict(idx.home_idx[target], idx.away_idx[target])
        cutoff_of[target] = np.datetime64(cutoff)
        n_train[target] = model.n_train
        stale[target] = stale_share

    work["lam_h"] = lam_h
    work["lam_a"] = lam_a
    work["fit_cutoff"] = cutoff_of
    work["n_train"] = n_train
    work["stale_share"] = stale
    out = work[np.isfinite(lam_h)].reset_index(drop=True)

    # The property the whole exercise depends on, asserted rather than assumed.
    late = out["fit_cutoff"] > out["match_date"]
    if bool(late.any()):
        raise AssertionError(
            f"{int(late.sum())} predictions came from a fit dated after the match"
        )
    return embargo(out, cfg.embargo_regimes)


def embargo(frame: pd.DataFrame, regimes: tuple[str, ...]) -> pd.DataFrame:
    """Drop matches inside the named regime windows from SCORING.

    Training is untouched; see the module docstring for why.
    """
    if not regimes:
        return frame
    known = {r.name: r for r in REGIMES}
    keep = np.ones(len(frame), dtype=bool)
    days = frame["match_date"]
    for name in regimes:
        regime = known[name]
        end = pd.Timestamp(regime.end) if regime.end else days.max()
        keep &= ~((days >= pd.Timestamp(regime.start)) & (days <= end)).to_numpy()
    return frame[keep].reset_index(drop=True)


def season_day(frame: pd.DataFrame) -> np.ndarray:
    """Days since the first match of that division's season. The OPEN-3 subset.

    Measured from the first match rather than from the 1 July boundary, because
    divisions start on different dates and what the off-season arm is about is
    how much football has been played, not what the calendar says.
    """
    first = frame.groupby(["season", "division"])["match_date"].transform("min")
    return (frame["match_date"] - first).dt.days.to_numpy()
