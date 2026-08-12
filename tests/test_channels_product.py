"""B14 in the product's currency, `BACKLOG.md` B14.

The gate itself walk-forwards three heads over the whole corpus, which is far
too slow for a unit test. What belongs here is the part a silent change would
misreport: the pre-registered read. It was fixed in writing before the gate ran,
and this is what stops it drifting afterwards.
"""

from __future__ import annotations

from engine.eval import channels_product


def _arm(delta, excludes_zero):
    return {"vs_shipped": delta, "vs_shipped_excludes_zero": excludes_zero}


def test_a_resolved_gain_over_the_blind_control_reads_go():
    verdict = channels_product.read_verdict(
        a1=_arm(+0.45, True), c1=_arm(-1.60, True))

    assert verdict == "GO"


def test_an_unresolved_arm_reads_no_go_however_far_it_beats_the_control():
    """The measured case. A1 beat both controls by more than a point and still
    does not resolve, and beating a control is not evidence of an effect."""
    verdict = channels_product.read_verdict(
        a1=_arm(-0.095, False), c1=_arm(-1.643, True))

    assert verdict == "NO-GO"


def test_a_control_that_also_gains_voids_a_resolved_arm():
    """The ordering that makes VOID worth having. If a blind perturbation gains
    too, the instrument is measuring perturbation rather than information -- and
    without this branch checked first, A1's own interval would read as a GO."""
    verdict = channels_product.read_verdict(
        a1=_arm(+0.60, True), c1=_arm(+0.55, True))

    assert verdict == "VOID"
