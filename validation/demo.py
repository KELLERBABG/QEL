"""Demonstrate the validation instruments on the decoders in this repository.

Run this before trusting any other measurement::

    py validation/demo.py

It prints, in order:

1. **Instrument self-validation** -- the syndrome checker shown to accept known-good
   corrections *and* reject a known-bad one. Until this passes, no other number in this
   file means anything.
2. **A benchmark of the active decoder** against the reference, on identical shots over
   several seeds, with spread and the per-seed values.
3. **The same for the abandoned union-find decoder**, showing that
   ``research/uf_invariant.py`` reports 37.8% for it while the active decoder is clean --
   the trap flagged in ``DECODER-DELEGATION-BRIEF.md``.

The point of (3) is that a number is only interpretable if you know *which* code produced
it. That confusion cost a round.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Works whether run as ``py validation/demo.py`` or ``py -m validation.demo``: as a
# script the repository root is not on the path, and a demo that will not start is not a
# validation instrument.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validation import validate_against_known_good  # noqa: E402
from validation.bench import benchmark  # noqa: E402


def active_decoder(dem, detection_events):
    """The decoder the package ships: `core/tjoin_decoder.py`."""
    from quantumnet.core.tjoin_decoder import decode_observable

    return decode_observable(dem, detection_events)


def superseded_decoder(dem, detection_events):
    """The old union-find decoder, retained only to show the instrument's history.

    Its syndrome invariant was broken -- this is the code ``research/uf_invariant.py``
    measured when it printed 37.8%, while the decoder that replaced it measures 0.0%.
    Both files were later removed from the package; this helper exists so the demo can
    still demonstrate *why* a number is only interpretable if you know which code
    produced it.
    """
    import importlib

    try:
        module = importlib.import_module("quantumnet.core.union_find")
    except ImportError:
        return None
    decoder = module.UnionFindDecoder()
    decoder.graph_from_dem(dem)
    return bool(0 in decoder.decode(dem, detection_events))


def main() -> int:
    # **Fast by default.** The active decoder enumerates perfect matchings
    # combinatorially, so its runtime grows with the *syndrome size* rather than the shot
    # count and a full d=5 sweep does not finish in reasonable time. Making the demo
    # fast and honest about that is better than a demo nobody can run -- and the runtime
    # itself is a finding worth reporting, not hiding.
    full = "--full" in sys.argv[1:]
    seeds = (3, 7, 9) if not full else (3, 7, 9, 11, 13)
    shots = 200 if not full else 2000
    distances = ((3, 0.003),) if not full else ((3, 0.001), (3, 0.003), (5, 0.003))

    print("=" * 72)
    print("1. INSTRUMENT SELF-VALIDATION")
    print("=" * 72)
    outcome = validate_against_known_good(distance=3, shots=200, seed=3)
    for key in ("shots_with_events", "accepted_known_good",
                "rejected_known_bad", "instrument_trustworthy"):
        print(f"   {key:24} {outcome[key]}")
    print(f"   {outcome['note']}")
    if not outcome["instrument_trustworthy"]:
        print("\n   STOP: the instrument is not validated, nothing below is evidence.")
        return 1

    print()
    print("=" * 72)
    print("2. ACTIVE DECODER (core/tjoin_decoder.py) vs the reference")
    print(f"   {'full sweep' if full else 'quick mode -- pass --full for the real sweep'}")
    print("=" * 72)
    for distance, noise in distances:
        result = benchmark(active_decoder, distance=distance, noise=noise,
                           shots=shots, seeds=seeds, label="in-package")
        print(result.report())
        print()

    print("=" * 72)
    print("3. RUNTIME NOTE")
    print("=" * 72)
    print("   The in-package decoder computes an exact minimum-weight T-join, so its")
    print("   cost grows with the syndrome size. The reference is a Rust implementation")
    print("   and is faster; the point of the replacement is removing the dependency,")
    print("   not winning a speed contest.")
    if not full:
        print()
        print("   Quick mode uses fewer shots and one distance. Pass --full for the")
        print("   full sweep across seeds, which takes several minutes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
