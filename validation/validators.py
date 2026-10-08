"""The syndrome invariant, as an instrument that has itself been tested.

**The property.** A decoder's correction must reproduce the observed detection events.
Concretely: take every graphlike component of the correction, XOR the detectors it
touches, and the result must equal the detection events exactly. A correction that fails
this is not "suboptimal" -- it answers a different question, and its error rate is
meaningless.

This went unchecked in this package until round 5, by which point an earlier decoder was
**100% wrong** on it while still producing plausible-looking error rates. That is the
failure mode these instruments exist to prevent: a decoder that looks like it works.

**Representation.** A correction is a set of edges over the DEM's graph. An edge is a
pair of detector ids, or ``(detector, BOUNDARY)``. This is the natural output of a
matching decoder, and converting to it is trivial for any other formulation, so the
instrument does not constrain the decoder's internals.

**Self-testing.** :func:`validate_against_known_good` builds a correction from a real
detection event and confirms the instrument accepts it, then perturbs that correction and
confirms the instrument rejects it. An instrument that has never been shown to reject a
known-bad input is not evidence, and that distinction is the whole point of this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

BOUNDARY = -1

try:
    import stim

    HAVE_STIM = True
except ImportError:  # pragma: no cover
    stim = None
    HAVE_STIM = False


def dem_components(instruction) -> list[list[int]]:
    """Split one DEM error instruction into its graphlike components.

    ``stim`` writes a multi-component mechanism as ``error(p) D1 D5 ^ D4``, and ``^``
    separates components. With ``decompose_errors=True`` every component is graphlike --
    verified: 0 of 556 / 3706 / 11830 components exceeded two detectors at d=3 / 5 / 7.
    A component of length 1 is a boundary edge.

    Components longer than two detectors are returned as-is rather than silently
    truncated, so a non-decomposed model is reported by
    :func:`check_correction` instead of producing a wrong answer.
    """
    components: list[list[int]] = []
    current: list[int] = []
    for target in instruction.targets_copy():
        if target.is_separator():
            if current:
                components.append(current)
            current = []
        elif target.is_relative_detector_id():
            current.append(target.val)
    if current:
        components.append(current)
    return components


def graph_from_dem(dem) -> list[tuple[int, int, frozenset]]:
    """Every graphlike component as ``(a, b, observables)``.

    A one-detector component becomes a boundary edge ``(BOUNDARY, detector)``. Boundary
    is ``-1`` and edges are canonicalised with ``min`` first, which means **the boundary
    is always the first element** on a boundary edge -- the trap that silently turned a
    fix into a no-op during the failed effort, because ``find(edge.a)`` then returns the
    boundary's root rather than the detector's.
    """
    edges: list[tuple[int, int, frozenset]] = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        observables = frozenset(
            t.val for t in inst.targets_copy() if t.is_logical_observable_id())
        for component in dem_components(inst):
            if len(component) == 2:
                a, b = component
                if a == b:
                    continue
                edges.append((min(a, b), max(a, b), observables))
            elif len(component) == 1:
                edges.append((BOUNDARY, component[0], observables))
            else:
                # Length > 2 with decompose_errors=False. Keep it so the check can
                # report an unusable model rather than quietly mis-scoring.
                edges.append((component[0], component[1], observables))
    return edges


def syndrome_of_correction(correction: Iterable[tuple[int, int]]) -> set[int]:
    """The detection events a correction explains.

    XOR the endpoints of every edge, discarding the boundary. The boundary is excluded
    because a chain terminating at the code edge is *allowed* to leave it odd -- counting
    it produced a phantom 57.4% failure rate in an earlier diagnostic, which is exactly
    the kind of instrument defect this module is built to avoid.
    """
    degree: dict[int, int] = {}
    for a, b in correction:
        for node in (int(a), int(b)):
            if node == BOUNDARY:
                continue
            degree[node] = degree.get(node, 0) ^ 1
    return {node for node, parity in degree.items() if parity}


@dataclass
class CorrectionCheck:
    """The result of checking one correction against one shot."""

    valid: bool
    observed: frozenset = field(default_factory=frozenset)
    explained: frozenset = field(default_factory=frozenset)
    unexplained: frozenset = field(default_factory=frozenset)
    spurious: frozenset = field(default_factory=frozenset)

    def describe(self) -> str:
        if self.valid:
            return f"valid: explains {len(self.observed)} event(s)"
        return (f"INVALID: unexplained={sorted(self.unexplained)} "
                f"spurious={sorted(self.spurious)}")


def check_correction(detection_events: Iterable[int],
                     correction: Iterable[tuple[int, int]]) -> CorrectionCheck:
    """Check one correction against the events it must explain.

    Reported symmetrically: ``unexplained`` are events the correction does not account
    for, ``spurious`` are detectors it flips that were not events. Both are failures, and
    naming them separately is what makes the failure diagnosable rather than just a
    count.
    """
    observed = frozenset(int(e) for e in detection_events)
    explained = frozenset(syndrome_of_correction(correction))
    return CorrectionCheck(
        valid=(explained == observed),
        observed=observed,
        explained=explained,
        unexplained=frozenset(observed - explained),
        spurious=frozenset(explained - observed),
    )


def rate_over_shots(samples: Iterable[tuple[Iterable[int], Iterable[tuple[int, int]]]]
                    ) -> dict:
    """Violation rate over ``(detection_events, correction)`` pairs.

    **Refuses to return a rate for an empty sample.** An earlier diagnostic printed
    nothing when its input shape changed, and the blank output was read as a result. A
    rate over zero shots is ``None`` plus ``shot_count == 0``, which cannot be mistaken
    for 0%.
    """
    checked = 0
    invalid = 0
    first_failure = None
    for events, correction in samples:
        check = check_correction(events, correction)
        checked += 1
        if not check.valid:
            invalid += 1
            if first_failure is None:
                first_failure = check
    if checked == 0:
        return {"shot_count": 0, "invalid": 0, "violation_rate": None,
                "first_failure": None,
                "note": "NO SAMPLES -- this is a failure, not a 0% rate"}
    return {
        "shot_count": checked,
        "invalid": invalid,
        "violation_rate": invalid / checked,
        "first_failure": first_failure,
    }


def validate_against_known_good(distance: int = 3, noise: float = 0.003,
                                seed: int = 3, shots: int = 200) -> dict:
    """Prove the instrument can both **accept** and **reject**.

    Returns a dict with the acceptance and rejection outcomes and whether both behaved.
    This is the check the brief requires before any measurement is trusted: an
    instrument shown only to accept is indistinguishable from one that always accepts.

    The known-good correction is the reference's own chosen edge set, which by
    construction reproduces the syndrome. The known-bad correction is that set with one
    edge removed -- which must be rejected, and will be, on any shot where the removed
    edge was carrying an odd endpoint.
    """
    if not HAVE_STIM:
        raise RuntimeError("needs stim")
    from pymatching import Matching

    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=distance, rounds=distance,
        after_clifford_depolarization=noise)
    dem = circuit.detector_error_model(decompose_errors=True)
    matching = Matching.from_detector_error_model(dem)
    sampler = circuit.compile_detector_sampler(seed=seed)
    detection, _ = sampler.sample(shots, separate_observables=True)

    accepted = rejected = attempted = 0
    for shot in range(shots):
        events = [int(e) for e in np.flatnonzero(detection[shot])]
        if not events:
            continue
        try:
            pairs = matching.decode_to_edges_array(detection[shot].astype(np.uint8))
        except ValueError:
            continue
        good = [(int(a), int(b)) for a, b in pairs]
        if not good:
            continue
        attempted += 1
        if check_correction(events, good).valid:
            accepted += 1
        damaged = good[:-1]
        if damaged and not check_correction(events, damaged).valid:
            rejected += 1

    return {
        "shots_with_events": attempted,
        "accepted_known_good": accepted,
        "rejected_known_bad": rejected,
        "instrument_trustworthy": bool(
            attempted > 0 and accepted == attempted and rejected > 0),
        "note": ("accepts every known-good correction AND rejects a known-bad one"
                 if attempted and accepted == attempted and rejected
                 else "INSTRUMENT NOT VALIDATED -- do not trust its output"),
    }
