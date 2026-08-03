"""Frozen model artifacts and the version string that identifies them.

A served prediction is only auditable if the exact thing that produced it can
be named and reloaded. So every artifact carries a version string derived from
everything that could change its output -- hyperparameters, training cutoff,
team roster, and a digest of the matches it was fitted on.

The version is a *derivation*, never a counter. Two artifacts with the same
version must be the same artifact, and any change to an input must change the
string. Both directions are tested; a version that can be bumped by hand is a
version that will eventually lie about what served a bet.

The training corpus digest deliberately covers the match ids and their goals.
Re-running the same fit on the same data reproduces the string exactly, which
is what makes a stored prediction reproducible months later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from engine.eval.walkforward import WalkForwardConfig, _fit_at, _index
from engine.models.poisson import PoissonFit

ARTIFACT_VERSION = 1  # bumped when the on-disk shape changes, not per fit


def corpus_digest(frame: pd.DataFrame) -> str:
    """Stable digest of the matches an artifact was fitted on.

    Sorted before hashing so that row order -- which no fit depends on -- does
    not change the identity of the artifact.
    """
    columns = [c for c in ("match_id", "match_date", "home_team", "away_team", "fthg", "ftag")
               if c in frame.columns]
    ordered = frame[columns].sort_values(columns).astype(str)
    payload = ordered.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass(frozen=True)
class Artifact:
    """A fitted head, frozen with everything needed to reproduce and audit it."""

    version: str
    fitted_at: str          # the training cutoff, NOT wall-clock time
    config: dict
    teams: tuple[str, ...]
    intercept: float
    home: float
    att: tuple[float, ...]
    dfn: tuple[float, ...]
    n_train: int
    corpus_digest: str
    artifact_version: int = ARTIFACT_VERSION

    # --- use ---------------------------------------------------------------

    def fit(self) -> PoissonFit:
        return PoissonFit(self.intercept, self.home,
                          np.array(self.att), np.array(self.dfn), self.n_train)

    def predict(self, home_teams, away_teams) -> tuple[np.ndarray, np.ndarray]:
        """Lambdas for named fixtures.

        Raises on an unknown club rather than substituting the league average.
        A silent average is exactly the cold-start case the P2 player prior
        exists to handle properly, and hiding it here would make that gap
        invisible in production.
        """
        lookup = {name: i for i, name in enumerate(self.teams)}
        missing = sorted({t for t in [*home_teams, *away_teams] if t not in lookup})
        if missing:
            raise KeyError(f"artifact {self.version} has never seen: {', '.join(missing)}")
        home_idx = np.array([lookup[t] for t in home_teams])
        away_idx = np.array([lookup[t] for t in away_teams])
        return self.fit().predict(home_idx, away_idx)

    # --- storage -----------------------------------------------------------

    def save(self, directory: Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{self.version}.json"
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "Artifact":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        stored = payload.pop("version")
        artifact = cls(version=stored, **{
            **payload,
            "teams": tuple(payload["teams"]),
            "att": tuple(payload["att"]),
            "dfn": tuple(payload["dfn"]),
        })
        if artifact.derive_version() != stored:
            raise ValueError(
                f"artifact at {path} claims version {stored} but its contents derive "
                f"{artifact.derive_version()}; it has been edited since it was frozen"
            )
        return artifact

    # --- identity ----------------------------------------------------------

    def derive_version(self) -> str:
        """Recompute the version from the contents. `load` checks this."""
        return _version_string(self.config, self.fitted_at, self.teams,
                               self.corpus_digest, self.intercept, self.home,
                               self.att, self.dfn)


def _version_string(config, fitted_at, teams, digest, intercept, home, att, dfn) -> str:
    payload = json.dumps({
        "artifact_version": ARTIFACT_VERSION,
        "config": config,
        "fitted_at": str(fitted_at),
        "teams": list(teams),
        "corpus_digest": digest,
        # Coefficients are rounded before hashing so that a re-fit which lands
        # on the same optimum to nine decimal places is recognised as the same
        # artifact, rather than acquiring a new identity from optimiser noise.
        "intercept": round(float(intercept), 9),
        "home": round(float(home), 9),
        "att": [round(float(v), 9) for v in att],
        "dfn": [round(float(v), 9) for v in dfn],
    }, sort_keys=True).encode("utf-8")
    return "p1-" + hashlib.sha256(payload).hexdigest()[:16]


def freeze(frame: pd.DataFrame, cutoff, cfg: WalkForwardConfig | None = None) -> Artifact:
    """Fit at `cutoff` on everything strictly earlier, and freeze the result."""
    cfg = cfg or WalkForwardConfig()
    cutoff = pd.Timestamp(cutoff)
    work = frame.reset_index(drop=True)
    indexed = _index(work, cfg.fit_divisions)
    model, _ = _fit_at(indexed, cutoff, cfg)
    if model is None:
        raise ValueError(f"not enough history before {cutoff.date()} to fit an artifact")

    trained_on = work[(work["match_date"] < cutoff)
                      & work["division"].isin(cfg.fit_divisions)]
    config = {k: (list(v) if isinstance(v, tuple) else v)
              for k, v in cfg.__dict__.items()}
    digest = corpus_digest(trained_on)
    att, dfn = tuple(model.att.tolist()), tuple(model.dfn.tolist())
    return Artifact(
        version=_version_string(config, cutoff.isoformat(), indexed.teams, digest,
                                model.intercept, model.home, att, dfn),
        fitted_at=cutoff.isoformat(),
        config=config,
        teams=indexed.teams,
        intercept=float(model.intercept),
        home=float(model.home),
        att=att,
        dfn=dfn,
        n_train=int(model.n_train),
        corpus_digest=digest,
    )
