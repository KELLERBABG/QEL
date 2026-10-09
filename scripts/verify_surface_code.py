"""Extract the rotated surface code spec from stim, for cross-checking QEL.

``stim`` is a **verification-only** tool: it is not a QEL dependency and this
script is not part of the test suite's required path (``stim`` is a dev extra).

Why you would run this
----------------------
A rotated surface code is easy to get subtly wrong in a way that never raises:
a hook-prone CNOT ordering keeps the circuit runnable and keeps it producing
syndromes, while dropping the circuit-level fault distance to roughly ``d/2``.
This script prints the reference layout, the per-ancilla CNOT order that stim
emits, and the reference fault distance -- so any QEL implementation can be
diffed against an authoritative source instead of against a recollection.

Usage
-----
    py scripts/verify_surface_code.py            # d = 3, 5, 7, 9
    py scripts/verify_surface_code.py 3 5 7      # explicit distances

The default set is the four distances ``VERIFIED_SITES`` pins a layout for, so the default
run covers exactly what the module claims to have verified. An earlier version defaulted to
``3 5``, which meant a reader who ran it without arguments checked less than the docstring in
``surface_code.py`` promised.

Requires ``pip install stim``.  Exits non-zero if a claimed invariant fails.
"""

from __future__ import annotations

import sys

try:
    import stim
except ImportError:  # pragma: no cover - dev-only tool
    print("stim is required: py -m pip install stim", file=sys.stderr)
    raise SystemExit(2)


def analyse(d: int, rounds: int = 2, noise: float = 0.001) -> dict:
    clean = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=d, rounds=rounds)

    coords: dict[int, tuple[int, int]] = {}
    for inst in clean.flattened():
        if inst.name == "QUBIT_COORDS":
            targets = inst.targets_copy()
            coords[targets[0].value] = tuple(
                int(v) for v in inst.gate_args_copy())

    data = {q: xy for q, xy in coords.items()
            if xy[0] % 2 == 1 and xy[1] % 2 == 1}
    meas = {q: xy for q, xy in coords.items() if q not in data}

    controls: set[int] = set()
    for inst in clean.flattened():
        if inst.name in ("CX", "CNOT"):
            targets = [t.value for t in inst.targets_copy()]
            for j in range(0, len(targets), 2):
                controls.add(targets[j])
    x_type = {q for q in meas if q in controls}

    # One syndrome round = the first four TICK-delimited CNOT layers.
    order: dict[int, list[int]] = {q: [] for q in meas}
    layers, current = [], []
    for inst in clean.flattened():
        if inst.name in ("CX", "CNOT"):
            targets = [t.value for t in inst.targets_copy()]
            for j in range(0, len(targets), 2):
                current.append((targets[j], targets[j + 1]))
        elif inst.name == "TICK":
            if current:
                layers.append(current)
                current = []
            if len(layers) == 4:
                break
    for layer in layers:
        for a, b in layer:
            if a in meas and b in data:
                order[a].append(b)
            elif b in meas and a in data:
                order[b].append(a)

    noisy = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=d, rounds=rounds,
        after_clifford_depolarization=noise)
    return {
        "d": d,
        "data": data,
        "meas": meas,
        "x_type": x_type,
        "order": order,
        "fault_distance": len(noisy.shortest_graphlike_error()),
    }


#: The distances ``VERIFIED_SITES`` pins a layout for. The default run uses these, so it
#: checks exactly what the module claims rather than a subset of it.
DEFAULT_DISTANCES = (3, 5, 7, 9)


def main(argv: list[str]) -> int:
    distances = [int(a) for a in argv[1:]] or list(DEFAULT_DISTANCES)

    print(f"stim {stim.__version__}")
    print()
    failures: list[str] = []

    for d in distances:
        info = analyse(d)
        data, meas, x_type, order = (info["data"], info["meas"],
                                     info["x_type"], info["order"])

        print("=" * 78)
        print(f"d = {d}: {len(data)} data, {len(meas)} measure, "
              f"{2 * d * d - 1} total "
              f"({len(x_type)} X-type, {len(meas) - len(x_type)} Z-type)")
        print("=" * 78)

        checks = [
            ("qubit count", len(data) == d * d and len(meas) == d * d - 1),
            ("data on odd-odd sublattice",
             all(x % 2 == 1 and y % 2 == 1 for x, y in data.values())),
            ("X/Z split is even",
             len(x_type) == (d * d - 1) // 2),
            ("weights are 2 or 4",
             {len(v) for v in order.values()} <= {2, 4}),
            ("fault distance == d", info["fault_distance"] == d),
        ]
        for label, ok in checks:
            print(f"  [{'ok ' if ok else 'FAIL'}] {label}")
            if not ok:
                failures.append(f"d={d}: {label}")

        print(f"\n  per-ancilla CNOT order (offsets from the ancilla):")
        for ancilla in sorted(meas, key=lambda q: meas[q]):
            ax, ay = meas[ancilla]
            offsets = [(data[q][0] - ax, data[q][1] - ay)
                       for q in order[ancilla]]
            kind = "X" if ancilla in x_type else "Z"
            print(f"    anc {ancilla:3d} at ({ax:2d},{ay:2d})  {kind}-type  "
                  f"w={len(offsets)}  order={offsets}")
        print()

    if failures:
        print("FAILED invariants:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("All invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
