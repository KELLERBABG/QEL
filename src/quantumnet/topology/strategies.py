"""Pluggable routing strategies.

Why an interface rather than a function
---------------------------------------
QEL already had two good routers -- an exhaustive fidelity ranking and a
Dijkstra -- but they were free functions with different call shapes and no way
to say *which* policy a result came from.  That matters for two reasons:

1. **A comparison needs a control.**  "QEL routes better than a general-purpose
   simulator" is only meaningful against that simulator's actual policy.  The
   incumbent's stock static routing is Dijkstra on **physical distance**, so
   that policy is implemented here as :class:`LengthRouting` -- not to use it,
   but so it can be beaten *measurably* rather than rhetorically.
2. **Strategies must be substitutable.**  A planner should be able to swap the
   policy without editing the caller, and a third party should be able to add
   one without touching this file -- which is what the registry provides.

The strategies
--------------
:class:`FidelityOptimalRouting`
    Dijkstra on ``-log W`` where ``W = (4F-1)/3``.  Provably optimal for
    end-to-end fidelity, because the Werner parameter is exactly multiplicative
    under swapping and therefore ``-log W`` is exactly additive along a path.
    This is QEL's differentiator and it is the default.
:class:`LengthRouting`
    Dijkstra on physical distance, matching the incumbent's stock policy.
    The control condition.
:class:`HopCountRouting`
    Fewest links.  Included because it is the obvious naive choice, and because
    on a loss-heavy network it is *not* the same as the fidelity-optimal route.
:class:`StaticRouting`
    A hand-configured forwarding table, for reproducing a fixed deployment.

All of them return a :class:`~quantumnet.topology.routing.Route`, so nothing
downstream needs to know which policy produced it.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .graph import QuantumTopology
from .routing import Route, optimal_swap_order


class RoutingError(ValueError):
    """Raised when a routing strategy cannot be resolved or applied."""


# Edge weights

def werner_parameter(fidelity: float) -> float:
    """``W = (4F - 1) / 3``, the parameter that multiplies under swapping."""
    return (4.0 * float(fidelity) - 1.0) / 3.0


def fidelity_weight(link) -> float:
    """``-log W``: the exactly-additive cost whose minimisation maximises fidelity.

    Returns ``inf`` for a link at or below the classical limit (``F <= 1/4``),
    which can never carry entanglement, so no path may use it.
    """
    w = werner_parameter(link.fidelity())
    if w <= 0.0:
        return math.inf
    return -math.log(w)


def length_weight(link) -> float:
    """Physical distance in km.  This is the incumbent's stock policy."""
    return float(link.length_km)


def hop_weight(link) -> float:
    """Unit cost per link, so minimising it minimises hop count."""
    return 1.0


# Base class and registry

@dataclass
class RoutingStrategy:
    """A policy that selects a route between two nodes.

    Subclasses implement :meth:`_select`, which returns the path as a list of
    node ids or ``None``.  The base class handles the shared work: resolving the
    path into a :class:`Route` with the correct swap order and end-to-end
    fidelity, so every strategy reports fidelity the same way and two policies
    can be compared on equal terms.
    """

    name: str = "strategy"

    def _select(self, topology: QuantumTopology, src: str,
                dst: str) -> list[str] | None:
        raise NotImplementedError

    def select(self, topology: QuantumTopology, src: str,
               dst: str) -> Route | None:
        """Return the chosen route, or None when none exists."""
        path = self._select(topology, src, dst)
        if not path:
            return None
        return route_from_path(topology, path)

    def route_all(self, topology: QuantumTopology,
                  src: str) -> dict[str, Route | None]:
        """Routes from ``src`` to every other node."""
        return {dst: self.select(topology, src, dst)
                for dst in topology.nodes if dst != src}

    def forwarding_table(self, topology: QuantumTopology) -> dict[str, str]:
        """``{destination: next_hop}`` for every node.

        The shape a router actually needs.  Destinations that are unreachable
        are omitted rather than mapped to a placeholder, so a caller cannot
        mistake "no route" for "route to nowhere".
        """
        table: dict[str, str] = {}
        for src in topology.nodes:
            for dst, route in self.route_all(topology, src).items():
                if route is not None and len(route.path) >= 2:
                    table[f"{src}->{dst}"] = route.path[1]
        return table

    def describe(self) -> str:
        return self.name


@dataclass
class StaticRouting(RoutingStrategy):
    """A fixed forwarding table, keyed ``"src->dst"`` to the next hop.

    Exists to reproduce a hand-planned deployment and to serve as a control in
    comparisons: whatever a dynamic strategy produces should be judged against
    a fixed table, not only against another dynamic one.
    """

    table: dict[str, str] = field(default_factory=dict)
    name: str = "static"

    def _select(self, topology, src, dst):
        hops = [src]
        seen = {src}
        current = src
        while current != dst:
            nxt = self.table.get(f"{current}->{dst}")
            if nxt is None or nxt in seen or nxt not in topology.nodes:
                return None
            hops.append(nxt)
            seen.add(nxt)
            current = nxt
            if len(hops) > len(topology.nodes):
                return None
        return hops


@dataclass
class _DijkstraRouting(RoutingStrategy):
    """Dijkstra over a pluggable edge weight.

    One implementation, three policies: the weight function is the only thing
    that differs between minimising fidelity loss, distance, or hop count, so
    the search cannot drift between them.
    """

    weight: Callable = fidelity_weight

    def _select(self, topology, src, dst):
        if src not in topology.nodes or dst not in topology.nodes:
            return None
        if src == dst:
            return None

        dist: dict[str, float] = {src: 0.0}
        prev: dict[str, str] = {}
        visited: set[str] = set()
        heap: list[tuple[float, str]] = [(0.0, src)]

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == dst:
                break
            for v in topology.neighbors(u):
                if v in visited:
                    continue
                link = topology.link(u, v)
                if link is None:
                    continue
                step = self.weight(link)
                if not math.isfinite(step):
                    continue
                nd = d + step
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))

        if dst not in visited:
            return None
        path = [dst]
        while path[-1] != src:
            path.append(prev[path[-1]])
        path.reverse()
        return path


@dataclass
class FidelityOptimalRouting(_DijkstraRouting):
    """Dijkstra on ``-log W``: provably the highest-fidelity route.

    Optimal because swapping multiplies the Werner parameter, so ``-log W``
    sums along a path and shortest-path search is exact.  Weighting by
    ``-log F`` instead is the common approximation and is *not* optimal; see
    ``tests/test_topology/test_routing_optimality.py`` for a worked
    counterexample.
    """

    name: str = "fidelity-optimal"


@dataclass
class LengthRouting(_DijkstraRouting):
    """Dijkstra on physical distance: the incumbent simulator's stock policy.

    The control condition for any claim that fidelity-aware routing is better.
    """

    weight: Callable = length_weight
    name: str = "shortest-distance"


@dataclass
class HopCountRouting(_DijkstraRouting):
    """Fewest links.  The obvious naive choice, and not the same as optimal."""

    weight: Callable = hop_weight
    name: str = "fewest-hops"


#: Registry of strategies by name, so one can be chosen from a config file.
_REGISTRY: dict[str, type[RoutingStrategy]] = {}


def register_routing(name: str, strategy: type[RoutingStrategy] | None = None):
    """Register a strategy class under ``name``.

    Usable as a decorator or called directly, so a third party can add a policy
    without editing this module::

        @register_routing("my-policy")
        class MyPolicy(RoutingStrategy): ...
    """
    def _register(cls: type[RoutingStrategy]) -> type[RoutingStrategy]:
        _REGISTRY[name] = cls
        return cls

    return _register(strategy) if strategy is not None else _register


def path_secret_key_rate(
    topology: QuantumTopology,
    path: list[str],
    *,
    p_bsm: float = 0.5,
    swap_fidelity: float = 1.0,
    t_swap_s: float = 0.0,
    serial_sharing: bool = True,
    qber_model: str = "werner",
) -> dict:
    """Compute exact end-to-end Secret Key Rate (bps) along `path`."""
    from .placement import key_fraction

    if len(path) < 2:
        return {"skr_hz": 0.0, "e2e_fidelity": 0.0, "e2e_rate_hz": 0.0, "hops": 0}
    h = len(path) - 1
    rates: list[float] = []
    w_prod = 1.0
    for a, b in zip(path, path[1:]):
        link = topology.link(a, b)
        if link is None:
            return {"skr_hz": 0.0, "e2e_fidelity": 0.0, "e2e_rate_hz": 0.0, "hops": h}
        rates.append(float(link.generation_rate()))
        w_e = max(0.0, (4.0 * float(link.fidelity()) - 1.0) / 3.0)
        if t_swap_s > 0.0:
            node_a = topology.nodes[a]
            gamma = (0.0 if node_a.t1_s <= 0 else 1.0 / node_a.t1_s) + (
                0.0 if node_a.t2_s <= 0 else 1.0 / node_a.t2_s
            )
            w_e *= float(np.exp(-gamma * t_swap_s))
        w_prod *= w_e

    w_swap = max(0.0, (4.0 * float(swap_fidelity) - 1.0) / 3.0)
    w_e2e = w_prod * (w_swap ** (h - 1))
    f_e2e = (1.0 + 3.0 * w_e2e) / 4.0
    bottleneck = min(rates)
    sync_rate = (bottleneck / h) if serial_sharing else bottleneck
    e2e_rate = sync_rate * (float(p_bsm) ** (h - 1))
    kf = key_fraction(f_e2e, qber_model=qber_model)
    return {
        "skr_hz": float(e2e_rate * kf),
        "e2e_fidelity": float(f_e2e),
        "e2e_rate_hz": float(e2e_rate),
        "key_fraction": float(kf),
        "hops": h,
    }


@dataclass
class SKROptimalRouting(RoutingStrategy):
    """Exact polynomial-time Secret-Key-Rate-Optimal Routing (08 §3.3 Formulation A).

    Stratifies over distinct link generation rates R_(q) and runs an h_max-layered
    Bellman-Ford / shortest-path DP on -log(W_e) to find the global SKR-optimal simple path.
    """

    name: str = "skr-optimal"
    p_bsm: float = 0.5
    swap_fidelity: float = 1.0
    t_swap_s: float = 0.0
    max_hops: int = 8
    serial_sharing: bool = True
    qber_model: str = "werner"

    def _select(self, topology: QuantumTopology, src: str, dst: str) -> list[str] | None:
        if src not in topology.nodes or dst not in topology.nodes or src == dst:
            return None
        distinct_rates = sorted({float(l.generation_rate()) for l in topology.links.values() if l.generation_rate() > 0})
        if not distinct_rates:
            return None

        h_limit = min(self.max_hops, max(1, len(topology.nodes) - 1))
        best_path: list[str] | None = None
        best_Tuple: tuple[float, float] = (-1.0, -1.0)  # (skr_hz, e2e_fidelity)

        for r_min in distinct_rates:
            # dp[h][node] = (min_cost, path_list)
            dp: list[dict[str, tuple[float, list[str]]]] = [{} for _ in range(h_limit + 1)]
            dp[0][src] = (0.0, [src])
            for h in range(1, h_limit + 1):
                prev_layer = dp[h - 1]
                if not prev_layer:
                    break
                cur_layer = dp[h]
                for u, (cost_u, path_u) in prev_layer.items():
                    for v in topology.neighbors(u):
                        if v in path_u:
                            continue
                        link = topology.link(u, v)
                        if link is None or link.generation_rate() + 1e-12 < r_min:
                            continue
                        step = fidelity_weight(link)
                        if not math.isfinite(step):
                            continue
                        if self.t_swap_s > 0.0:
                            na = topology.nodes[u]
                            gamma = (0.0 if na.t1_s <= 0 else 1.0 / na.t1_s) + (
                                0.0 if na.t2_s <= 0 else 1.0 / na.t2_s
                            )
                            step += gamma * self.t_swap_s
                        new_cost = cost_u + step
                        existing = cur_layer.get(v)
                        if existing is None or new_cost < existing[0] - 1e-12:
                            cur_layer[v] = (new_cost, path_u + [v])
                if dst in cur_layer:
                    cand_path = cur_layer[dst][1]
                    info = path_secret_key_rate(
                        topology,
                        cand_path,
                        p_bsm=self.p_bsm,
                        swap_fidelity=self.swap_fidelity,
                        t_swap_s=self.t_swap_s,
                        serial_sharing=self.serial_sharing,
                        qber_model=self.qber_model,
                    )
                    score = (info["skr_hz"], info["e2e_fidelity"])
                    if score > best_Tuple:
                        best_Tuple = score
                        best_path = cand_path
        return best_path


register_routing("skr-optimal", SKROptimalRouting)
register_routing("fidelity-optimal", FidelityOptimalRouting)
register_routing("fidelity", FidelityOptimalRouting)
register_routing("log-w", FidelityOptimalRouting)
register_routing("shortest-distance", LengthRouting)
register_routing("distance", LengthRouting)
register_routing("fewest-hops", HopCountRouting)
register_routing("hops", HopCountRouting)
register_routing("static", StaticRouting)


def available_strategies() -> list[str]:
    """Sorted registered strategy names."""
    return sorted(_REGISTRY)


def make_strategy(name: str, **kwargs) -> RoutingStrategy:
    """Instantiate a registered strategy by name."""
    if name not in _REGISTRY:
        raise RoutingError(
            f"unknown routing strategy {name!r}; available: "
            f"{available_strategies()}"
        )
    return _REGISTRY[name](**kwargs)


# Shared helpers

def route_from_path(topology: QuantumTopology, path: list[str]) -> Route:
    """Build a :class:`Route` from a node path, resolving fidelities and order."""
    fidelities: list[float] = []
    for a, b in zip(path, path[1:]):
        link = topology.link(a, b)
        if link is None:
            raise RoutingError(f"path uses a non-existent link {a}-{b}")
        fidelities.append(link.fidelity())
    order, final = optimal_swap_order(fidelities)
    return Route(path=list(path), link_fidelities=fidelities,
                 e2e_fidelity=final, swap_order=order)


@dataclass
class StrategyComparison:
    """Per-strategy outcome for one source-destination pair."""

    src: str
    dst: str
    results: dict[str, Route | None] = field(default_factory=dict)

    @property
    def best_name(self) -> str | None:
        scored = [(name, r.e2e_fidelity) for name, r in self.results.items()
                  if r is not None]
        if not scored:
            return None
        return max(scored, key=lambda kv: kv[1])[0]

    def fidelity(self, name: str) -> float | None:
        route = self.results.get(name)
        return None if route is None else route.e2e_fidelity

    def describe(self) -> str:
        lines = [f"{self.src} -> {self.dst}"]
        for name in sorted(self.results):
            route = self.results[name]
            if route is None:
                lines.append(f"  {name:<20} no route")
            else:
                lines.append(f"  {name:<20} F={route.e2e_fidelity:.6f}  "
                             f"hops={route.hops}  "
                             f"{' -> '.join(route.path)}")
        best = self.best_name
        if best:
            lines.append(f"  best: {best}")
        return "\n".join(lines)


def compare_strategies(topology: QuantumTopology, src: str, dst: str,
                       names: list[str] | None = None) -> StrategyComparison:
    """Run several *named* strategies over one pair and report them side by side."""
    chosen = names or ["fidelity-optimal", "shortest-distance", "fewest-hops"]
    return compare_instances(topology, src, dst,
                             [(name, make_strategy(name)) for name in chosen])


def compare_instances(topology: QuantumTopology, src: str, dst: str,
                      strategies: list[tuple[str, RoutingStrategy]]
                      ) -> StrategyComparison:
    """Compare arbitrary strategy *instances*, keyed by a label of your choosing.

    Needed because two strategies cannot always be named -- a configured
    :class:`StaticRouting` carries a table, and a control condition may be a
    one-off implementation.  Comparing objects rather than registry keys is what
    lets any policy be judged against any other.
    """
    comparison = StrategyComparison(src=src, dst=dst)
    for label, strategy in strategies:
        comparison.results[label] = strategy.select(topology, src, dst)
    return comparison


def route_with(topology: QuantumTopology, src: str, dst: str,
               strategy: str = "fidelity-optimal") -> Route | None:
    """Convenience: route one pair with a named strategy."""
    return make_strategy(strategy).select(topology, src, dst)
