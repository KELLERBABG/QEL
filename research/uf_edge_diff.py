"""Edge-by-edge: why does a lighter correction flip the observable?

Round 10 established that the in-package correction is **strictly lighter** than the
reference's on 87% of shots and never heavier, yet produces **7.2x more logical
errors**. A miscalibrated cost would make it heavier, so the cost is not the problem.

The remaining question is the observable. This compares, on the shots where the two
decoders disagree, exactly which edges each chose and what observable each edge set
implies -- so the disagreement is located rather than inferred.
"""
import numpy as np
import stim
from pymatching import Matching

from quantumnet.core.tjoin import (
    BOUNDARY,
    build_graph,
    decode,
    pair_minimum_weight,
    shortest_routes,
)


def reference_edges_and_observable(dem, matching, syndrome_row):
    """The reference's chosen edge set and the observable it implies."""
    try:
        pairs = matching.decode_to_edges_array(syndrome_row.astype(np.uint8))
    except ValueError:
        return None, None
    chosen = set()
    obs = 0
    for a, b in pairs:
        a, b = int(a), int(b)
        key = frozenset((a, b))
        if key in chosen:
            continue
        chosen.add(key)
        try:
            if a == -1 or b == -1:
                data = matching.get_boundary_edge_data(b if a == -1 else a)
            else:
                data = matching.get_edge_data(a, b)
            if 0 in set(data.get("fault_ids") or []):
                obs ^= 1
        except Exception:
            pass
    return chosen, bool(obs)


def reference_edge_weight(dem, matching):
    """Weights keyed by detector pair, from the reference's own graph."""
    weights = {}
    edges, _ = build_graph(dem)
    for edge in edges:
        weights[frozenset((edge.a, edge.b))] = edge.weight
    return weights


def my_routes(adjacency, events, pairing, max_events=12):
    """The edge pairs my decoder's routes traverse."""
    routes = {e: shortest_routes(adjacency, e) for e in events}
    traversed = set()
    pairs = {e: pairing.get(e) for e in events}
    seen = set()
    for event in events:
        partner = pairs.get(event)
        if partner is None:
            continue
        key = frozenset((event, partner))
        if key in seen:
            continue
        seen.add(key)
        # Re-walk the route by greedy descent on the distance function.
        dist = routes[event]
        if partner not in dist:
            continue
        cost = dist[partner][0]
        node = partner
        guard = 0
        while cost > 1e-9 and guard < 1000:
            guard += 1
            for neighbour, weight, _obs in adjacency.get(node, []):
                found = dist.get(neighbour)
                if found is not None and abs(found[0] - (cost - weight)) < 1e-9:
                    traversed.add(frozenset((node, neighbour)))
                    node, cost = neighbour, found[0]
                    break
            else:
                break
    return traversed


def main():
    for distance in (3, 5):
        circuit = stim.Circuit.generated(
            "surface_code:rotated_memory_z", distance=distance,
            rounds=distance, after_clifford_depolarization=0.003)
        dem = circuit.detector_error_model(decompose_errors=True)
        matching = Matching.from_detector_error_model(dem)
        edges, adjacency = build_graph(dem)
        sampler = circuit.compile_detector_sampler(seed=13)
        detection, observables = sampler.sample(2000, separate_observables=True)
        truth = observables[:, 0].astype(bool)

        disagree = 0
        only_ref = 0
        only_mine = 0
        obs_differs = 0
        shared_pairs = 0
        for shot in range(2000):
            events = sorted(int(e) for e in np.flatnonzero(detection[shot])
                            if int(e) in adjacency)
            mine_obs = bool(0 in decode(dem, np.flatnonzero(detection[shot])))
            ref_chosen, ref_obs = reference_edges_and_observable(
                dem, matching, detection[shot])
            if ref_chosen is None:
                continue
            if mine_obs == ref_obs:
                continue
            disagree += 1
            if not events:
                continue
            pairing, _ = pair_minimum_weight(adjacency, events)
            mine_edges = my_routes(adjacency, events, pairing)
            overlap = mine_edges & ref_chosen
            shared_pairs += 1
            if mine_edges - ref_chosen:
                only_mine += 1
            if ref_chosen - mine_edges:
                only_ref += 1
            if mine_obs != ref_obs:
                obs_differs += 1

        print(f"d={distance}: {disagree} shots where the observables differ"
              f"  (of 2000)")
        if disagree:
            print(f"   shots where I used an edge the reference did not: "
                  f"{only_mine}")
            print(f"   shots where the reference used an edge I did not: "
                  f"{only_ref}")
        print()


if __name__ == "__main__":
    main()
