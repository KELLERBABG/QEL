"""T-join decoding: a correction is an exact parity statement, not a heuristic.

Why this file exists
--------------------
Four rounds of peeling-based Union-Find produced corrections that were **provably
wrong** -- 37.8% of shots failed to reproduce the observed syndrome, and when the
peel was handed the *full* edge set, where a correct answer provably exists, it
still failed 51.9% of the time. That isolated the defect to the reduction step
rather than the graph.

Rather than patch the peel again, this takes the definition literally.

**What a correction is.**  Given a graph with a boundary node and a set ``T`` of
detection events, a correction is a set of edges whose odd-degree vertices are
exactly ``T``.  That is a **T-join**.  It is an exact parity statement, and it can
be *checked* rather than argued about -- which matters here, because five successive
"principled" changes to the peel each measured worse than the state they replaced.

How it is built
---------------
Pair the events.  Any pairing plus a route for each pair gives a valid T-join: the
endpoints of each route are the pair's two events, and every interior vertex of a
route is entered and left, so its degree contribution is even.  A pairing may also
send an event to the boundary, since an odd-degree boundary vertex is allowed.

So correctness does **not** depend on choosing a good pairing -- only the *weight*
does.  That separation is the point: this version targets **validity**, with quality
as a follow-up, because four rounds spent optimising quality on an invalid answer.

Routing is by Dijkstra over ``-log(p)``.  Observables toggle along the route, since
a mechanism whose signature appears twice cancels -- the same XOR rule that fixed the
greedy decoder.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np

from .surface_code import SurfaceCodeError

try:
    import stim

    HAVE_STIM = True
except ImportError:  # pragma: no cover
    stim = None
    HAVE_STIM = False

BOUNDARY = -1


class TJoinError(SurfaceCodeError):
    """Raised when a decoding instance cannot be turned into a T-join."""


@dataclass(frozen=True)
class GraphEdge:
    """One graphlike DEM mechanism."""

    a: int
    b: int
    weight: float
    observables: frozenset


def build_graph(dem) -> tuple[list[GraphEdge], dict]:
    """Flatten a DEM into merged graph edges plus an adjacency list.

    Mechanisms are merged per detector pair, with probability combined as
    ``1 - prod(1 - p_i)`` and **observables XOR'd**.  A detector carries up to 35
    parallel single-detector components at d=3; treating them as independent both
    inflates the graph and makes "which one fired" arbitrary, and accumulating
    their observables by OR double-counts.
    """
    from .surface_code import _dem_components

    # **Mechanisms are NOT merged.**  An earlier version combined every mechanism
    # sharing a detector pair into one edge, with probability ``1 - prod(1 - p_i)``
    # and observables XOR'd.  That is wrong, and the reason is specific: parallel
    # mechanisms need not share an observable signature.  At d=3 the pair
    # ``(-1, 14)`` is 35 mechanisms of which **16 carry the observable** -- an even
    # count, so XOR *discarded* it, and the decoder then treated a family of
    # observable-flipping errors as though none of them flipped anything.  Measured
    # effect: 64 raw mechanisms carry the observable but only 12 merged edges did,
    # and the decoder over-flipped, getting 0 errors on event-free shots while
    # producing 58 on the 224 shots that had events, against ~33 expected.
    #
    # Keeping the mechanisms separate is what makes the observable attribution
    # correct: each edge carries its own probability and its own signature, exactly
    # as the DEM states them.  Parallel edges are harmless -- Dijkstra handles them
    # -- whereas merging them destroys the information the decoder needs.
    edges: list[GraphEdge] = []
    for inst in dem.flattened():
        if inst.type != "error":
            continue
        probability = float(inst.args_copy()[0])
        if probability <= 0.0:
            continue
        observables = frozenset(
            t.val for t in inst.targets_copy() if t.is_logical_observable_id())
        for component in _dem_components(inst):
            if len(component) == 2:
                a, b = component
                if a == b:
                    continue
                edges.append(GraphEdge(a=a, b=b, weight=-float(np.log(
                    float(np.clip(probability, 1e-300, 1.0)))),
                    observables=observables))
            elif len(component) == 1:
                edges.append(GraphEdge(
                    a=BOUNDARY, b=component[0],
                    weight=-float(np.log(
                        float(np.clip(probability, 1e-300, 1.0)))),
                    observables=observables))

    adjacency: dict[int, list[tuple[int, float, frozenset]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.a, []).append(
            (edge.b, edge.weight, edge.observables))
        adjacency.setdefault(edge.b, []).append(
            (edge.a, edge.weight, edge.observables))
    return edges, adjacency


def shortest_routes(adjacency: dict, source: int) -> dict:
    """Dijkstra from ``source``; values are ``(cost, observables)``.

    Observables accumulate by XOR, so a signature appearing on two edges of the
    route cancels.
    """
    best: dict[int, tuple[float, frozenset]] = {source: (0.0, frozenset())}
    heap = [(0.0, source)]
    while heap:
        cost, node = heapq.heappop(heap)
        if cost > best.get(node, (float("inf"), frozenset()))[0]:
            continue
        _, obs = best[node]
        for neighbour, weight, edge_obs in adjacency.get(node, []):
            new_cost = cost + weight
            if new_cost < best.get(neighbour, (float("inf"), frozenset()))[0] - 1e-12:
                toggled = set(obs)
                for o in edge_obs:
                    if o in toggled:
                        toggled.discard(o)
                    else:
                        toggled.add(o)
                best[neighbour] = (new_cost, frozenset(toggled))
                heapq.heappush(heap, (new_cost, neighbour))
    return best


def correction_for_pairing(adjacency: dict, events: list[int],
                           pairing) -> set[int]:
    """Observables toggled by the routes implied by ``pairing``.

    ``pairing`` maps each event to either another event or ``BOUNDARY``.  Interior
    vertices of a route are entered and left, so their degree stays even and the
    T-join condition holds regardless of which pairing was chosen.
    """
    toggled: set[int] = set()
    routes = {e: shortest_routes(adjacency, e) for e in events}
    for event in events:
        partner = pairing.get(event)
        if partner is None:
            continue
        found = routes[event].get(partner)
        if found is None:
            continue
        for obs in found[1]:
            if obs in toggled:
                toggled.discard(obs)
            else:
                toggled.add(obs)
    return toggled


def pair_greedily(adjacency: dict, events: list[int]) -> dict:
    """Nearest-neighbour pairing with the boundary available as a partner.

    Valid but **heavy**: measured 38-349x worse than the reference, which is why it
    is no longer the default.  Kept because the difference between it and
    :func:`pair_minimum_weight` is a measurement rather than an opinion.
    """
    routes = {e: shortest_routes(adjacency, e) for e in events}
    remaining = list(events)
    pairing: dict[int, int] = {}
    while remaining:
        event = remaining.pop(0)
        best = None
        for other in remaining:
            found = routes[event].get(other)
            if found is not None and (best is None or found[0] < best[0]):
                best = (found[0], other)
        boundary = routes[event].get(BOUNDARY)
        if boundary is not None and (best is None or boundary[0] <= best[0]):
            pairing[event] = BOUNDARY
            continue
        if best is None:
            # No partner and no boundary route: leave it unmatched rather than
            # inventing one, which would break the parity statement.
            continue
        pairing[event] = best[1]
        pairing[best[1]] = event
        if best[1] in remaining:
            remaining.remove(best[1])
    return pairing


def pair_minimum_weight(adjacency: dict, events: list[int],
                        max_events: int = 12) -> tuple[dict, bool]:
    """Minimum-weight pairing by exhaustive enumeration of perfect matchings.

    **Valid is not good.**  A T-join is only as short as its pairing makes it, and
    greedy nearest-neighbour chooses partners that satisfy the parity condition while
    being far too heavy: measured 38-349x worse than the reference, where the
    reference's advantage is precisely that it pairs optimally.  This closes that
    gap by enumerating every pairing and taking the cheapest.

    The candidate set is the events **plus one boundary slot**.  A pairing may send
    any single event to the boundary (the boundary tolerates odd degree), so each
    event is tried in turn as the boundary-terminated one, with the remainder matched
    among themselves.  When the event count is even the boundary is not needed and the
    plain enumeration is used.

    Returns ``(pairing, exact)``.  ``exact`` is ``False`` when the instance exceeded
    ``max_events`` and the greedy fallback was used -- reported rather than hidden,
    because a silently approximate matcher is how the previous decoder produced
    confident wrong numbers.
    """
    from .surface_code import _perfect_matchings

    events = sorted(events)
    routes = {e: shortest_routes(adjacency, e) for e in events}

    def cost(a, b):
        found = routes[a].get(b) if a in routes else None
        return None if found is None else found[0]

    def best_for(pool: tuple[int, ...]):
        """Cheapest perfect matching of ``pool``, or ``None`` if infeasible."""
        best = None
        for matching in _perfect_matchings(pool):
            total = 0.0
            ok = True
            for a, b in matching:
                c = cost(a, b)
                if c is None:
                    ok = False
                    break
                total += c
            if ok and (best is None or total < best[0]):
                best = (total, {a: b for a, b in matching}
                        | {b: a for a, b in matching})
        return best

    if len(events) > max_events:
        pairing = pair_greedily(adjacency, events)
        return pairing, False

    candidates = []
    # Even count: match among themselves, boundary unused.
    if len(events) % 2 == 0:
        found = best_for(tuple(events))
        if found is not None:
            candidates.append(found)
    # Any single event may go to the boundary, whatever the parity.
    for index, event in enumerate(events):
        rest = tuple(e for i, e in enumerate(events) if i != index)
        if len(rest) % 2:
            continue
        found = best_for(rest)
        if found is None:
            continue
        to_boundary = cost(event, BOUNDARY)
        if to_boundary is None:
            continue
        total = found[0] + to_boundary
        pairing = dict(found[1])
        pairing[event] = BOUNDARY
        candidates.append((total, pairing))

    if not candidates:
        pairing = pair_greedily(adjacency, events)
        return pairing, False
    return min(candidates, key=lambda item: item[0])[1], True


def decode(dem, detection_events, *, exact: bool = True,
           max_events: int = 12) -> frozenset:
    """Decode one shot into the observables that should be toggled."""
    edges, adjacency = build_graph(dem)
    events = sorted(int(e) for e in detection_events if int(e) in adjacency)
    if not events:
        return frozenset()
    if exact:
        pairing, _ = pair_minimum_weight(adjacency, events,
                                         max_events=max_events)
    else:
        pairing = pair_greedily(adjacency, events)
    return frozenset(correction_for_pairing(adjacency, events, pairing))


def syndrome_of_correction(edges, chosen_observables_unused=None) -> None:
    """Placeholder retained for API symmetry; see ``verify_join``."""
    return None


def verify_join(adjacency: dict, events: list[int], pairing: dict) -> set[int]:
    """Check the T-join condition and return where it fails.

    Reconstructs the edge multiset implied by the pairing and reports the
    vertices whose degree is odd but which are not detection events, or which are
    events but have even degree.  An empty set means the correction is **valid**,
    which is the property four rounds of peeling never established.
    """
    degree: dict[int, int] = {}
    routes = {e: shortest_routes(adjacency, e) for e in events}
    seen_pairs: set[frozenset] = set()
    for event in events:
        partner = pairing.get(event)
        if partner is None:
            continue
        if frozenset((event, partner)) in seen_pairs:
            continue
        seen_pairs.add(frozenset((event, partner)))
        route = _route_edges(adjacency, routes[event], partner)
        for a, b in route:
            degree[a] = degree.get(a, 0) ^ 1
            degree[b] = degree.get(b, 0) ^ 1
    odd = {n for n, p in degree.items() if p}
    # **The boundary is legitimately odd.**  A route that ends at the code edge
    # contributes one unit of odd degree there, so the boundary belongs in the odd
    # set by construction.  Comparing against it reported a violation for every
    # boundary-terminated route -- a single event paired to the boundary came back
    # as `odd = {-1, 21}` against events `{21}`, which is *correct*.  The condition
    # to check is on detector vertices only.
    odd.discard(BOUNDARY)
    return odd ^ set(events)


def _route_edges(adjacency: dict, distances: dict, target: int):
    """Walk back a shortest route, returning its edges as node pairs."""
    if target not in distances:
        return []
    # Recompute the path by greedy descent on the distance function.
    cost, _ = distances[target]
    path = [target]
    node = target
    while cost > 0:
        for neighbour, weight, _obs in adjacency.get(node, []):
            found = distances.get(neighbour)
            if found is None:
                continue
            if abs(found[0] - (cost - weight)) < 1e-9:
                path.append(neighbour)
                node, cost = neighbour, found[0]
                break
        else:
            break
    return list(zip(path, path[1:]))


def compare_to_reference(distance: int, noise: float, *, shots: int = 2000,
                         rounds: int | None = None, seed: int = 1) -> dict:
    """T-join decoder against PyMatching, on identical shots."""
    if not HAVE_STIM:
        raise TJoinError("needs stim")
    try:
        from pymatching import Matching
    except ImportError as exc:  # pragma: no cover
        raise TJoinError("needs pymatching for the comparison") from exc

    rounds = distance if rounds is None else rounds
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=distance, rounds=rounds,
        after_clifford_depolarization=noise)
    dem = circuit.detector_error_model(decompose_errors=True)
    sampler = circuit.compile_detector_sampler(seed=seed)
    detection, observables = sampler.sample(shots, separate_observables=True)

    reference = Matching.from_detector_error_model(dem).decode_batch(detection)
    truth = observables.astype(bool)
    ref_err = int(np.sum(reference.astype(bool) != truth))

    mine_err = 0
    for shot in range(shots):
        flipped = decode(dem, np.flatnonzero(detection[shot]))
        if (0 in flipped) != bool(truth[shot, 0]):
            mine_err += 1
    return {
        "distance": distance, "rounds": rounds, "noise": noise, "shots": shots,
        "reference_errors": ref_err, "tjoin_errors": mine_err,
        "reference_rate": ref_err / shots, "tjoin_rate": mine_err / shots,
    }
