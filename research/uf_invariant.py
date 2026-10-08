"""Diagnose whether Union-Find's corrections reproduce the syndrome.

**A correction must satisfy one invariant: the detectors incident to an odd number
of its edges must equal the observed detection events.** No decoder in this package
has ever checked it, and a violation means the answer is *provably wrong* rather
than merely suboptimal -- which is the difference between "the matcher chose a poor
partner" (fixable by better pairing) and "the correction does not correspond to the
syndrome at all" (not fixable by any pairing).

This script measures the violation rate directly, because three different matchers
have all landed 20-100x off and the shared assumption is the one nobody tested.
"""
import numpy as np
import stim

from quantumnet.core.surface_code import _dem_components
from quantumnet.core.union_find import BOUNDARY, UnionFindDecoder


def node_edges_of(edges):
    """``{node: [edge index]}`` -- the incidence the growth phase needs."""
    node_edges: dict[int, list[int]] = {}
    for edge in edges:
        node_edges.setdefault(edge.a, []).append(edge.index)
        node_edges.setdefault(edge.b, []).append(edge.index)
    return node_edges


def correction_and_syndrome(decoder, dem, edges, events):
    """Return ``(chosen_edge_indices, induced_syndrome, observed_syndrome)``.

    ``induced_syndrome`` is the set of detector nodes incident to an odd number of
    chosen edges -- the boundary of the correction, which is what must match.
    """
    index_of = {}
    for edge in edges:
        index_of[edge.index] = edge

    parent, size, parity, touches, members, boundary_of = decoder._grow(
        edges, node_edges_of(edges), list(events))
    chosen = decoder._peel(edges, parent, parity, touches, members, list(events))
    for root, index in boundary_of.items():
        if parity.get(root, 0):
            chosen.add(index)

    touched: dict[int, int] = {}
    for index in chosen:
        edge = index_of[index]
        for node in (edge.a, edge.b):
            if node == BOUNDARY:
                continue
            touched[node] = touched.get(node, 0) ^ 1
    induced = {n for n, p in touched.items() if p}
    return chosen, induced, set(int(e) for e in events)


def main():
    for distance in (3, 5):
        for noise in (0.003,):
            circuit = stim.Circuit.generated(
                "surface_code:rotated_memory_z", distance=distance,
                rounds=distance, after_clifford_depolarization=noise)
            dem = circuit.detector_error_model(decompose_errors=True)
            decoder = UnionFindDecoder()
            edges, _ = decoder.graph_from_dem(dem)
            sampler = circuit.compile_detector_sampler(seed=5)
            detection, observables = sampler.sample(400, separate_observables=True)

            violations = 0
            total_mismatch = 0
            with_events = 0
            for shot in range(400):
                events = np.flatnonzero(detection[shot])
                if len(events) == 0:
                    continue
                with_events += 1
                _, induced, observed = correction_and_syndrome(
                    decoder, dem, edges, events)
                if induced != observed:
                    violations += 1
                    total_mismatch += len(induced ^ observed)

            print(f"d={distance} p={noise}: {with_events} shots with events")
            print(f"   correction does NOT reproduce syndrome: {violations}"
                  f"  ({100 * violations / max(with_events, 1):.1f}%)")
            if violations:
                print(f"   mean disagreeing detectors when it fails: "
                      f"{total_mismatch / violations:.2f}")
            print()


if __name__ == "__main__":
    main()
