# `validation/` — decoder-agnostic validation instruments

**What this is:** a small, tested toolkit for checking a quantum error-correction decoder
and benchmarking it honestly. It is independent of how a decoder is implemented — nothing
here imports the decoders in `src/quantumnet/core/`.

**Why it exists:** twelve rounds of decoder work in this repository failed, and the
largest single cause was *the measuring instrument, not the code*. Five separate times a
diagnostic reported a defect that did not exist, or an absence of output that was read as
a result. The instruments here are therefore designed to be **trustworthy before they are
used**, and each is tested against inputs whose answers are known in advance.

> **This folder is the instrument, not the workbench.** Do not grow it into an
> experiment area, and do not put decoder code in it — its value is that it stays
> independent of what it measures.

---

## The two instruments

### 1. The syndrome invariant — `validation/validators.py`

**The property:** a decoder's correction must reproduce the observed detection events.
XOR the detectors touched by the correction's edges; the result must equal the events.

This went unchecked in this package until round 5, by which point an earlier decoder was
**100% wrong** on it while still producing plausible error rates. That is the failure it
exists to prevent: a decoder that looks like it works.

```python
from validation import check_correction, rate_over_shots

check = check_correction([6, 12], [(6, 12)])
print(check.valid, check.describe())
# -> True valid: explains 2 event(s)

# A rate over several shots. Refuses to report 0% for an empty sample.
result = rate_over_shots([(events, correction) for events, correction in pairs])
print(result["violation_rate"], result["shot_count"])
```

A correction is a set of edges: pairs of detector ids, or `(detector, BOUNDARY)`. That is
the natural output of a matching decoder and trivial to produce from any other
formulation, so the instrument never constrains your internals.

### 2. The benchmark — `validation/bench.py`

**The problem it solves:** "before" and "after" numbers taken at *different seeds* are not
comparable. At these error rates one seed swings the count by more than most fixes change
it. A 400-shot sample at a single seed once read as *"2 errors vs 0 — essentially solved"*;
the multi-seed 2000-shot measurement was **7.2×**.

```python
from validation.bench import benchmark

def my_decoder(dem, detection_events) -> bool:
    """Given a DEM and one shot's events, predict whether the observable flips."""
    ...

result = benchmark(my_decoder, distance=3, noise=0.003, shots=2000,
                   seeds=(3, 7, 9, 11, 13), label="mine")
print(result.report())
```

```
mine: d=3 p=0.003 2000 shots x 5 seeds
  decoder   mean     28.8  rate 0.01440
  reference mean      4.0  rate 0.00200
  ratio     7.20x
  per seed (seed, decoder, reference): [(3, 21, 4), (7, 30, 5), ...]
  below physical rate (0.003)? NO
```

Both decoders see the **same sampled shots**, and the reference is scored on those shots
rather than trusted from a previous run. `beats_physical_rate()` is separate from `ratio`
because they answer different questions: a decoder can be close to the reference and still
be above the physical rate, which means **no threshold is recoverable from it**.

---

## Run the self-check first

```powershell
py validation\demo.py
```

It prints, in order:

1. **Instrument self-validation** — the checker shown to accept known-good corrections
   *and* reject a known-bad one. **Until this passes, no other number means anything.**
   An instrument only ever shown to accept is indistinguishable from one that always
   accepts.
2. A benchmark of the **in-package** decoder against the reference.
3. A note that the decoder is exact and therefore slower than the Rust reference.

The instruments are decoder-agnostic: nothing in this folder imports the decoders in
`src/`, so they measure a decoder without depending on it. That independence is what lets
the same syndrome check be pointed at a new implementation, and it is why the folder is
kept as the instrument rather than the workbench.

> **Known issue, recorded rather than hidden:** step 2 is slow at d=5, because the active
> decoder enumerates perfect matchings combinatorially. Its runtime grows with the
> syndrome size, not with the shot count. If the demo appears to hang, that is why — it is
> a real property of the decoder under test, not a fault in the instrument. For quick
> iteration, benchmark at `shots=200` on a single seed, then do the full run once.

---

## Rules these instruments enforce, and the failures behind them

| rule | the failure it prevents |
|---|---|
| **Every check is validated both ways** | a checker compared the correction against the *boundary*, which is legitimately odd, and reported **57.4% failures that did not exist** |
| **A rate over zero shots is `None`, never 0%** | a script silently unpacked a stale tuple length, printed **nothing**, and the blank was read as a result |
| **Abstaining is not credited** | a decoder returning *empty* corrections scored **better** than a working one, because "no flip" is right ~97% of the time |
| **Rates come with shot count and per-seed values** | single-seed numbers were treated as comparable across changes |
| **The reference stays a reference** | an oracle you have replaced is no longer an oracle |
| **Correctness before quality** | four rounds went into accuracy on a decoder that was **100% invalid** |

## Tests

```powershell
py -m pytest tests/test_validation -q
```

25 tests, all fast. They test the **ruler**, not a decoder — including that the instrument
can *reject*, that an empty sample yields `None` rather than `0.0`, that "never flip"
is not credited, and that `graph_from_dem` puts the boundary first (`-1` sorts first, so
on a boundary edge `edge.a` **is** the boundary — a trap that silently turned a fix into a
no-op during the failed effort).
