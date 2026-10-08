# Delegation Brief: Replace the PyMatching Dependency with an In-Package Decoder

**Audience:** an agent taking over this task.
**Goal:** make `quantumnet`'s surface-code threshold independent of `pymatching`, by
implementing a decoder in-package that matches PyMatching's accuracy closely enough to
recover the same threshold.

**Read this whole file before writing any code.** It is long on purpose. A previous
attempt (mine) spent twelve rounds and ~50 changes on this exact task and failed. The
failure was *not* conceptual — Union-Find and matching decoders are solved problems —
it was process. Almost everything below is a record of a specific way I wasted a round.

---

## 1. What exists right now, measured

Every number here was produced by a command in §8, not remembered.

| fact | value |
|---|---|
| Test suite | **862 passed**, 57 modules, 0 import failures |
| In-package decoder error rate, d=3, p=0.003 | **28.8** per 2000 shots (multi-seed mean) |
| PyMatching on identical shots | **4.0** per 2000 |
| Ratio | **7.2x worse** |
| In-package rate, d=5, p=0.003 | **79/2000 = 3.95%** |
| Physical error rate at that point | 0.3% |
| Threshold recoverable from in-package decoder? | **No** — its rate exceeds the physical rate |
| Is it wired into `logical_error_rate`? | **No**, deliberately |
| Fusion order (separate item, already done) | optimal, verified vs exhaustive search |

**Bottom line:** the decoder is *correct but not accurate*. It is unusable for the
threshold as it stands. Partial credit does not count here.

### Correctness is already met — do not regress it

Measured on the **active** decoder (`tjoin.py`), 132 shots with detection events at d=3,
p=0.003:

```
syndrome-invariance violations: 0 / 132  =  0.0%
```

Meaning: **every correction reproduces the observed detection events.** Gate C1 below is
therefore already satisfied at d=3. Preserve it — add a regression test if there is not
one, and re-measure after every change. An earlier generation of this decoder was
**100% wrong** on this property while still producing plausible error rates, which is
precisely how a decoder can look like it works and be meaningless.

> **Trap — read this before running the diagnostics.** `research/uf_invariant.py`
> currently measures the **abandoned union-find decoder** in `core/union_find.py`,
> and reports **37.8% violations**. That number is *not* the active decoder's. The
> active decoder is clean at 0.0%. **Retarget that script at your decoder before
> trusting it**, or you will spend a round chasing a defect in code you are not using.
> This exact confusion is why P1 exists in §5.

### Files

| path | what it is |
|---|---|
| `src/quantumnet/core/tjoin.py` | **the active decoder.** T-join construction + matching. Read it first. |
| `src/quantumnet/core/union_find.py` | earlier Union-Find attempt, abandoned. Still imported; do not assume it works. |
| `src/quantumnet/core/dem_decoder.py` | earlier greedy DEM decoder, superseded |
| `src/quantumnet/core/logical.py` | `logical_error_rate(..., matcher=...)`, `minimum_weight_decoder` |
| `src/quantumnet/core/surface_code.py` | `_dem_components`, `VERIFIED_SITES`, `dem_matching_graph` |
| `research/uf_invariant.py` | **the correctness diagnostic.** Run it after every change. |
| `research/uf_weight_gap.py` | compares correction weights against the reference |
| `research/uf_edge_diff.py` | compares chosen edges against the reference |
| `QEL-MASTER-PLAN.md` §3.12–3.24 | the full narrative record of the failure |

---

## 2. The single most important insight

**The reference's correction IS a matched edge set.** Its observable is the XOR of the
labels of those edges, each counted **once**.

The failed implementation instead **routes paths** and XORs labels *along* them. A path
crossing a labelled detector pair contributes that label **once per traversal**. These
are different quantities, and no amount of tuning the edge-label convention reconciles
them.

This is why three attempts to "adopt the reference's convention" all measured *worse*:

| attempt | d=3 p=0.003 errors / 2000 |
|---|---|
| **unmerged graph, per-mechanism labels, path-based (current)** | **30** |
| merged graph, ANY labels, endpoint-label matching | 193 |
| merged graph, XOR labels | 130 |
| unmerged graph, pair-level ANY labels | 128 |

**Requirement, therefore, in one sentence:** implement a minimum-weight matching whose
**output is the set of matched edges on the merged graph**, and take observables from
those edges.

**Corollary — do not do this:** enumerating perfect matchings over the **metric
closure** (precomputed pairwise shortest-path distances) cannot produce that output. It
commits to pairwise routes rather than to a set of edges. That is what the current
`pair_minimum_weight` does, and it is the structural reason the current decoder is 7.2x
off rather than merely suboptimal.

---

## 3. Domain facts that are verified — do not rediscover these

Each was established by direct test against `stim`/PyMatching. They cost me rounds.

### Surface code layout
- Rotated code. Data qubits at **(odd, odd)** coordinates; ancillas at **(even, even)**.
- `d²` data qubits, `d²-1` ancillas. Check weights ∈ {2, 4}.
- **X-type ancillas are CNOT controls.**
- `VERIFIED_SITES` in `surface_code.py` pins the ancilla layout for d ∈ {3,5,7,9}. Other
  distances are refused. **Do not extrapolate the layout to untested distances.**

### CNOT layer rule (verified against stim at d = 3, 5, 7, 9, 11)
- X-type ancilla order: `(1,1) → (-1,1) → (1,-1) → (-1,-1)`
- Z-type ancilla order: `(1,1) → (1,-1) → (-1,1) → (-1,-1)`
- The layer is a property of the **offset kind**, *not* of qubit availability. Getting
  this backwards is a silent error that still produces plausible numbers.

### Detector error model
- With `decompose_errors=True`, stim writes e.g. `error(p) D1 D5 ^ D4`.
- **`^` separates components.** Each component is independently graphlike — verified: 0
  of 556/3706/11830 components exceeded 2 detectors at d=3/5/7.
- A component with **1** detector is a **boundary edge**.
- `_dem_components(inst)` in `surface_code.py` already splits on `target.is_separator()`.
  Use it; do not re-derive.

### Boundary node canonicalisation — a bug factory
- Boundary is represented as `-1`.
- Edges are canonicalised as `(min, max)`, and `-1` sorts **first**, so **the boundary is
  always `edge.a`**.
- Consequently `find(edge.a)` on a boundary edge returns the *boundary's* root, not the
  detector's. This silently produced a no-op in one attempt and a persistent
  explain-nothing loop in another.
- **Always key on the non-boundary endpoint.** Consider a `is_boundary(edge)` helper and
  use it everywhere rather than comparing endpoints inline.

### Weights
- `-log W` is the additive route weight, **not** `-log F`. Proven by brute force over
  554 graphs (7 of 554 differ), for Werner states `W = (4F-1)/3`.
- **BUT** for DEM decoding, PyMatching's edge weights come from the DEM probabilities
  and agree with `-log p` to within 0.2%. Verified in both directions. So for *this*
  task, `-log p` is right; the `-log W` result matters for the link-level routing code,
  not the decoder.

### The reference's graph
- PyMatching **merges** mechanisms sharing a detector pair: 78 edges at d=3, exactly the
  number of distinct pairs.
- Its observable label uses **ANY**: an edge is observable-carrying when *any* of its
  mechanisms is. Confirmed against `fault_ids`. That is **20** edges at d=3.
- XOR gives **12**. The two conventions disagree on **16 of 78** pairs.
- Reading it: `Matching.get_edge_data(a, b)` and `get_boundary_edge_data(a)` return dicts
  with `weight`, `fault_ids`, `error_probability`.
- Extracting its chosen edges: `Matching.decode_to_edges_array(syndrome_row)` — needs a
  **1-D boolean/uint8 array**, not the 2-D `(shots, detectors)` batch. Passing the batch
  raises. `decode_batch` takes the array and returns `(shots, observables)`.

### Threshold reference point
- Measured threshold with PyMatching is p ≈ 0.006–0.008, consistent with published
  surface-code thresholds. That is the number to reproduce.

---

## 4. What I tried and why each failed

Do not repeat these. Each measured worse than what it replaced.

| # | attempt | outcome |
|---|---|---|
| 1 | Union-Find peeling seeded from **leaf degree** (`degree % 2 == 1`) | **100% of corrections failed to reproduce the syndrome.** Every leaf is odd by definition, so every path was stripped and the correction came out `[]` |
| 2 | Fixed seeding to **syndrome parity** | 100% → 37.8% invalid. Kept |
| 3 | Marked the **boundary node odd** | 75.0% invalid (worse); reverted. Then restoring it gave 54%; the boundary *should* be odd, and the real fault was elsewhere |
| 4 | Rewrote `_grow` as **radius growth** (merging only unfinished clusters) | **Changed the headline numbers by nothing.** The growth order was never the problem |
| 5 | Grouped grown edges by **current** root (`find`) instead of stored root | No change. Kept because the staleness is real, not because it helped |
| 6 | Stripped leaves from a **spanning forest** instead of the cyclic graph | No change |
| 7 | Keyed `boundary_of` on the **non-boundary** endpoint | Correct, but could not help: the growth phase was unioning along boundary edges, destroying per-cluster parity |
| 8 | **Abandoned peeling entirely**; wrote the correction as a T-join (pair events, route each pair) | **37.8% → 0.0% invalid.** The one genuine breakthrough. Correctness came from changing the *frame*, not from another patch |
| 9 | **Merged** parallel mechanisms, observables **XOR'd** | 130 errors. XOR cancels when an even number of mechanisms carry the observable |
| 10 | **Unmerged** the graph (556 edges), per-mechanism labels | **14–30 errors. Best result achieved.** Kept |
| 11 | **Greedy** nearest-neighbour pairing | 152 errors. Valid but far too heavy |
| 12 | **Minimum-weight** pairing by enumerating perfect matchings | 58 errors. Real improvement, still 38x off |
| 13 | Merged graph + ANY labels + endpoint-label matching | 193. Worse |
| 14 | Unmerged graph + pair-level ANY labels | 128. Worse |

**Attempt 8 is the lesson:** the fix that worked was not another correction to the
algorithm. It was rewriting the answer in terms of its *definition*. When you are 37.8%
invalid and each patch does nothing, stop patching and change the representation.

---

## 5. Process rules — the actual failure was here

**Five separate times, the defect was in my measuring instrument, not the code.** When
your ruler is wrong that often, no measurement is trustworthy, and you cannot debug by
measurement. These rules are not stylistic.

### P1 — Test the instrument before you trust it
Before using any checker or diagnostic, run it against an input whose answer you already
know. Example of the failure: a checker flagged the boundary as a "violation" because a
route ending at the code edge legitimately contributes odd degree there. It reported
**57.4% failures** that did not exist. **A checker that has never been validated on a
known-correct input is not evidence.**

### P2 — Never accept a silently empty diagnostic
A script unpacked a 6-tuple that had become a 7-tuple, printed **nothing**, and I read the
blank output as a result for one measurement. If a diagnostic produces no output, that is
a **failure**, not a finding. Make every diagnostic assert it processed a non-zero number
of items and print that count.

### P3 — Verify your edit is actually live before and after
Three consecutive "fixes" changed the headline numbers by exactly nothing. That is the
signature of an edit that is not executing. After every change, print the loaded module's
hash or a sentinel from the changed function, and confirm the numbers *move*. If a
measurement is bit-identical after a substantive change, suspect the plumbing first.

### P4 — Never report a single-seed number
A 400-shot sample at one seed showed "2 errors vs the reference's 0", which reads as
solved. The multi-seed 2000-shot measurement shows **7.2x**. At these error rates small
samples are noise. Use **≥ 2000 shots × ≥ 5 seeds**, and report the **mean and spread**.
Several figures in `QEL-MASTER-PLAN.md` §3.17–3.20 are single-seed and should be treated
as one sample each.

### P5 — State the claim before measuring, and pick a discriminator
Before running a measurement, write down the claim it tests and what result would
*refute* it. Example of doing this well: to decide whether the peel or the growth phase
was at fault, feed the peel the **full edge set** — where a correct answer provably
exists — and require 0% violations. It scored 51.9%, which located the fault
immediately. That one test replaced two rounds of guessing.

### P6 — Verify against an independent oracle, or brute force
PyMatching is installed and is the oracle for this task. For small instances, exhaustive
search is the oracle (that is how the fusion order was verified optimal). **Nothing is
"done" because a file exists or a function returns.** Every self-claim needs a command.

### P7 — Compare on identical inputs, pre and post
Changing the seed between "before" and "after" invalidates the comparison. Generate the
shots once and decode them with both decoders. `compare_to_reference` already does this —
use it rather than writing a new harness.

### P8 — Record negative results
"Radius growth changed nothing" is worth as much as a fix, because it removes a
hypothesis. Write it down. A decade of these is what §4 is.

---

## 6. What to do — concrete plan

### Step 0: do not skip this
**Read the algorithm properly before writing decoder code.** Do not implement from
memory or from this brief's summary. The failed attempt's root cause was reconstructing a
known algorithm by reasoning. Sources:

- Delfosse & Nickerson, *Almost-linear time decoding algorithm for topological codes*,
  arXiv:1709.06218 — Union-Find (simpler; start here)
- Kolmogorov, *Blossom V*, Math. Prog. Comp. (2009) — minimum-cost perfect matching
- Higgott & Gidney, *Sparse Blossom*, arXiv:2303.15933 — how PyMatching does it
- `stim`'s detector-error-model documentation for the DEM semantics in §3

**Acceptance test for "read it properly":** write out the algorithm step by step, with
data structures, **without gaps**. If you reach a step whose details you are inferring,
you have not read it — go back. If you cannot do this, do not proceed to Step 2.

### Step 1: build the validators first, before the decoder
Write these and prove them on known-correct input (§7, gates C1–C3). **Do not write a
decoder until the instruments are trustworthy.** This inverts the order I used, and that
inversion is the point.

### Step 2: choose one of two viable routes

**Route A — Union-Find, done correctly.** Simpler to get right than Blossom. The three
parts that must all be present:
1. **Radius growth**: advance all clusters together by increasing radius; stop a cluster
   the moment it is valid. (My version walked the edge list once — not radius growth.)
2. **Validity**: a cluster is valid when its event count is even **or** it touches the
   boundary.
3. **Peeling**: leaf-stripping seeded from **syndrome parity**, run to convergence.
   Odd-parity vertices, including the boundary, are never stripped.

Note: Union-Find's growth produces a spanning forest, and its *peeling* needs that forest,
not the cyclic grown graph. My attempt to strip leaves from the cyclic graph left a 2-core
whose edges need not lie on any valid syndrome path.

**Route B — Sparse Blossom on the merged graph.** Higher ceiling, closer to the
reference. Requires a real matching implementation (alternating trees, blossom
contraction/expansion, augmenting paths). **The output must be the matched edge set**,
and observables must come from those edges — see §2.

**Recommendation: Route A first**, then Route B only if A plateaus short of the gates.
Union-Find at the boundary-node level has fewer places to be subtly wrong.

### Step 3: verify against the gates at every step, not at the end

| gate | requirement |
|---|---|
| **C1** | Syndrome violation rate on corrections is **0.0%** — *already met by `tjoin.py` at d=3; preserve it and extend to d=5* |
| **C2** | Chosen edges overlap the reference's edge set on **≥ 90%** of disagreeing shots |
| **C3** | Error rate within **2x** of PyMatching at d=3, p=0.003 |
| **C4** | `p_L` at d=5, p=0.003 is **below the physical rate** (0.003) |
| **C5** | Suite passes; 0 import failures |
| **C6** | Threshold recovered in the range **p ≈ 0.006–0.008** |

C1 and C2 are **correctness** gates and must be met before optimising quality. This is the
mistake that defined the whole failed effort: I spent four rounds optimising accuracy on a
decoder that was **100% invalid**. Validity first, always.

---

## 7. Commands

```powershell
# CORRECTNESS diagnostic.
# WARNING: as shipped this targets the ABANDONED union-find decoder and prints 37.8%.
# The ACTIVE decoder (tjoin.py) measures 0.0%. Retarget this at your decoder first.
py research\uf_invariant.py

# accuracy vs the reference, identical shots (use this, not a new harness)
py -c "from quantumnet.core.tjoin import compare_to_reference; print(compare_to_reference(3,0.003,shots=2000,seed=7))"

# multi-seed, the only honest way to report a rate
py -c "
from quantumnet.core.tjoin import compare_to_reference
import statistics
ref=[]; mine=[]
for s in (3,7,9,11,13):
    r=compare_to_reference(3,0.003,shots=2000,seed=s); ref.append(r['reference_errors']); mine.append(r['tjoin_errors'])
print(f'reference {statistics.mean(ref):.1f}  mine {statistics.mean(mine):.1f}')"

# weight and edge-set comparison against the reference
py research\uf_weight_gap.py
py research\uf_edge_diff.py

# suite and import audit
py -m pytest -q
py scripts\audit_imports.py
```

### Tests to write as you go
- Every defect in §4 gets a **regression test naming the failure** (the suite already does
  this in places; follow that style).
- A test asserting C1 (0% syndrome violations) over a fixed shot sample.
- A test asserting that a **single detection event on a detector with a direct boundary
  edge** yields a non-empty correction. That specific case was empty for four rounds.
- A test asserting the correction's boundary **equals** the observed syndrome, on a fixed
  sample — the invariant no decoder in this package checked until round 5.

---

## 8. Definition of done

The task is complete only when **all** hold, each with a command behind it:

1. C1–C6 pass at d=3 **and** d=5, multi-seed.
2. The in-package decoder is reachable on the threshold path with **no PyMatching
   import** on that route. The existing switch is `matcher=`: `"auto"` prefers
   PyMatching and falls back to the in-package matcher; **`"greedy"` forces the
   in-package one** (see `minimum_weight_decoder` in `logical.py`). Add your decoder as
   a third value and point the threshold work at it — do not silently change what
   `"auto"` does.
3. A threshold is recovered from the in-package decoder, in the range p ≈ 0.006–0.008.
4. `pymatching` is **optional** for the test suite: the suite passes with it uninstalled
   except for tests explicitly marked as reference comparisons.
5. The suite passes; 0 import failures; no network access in tests.
6. `QEL-MASTER-PLAN.md` records the final measured numbers and the commands that
   produced them.

**If you cannot reach C3, stop and report.** Do not wire a decoder that is 7x off into
`logical_error_rate` to make the dependency look removed. A documented dependency is
honest; a silently-worse threshold is not. The current state deliberately keeps
PyMatching on the threshold path for exactly this reason.

---

## 9. Anti-patterns — the condensed list

1. **Do not** optimise accuracy before correctness is proven (C1 before C3).
2. **Do not** adopt the reference's *conventions* without its *algorithm* (§2).
3. **Do not** accumulate observables along **paths** when the labels are per-edge (§2).
4. **Do not** merge parallel mechanisms before matching — merge first, then match, and
   the label is `ANY`, not `XOR` (§3).
5. **Do not** enumerate perfect matchings over the **metric closure** and call it a
   minimum-weight T-join (§2).
6. **Do not** rely on `edge.a` for anything meaningful on a boundary edge — `-1` sorts
   first (§3).
7. **Do not** trust a diagnostic you have not validated on known-correct input (P1).
8. **Do not** read empty diagnostic output as a result (P2).
9. **Do not** report single-seed numbers (P4).
10. **Do not** treat an identical measurement after a substantive edit as a finding —
    check the edit is live (P3).
11. **Do not** patch a heuristic that is failing structurally; change the representation
    (attempt 8, §4).
12. **Do not** declare done because a file exists, a function returns, or a test passes
    that you wrote to match your own output.

---

## 10. Context you may need, and one thing you should not inherit

**The `-log W` vs `-log F` distinction** (Werner states, `W = (4F-1)/3`) is settled and
belongs to the link-level routing code. For DEM decoding, `-log p` is correct. Do not
re-litigate it.

**`research/` and `.freebuff/` are deliberately untracked** — the first for third-party
paper copyright, the second because it is local tool state.

**What not to inherit:** the belief that this is nearly done because the last change
almost worked. It is not nearly done. Seven defects were found and fixed and the decoder
is still 7.2x off, because the structural requirement in §2 was never implemented. Treat
the existing `tjoin.py` as **a source of verified facts and validators**, not as a
foundation to extend. The fastest path is likely a clean implementation of Route A or B
alongside it, verified against the same oracle, rather than more surgery on it.
