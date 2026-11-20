"""Two-pass correlated T-join decoding with heralded erasures (topic 09 §8).

This is the file the implementation plan names for the Slice 7 gate.  Three properties
are checked:

1. The ``^``-correlated structure a decomposed Stim DEM carries is actually found.
2. ``decode_correlated`` never mutates the cached ``CompiledDEMGraph`` -- the cache
   rule in the specification, because changing cached edge weights would corrupt every
   later shot decoded through the same DEM.
3. A herald that flags the true fault edges turns a decoding failure into a zero-error
   shot, while false-positive erasure flags at percolation density degrade the result
   ("Hypochonder percolation", denker-2 Widerrede 2).
"""

from __future__ import annotations

import numpy as np
import pytest

from quantumnet.core.tjoin_decoder import (
    BOUNDARY,
    _get_compiled,
    decode_correlated,
    parse_dem_correlations,
)

stim = pytest.importorskip("stim")


def _d3_dem():
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=3, rounds=3,
        after_clifford_depolarization=0.003)
    return circuit.detector_error_model(decompose_errors=True)


def test_dem_correlations_are_found_on_rotated_memory_z():
    corr = parse_dem_correlations(_d3_dem())
    assert corr, "no ^-correlations extracted from the decomposed DEM"
    assert any(len(partners) > 0 for partners in corr.values())


def test_decode_correlated_does_not_mutate_the_cached_graph():
    dem = _d3_dem()
    before = _get_compiled(dem)
    before_pairs = {(e.a, e.b): (e.weight, e.probability) for e in before.edges}

    # Erase a handful of real edges, then decode a two-event syndrome through them.
    edges = [e for e in before.edges if e.a != BOUNDARY and e.b != BOUNDARY][:5]
    erasures = [(e.a, e.b) for e in edges]
    decode_correlated(dem, [edges[0].a, edges[0].b], erasure_edges=erasures)

    after = _get_compiled(dem)
    assert after is before
    after_pairs = {(e.a, e.b): (e.weight, e.probability) for e in after.edges}
    assert after_pairs == before_pairs


def _fooling_chain(dem):
    """A weight-2 error chain (two adjacent DEM edges) that unflagged matching gets wrong.

    The chain fires two mechanisms sharing one detector, so its syndrome is the two
    outer detectors. If some other, cheaper route between them exists, minimum-weight
    matching takes it and flips the wrong observable -- exactly the shot a herald for
    the true fault edge rescues. Returns ``(key1, key2, syndrome, true_observables)``.
    """
    compiled = _get_compiled(dem)
    graphlike = [e for e in compiled.edges
                 if e.a != BOUNDARY and e.b != BOUNDARY and e.a != e.b]
    for e1 in graphlike:
        s1 = {e1.a, e1.b}
        for e2 in graphlike:
            if e2 is e1:
                continue
            s2 = {e2.a, e2.b}
            common = s1 & s2
            if len(common) != 1:
                continue
            outer = (s1 | s2) - common
            if len(outer) != 2:
                continue
            u, w = sorted(outer)
            if u == w:
                continue
            true_obs = e1.observables ^ e2.observables
            _, obs = decode_correlated(dem, [u, w])
            if obs != true_obs:
                k1 = (min(e1.a, e1.b), max(e1.a, e1.b))
                k2 = (min(e2.a, e2.b), max(e2.a, e2.b))
                return k1, k2, [u, w], true_obs
    return None


def test_heralded_erasure_flag_decodes_the_true_fault_edge_exactly():
    dem = _d3_dem()
    chain = _fooling_chain(dem)
    assert chain is not None, (
        "no weight-2 chain on d=3 fools unflagged matching; the erasure gate would "
        "then be asserting nothing")
    k1, k2, syndrome, true_obs = chain

    _, unflagged_obs = decode_correlated(dem, syndrome)
    matched, flagged_obs = decode_correlated(dem, syndrome, erasure_edges=[k1, k2])

    assert unflagged_obs != true_obs          # the unflagged decoder is wrong here
    assert flagged_obs == true_obs            # the herald fixes it: zero logical errors
    assert k1 in matched or k2 in matched


def test_false_positive_erasures_at_percolation_density_degrade_the_result():
    """65% random false-positive heralds must make the logical error rate worse."""
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=3, rounds=3,
        after_clifford_depolarization=0.01)
    dem = circuit.detector_error_model(decompose_errors=True)
    sampler = circuit.compile_detector_sampler(seed=3)
    detection, observables = sampler.sample(200, separate_observables=True)

    compiled = _get_compiled(dem)
    candidates = [(e.a, e.b) for e in compiled.edges
                  if e.a != BOUNDARY and e.b != BOUNDARY and e.a != e.b]
    assert len(candidates) > 10

    rng = np.random.default_rng(7)
    baseline_errors = 0
    flooded_errors = 0
    for shot in range(detection.shape[0]):
        events = np.flatnonzero(detection[shot])
        _, obs = decode_correlated(dem, events)
        if (0 in obs) != bool(observables[shot][0]):
            baseline_errors += 1

        k = int(0.65 * len(candidates))
        picks = rng.choice(len(candidates), size=k, replace=False)
        flags = [candidates[i] for i in picks]
        _, obs = decode_correlated(dem, events, erasure_edges=flags)
        if (0 in obs) != bool(observables[shot][0]):
            flooded_errors += 1

    # "Hypochonder percolation": flooding the decoder with heralds it cannot trust
    # destroys the correction the honest herald budget would have delivered.
    assert flooded_errors > baseline_errors
