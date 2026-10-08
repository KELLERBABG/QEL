"""Deterministic shots and a reference decoder, so two decoders meet identical inputs.

**Why this exists.** During the failed effort, "before" and "after" numbers were taken at
different seeds and treated as comparable. They are not: at these error rates a single
seed swings the count by more than most fixes change it. A 400-shot sample at one seed
read as "2 errors vs 0 -- essentially solved"; the multi-seed 2000-shot measurement was
**7.2x**. The lesson is not "use more shots", it is **fix the inputs and the statistics
before comparing anything**.

This module hands out the same shots to every decoder and reports means with spread, so a
difference between two decoders cannot be sampling noise.

The reference is PyMatching. It stays a *comparison* oracle here, never the thing under
test -- keeping it in place is deliberate, because an oracle you have replaced is no
longer an oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

import numpy as np

try:
    import stim

    HAVE_STIM = True
except ImportError:  # pragma: no cover
    stim = None
    HAVE_STIM = False


DEFAULT_SEEDS = (3, 7, 9, 11, 13)
DEFAULT_SHOTS = 2000


@dataclass
class BenchmarkResult:
    """Accuracy of one decoder against the reference over several seeds."""

    label: str
    distance: int
    noise: float
    shots_per_seed: int
    per_seed: list[tuple[int, int, int]] = field(default_factory=list)
    #: (seed, decoder_errors, reference_errors)

    @property
    def seeds(self) -> int:
        return len(self.per_seed)

    @property
    def mean_decoder(self) -> float:
        return (sum(d for _s, d, _r in self.per_seed) / self.seeds
                if self.seeds else float("nan"))

    @property
    def mean_reference(self) -> float:
        return (sum(r for _s, _d, r in self.per_seed) / self.seeds
                if self.seeds else float("nan"))

    @property
    def decoder_rate(self) -> float:
        return (self.mean_decoder / self.shots_per_seed if self.seeds
                else float("nan"))

    @property
    def reference_rate(self) -> float:
        return (self.mean_reference / self.shots_per_seed if self.seeds
                else float("nan"))

    @property
    def ratio(self) -> float:
        """Decoder error rate over the reference's.

        ``inf`` when the reference made **zero** errors: a ratio against zero is not a
        number, and printing one would overstate the gap. At small shot counts this
        happens routinely -- the reference is clean while the decoder is not -- so the
        report names it rather than dividing.
        """
        if not self.seeds:
            return float("nan")
        if self.mean_reference <= 0:
            return float("inf")
        return self.mean_decoder / self.mean_reference

    @property
    def reference_is_clean(self) -> bool:
        return bool(self.seeds and self.mean_reference <= 0)

    def beats_physical_rate(self, physical: float | None = None) -> bool:
        """Whether the rate is below the physical error rate.

        A decoder above the physical rate cannot demonstrate any suppression, so no
        threshold is recoverable from it. This is the gate that matters for the threshold
        claim, and it is separate from "is it competitive with the reference".
        """
        limit = self.noise if physical is None else physical
        return bool(self.seeds and self.decoder_rate < limit)

    def report(self) -> str:
        plural = "seed" if self.seeds == 1 else "seeds"
        if self.reference_is_clean:
            ratio_line = ("  ratio     n/a -- the reference made 0 errors at this "
                          "sample size")
        else:
            ratio_line = f"  ratio     {self.ratio:.2f}x"
        lines = [
            f"{self.label}: d={self.distance} p={self.noise} "
            f"{self.shots_per_seed} shots x {self.seeds} {plural}",
            f"  decoder   mean {self.mean_decoder:8.1f}  rate {self.decoder_rate:.5f}",
            f"  reference mean {self.mean_reference:8.1f}  rate "
            f"{self.reference_rate:.5f}",
            ratio_line,
            f"  per seed (seed, decoder, reference): {self.per_seed}",
            f"  below physical rate ({self.noise})? "
            f"{'yes' if self.beats_physical_rate() else 'NO'}",
        ]
        if self.reference_is_clean:
            lines.append(
                "  NOTE: the reference is clean here, so this sample size cannot "
                "resolve the gap.\n        Use more shots, or read the d=3 p=0.003 "
                "multi-seed figure instead.")
        return "\n".join(lines)


def reference_decoder(distance: int, noise: float, rounds: int | None = None):
    """PyMatching as the comparison oracle. Not the thing under test."""
    if not HAVE_STIM:
        raise RuntimeError("needs stim")
    from pymatching import Matching

    rounds = distance if rounds is None else rounds
    circuit = stim.Circuit.generated(
        "surface_code:rotated_memory_z", distance=distance, rounds=rounds,
        after_clifford_depolarization=noise)
    dem = circuit.detector_error_model(decompose_errors=True)
    matching = Matching.from_detector_error_model(dem)
    return circuit, dem, matching


def benchmark(decoder: Callable, distance: int = 3, noise: float = 0.003,
              shots: int = DEFAULT_SHOTS, seeds: Iterable[int] = DEFAULT_SEEDS,
              rounds: int | None = None, label: str = "decoder") -> BenchmarkResult:
    """Run ``decoder`` and the reference over identical shots, several seeds.

    ``decoder(dem, detection_events) -> bool``: given the DEM and one shot's detection
    events (an array of detector indices), return whether it predicts the observable
    should be flipped. Keeping the interface this narrow means any formulation can be
    measured -- matching, union-find, or something else -- without the harness knowing
    how it works.

    Both decoders see the **same sampled shots**, and the reference is scored on those
    shots rather than trusted from a previous run.
    """
    circuit, dem, matching = reference_decoder(distance, noise, rounds)
    result = BenchmarkResult(label=label, distance=distance, noise=noise,
                             shots_per_seed=shots)

    for seed in seeds:
        sampler = circuit.compile_detector_sampler(seed=seed)
        detection, observables = sampler.sample(shots, separate_observables=True)
        truth = observables[:, 0].astype(bool)

        reference = matching.decode_batch(detection)[:, 0].astype(bool)
        reference_errors = int(np.sum(reference != truth))

        decoder_errors = 0
        for shot in range(shots):
            events = np.flatnonzero(detection[shot])
            predicted = bool(decoder(dem, events))
            if predicted != bool(truth[shot]):
                decoder_errors += 1

        result.per_seed.append((int(seed), decoder_errors, reference_errors))

    return result


__all__ = [
    "BenchmarkResult",
    "benchmark",
    "reference_decoder",
    "DEFAULT_SEEDS",
    "DEFAULT_SHOTS",
]
