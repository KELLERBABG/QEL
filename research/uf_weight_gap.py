"""Is my matching heavier than the reference's? The metric-closure test.

The leading hypothesis for why the in-package decoder is ~6x off is that matching over
the **metric closure** -- precomputed pairwise shortest-path distances -- is not the
minimum-weight T-join. The true optimum may route two pairs through **shared edges**,
which no perfect matching over pairwise distances can express.

That is testable directly: ask the reference for the edges it chose, total their
weights, and compare with the weight of my matching's routes. If the reference's total
is lower, the gap is real and quantified; if the totals agree, the hypothesis is dead.
"""
import numpy as np
import stim
from pymatching import Matching

from quantumnet.core.tjoin import build_graph, shortest_routes, BOUNDARY


def reference_edge_weight(dem, matching, syndrome_vector):
    """Total weight of the edges the reference chose, and how many."""
    try:
        pairs = matching.decode_to_edges_array(syndrome_vector.astype(np.uint8))
    except ValueError:
        return None, None, None

    merged = {}
    for edge in build_graph(dem)[0]:
        merged[frozenset((edge.a, edge.b))] = edge.weight

    total, count, unknown = 0.0, 0, 0
    seen = set()
    for a, b in pairs:
        key = frozenset((int(a), int(b)))
        if key in seen:
            continue
        seen.add(key)
        w = merged.get(key)
        if w is None:
            unknown += 1
        else:
            total += w
            count += 1
    return total, count, unknown


def my_route_weight(adjacency, events, pairing):
    """Total weight of the routes my pairing uses."""
    routes = {e: shortest_routes(adjacency, e) for e in events}
    total = 0.0
    seen = set()
    for event in events:
        partner = pairing.get(event)
        if partner is None:
            continue
        key = frozenset((event, partner))
        if key in seen:
            continue
        seen.add(key)
        found = routes[event].get(partner)
        if found is not None:
            total += found[0]
    return total


def main():
    from quantumnet.core.tjoin import pair_minimum_weight

    for distance in (3, 5):
        circuit = stim.Circuit.generated(
            "surface_code:rotated_memory_z", distance=distance,
            rounds=distance, after_clifford_depolarization=0.003)
        dem = circuit.detector_error_model(decompose_errors=True)
        matching = Matching.from_detector_error_model(dem)
        edges, adjacency = build_graph(dem)
        sampler = circuit.compile_detector_sampler(seed=9)
        detection, _ = sampler.sample(400, separate_observables=True)

        heavier = lighter = equal = unknown_total = 0
        gaps = []
        for shot in range(400):
            events = sorted(int(e) for e in np.flatnonzero(detection[shot])
                            if int(e) in adjacency)
            if not events:
                continue
            pairing, exact = pair_minimum_weight(adjacency, events)
            if not exact:
                continue
            mine = my_route_weight(adjacency, events, pairing)
            ref, count, unknown = reference_edge_weight(
                dem, matching, detection[shot])
            if ref is None or unknown:
                unknown_total += 1
                continue
            gap = mine - ref
            gaps.append(gap)
            if gap > 1e-6:
                heavier += 1
            elif gap < -1e-6:
                lighter += 1
            else:
                equal += 1

        print(f"d={distance}: {len(gaps)} comparable shots"
              f"  (unknown/unavailable: {unknown_total})")
        if gaps:
            print(f"   my routes HEAVIER than the reference: {heavier}")
            print(f"   my routes LIGHTER:                    {lighter}")
            print(f"   equal:                                {equal}")
            print(f"   mean gap: {np.mean(gaps):+.4f}   max: {max(gaps):+.4f}")
        print()


if __name__ == "__main__":
    main()
