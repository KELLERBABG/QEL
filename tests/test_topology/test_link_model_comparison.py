"""The Barrett-Kok model against the pre-existing heuristic rate.

``topology.graph.QuantumLink`` computes its generation rate as
``pulse_rate * (detector_eff * transmissivity)^2``.  That is a *single-photon*
scheme: one photon per arm, both detected.  Barrett-Kok is a *double-heralded*
scheme whose ideal probability is 1/2, so the two differ by that factor and by
the dark-count treatment.

The tests here exist so the difference is **visible and attributable** rather
than a silent inconsistency between two parts of the same codebase.  Neither
number is wrong; they describe different hardware.  What would be wrong is
quoting one while the other is what the simulator actually uses.
"""

from __future__ import annotations

import pytest

from quantumnet.core.photonics import (
    BARRETT_KOK_IDEAL_SUCCESS,
    Detector,
    PhotonicLink,
    BarrettKok,
    compare_link_models,
    elementary_link_from_specs,
    single_photon_attempt_probability,
)
from quantumnet.topology.graph import QuantumLink


def test_the_two_models_differ_by_the_beamsplitter_factor_at_low_dark_counts():
    """The legacy heuristic omits the 1/2, so it is ~2x the Barrett-Kok rate.

    Verified rather than asserted in prose: if a future change makes the legacy
    rate match, either the heuristic gained the factor or the Barrett-Kok model
    lost it -- and both cases deserve to fail a test.
    """
    link = QuantumLink(a="A", b="B", length_km=50.0,
                       dark_count_hz=1e-9, detector_eff=0.8)
    comparison = compare_link_models(link)
    assert comparison["ratio"] == pytest.approx(2.0, rel=0.05), (
        f"ratio {comparison['ratio']} -- expected ~2x from the missing 1/2"
    )


def test_barrett_kok_rate_is_strictly_below_the_single_photon_heuristic():
    for length in (10.0, 50.0, 100.0):
        link = QuantumLink(a="A", b="B", length_km=length,
                           dark_count_hz=1e-9, detector_eff=0.8)
        comparison = compare_link_models(link)
        assert comparison["barrett_kok_rate_hz"] < comparison["legacy_rate_hz"]


def test_both_models_agree_on_the_distance_scaling():
    """They differ by a constant factor, so the *slope* must be identical.

    This is the check that matters for comparing against a published curve:
    a disagreement in exponent would mean one of them models the wrong physics,
    whereas a constant offset is a definitional difference.
    """
    ratios = []
    for length in (20.0, 40.0, 80.0):
        link = QuantumLink(a="A", b="B", length_km=length,
                           dark_count_hz=1e-9, detector_eff=0.8)
        ratios.append(compare_link_models(link)["ratio"])
    assert max(ratios) - min(ratios) < 0.05, f"slopes differ: {ratios}"


def test_the_ratio_is_exactly_two_in_the_no_dark_count_limit():
    """Stated analytically: legacy = 2 * Barrett-Kok when dark counts vanish."""
    link = QuantumLink(a="A", b="B", length_km=50.0,
                       dark_count_hz=0.0, detector_eff=0.8)
    comparison = compare_link_models(link)
    assert comparison["ratio"] == pytest.approx(2.0, rel=1e-6)


def test_single_photon_probability_matches_the_legacy_squared_form():
    """The legacy rate is ``pulse_rate * eta^2``; confirm that reading of it."""
    for length in (0.0, 25.0, 50.0):
        eta = single_photon_attempt_probability(length, detector_efficiency=0.8)
        link = QuantumLink(a="A", b="B", length_km=length,
                           dark_count_hz=0.0, detector_eff=0.8)
        assert link.generation_rate() == pytest.approx(
            link.pulse_rate_hz * eta ** 2, rel=1e-9)


def test_high_dark_counts_close_the_gap_between_the_models():
    """Dark counts add to the Barrett-Kok rate, so the ratio falls below 2."""
    quiet = QuantumLink(a="A", b="B", length_km=100.0,
                        dark_count_hz=0.0, detector_eff=0.8)
    noisy = QuantumLink(a="A", b="B", length_km=100.0,
                        dark_count_hz=1e7, detector_eff=0.8)
    assert compare_link_models(noisy)["ratio"] < compare_link_models(quiet)["ratio"]


def test_elementary_link_helper_builds_a_symmetric_link():
    link = elementary_link_from_specs(30.0, detector_efficiency=0.9)
    assert link.arm_a.length_km == link.arm_b.length_km == 30.0
    assert link.arm_a.detector.efficiency == 0.9
    assert link.success_probability() > 0.0


def test_elementary_link_fidelity_is_high_when_mode_matching_is_perfect():
    link = elementary_link_from_specs(10.0, coincidences_window_s=1e-12)
    assert link.raw_fidelity() > 0.99


def test_comparison_reports_every_field_a_caller_needs():
    link = QuantumLink(a="A", b="B", length_km=50.0)
    comparison = compare_link_models(link)
    for key in ("legacy_rate_hz", "barrett_kok_rate_hz", "success_probability",
                "raw_fidelity", "ratio", "length_km"):
        assert key in comparison
    assert comparison["length_km"] == 50.0


def test_a_span_too_long_to_be_useful_reports_underflow_not_a_false_ratio():
    """Past a few hundred km the Barrett-Kok rate underflows to zero.

    An infinite ratio would read as a modelling failure; ``None`` says the
    dynamic range ran out, which is the true reason and a different thing.
    """
    link = QuantumLink(a="A", b="B", length_km=500.0,
                       dark_count_hz=0.0, detector_eff=0.8)
    comparison = compare_link_models(link)
    assert comparison["barrett_kok_rate_hz"] == 0.0
    assert comparison["legacy_rate_hz"] > 0.0
    assert comparison["ratio"] is None
