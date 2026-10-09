"""Measure the in-package decoder against PyMatching: accuracy, edge sets, weights.

Why this exists
---------------
`core/tjoin_decoder.py` claimed for a while that its corrections were "identical" to
PyMatching's, "the same edge set and same total weight on 4,359 of 4,359 shots". Nothing in
the repository measured that. `compare_to_reference` counts observable errors, and no test
compared corrections. When it was finally measured, the claim was wrong: the edge sets agree
on 1 of 647 non-trivial shots at d=3 and 0 of 2239 at d=5, and this decoder's correction is
heavier in about four cases out of five.

A claim nobody can re-run is how that survived. So the measurement lives here.

Usage
-----
    py scripts/decoder_claim_check.py            # d = 3, 5; three seeds; 1000 shots each
    py scripts/decoder_claim_check.py --shots 300 --distances 3

Exits non-zero if the accuracy claim fails, so it can guard a regression. The edge-set and
weight figures are reported but do not fail the run: they describe a known, unexplained
discrepancy rather than a pass/fail property.

Two library details that cost real time to discover, recorded so they are not rediscovered:

  * ``Matching.decode(syndrome)`` returns the OBSERVABLE flips, not the correction edges. Its
    length is num_fault_ids. Reading it as edges yields a correction of no edges carrying a
    non-zero weight.
  * A boundary edge is addressed by node ``None`` in PyMatching and by ``-1`` in the
    in-package graph, so the two must be normalised before their edge sets are comparable.
    Without that, every boundary edge appears once on each side and the comparison reports
    zero agreement.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np

try:
    import stim
    from pymatching import Matching
except ImportError as exc:  # pragma: no cover
    print(f"needs stim and pymatching: {exc}", file=sys.stderr)
    raise SystemExit(2)

from quantumnet.core.tjoin_decoder import build_graph, decode_batch, decode_edges_and_observables

BOUNDARY = -1
NOISE = 0.003
SEEDS = (1, 7, 13)

#: The accuracy claim. Over 18,000 shots the two decoders made 24 and 26 logical errors, so
#: at these rates the two are equivalent and a small absolute excess is noise.
#:
#: Both bounds must be exceeded for the run to fail. The margin is absolute rather than
#: proportional because at low error counts a proportional margin collapses: with the
#: reference at 2 errors, a 50% excess is 3, which is inside the noise of a single shot.
#: An earlier version added a flat +2 after the proportional term, which made the check
#: unable to fail at all on small runs.
MAX_ERROR_EXCESS = 0.5
MIN_ERROR_MARGIN = 4


def norm(a, b) -> tuple[int, int]:
    """Normalise a node pair; -1 and None both mean the boundary endpoint."""
    a = BOUNDARY if a is None else int(a)
    b = BOUNDARY if b is None else int(b)
    if a == BOUNDARY:
        return (b, BOUNDARY)
    if b == BOUNDARY:
        return (a, BOUNDARY)
    return (a, b) if a <= b else (b, a)


def graph_weights(distance: int):
    """The DEM and both decoders' edge-weight tables, keyed identically."""
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=distance, rounds=distance,
        after_clifford_depolarization=NOISE)
    dem = circuit.detector_error_model(decompose_errors=True)

    edges, _ = build_graph(dem)
    mine = {}
    for e in edges:
        a = int(e.a)
        b = BOUNDARY if getattr(e, "is_boundary", False) else int(e.b)
        mine[norm(a, b)] = float(e.weight)

    ref = {norm(u, v): float(d["weight"]) for u, v, d in
           Matching.from_detector_error_model(dem).edges()}

    # The two graphs should agree edge for edge. Asserted, not assumed: if this ever fails,
    # every comparison below is meaningless and the failure should say so loudly.
    if set(mine) != set(ref):
        raise AssertionError(
            f"d={distance}: matching graphs differ. mine-only "
            f"{len(set(mine) - set(ref))}, ref-only {len(set(ref) - set(mine))}")
    return circuit, dem, mine, ref


def measure(distance: int, shots: int) -> dict:
    circuit, dem, my_w, ref_w = graph_weights(distance)
    m = Matching.from_detector_error_model(dem)

    r = dict(distance=distance, shots=0, empty=0, edges_same=0, weight_same=0,
             heavier=0, lighter=0, max_gap=0.0, my_errors=0, ref_errors=0)
    for seed in SEEDS:
        det, obs = circuit.compile_detector_sampler(seed=seed).sample(
            shots, separate_observables=True)
        truth = obs.astype(bool)

        my_pred = decode_batch(dem, det).astype(bool)
        ref_pred = m.decode_batch(det).astype(bool)
        r["my_errors"] += int(np.sum(my_pred[:, 0] != truth[:, 0]))
        r["ref_errors"] += int(np.sum(ref_pred[:, 0] != truth[:, 0]))

        for i in range(shots):
            if np.flatnonzero(det[i]).size == 0:
                r["empty"] += 1
                continue
            r["shots"] += 1

            mp, _ = decode_edges_and_observables(dem, det[i])
            mine = {norm(a, b) for a, b in mp}
            ref = {norm(u, v) for u, v in np.atleast_2d(m.decode_to_edges_array(det[i]))}

            if mine == ref:
                r["edges_same"] += 1
            gap = sum(my_w[k] for k in mine) - sum(ref_w[k] for k in ref)
            if abs(gap) < 1e-9:
                r["weight_same"] += 1
            else:
                r["max_gap"] = max(r["max_gap"], abs(gap))
                r["heavier" if gap > 0 else "lighter"] += 1
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--shots", type=int, default=1000,
                    help="shots per seed per distance (default 1000)")
    ap.add_argument("--distances", type=int, nargs="+", default=[3, 5])
    args = ap.parse_args(argv)

    print("=" * 74)
    print("DECODER: accuracy against the reference, and correction agreement")
    print("=" * 74)

    total_shots = total_my = total_ref = 0
    failures = []
    for d in args.distances:
        r = measure(d, args.shots)
        n = r["shots"]
        short = 1.0 - r["my_errors"] / max(r["ref_errors"], 1)
        print(f"\n  d={d}   non-trivial shots {n}   empty-syndrome {r['empty']}")
        print(f"     accuracy   : this {r['my_errors']:>4} errors, "
              f"reference {r['ref_errors']:>4} over {args.shots * len(SEEDS)} shots")
        if n:
            print(f"     edge sets  : agree {r['edges_same']}/{n} "
                  f"({100 * r['edges_same'] / n:.1f}%)")
            print(f"     total weight: agree {r['weight_same']}/{n} "
                  f"({100 * r['weight_same'] / n:.1f}%)")
            print(f"     this decoder heavier {r['heavier']}, lighter {r['lighter']}, "
                  f"max gap {r['max_gap']:.2f}")

        # Fail only if BOTH the proportional excess and the absolute margin are exceeded,
        # so the check is meaningfully strict on a large run and not hair-trigger on a small
        # one. See MIN_ERROR_MARGIN for why a flat additive term alone was wrong.
        allowed = max(r["ref_errors"] * (1 + MAX_ERROR_EXCESS),
                      r["ref_errors"] + MIN_ERROR_MARGIN)
        if r["my_errors"] > allowed:
            failures.append(
                f"d={d}: {r['my_errors']} errors against the reference's {r['ref_errors']}, "
                f"allowed {allowed:.1f}")

        total_shots += args.shots * len(SEEDS)
        total_my += r["my_errors"]
        total_ref += r["ref_errors"]

    print("\n" + "=" * 74)
    print(f"  TOTAL accuracy over {total_shots} shots: this {total_my}, "
          f"reference {total_ref}")
    print("  The edge-set and weight figures describe a known, unexplained discrepancy.")
    print("  They are reported, not asserted: they are the measurement that replaced a")
    print("  claim of identity which turned out to be wrong.")
    if failures:
        print()
        for f in failures:
            print(f"  FAIL  {f}")
        return 1
    print("\n  accuracy claim holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
