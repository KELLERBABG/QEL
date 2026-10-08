"""Decoder-agnostic validation instruments.

Why this package exists
-----------------------
Twelve rounds of decoder work failed, and the largest single cause was **the measuring
instrument, not the code**. Five separate times a diagnostic reported a defect that did
not exist, or an absence of output that was read as a result:

* a checker compared the correction's odd-degree set against the boundary, which is
  *legitimately* odd, and reported **57.4% failures** that were not failures;
* a script silently unpacked a stale tuple length, printed **nothing**, and the blank
  output was treated as a measurement;
* three consecutive "fixes" changed the headline numbers by exactly nothing, because the
  edit was not executing.

So these instruments are written to be **trustworthy before they are used**, and each one
is tested against inputs whose answers are already known:

* :mod:`validation.validators` -- does a correction reproduce the observed syndrome?
  The property no decoder in this package checked until round 5, by which point an
  earlier generation was **100% wrong** on it while still producing plausible error
  rates. Its own tests include known-good and known-bad corrections, so a passing
  instrument is distinguishable from a blind one.
* :mod:`validation.bench` -- deterministic shots and a reference decoder, so two decoders
  can be compared on **identical inputs**. Changing the seed between "before" and "after"
  invalidates the comparison, and that happened here.

Both are independent of how a decoder is implemented. Nothing in this package imports the
in-package decoders.
"""

from .validators import (
    CorrectionCheck,
    check_correction,
    syndrome_of_correction,
    validate_against_known_good,
)
from .bench import BenchmarkResult, benchmark, reference_decoder

__all__ = [
    "CorrectionCheck",
    "check_correction",
    "syndrome_of_correction",
    "validate_against_known_good",
    "BenchmarkResult",
    "benchmark",
    "reference_decoder",
]
