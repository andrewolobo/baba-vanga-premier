"""The evidence pack: everything the analysis may say, as code computed it.

One pack per published call (D2). The pack carries:

- the call itself;
- the menu the rule chose it from, with the model's probability for each
  market;
- the facts;
- the data caveats.

The LLM explains the call. It cannot change it, and it cannot add a number
that is not in the pack.

**The menu is recomputed, then checked against the published call.**

- The probabilities are read from the prediction row the tip was made
  from (`tips.prediction_id`), as the call drawer reads them (B22), not
  from the fixture's latest prediction.
- The +1.5 comes off the same score matrix `engine.serve.tips.select`
  used.
- The rule (`engine.eval.b21.recommend`) is then run on those numbers. If it
  does not reproduce the published side and probability, building the pack
  fails.

So a pack can never explain a call the rule would not have made.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from api import teams
from engine import db
from engine.eval import b21
from engine.eval.dispersion import score_matrix
from engine.serve import tips
from services.analysis.facts import build_facts, division_name
from services.analysis.schemas import Call, EvidencePack, MenuLine

#: The published call for a fixture -- the latest, as on the match page
#: (review R5) -- with the prediction row it was made from.
CALL = """
    SELECT f.fixture_id, f.division, f.match_date, f.kickoff_time,
           f.home_team_id, f.away_team_id,
           h.canonical_name AS home_team, a.canonical_name AS away_team,
           t.tip_id, t.side, t.model_prob, t.floor, t.ceiling, t.rule_version,
           p.model_version, p.lam_h, p.lam_a, p.p_home, p.p_draw, p.p_away
    FROM fixtures f
    JOIN teams h ON h.team_id = f.home_team_id
    JOIN teams a ON a.team_id = f.away_team_id
    JOIN tips t ON t.fixture_id = f.fixture_id
    JOIN predictions p ON p.prediction_id = t.prediction_id
    WHERE f.fixture_id = %s
    ORDER BY t.tip_id DESC
    LIMIT 1
"""


def call_label(side: str, home: str, away: str) -> str:
    """The call in words. Mirrors `callLabel` in `web/src/lib/api.js`."""
    return {"H": f"{home} win", "A": f"{away} win", "D": "Draw",
            "1X": f"{home} or draw", "X2": f"{away} or draw", "12": "Either team to win",
            "H+1.5": f"{home} Home +1.5", "A+1.5": f"{away} Away +1.5"}.get(side, side)


def call_means(side: str, home: str, away: str) -> str | None:
    """What has to happen. Mirrors `callMeans` in `web/src/lib/api.js`."""
    return {"1X": f"{home} must win or draw", "X2": f"{away} must win or draw",
            "12": f"either {home} or {away} must win",
            "H+1.5": f"{home} must not lose by 2 or more goals",
            "A+1.5": f"{away} must not lose by 2 or more goals"}.get(side)


def _pct(p: float) -> float:
    return round(100 * float(p), 1)


def menu(row: dict, home: str, away: str) -> list[MenuLine]:
    """The markets the rule weighed for this call, each with its probability,
    its place in the rule and whether the rule could take it.

    Raises ValueError when the rule, run on these numbers, does not
    reproduce the published side and probability.
    """
    probs = np.array([[row["p_home"], row["p_draw"], row["p_away"]]], dtype=float)
    joint = score_matrix(np.array([row["lam_h"]], dtype=float),
                         np.array([row["lam_a"]], dtype=float))
    p_dog = b21.dog15_probs(joint, probs)
    fav_home = bool(probs[0, 0] >= probs[0, 2])
    dog_side = "A+1.5" if fav_home else "H+1.5"

    market, prob = b21.recommend(probs, p_dog, floor=row["floor"], ceiling=row["ceiling"])
    side = dog_side if market[0] == b21.DOG15 else str(market[0])
    if side != row["side"] or abs(float(prob[0]) - row["model_prob"]) > 1e-9:
        raise ValueError(
            f"fixture {row['fixture_id']}: the rule on the stored prediction gives "
            f"{side} at {float(prob[0]):.6f}, but {row['side']} at "
            f"{row['model_prob']:.6f} was published")

    p_h, p_d, p_a = (float(x) for x in probs[0])
    lines = [
        ("H", p_h, "outright" if fav_home else "off_menu"),
        ("D", p_d, "off_menu"),
        ("A", p_a, "off_menu" if fav_home else "outright"),
        ("1X", p_h + p_d, "fallback"),
        ("X2", p_a + p_d, "fallback"),
        ("12", p_h + p_a, "fallback"),
        (dog_side, float(p_dog[0]), "fallback"),
    ]
    return [MenuLine(
        id=f"MENU_{code.replace('+1.5', '15')}",
        side=code, label=call_label(code, home, away), p_model=_pct(p),
        role=role,
        eligible=(p >= row["floor"] if role == "outright"
                  else p <= row["ceiling"] if role == "fallback" else False),
        is_call=code == row["side"]) for code, p, role in lines]


def build_pack(conn: db.Connection, fixture_id: int, *,
               data_as_of: str | None = None) -> EvidencePack:
    """The evidence pack for one fixture's published call.

    Raises LookupError when the fixture has no published call, and
    ValueError when the call was made under a rule other than the current
    one (an older rule's menu is not this one's) or the menu does not
    reproduce it.
    """
    row = conn.execute(CALL, (fixture_id,)).fetchone()
    if row is None:
        raise LookupError(f"fixture {fixture_id} has no published call")
    if row["rule_version"] != tips.RULE_VERSION:
        raise ValueError(f"fixture {fixture_id} was called under {row['rule_version']},"
                         f" not {tips.RULE_VERSION}")
    home, away = teams.display_name(row["home_team"]), teams.display_name(row["away_team"])
    lines = menu(row, home, away)
    facts, flags, omitted = build_facts(conn, {**row, "home": home, "away": away})
    return EvidencePack(
        fixture_id=row["fixture_id"], division=row["division"],
        division_name=division_name(row["division"]),
        match_date=row["match_date"], kickoff_time=row["kickoff_time"],
        home=home, away=away,
        home_team_id=row["home_team_id"], away_team_id=row["away_team_id"],
        call=Call(tip_id=row["tip_id"], side=row["side"],
                  label=call_label(row["side"], home, away),
                  means=call_means(row["side"], home, away),
                  model_prob=_pct(row["model_prob"]), floor=_pct(row["floor"]),
                  ceiling=_pct(row["ceiling"]), rule_version=row["rule_version"]),
        menu=lines, facts=facts, flags=flags, omitted=omitted,
        model_version=row["model_version"],
        data_as_of=data_as_of or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )
