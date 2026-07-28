"""The holdout seal must fire, and must not fire where it shouldn't.

SPEC §5.4: 2023-24 through 2025-26 are read once, at the end, against a prior
written commitment. These tests exist because a seal that is only documented is
a seal that gets opened by accident.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine import ledger, store
from engine.ingest.holdout import (
    Corpus,
    HoldoutViolation,
    MeasurementOnLiveCorpus,
    Purpose,
    resolve_seasons,
)
from engine.seasons import DEV_SEASONS, HOLDOUT_SEASONS, SEASONS


# --- the rule fires --------------------------------------------------------


@pytest.mark.parametrize("sealed", sorted(HOLDOUT_SEASONS))
def test_dev_refuses_each_sealed_season(sealed):
    with pytest.raises(HoldoutViolation, match=sealed):
        resolve_seasons(Purpose.DEV, (sealed,))


def test_dev_refuses_rather_than_silently_dropping():
    """Asking for 16 seasons and getting 13 is how a holdout gets believed but
    not enforced, so a mixed request raises instead of filtering."""
    with pytest.raises(HoldoutViolation):
        resolve_seasons(Purpose.DEV, ("201011", "202324"))


def test_holdout_read_requires_a_reason_and_a_ledger(conn):
    with pytest.raises(HoldoutViolation, match="unseal_reason"):
        resolve_seasons(Purpose.HOLDOUT_READ, ("202324",), conn=conn)
    with pytest.raises(HoldoutViolation, match="ledger"):
        resolve_seasons(Purpose.HOLDOUT_READ, ("202324",), unseal_reason="because")


def test_measurement_on_a_live_corpus_is_refused():
    frame = pd.DataFrame({"x": [1]})
    live = Corpus(frame, Purpose.LIVE, ("202526",), ("E0",))
    with pytest.raises(MeasurementOnLiveCorpus):
        live.for_measurement()


# --- the rule self-skips ---------------------------------------------------


def test_dev_default_is_the_development_set():
    assert resolve_seasons(Purpose.DEV, None) == DEV_SEASONS
    assert not set(DEV_SEASONS) & HOLDOUT_SEASONS
    assert len(DEV_SEASONS) == 13


def test_dev_allows_unsealed_seasons():
    assert resolve_seasons(Purpose.DEV, ("201011", "201112")) == ("201011", "201112")


def test_live_sees_everything_because_fitting_is_not_measuring():
    """Serving 2026-27 needs 2023-26 to know where teams stand. That is a fit,
    not a measurement, so it is allowed -- and marked."""
    assert resolve_seasons(Purpose.LIVE, None) == SEASONS
    assert set(resolve_seasons(Purpose.LIVE, None)) >= HOLDOUT_SEASONS


def test_measurement_on_a_dev_corpus_is_allowed():
    frame = pd.DataFrame({"x": [1]})
    dev = Corpus(frame, Purpose.DEV, ("201011",), ("E0",))
    assert dev.for_measurement().equals(frame)
    assert not dev.touches_holdout


# --- every unseal is recorded ---------------------------------------------


def test_unseal_writes_to_the_gate_ledger(conn):
    assert ledger.trial_count(conn, kinds=(ledger.HOLDOUT_UNSEAL,)) == 0
    seasons = resolve_seasons(
        Purpose.HOLDOUT_READ,
        ("202324",),
        conn=conn,
        unseal_reason="P6 final read, criteria pre-committed 2026-07-28",
        name="test.read",
    )
    assert seasons == ("202324",)
    row = conn.execute("SELECT * FROM gate_ledger").fetchone()
    assert row["kind"] == ledger.HOLDOUT_UNSEAL
    assert row["seasons"] == "202324"
    assert "pre-committed" in row["reason"]


# --- the store path carries the same guard --------------------------------


def test_store_reads_are_guarded_too(conn):
    """The database holds sealed seasons so that serving can fit on them. If the
    seal applied only to the CSV loaders it would be open on the path people
    actually use, which is worse than no seal because it looks safe."""
    with pytest.raises(HoldoutViolation):
        store.read_matches(conn, purpose=Purpose.DEV, seasons=("202526",))

    corpus = store.read_matches(conn, purpose=Purpose.LIVE, seasons=("202526",))
    assert corpus.purpose is Purpose.LIVE
    with pytest.raises(MeasurementOnLiveCorpus):
        corpus.for_measurement()
