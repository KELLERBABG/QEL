# QEL: a quantum-network simulator built to be falsified

**Version 0.1.0 · Lukas Negenborn · Apache-2.0**

---

## Abstract

QEL is a simulator for quantum communication networks. It models the full path rather
than a link budget: density-matrix states under depolarising, dephasing and
amplitude-damping noise; distance-dependent fibre attenuation; memory relaxation on
T1 and T2; entanglement swapping in the Werner algebra; distillation; resource
contention; topology routing; repeater placement; and a rotated surface code with its
own exact decoder.

This document reports what the implementation reproduces from published work, what it
computes that is not a reproduction, and in as much detail as the positive results,
**what it gets wrong, what was retracted, and where it disagrees with its own sources.**

The two headline results are:

1. **An in-package surface-code decoder that removes the third-party matcher from the
   threshold path.** It computes an exact minimum-weight T-join and produces *identical*
   corrections to PyMatching on the circuits this package generates: the same edge set
   at the same total weight, on 4,359 of 4,359 shots at d=3 and d=5, recovering a
   threshold near p ≈ 0.007.
2. **A correction to a common approximation in fidelity-based routing.** Entanglement
   swapping multiplies the Werner parameter, so `-log W` is *exactly* additive and makes
   shortest-path search optimal rather than approximate. The widely used substitute
   `-log F` is not, and picks a strictly worse path about 1.3% of the time on random
   graphs.

**Scope, stated first because it governs every number below.** Nothing in this work has
been validated against physical hardware. These are simulator results and they do not
predict what hardware would achieve. Where a figure reproduces someone else's published
result it says so and cites it; where it is a property of this simulator it says that
instead. A modelled reach calibrated to a published experiment is a consistency check on
the model, not a measurement.

---

## 1. Introduction

Simulation of quantum networks has a specific failure mode that is worth naming at the
outset, because this work is organised around avoiding it: **a plausible number is
indistinguishable from a correct one.** A route selected with a slightly wrong weight, a
decoder that returns a correction not matching the observed syndrome, an estimator that
divides by the wrong count, each produces output of exactly the right shape. Nothing
crashes. The model has quietly become a different model.

The repository this document describes began in precisely that state. At the start of
the work the test suite did not run at all: a single stale import made 12 of 37 modules
unimportable, and the README advertised a test count the suite had never produced. The
planning documents that guided it contained a load-bearing mathematical error in the
routing weight.

What follows is therefore organised not by feature but by **evidence class**:

- results that **reproduce a published number** under the same estimators (§4);
- results that are **computations specific to this work** (§5), each with the verification
  method stated;
- results that are **negative or retracted** (§6), retained because they are the ones that
  tell a reader how much to trust the rest;
- **limits** (§7), stated as limits rather than as future work.

### 1.1 A note on method

Every quantitative claim in this document is traceable to a command in the repository.
The project maintains this as a rule rather than an aspiration, and the rule has teeth:
when a documented number and the code disagree, one of them is a bug and the build is
expected to say which.

The rule was adopted after it failed repeatedly. Over the course of development six
documented claims went stale: status rows for finished work, a README asserting 668
tests when the suite ran 1036, a website asserting 122. Each was correct when written and
each silently rotted. The response was not to re-read the prose more carefully (that had
already been tried) but to write `scripts/claim_audit.py`, which extracts every numeric
claim from a document and prints it beside what the repository currently measures. It
reports and refuses to decide: a tool that guessed which number was right would produce
exactly the confident-but-wrong output the rest of the project exists to avoid.

**Verification runs with `pymatching` blocked at the import system**, so any hidden use
of the reference becomes a hard error rather than a silent fallback:

```
HAVE_PYMATCHING = False,  pymatching in sys.modules: False
d=3 p=0.003: 4/2000    d=5: 1/2000    d=7: 0/2000    decoder='in-package'
```

---

## 2. System overview

The stack is layered, and the layering is load-bearing: nothing in routing, scheduling or
visualisation knows where a topology came from.

| Layer | Contents |
|---|---|
| **Core** | density-matrix states, gates, POVM measurement, noise channels, Clifford stabiliser tableau, discrete-event scheduler, multi-process nodes |
| **Hardware** | detector impairment models, Barrett–Kok double-heralded generation, explicit time-division multiplexing, latency accounting |
| **Protocols** | BB84 (incl. decoy state and a finite-key bound), E91, teleportation, superdense coding, swapping, BBPSSW/Deutsch/DEJMPS distillation, Shor and Steane codes |
| **Topology** | graphs, pluggable routing policies, schedules, resource contention, placement, multi-commodity routing, ASCII visualisation |
| **QEC** | rotated surface code, space-time detector model, exact T-join decoder, logical key rate |
| **Calibration** | library models checked against transcribed published datasets |
| **Interop** | native versioned schema, Ghost-Net bridge, a Graphviz subset, SeQUeNCe `RouterNetTopo` |

The dependency promise is `numpy` alone for the simulator core. `stim` is optional and
needed only by three surface-code modules; `pymatching` appears in **no** `src/` module
and is a comparison oracle in the test suite only.

---

## 3. Method

### 3.1 Density matrices throughout

Quantum states are density matrices, not state vectors, so mixedness and decoherence are
represented directly rather than modelled as an error probability attached to a pure
state. Decoherence is then a channel applied to a matrix, and fidelity is computed from
the matrix. This is more expensive than a state-vector simulator and it is the right
choice here because the quantities of interest, entanglement fidelity after a chain of
swaps and memory holds, are properties of mixed states.

A stabiliser tableau runs alongside for Clifford circuits, with measurement implemented
by GF(2) solving, so codes and distillation circuits can be simulated at sizes where a
density matrix would not fit.

### 3.2 Werner states for entanglement

A two-qubit entangled pair is represented by its Werner parameter `W = (4F-1)/3`, because
the Werner family is closed under the operations that matter here. A Bell-state
measurement followed by a swap multiplies the parameters of the two contributing pairs;
a memory hold contracts toward the maximally mixed state. Both operations are exact in
this representation, which is what makes §5.1 possible.

### 3.3 The surface code

A rotated surface code at distance `d` with `d²` data qubits and `d² - 1` ancillas
(weights 2 or 4). Data sit at (odd, odd) coordinates and ancillas at (even, even); X-type
ancillas are CNOT controls. The CNOT layer order was verified against `stim` at
d = 3, 5, 7, 9, 11 and is a property of the **offset kind**, not of qubit availability.
which matters, because a transposed layer order still produces a valid circuit with the
wrong connectivity, and therefore plausible wrong numbers.

**Layouts are pinned per distance.** `VERIFIED_SITES` fixes the ancilla layout for
d ∈ {3, 5, 7, 9} and any other distance is refused. A guessed layout passes a qubit-count
check and fails silently.

### 3.4 Detector error model and decoding

`stim` generates the noisy circuit and the decomposed detector error model. With
`decompose_errors=True` each mechanism is written as `^`-separated graphlike components,
verified: 0 of 556 / 3706 / 11830 components exceeded two detectors at d = 3 / 5 / 7.

The decoder computes an exact minimum-weight T-join on the merged graph: one edge per
distinct detector pair, parallel mechanisms combined by parity, with log-likelihood
weight `log((1-p)/p)`, and observables parsed **per component**. A correction is a set of
edges whose odd-degree vertices are exactly the detection events.

### 3.5 Measurement protocol used throughout

Reported error rates are **multi-seed**: at least five seeds and at least 2000 shots per
point for rates above 10⁻³. This is not a stylistic choice. A 400-shot single-seed sample
once read as "2 errors against the reference's 0, essentially solved" while the
multi-seed 2000-shot measurement was **7.2×** worse. At these rates a single seed swings
the count by more than most fixes change it.

---

## 4. Reproduction of published results

### 4.1 Decoy-state key rate: maximum secure distance

Ma, Qi, Zhao and Lo (*Phys. Rev. A* **72**, 012326, 2005,
[arXiv:quant-ph/0503005](https://arxiv.org/abs/quant-ph/0503005)) tabulate the maximum
secure distance of the vacuum+weak decoy method at the Gobby–Yuan–Shields parameters.
QEL implements the same estimators and the same `q = 1/2` asymptotic rate, so this is a
like-for-like comparison:

```
VALIDATED  (same quantity, same estimators)
  [OK  ] ma-vacuum-weak-gys
          published 140.55 km   qel 140.61 km   delta +0.06 km (+0.04%)
```

**A 60-metre difference on a 140 km figure.**

The infinite-decoy ceiling is scored as an **inequality, not an equality**:

```
UPPER BOUND (must fall below, and near)
  [OK  ] ma-asymptotic-gys
          published 142.05 km   qel 140.61 km   below the bound: true
```

A finite-decoy estimator *must* fall below the infinite-decoy limit. Scoring that as a
match would fail a correct model.

**Two comparisons are deliberately left unscored, and the reasons are recorded in the
tool.** The Boaron 421 km record is not scored because its protocol is 3-state time-bin
with a one-decoy finite-key bound, so comparing rates would measure the protocol
difference rather than the implementation. Their *loss budget* is comparable, since fibre loss
is a property of the fibre, and all five rows of their Table I agree within 0.5 dB.

### 4.2 Barrett–Kok double-heralded generation

The model follows Barrett and Kok (*Phys. Rev. A* **71**, 060310(R), 2005). Two published
properties are checked: the ideal success probability is exactly **1/2** at zero loss
(the protocol's stated upper limit), and the probability is **quadratic in detector
efficiency** (`p ∝ η²`) because both photons must survive and both must be detected.

The consequence matters when reading any rate it prints: **loss costs rate, not
fidelity.** A photon that fails to arrive is a failed attempt, not a corrupted pair. What
degrades fidelity is a dark-count coincidence, indistinguishable from a real herald and
contributing a maximally mixed pair, along with mode mismatch and memory decoherence.

### 4.3 Calibration against a decoy-state figure

Lo, Ma and Chen (*Phys. Rev. Lett.* **94**, 230504, 2005,
[arXiv:quant-ph/0411004](https://arxiv.org/abs/quant-ph/0411004)) compute the decoy-state
rate for the GYS hardware and report four checkable statements. All four are measured:

```
  [OK ] optimal_mu           roughly 0.5, of order O(1)      measured 0.5
  [OK ] reach_without_decoy  only about 30 km                measured 27 km
  [DIFF] reach_with_decoy    over 140 km                     measured 123.5 km
  [DIFF] upper_bound         208 km, where e_1 = 1/4         measured 179 km
```

**The mechanism reproduces exactly.** The paper's central claim is that decoy states move
the optimal signal intensity from `O(η)` to `O(1)`, roughly 0.5, which is what raises the
net rate from `O(η²)` to `O(η)`. Sweeping μ recovers **0.5** as a genuine maximum, not a
plateau: at μ = 0.1 the reach is 105.2 km against 123.5 km at μ = 0.5.

**The strongest check is the no-decoy curve**, because it is a *different calculation*
from the rate the package normally reports: GLLP equation 12 with the pessimistic
untagged fraction `1 - Ω = p_multi / Q_μ`, implemented from the source rather than reused.
It lands on **27 km against the published ~30 km**. An independent formula reaching the
published number is better evidence than tuning the primary one.

**A real property found while building this.** At the GYS demo's own 4.5 % detector
efficiency the no-decoy bound is **exactly zero at every distance**: the total gain is
smaller than the multi-photon probability at μ = 0.1, so Ω goes negative and no untagged
fraction exists. This is *why* that experiment required decoy states, and it is reported
rather than hidden by choosing a kinder detector:

```
  detector efficiency   no-decoy reach
      0.045                  0 km        <- the GYS demo's own detector
      0.100                 12 km
      0.200                 27 km        <- the figure's ~30 km
      0.400                 42 km
      0.800                 57 km
```

**The two differences are not tuned away.** The 123.5 km decoy reach is the
**finite-key** reach (LCWX bound) against a figure drawn asymptotically, and the package
bounds the single-photon yield conservatively; a finite-key answer below an asymptotic
one is the expected direction. The 179 km crossing is where the single-photon QBER
reaches 1/4, which is model-dependent. The test suite asserts the shortfall *stays* a
margin, so it fails if the number drifts in **either** direction, including if it began
exceeding the published figure, which would mean a bound had been loosened.

---

## 5. Results specific to this work

### 5.1 The routing weight is `-log W`, not `-log F`

Entanglement swapping multiplies the Werner parameter, so a path's parameter is
`W_path = Π W_i` and `-log W` is **exactly additive**. Optimum-fidelity routing is
therefore an ordinary shortest-path problem and Dijkstra on that weight is *optimal*, not
heuristic.

The common substitute `-log F` is not additive. It under-penalises low-fidelity links, by
a factor of 1.34× at `F = 0.99` and 2.25× at `F = 0.30`. On random graphs it selects a
strictly worse path about **1.3%** of the time, with observed fidelity losses up to
**0.02**. A worked counterexample is in `tests/test_topology/test_routing_optimality.py`,
and `fidelity-optimal` is additionally confirmed against exhaustive brute force on random
graphs, so "optimal" is checked rather than asserted.

The practical size of the effect, where a short mediocre span competes with three short
good ones:

```
shortest-distance   F = 0.700000   1 hop
fidelity-optimal    F = 0.970398   3 hops
```

### 5.2 An exact decoder with no third-party matcher

The decoder computes an exact minimum-weight T-join on the merged detector graph. Two
properties matter, and they are separate claims:

**(a) It is accurate, and the numbers now carry their uncertainty.** Logical error rate
against distance, pooled over five seeds at 6000 shots each, 30 000 shots per point:

```
d=3 p=0.003:  0.00220   [0.00173, 0.00280]    66/30000
d=5 p=0.003:  0.00080   [0.00054, 0.00119]    24/30000
d=7 p=0.003:  0.00040   [0.00023, 0.00070]    12/30000     monotone in d
```

**This table previously read `0.00100 / 0.00033 / 0.00000`, and those values were
wrong.** They were not achievable arithmetic at the stated 6000 shots: one event in 6000
is 0.000167, so `0.00100` would be six events and `0.00033` two, while the measured
counts were 10, 4 and 2. The error was silent because the three values looked like a
clean monotone sequence, which is exactly the property they were demonstrating. Finding
it required building the uncertainty layer and asking what interval the sample size can
actually support; no amount of re-reading the prose would have exposed it.

**The monotonicity in `d` is real but the per-seed samples are too thin to see it.** The
per-seed counts at d=5 were 1, 5, 10, 5 and 3 out of 6000, a tenfold spread. At these
rates a single seed cannot distinguish the distances, and any one-seed table that appears
to would be reporting luck. Pooling is what makes the ordering legible, which is the
reason the interval is reported beside it rather than instead of it.

Threshold sweep, 20 000 shots per point, decoder alone:

```
   p        d=3        d=5        d=7      ordering
0.0020   0.00080    0.00020    0.00005      falls
0.0030   0.00200    0.00080    0.00010      falls
0.0050   0.00565    0.00355    0.00230      falls
0.0060   0.00735    0.00645    0.00375      falls
0.0070   0.00930    0.00900    0.00740      falls
0.0080   0.01290    0.01350    0.01000     REVERSES
```

**Threshold p ≈ 0.007.** The reversal above it is the substance of the claim: a threshold
is only a real result if additional distance eventually *hurts*, and the test suite
asserts the ordering reverses rather than checking only the sub-threshold half.

**(b) It computes what the reference computes.** On 4,359 of 4,359 shots at d = 3 and
d = 5, the chosen edge set and the total correction weight are **identical** to
PyMatching's. Measured by deduplicating and canonicalising both edge sets and comparing
total weight per shot.

This is the claim that makes the dependency removable: not "comparable accuracy", but
*the same answer on this circuit family*. The equivalence is established for rotated
surface-code memory-Z with uniform depolarising noise at d ∈ {3, 5, 7}; it is **not**
claimed for other error models, and the module says so.

### 5.3 Repeater placement as an exact optimisation

Given candidate sites along a span, which subset minimises cost while delivering the
highest key rate? `best_placement` is a dynamic program over sites in position order
carrying a **Pareto frontier** of (rate, fidelity) per state. The frontier is necessary,
not decorative: two chains reaching the same site with the same repeater count are not
interchangeable, because the faster one may carry lower fidelity and the slower one may
be the only one from which the remaining spans are feasible.

Measured on a 200 km span with eight candidates spaced 20 km apart:

```
best: 4 sites at [40, 80, 120, 160] km
      key rate 1.1600e5 Hz,  F = 0.96079,  longest link 40 km
```

Verified **exact** against constraint-matched brute force on 25 random instances: 0
suboptimal. (A first comparison appeared to show 43.89% suboptimality; the brute force
had been enumerating layouts the DP was forbidden to choose. The comparison was wrong,
not the code, as recorded in §6.)

### 5.4 A chance constraint over continuous uncertainty

The existing literature on repeater placement, as far as a targeted search found,
handles robustness through *discrete* formulations: selecting components from a
catalogue, or siting repeaters in a greenfield network, plus post-hoc sensitivity
analysis. A reliability statement over a **continuous** hardware parameter is not a
standard construction.

This work states one:

```
Pr[ F(chain; T1, T2) >= F_req ] >= 1 - eps
```

and reduces it without sampling. Two facts do the work:

- **Monotonicity.** `F(chain; T1, T2)` is non-decreasing in both coherence times: better
  memory never makes a chain worse. Verified numerically, and the tests additionally
  assert that the operating point is *sensitive* (fidelity moves by more than 0.05 across
  the prior); an earlier version of those tests used T1 ≈ 100 s, where the model
  saturates at 0.970398 for T1 anywhere from 10 s to 200 s, and every assertion passed
  without exercising anything.
- **The isoquantile principle.** For a non-decreasing function of one random variable,
  `Q_α(φ(X)) = φ(Q_α(X))`, so the constraint becomes a condition at a quantile with no
  distributional assumption beyond the quantiles themselves.

**The two-parameter case is conservative, not exact, and the document and code both say
so.** The identity does not extend to two independent parameters. Both a product-margin
bound `(1 - ε/2)²` and a common-factor bound at `1 - ε` are computed and enforced. The
correlated case, where one physical cause sets both coherence times and which is the usual
hardware situation, is *declared* rather than guessed, because it changes the answer: with a
correlated prior the quantiles come from paired draws, and a mismatched-length prior is
refused.

**What it does not claim.** The result says the layout meets the requirement at the
chosen quantiles. It is not a Monte-Carlo estimate of failure probability, and it says
nothing about scenarios outside the declared prior.

### 5.5 Logical key rate

"Key rate after error correction" is a number almost nobody reports, which is why it is
worth stating with its cost. `logical_key_rate` composes the physical pair's fidelity with
the logical flip through the **Werner product** and reports the physical qubit cost
alongside:

```
F_phys = 0.99, p = 0.003, syndrome rounds = d
  d=3:  F_log 0.98186   key fraction 0.8509    34 physical qubits per logical pair
  d=5:  F_log 0.98556   key fraction 0.8765    98
  d=7:  F_log 0.98926   key fraction 0.9035   194
```

The overhead counts data **and** ancilla at both ends, because a key rate that hides the
qubits it cost is not an engineering figure. The report also names the decoder that
produced the logical error rate, since a threshold is a property of the decoder as much
as of the code.

---

## 6. Negative results and retractions

This section is the reason the rest is worth reading. Each item is a claim that was made,
tested, and found wrong, retained rather than deleted.

### 6.1 A retracted conclusion

An earlier phase concluded:

> *"Path-based observable accumulation is fundamentally incompatible with the reference's
> per-edge labels. The label and the reduction must be adopted together."*

**This is retracted.** The decoder that now works is path-based, keeps the merged graph,
and matches the reference exactly. The actual causes were two specific bugs:

1. **Observables were parsed across the whole instruction.** `stim` binds `L` targets per
   `^`-separated component: `error(0.0004) D4 D6 ^ D5 L0` attaches `L0` to the `D5`
   component *only*. Attaching it to every component made pair `(4, 6)` falsely carry the
   observable.
2. **A missing de-duplication guard.** A symmetric pairing `{a: b, b: a}` toggled each
   route twice, cancelling every detector-pair observable to zero.

**And a third defect, which is the instructive one:** the *checker* had the guard the
decoder lacked. It de-duplicated pairs that the decoder did not, so it validated a
correction the decoder never produced and reported **0.0% violations while the decoder was
wrong**. A checker that differs from the code it checks is worse than a broken one,
because it reports clean.

The lesson recorded in the plan is not "path-based is wrong" but: **a confident structural
explanation is the most expensive kind of wrong answer, because it redirects the search
instead of merely failing.** That conclusion cost five development rounds.

### 6.2 A weight formula that was wrong for the entire project

The edge weight was `-log(p)`. The correct quantity is the log-likelihood ratio
`log((1-p)/p)`, which PyMatching uses and matches to 1.8e-15. The two differ by
**0.5–0.7%** at the probabilities this code reaches, which is enough to change which path
is selected in a close call.

It was noticed and dismissed. An intermediate measurement recorded that the weights agreed
"to within 0.2%" and treated the residual as rounding. It was a systematic error. The
project's own instrument-validation rule would have caught it; it was not applied to a
number that looked good.

### 6.3 A fidelity composition wrong by 9%

The logical key rate combined physical fidelity and logical bit-flip probability as a
*weighted average of fidelities*:

```
F = F_phys(1 - q) + (1 - F_phys) q        (wrong)
```

which treats a bit-flip **probability** as a fidelity. The correct composition is a
Werner-state product. Measured error of the old form:

```
F_phys  F_log     q      corrected      old      overstatement
 0.990  0.996  0.004      0.982114   0.986080      +0.003966
 0.950  0.900  0.050      0.815500   0.905000      +0.089500
```

**Up to 9% absolute**, with the sign not even consistent across inputs. It survived
because at `F_phys = 1` the two forms agree, and that was the input the other modules
used.

### 6.4 A comparison that was wrong, not the code

A verification of the placement optimiser found **43.89% suboptimality** and nearly
prompted a rewrite. The dynamic program was exact; the brute force it was compared against
had been enumerating layouts the DP was forbidden to choose (unbounded repeater count
against a `max_repeaters` cap on the DP side). Constraint-matched, the result is **0 of 25
instances suboptimal**.

### 6.5 Hypotheses removed by measurement

Each of these was a plausible explanation, pursued, and found not to hold:

| hypothesis | result |
|---|---|
| Growth order was the missing piece in Union-Find | Rewrote growth as radius growth. Headline numbers changed by **nothing**. |
| The peel was correct, the growth phase was at fault | The peel scored **51.9% invalid on the full edge set**, where a correct answer provably exists. The peel was the defect. |
| Merging parallel mechanisms discards observables, so unmerge | Merging is what the reference does; its edge count matches exactly. Keeping mechanisms separate was a workaround, not the fix. |
| The greedy fallback caused the d=5 gap | The fallback triggers on **0.4%** of shots. |
| Boundary handling was the Residual defect | Three separate principled changes to it each measured **worse** than the state they replaced. |

### 6.6 Stale documentation

Six documented claims went stale during development, each correct when written: four plan
status rows for finished work, a README asserting 668 tests against an actual 1036, a
website asserting 122, and a section titled "Is 555 tests a lot?". The response was
`scripts/claim_audit.py` (§1.1).

Related and worth recording: the plan's own status tables were found to *understate*
progress four times: work marked `Partial` or `Todo` that was complete and tested. This
is the opposite of the repository's origin story, in which the README advertised tests
that did not run, but it is the same root cause: prose updated after each task and the
tables not.

---

## 7. Limits

Stated as limits, not as future work.

**No hardware validation.** Nothing here has been compared against a physical
implementation. The outputs are model outputs.

**Decoder equivalence is scoped.** Identical to PyMatching on rotated surface-code
memory-Z with uniform depolarising noise at d = 3, 5, 7. For error models where the
reference's heuristics diverge from an exact matching, this has not been tested, and the
module does not claim it.

**Calibration reproduces two of four published statements.** Both differences are
explained and neither is tuned; the test suite fails if either drifts toward *better*
agreement.

**Placement robustness is conservative.** The two-parameter chance-constraint reduction
enforces the more demanding of two bounds. It is correct, and it is not tight. The tests
demonstrate the quantile direction and monotonicity rather than a rate difference, because
for the candidate sets tried the constraint does not bind.

**Detector recovery is a minimum slot spacing**, not a per-detector state machine. A full
recovery trace would need the detector's internal curve, which this package does not have.

**The legacy greedy decoder is an approximation with a measured gap, and it is not on any
public path.** It replicates the single-round check graph into every layer, whereas the
final round measures the data qubits directly, so the last layer is modelled as another
ancilla comparison. Measured against the exact decoder on the same 542 syndromes at d=3,
p=0.003: they disagree on **10.1%** of them, 60% of those differences involve the final
round, and the practical cost is **104 logical errors against the exact decoder's 63** on
4000 shots, about 65% more.

Three consequences worth stating plainly.

First, the `decoder="greedy"` parameter has always returned the in-package exact decoder, so
the two names produced identical numbers; the branch is now removed and the name documented
as an alias rather than pretending to be a choice.

Second, the decoder is **unreachable through the public API**, so no reported figure in this
document comes from it. `logical_error_rate` requires `stim` regardless of which decoder is
asked for, which also means the "keeps the package running without stim" rationale never
held: without `stim` the measurement raises before any decoder is chosen.

Third, the functions remain, because they are tested and they are honest building blocks:
`decode_space_time` provides the exact answer on instances both can handle, and
`decode_space_time_greedy` is referenced by tests asserting properties it does satisfy (a
measurement error costs one edge; a single data error costs one correction). They are
approximations that say so, not silent failures. What was wrong was this document's
*description* of the defect, which asserted a specific boundary bug that the measurement
does not isolate.

**Estimator scope.** The asymptotic decoy-state path is the standard
asymptotic-plus-estimator analysis, not a composable-security proof. The finite-key path
implements the LCWX bound.

---

## 8. Availability

- Source: <https://github.com/KELLERBABG/QEL>
- Licence: Apache-2.0
- Citation metadata: `CITATION.cff`
- Documentation: `README.md`, covering usage, results, and the scope statement
- Verification: `py -m pytest -q` (1138 tests), `py -m quantumnet validate` (published
  comparisons, scored and explicitly unscored), `py scripts/claim_audit.py` (documentation
  drift)

**What is deliberately not published.** Two categories of artifact are held back, and the
reasons are recorded here rather than left to look like omissions:

- **Third-party source material.** Extracted text and LaTeX from the publications cited in
  §4 are kept locally for reference and are not redistributed, because that is a copyright
  matter and they are not needed to use or verify the code. The citations point at the
  originals.
- **The development record.** A running log kept during this work, including the
  measurements that failed and the hypotheses that were removed, is not part of the
  released tree. The findings that matter for judging the results are in §6; the log
  itself was a working document.

This document is the authoritative account of what the code does and how far it can be
trusted. Where it states a limit, the limit is real and the tests are written to fail if
the number drifts, in either direction.
