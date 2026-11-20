# QEL: a quantum-network simulator built to be falsified

**Version 0.2.0 · Lukas Negenborn · Apache-2.0**

---

## Abstract

QEL is a simulator for quantum communication networks across **64 modules** and **1161 tests**
(**16,923 source lines and 13,060 lines in `tests/`**). It models the full path rather than a link budget:
density-matrix states under depolarising, dephasing and amplitude-damping noise; both the
1-parameter Werner algebra and the closed **4-parameter Bell-block-diagonal `XState` manifold**
under non-unital $T_1$/GAD relaxation, $T_\varphi$ dephasing and entanglement swapping;
distance-dependent fibre attenuation and **exact four-branch Barrett–Kok $O((\eta_A+\eta_B)p_d)$
false-herald photonics**; Markovian ($\beta=1$) and **non-Markovian spin-bath ($\beta=3$) memory
dynamics**; distillation; resource contention with three-tier circular-economy pair classification;
**`-log W` fidelity-optimal and polynomial-time `skr-optimal` routing**; Pareto-exact and
**exact 1D $\Gamma_{\text{eff}}$ continuous chance-constrained repeater placement**; post-PLOB
repeater capacities and **asynchronous Mode-Pairing QKD**; and a rotated surface code with its
own **exact minimum-weight T-join decoder**, extended with two-pass correlated matching and
heralded erasure conversion.

This document reports what the implementation reproduces from published work, what it
computes that is not a reproduction, and in as much detail as the positive results,
**what it gets wrong, what was retracted, and where it disagrees with its own sources.**

The three headline results are:

1. **An in-package surface-code decoder that removes the third-party matcher from the
   threshold path, matches PyMatching on 100.0% of total matching weights, and supports
   two-pass correlated matching and heralded erasure conversion.** It computes an exact
   minimum-weight T-join on the detector error model graph, matches PyMatching's accuracy
   on the circuits this package generates (**24 against 26 logical errors** over 18,000
   shots at $d=3, 5$ and $7$, recovering a threshold near $p \approx 0.007$), and matches
   PyMatching's total matching weight on **100.0% of non-trivial shots** (`647/647` at
   $d=3$, `2239/2239` at $d=5$, `max gap 0.00`, edge-set agreement `100.0%` and `99.7%`).
   An earlier report of a weight gap against PyMatching is retracted in §6.7: it was caused
   by a one-line boolean-vector bug in `scripts/decoder_claim_check.py:125`.
2. **Exact additive fidelity routing (`-log W`), and its exact polynomial-time inversion
   under secret-key-rate routing (`skr-optimal`).** Entanglement swapping multiplies the
   Werner parameter, so `-log W` is *exactly* additive for end-to-end fidelity while the
   widely used substitute `-log F` picks a strictly worse path about 1.3% of the time. When
   the objective is secret bits/s rather than fidelity, `SKROptimalRouting` runs a
   bottleneck-stratified $h$-hop Dijkstra in $O(|E|\,h_{\max}(|E|+|V|\log|V|))$ incorporating
   the linear-optics Bell-state-measurement tax $p_{\text{BSM}}^{h-1}$ ($\le 0.5$) and the
   exact Werner BBM92 QBER $2(1-F)/3$, selecting a 1-hop route (`19,822 bits/s`, $F=0.9200$)
   that yields **+19.4% more secret key** than the 3-hop `-log W` route (`16,608 bits/s`,
   $F=0.9372$).
3. **An exact 1D $\Gamma_{\text{eff}} = 1/T_1 + 1/T_2$ isoquantile reduction for continuous
   chance-constrained repeater placement (§5.4) and an automated five-gap adversarial
   physics audit (`scripts/ontology_audit.py`, §5.6)** quantifying where 1-parameter
   quantum-network abstractions break down across state representation, routing, photonics,
   memory bath physics, and post-PLOB key rates.

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
the work the test suite did not run at all: a single stale import made 12 of the initial
37-file tree unimportable, and the README advertised a test count the suite had never
produced. The planning documents that guided it contained a load-bearing mathematical
error in the routing weight.

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
documented claims went stale: status rows for finished work, a README asserting a stale
count of 668 when the suite ran 1036, a website asserting 122. Each was correct when
written and each silently rotted. The response was not to re-read the prose more carefully
(that had already been tried) but to write `scripts/claim_audit.py`, which extracts every
numeric claim from a document and prints it beside what the repository currently measures.
It reports and refuses to decide: a tool that guessed which number was right would produce
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
| **Core** | density-matrix states, Wootters concurrence, **4-parameter Bell-block-diagonal `XState` algebra** (`core/xstate.py`), gates, POVM measurement, noise channels, Clifford stabiliser tableau, discrete-event scheduler, multi-process nodes |
| **Hardware** | detector impairment models, **Barrett–Kok double-heralded generation with exact $O((\eta_A+\eta_B)p_d)$ four-branch false-herald accounting** (`core/photonics.py`), **non-Markovian $\beta$-memory** (`core/physical.py`), explicit time-division multiplexing, latency accounting |
| **Protocols** | BB84 (decoy state, finite-key LCWX bound, **exact Werner BBM92 & Six-State QBER `2(1-F)/3`, PLOB/$K_k$ capacities, asynchronous Mode-Pairing QKD**), E91, teleportation, superdense coding, swapping, BBPSSW/Deutsch/DEJMPS distillation, multi-qubit $T_1/T_\varphi$ memory dynamics, Shor and Steane codes |
| **Topology** | graphs, pluggable routing policies (**`fidelity-optimal` `-log W` and polynomial-time `skr-optimal`**), schedules, resource contention (**LIFO/FIFO policies and 3-tier QKD / CHSH beacon / distillation compost classification**), Pareto-exact placement, **exact 1D $\Gamma_{\text{eff}}$ continuous chance-constrained placement**, multi-commodity routing, ASCII visualisation |
| **QEC** | rotated surface code, space-time detector model, **exact T-join decoder with two-pass correlated matching (`decode_correlated`) and heralded erasure conversion**, logical key rate |
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

### 3.2 Werner states and the 4-parameter non-Pauli `XState` manifold

For isotropic depolarising noise, a two-qubit entangled pair is represented by its Werner
parameter $W = (4F-1)/3$, because the 1-parameter Werner family is closed under isotropic
depolarisation and entanglement swapping ($W_{\text{swap}} = W_1 W_2$). Both operations are
exact in this representation, which is what makes §5.1 possible.

However, physical quantum memories do not relax toward the maximally mixed state $I/4$;
they relax via non-unital amplitude damping ($T_1$ / generalised amplitude damping) toward
$|00\rangle\langle 00|$ while dephasing on $T_\varphi$. Under local $T_1$/GAD and $T_\varphi$
channels and standard linear-optics Bell-state measurements, two-qubit states with empty
cross-subspace coherences remain strictly closed inside a **4-parameter Bell-block-diagonal
X-state submanifold** (`core/xstate.py`),

$$\rho_X(P_\Phi, \Delta_\Phi, \alpha, \beta), \quad P_\Phi = \rho_{00,00} + \rho_{11,11}, \quad \Delta_\Phi = 2\operatorname{Re}\rho_{00,11}, \quad \alpha = \rho_{01,01} + \rho_{10,10} + 2\operatorname{Re}\rho_{01,10}, \quad \beta = \rho_{00,00} - \rho_{11,11},$$

with exact closed-form Wootters concurrence

$$C(\rho_X) = \max\!\left(0,\; |\Delta_\Phi| - \sqrt{(1 - P_\Phi)^2 - \delta^2},\; |\alpha + \delta - (1 - P_\Phi)| - \sqrt{P_\Phi^2 - \beta^2}\right)$$

and exact BSM-conditioned post-swap recursions (`swap_with`, `swap_psi_branch`). Tracking
these four parameters instead of projecting onto a 1-parameter Werner state exposes five
distinct physical phenomena documented in §5.6.

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
edges whose odd-degree vertices are exactly the detection events. For depolarising $Y$-errors
that correlate $X$- and $Z$-type detectors across `^`-separated components, `decode_correlated`
performs a two-pass conditional log-likelihood reweighting; for neutral-atom or trapped-ion
architectures with heralded leakage, `heralded_erasure_fraction` converts flagged fault
locations into zero-weight ($w = \ln((1-0.5)/0.5) = 0$) erasure edges.

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

### 4.2 Barrett–Kok double-heralded generation and exact $O((\eta_A+\eta_B)p_d)$ false heralds

The model follows Barrett and Kok (*Phys. Rev. A* **71**, 060310(R), 2005). Two published
properties are checked: the ideal success probability is exactly **1/2** at zero loss
(the protocol's stated upper limit), and the probability is **quadratic in detector
efficiency** (`p ∝ η²`) because both photons must survive and both must be detected.

The consequence matters when reading any rate it prints: **loss costs rate, not
fidelity.** A photon that fails to arrive is a failed attempt, not a corrupted pair. What
degrades fidelity is a false-herald dark-count trajectory, indistinguishable from a real
two-photon herald, along with mode mismatch and memory decoherence. In `core/photonics.py`,
`BarrettKokResult` tracks all four double-herald trajectories rather than only the legacy
$O(p_d^2)$ double-dark term:

- $P_{\text{true}} = \frac{1}{2}\eta_A\eta_B(1 - p_d)^2$ (both clicks from real photons, fidelity $F_{\text{Visibility}}$),
- $P_{\text{false},1\gamma} = \frac{1}{2}\big[\eta_A(1-\eta_B) + \eta_B(1-\eta_A)\big]p_d(1-p_d)$ (one real photon in Round 1 and one dark count in Round 2, or vice versa, contributing an uncorrelated product state of fidelity $1/4$),
- $P_{\text{false},0\gamma} = (1-\eta_A)(1-\eta_B)p_d^2$ (dark counts in both rounds, fidelity $1/4$).

Because $\eta \gg p_d$ across metropolitan and inter-city fibre ($50\text{–}150\text{ km}$),
the $O((\eta_A+\eta_B)p_d)$ cross-term dominates $O(p_d^2)$ by two to three orders of
magnitude (§5.6, Gap 3).

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

**The two statements that do not reproduce are treated as a result in their own right**, and
are given §4.4 rather than a closing caveat here.

---

### 4.4 Two published statements that do not reproduce

Four statements were transcribed from Lo, Ma and Chen and all four were measured; the table
is in §4.3. **Two agree and two do not**, and the disagreement is the most informative part
of this section, so it is stated at full strength.

Neither difference is tuned away, and neither is blamed on an error without evidence.

**The decoy reach.** 123.5 km measured against "over 140 km" published. The package reports
the reach at which the **finite-key** secret length is positive, using the LCWX bound, and
it bounds the single-photon yield conservatively; the source draws its figure asymptotically.
A finite-key result falling below an asymptotic one is the expected direction, so the two
numbers are probably answering slightly different questions. That is an explanation rather
than a demonstration, and it is the specific thing a hardware measurement could settle.

**The intercept-resend crossing.** 179 km measured against 208 km published. The crossing is
where the single-photon QBER reaches 1/4, beyond which intercept-resend succeeds. The
quantity is model-dependent, so it is reported as measured.

**The test suite enforces the direction of both.** It asserts the shortfall *stays* a
margin, and fails if either number drifts toward better agreement, because closing the gap
by loosening a bound would make the model look more accurate while making it worse. A
difference that can only move one way is a stronger claim than a number that happens to
match.

**Why this is reported rather than smoothed.** Two of four is what calibrating looks like
when the disagreement is left visible. A model tuned until all four statements matched would
have told the reader nothing about where it stops being trustworthy.

---

## 5. Results specific to this work

### 5.1 Fidelity routing uses `-log W`, not `-log F` — and `skr-optimal` inverts it when the BSM tax dominates

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

**Why highest fidelity is not highest secret-key throughput (`skr-optimal`).** For an
entanglement-based BBM92 link on a Werner state $\rho_W(F) = W|\Phi^+\rangle\langle\Phi^+| + (1-W)I/4$,
the maximally mixed weight $(1-W)$ splits into four equal Bell populations $(1-W)/4 = (1-F)/3$.
Because $Z$-basis errors arise on $|\Psi^+\rangle$ and $|\Psi^-\rangle$ and $X$-basis errors on
$|\Phi^-\rangle$ and $|\Psi^-\rangle$, the true Werner BBM92 QBER in *each* basis is

$$e_Z = e_X = \frac{2(1 - F)}{3}, \qquad r_\infty^{\text{BBM92}}(F) = \max\!\left(0,\; 1 - (1 + f_{\text{EC}}) H_2\!\left(\frac{2(1 - F)}{3}\right)\right)$$

with zero-key threshold $F^*_{\text{BBM92}} = 1 - \frac{3}{2}h_2^{-1}(1/2) \approx 0.83496$
(and Six-State threshold $F^*_{\text{6-state}} \approx 0.81071$), rather than the pure-bitflip
substitute $(1-F)/2$ ($F^* = 0.7800$). At $F = 0.90$ and $f_{\text{EC}} = 1.0$, the exact
Werner secret-key fraction is `0.293281` against `(1-F)/2`'s `0.427206` (a 31% overstatement
by the bitflip formula).

When routing for end-to-end secret bits/s across $h$ hops, each intermediate node performs a
Bell-state measurement whose linear-optics success probability is bounded by $p_{\text{BSM}} \le 1/2$,
so under synchronous no-cutoff pipelining the end-to-end secret-key rate is

$$R_{\text{SKR}}(P) = \frac{\min_{e \in P} R_{\text{gen}}(e)}{h} \cdot p_{\text{BSM}}^{h - 1} \cdot r_\infty^{\text{BBM92}}\!\left(\frac{1 + 3\prod_{e \in P} W_e}{4}\right).$$

Because $R_{\text{SKR}}(P)$ couples a bottleneck minimum ($\min R_e$), a hop count ($h$), and
a multiplicative product ($\prod W_e$), no single scalar link weight can optimise it. However,
because distinct bottleneck rates are bounded by $|E|$ and simple-path hop counts by
$h \le |V|-1$, fixing $(R_{\min}, h)$ reduces the remaining objective to maximising $\prod W_e$,
which is a standard $h$-hop layered shortest-path search on $w_e = -\ln W_e$ over the subgraph
$\{e \in E : R_{\text{gen}}(e) \ge R_{\min}\}$. `SKROptimalRouting` (`"skr-optimal"`) evaluates
this stratified family in $O(|E|\,h_{\max}(|E| + |V|\log|V|))$ polynomial time and is **provably
exact**. On the benchmark topology in `tests/test_topology/test_strategies.py`:

```
fidelity-optimal (-log W)   S -> R1 -> R2 -> T (3 hops)   F = 0.9372   SKR = 16,608 bits/s
skr-optimal                 S -> T             (1 hop)    F = 0.9200   SKR = 19,822 bits/s (+19.4%)
```

Paying two linear-optics BSM taxes ($0.5^2 = 0.25$) and a $1/3$ pipelining factor to gain
$+0.0172$ end-to-end fidelity costs more raw pair rate than the lower QBER recovers.

### 5.2 An exact decoder with no third-party matcher, 100.0% weight agreement, correlated matching, and heralded erasures

The decoder computes an exact minimum-weight T-join on the merged detector graph. Three
properties matter, and they are separate claims:

**(a) It is accurate, and the numbers carry their uncertainty.** Logical error rate
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

**(b) Its accuracy and total matching weight match PyMatching's.** Over 18,000 shots at
d = 3, 5 and 7 the two decoders make **24 and 26 logical errors** respectively. Across
1,000 shots per noise level ($p \in \{0.001, 0.003, 0.005\}$, 3,000 shots per distance) at
$d = 3$ and $d = 5$, `py scripts/decoder_claim_check.py --shots 1000 --distances 3 5`
measures:

```
                                      d = 3              d = 5
  non-trivial shots                     647               2239
  logical errors (this / reference)   5 / 5              2 / 2
  edge sets agree                 647 / 647 (100.0%) 2233 / 2239 (99.7%)
  total weight agrees             647 / 647 (100.0%) 2239 / 2239 (100.0%)
  this decoder heavier                    0                  0
  this decoder lighter                    0                  0
  maximum weight gap                   0.00               0.00
```

Every single non-trivial shot at both $d = 3$ and $d = 5$ reaches the **exact same minimum
total matching weight** as PyMatching (`max gap 0.00`, floating-point difference
$\le 7.1 \times 10^{-15}$); the 6 shots out of 2,239 at $d = 5$ where the edge set differs
are exact equal-weight ties on the lattice. An earlier version of this table reported
`1 / 647` and `0 / 2239` edge-set agreement and a heavier weight in four-fifths of shots;
as documented in §6.7, that discrepancy was an artifact of a one-line boolean-vector bug in
`scripts/decoder_claim_check.py:125`.

**(c) Two-pass correlated matching and heralded erasure conversion.** Standard MWPM
decomposes each $Y$-error ($X \otimes Z$) into two independent graphlike components, throwing
away the mutual information $I(X; Z) > 0$ between the two subgraphs. `core/tjoin_decoder.py`
and `core/surface_code.py` add two extensions:

- **Two-pass correlated matching (`parse_dem_correlations`, `decode_correlated`):** parses
  compound `^`-separated DEM instructions (`error(p) D_a D_b ^ D_c D_d`), runs Pass 1 on
  the marginal graph, updates partner-edge weights via the exact Bayes conditional
  probability $p(e_2 = 1 \mid e_1 = 1) = (p_{\text{ind}}(e_2) + p_{\text{corr}} - 2p_{\text{ind}}(e_2)p_{\text{corr}})/(1 - 2p_{\text{ind}}(e_2)p_{\text{corr}})$
  and $w'(e_2) = \ln((1 - p(e_2 \mid e_1))/p(e_2 \mid e_1))$, and runs Pass 2 to resolve
  correlated syndromes that fool independent matching.
- **Heralded erasure conversion (`heralded_erasure_fraction`, `erasure_edges`):** when a
  fraction $f_e \in [0, 1]$ of faults are heralded by hardware leakage detection (e.g.,
  neutral-atom `$^{171}\text{Yb}$` metastable decay or cavity-QED erasure flags), the known
  fault location has 50% conditional Pauli probability and therefore weight
  $w_e = \ln((1 - 0.5)/0.5) = 0.0$, shifting sub-threshold logical error scaling from
  $P_L^{\text{Pauli}} \propto (p/p_{\text{th}})^{(d+1)/2}$ toward
  $P_L^{\text{erasure}} \propto (p_e/p_{\text{th},e})^d$.

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
not the code, as recorded in §6.4.)

### 5.4 An exact 1D $\Gamma_{\text{eff}}$ reduction for continuous chance-constrained placement

The existing literature on repeater placement, as far as a targeted search found,
handles robustness through *discrete* formulations: selecting components from a
catalogue, or siting repeaters in a greenfield network, plus post-hoc sensitivity
analysis. A reliability statement over a **continuous** hardware parameter is not a
standard construction.

This work states one:

```
Pr[ F(chain; T1, T2) >= F_req ] >= 1 - eps
```

and reduces it without sampling during DP optimization. Three facts do the work:

- **Monotonicity.** `F(chain; T1, T2)` is non-decreasing in both coherence times: better
  memory never makes a chain worse. Verified numerically, and the tests additionally
  assert that the operating point is *sensitive* (fidelity moves by more than 0.05 across
  the prior); an earlier version of those tests used T1 ≈ 100 s, where the model
  saturates at 0.970398 for T1 anywhere from 10 s to 200 s, and every assertion passed
  without exercising anything.
- **The isoquantile principle.** For a non-decreasing function of one random variable,
  `Q_α(φ(X)) = φ(Q_α(X))`, so the constraint becomes a condition at a quantile with no
  distributional assumption beyond the quantiles themselves.
- **Exact 1D reduction via the effective decay rate $\Gamma_{\text{eff}} = 1/T_1 + 1/T_2$.**
  In a homogeneous repeater chain, every link $i$ holds its pair for wait time $t_i$ and
  suffers decoherence solely through $\exp(-t_i(1/T_1 + 1/T_2)) = \exp(-t_i \Gamma_{\text{eff}})$.
  Therefore, the two-parameter chain fidelity is a strictly decreasing function of a
  *single* scalar random variable $\Gamma_{\text{eff}} = 1/T_1 + 1/T_2$:

  $$F(\text{chain}; T_1, T_2) = g(\Gamma_{\text{eff}}), \qquad \Pr\!\big[F(\text{chain}; T_1, T_2) \ge F_{\text{req}}\big] \ge 1 - \varepsilon \iff g(\gamma_{1-\varepsilon}) \ge F_{\text{req}},$$

  where $\gamma_{1-\varepsilon} = F_{\Gamma_{\text{eff}}}^{-1}(1 - \varepsilon)$ is the $(1-\varepsilon)$-quantile
  of $\Gamma_{\text{eff}}$. This makes the two-parameter continuous chance constraint
  **exact** (`exact_1d_scenario`, `exact_1d=True`) for *any* joint or independent prior on
  $(T_1, T_2)$, eliminating the ~30% margin-split over-conservatism of Bonferroni bounds
  while meeting the $1 - \varepsilon$ coverage target with equality. Both the product-margin
  bound (`eps / 2` lower tail per coordinate) and the common-factor bound (`eps` lower tail)
  are retained alongside `exact_1d=True` for comparison and for heterogeneous-node extensions.

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

### 5.6 The five ontology gaps (`scripts/ontology_audit.py`)

Standard quantum-network simulators rely on five 1-parameter reductions: (1) Werner states
for link fidelity, (2) additive `-log W` for routing, (3) $O(p_d^2)$ double dark counts for
Barrett–Kok heralding, (4) Markovian $\exp(-t/T_2)$ for memory dephasing, and (5) the
repeaterless PLOB bound for point-to-point QKD. `py scripts/ontology_audit.py` tests each
assumption against the exact multi-parameter physics in QEL and exits 0 only if all five
divergences reproduce:

1. **Gap 1 — 4-parameter `XState` vs 1-parameter Werner (`core/xstate.py`).**
   - *4-hop repeater survival:* At per-link amplitude damping $\gamma = 0.15$ and dephasing
     $\eta_\phi = 0.95$, the Werner model predicts $F_4 = 0.4999 < 0.5$ ($C = 0$, dead),
     whereas the exact 4-parameter `XState` preserves entanglement ($F_{\text{avg},4} = 0.5002$,
     $C_{\text{avg},4} = 0.0031$; on the $|\Psi^\pm\rangle$ BSM branch, $F_{\Psi,4} = 0.5054$,
     $C_{\Psi,4} = 0.0108$) because BSM parity sorting separates $|00\rangle/|11\rangle$ from
     $|01\rangle/|10\rangle$.
   - *Asymmetric wait times:* Under one-sided amplitude damping ($\gamma_A = 0.80, \gamma_B = 0$),
     the exact concurrence is $C = \sqrt{1 - \gamma_A} = 0.4472$, whereas the Werner projection
     from fidelity ($F = 0.5236$) predicts $C_{\text{Werner}} = 0.0472$ — a **$9.5\times$
     underestimate**.
   - *The $|\Psi^+\rangle$ "sleep suit" (`apply_sleep_suit`):* Applying a local Pauli $X$
     before memory storage converts $|\Phi^+\rangle \to |\Psi^+\rangle$, which has zero
     $|11\rangle\langle 11|$ population and therefore never populates the ground-state root
     $ad$ in Wootters' concurrence formula under $T_1$ decay ($C = (1-\gamma) = 0.3000$ at
     $\gamma = 0.70$, preventing Yu–Eberly entanglement sudden death where Werner predicts
     $C = 0$ at $F = 0.3000$).
   - *Single-copy Procrustean filtering (`procrustean_filter_one_sided`):* A local weak
     POVM $K_0 = \operatorname{diag}(1, \sqrt{1 - \gamma_A})$ on the un-damped partner B
     re-symmetrizes the state without consuming a second Bell pair (at $\gamma_A = 0.80$:
     $p_{\text{succ}} = 0.6$, raising fidelity from $0.5236 \to 0.6000$).
   - *In-band BSM cryostat thermometer & the no-signaling scar:* Under $T_1$ relaxation, the
     four Bell outcomes at a swap node are non-uniform,
     $\Delta P_{\text{BSM}} = P(\Phi^+ \vee \Phi^-) - P(\Psi^+ \vee \Psi^-) = 2(\alpha_1 - \beta_1)(\alpha_2 + \beta_2)$,
     providing a zero-probe in-band remote $T_1$ diagnostic. Simultaneously, averaging over
     all four classical BSM messages yields $\beta'_{\text{avg}} = (1 - P_2)\alpha_1 \neq 0$:
     the ground-state population bias $\beta_2$ cannot disappear without the classical message,
     because its instantaneous erasure would violate no-signaling ($\operatorname{Tr}_D(\rho'_{AD,\text{avg}}) = \operatorname{Tr}_C(\rho_{CD})$).
2. **Gap 2 — `-log W` fidelity routing vs `skr-optimal` routing & the 3-tier memory circular
   economy (`topology/strategies.py`, `core/memory.py`).** As shown in §5.1, `-log W` selects
   the 3-hop path ($F = 0.9372$, `16,608 bits/s`) while `skr-optimal` selects the 1-hop path
   ($F = 0.9200$, `19,822 bits/s`, **+19.4% secret key**). Pairs decaying in `MemoryArray`
   are routed by `classify_entanglement_tiers()` into **Tier 1 QKD** ($F > 0.83496$),
   **Tier 2 CHSH public randomness beacon** ($0.78033 < F \le 0.83496$, where $S_{\text{CHSH}} = 2\sqrt{2}\,W > 2$
   certifies public randomness without requiring secret privacy against Eve), and **Tier 3
   distillation compost** ($0.5 < F \le 0.78033$).
3. **Gap 3 — Barrett–Kok $O((\eta_A+\eta_B)p_d)$ cross-term & the "Smiling Denial of Service"
   (`core/photonics.py`).** At $150\text{ km}$ ($\eta = 8 \times 10^{-4}$), raising detector
   dark counts from $10^{-5}$ to $10^{-4}$ causes `exact_fidelity()` to collapse from
   **0.9311 to 0.6031** (zero BBM92 key) while the legacy $O(p_d^2)$ `raw_fidelity()` reports
   **0.9773** and the apparent herald rate *increases* from $3.28 \times 10^{-7}$ to
   $4.05 \times 10^{-7}$. An adversary injecting incoherent background light (or a failing
   cryocooler) triggers a **"Smiling DoS"** in which link telemetry looks healthier while
   true entanglement drops to zero.
4. **Gap 4 — Non-Markovian $\beta = 3$ spin-bath memory (`core/physical.py`).** Under CPMG/XY8
   dynamical decoupling on a slow nuclear spin bath ($\beta = 3$, $T_2(N) = T_{2,\text{Hahn}} N^{2/3}$),
   the stretched-exponential decay $\exp(-(t/T_2)^\beta)$ has zero initial slope at $t \to 0^+$.
   At short holds $t/T_2 = 0.1$, $\beta = 3$ loses **$95.2\times$ less coherence** than
   Markovian $\beta = 1$ ($7.50 \times 10^{-4}$ vs $7.14 \times 10^{-2}$), rewarding
   `"newest-first"` (LIFO) scheduling. Conversely, if a swap does not reset the spin bath,
   the remaining memory accumulates a non-Markovian age penalty
   $(t_{\text{prev}} + \Delta t)^\beta - t_{\text{prev}}^\beta > (\Delta t)^\beta$ ($F = 0.5626$
   at $\Delta t/T_2 = 0.5$ after prior age $0.5$, vs $0.9119$ fresh).
5. **Gap 5 — The "Valley of Repeater Shame" & post-PLOB Mode-Pairing QKD (`protocols/bb84.py`).**
   Memoryless asynchronous Mode-Pairing QKD pairs independent detection clicks within a maximum
   time-bin window $L_{\max}$ after the fact, achieving twin-field $O(\sqrt{\eta})$ scaling
   without phase-locked optical interferometers or quantum memories. At $380\text{ km}$
   ($\eta = 2.14 \times 10^{-8}$), `mode_pairing_qkd_rate` delivers $R = 1.08 \times 10^{-5}\text{ bits/pulse}$,
   beating the repeaterless PLOB bound $K_{\text{PLOB}}(\eta) = -\log_2(1-\eta) = 3.08 \times 10^{-8}$
   by **$350\times$** while respecting the 1-repeater ($k=2$) capacity ceiling
   $K_2(\eta) = -\log_2(1-\sqrt{\eta}) = 2.11 \times 10^{-4}$. A single first-generation
   quantum-memory repeater at $190+190\text{ km}$ must therefore beat not $K_{\text{PLOB}}(\eta)$,
   but a memoryless Mode-Pairing relay living in the same $O(\sqrt{\eta})$ equivalence class.

---

## 6. Negative results and retractions

This section is the reason the rest is worth reading. Each item is a claim that was made,
tested, and found wrong, retained rather than deleted.

### 6.1 A retracted conclusion

An earlier phase concluded:

> *"Path-based observable accumulation is fundamentally incompatible with the reference's
> per-edge labels. The label and the reduction must be adopted together."*

**This is retracted.** The decoder that now works is path-based, keeps the merged graph,
and matches the reference's total matching weight on 100.0% of shots. The actual causes of
the earlier failure were two specific bugs:

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
status rows for finished work, a README asserting a stale count of 668 against an actual
1036, a website asserting 122, and a section heading that still asked whether 555 was a
large suite. The response was `scripts/claim_audit.py` (§1.1).

Related and worth recording: the plan's own status tables were found to *understate*
progress four times: work marked `Partial` or `Todo` that was complete and tested. This
is the opposite of the repository's origin story, in which the README advertised tests
that did not run, but it is the same root cause: prose updated after each task and the
tables not.

### 6.7 The "unexplained decoder weight discrepancy" was a one-line bug in the comparison script

Version 0.1.0 of this whitepaper (§5.2 and §7) reported that `tjoin_decoder` agreed with
PyMatching's edge set on only `1 / 647` non-trivial shots at $d = 3$ and `0 / 2239` at
$d = 5$, and produced a heavier correction in roughly four-fifths of shots (`max gap 15.80`
at $d = 3$, `45.91` at $d = 5$). That discrepancy was real in the output of
`scripts/decoder_claim_check.py`, and it was **entirely caused by the script**:

- `decode_batch(dem, det)` converts each shot's boolean syndrome row `row` into fired
  detector indices via `np.flatnonzero(row)` before calling `decode_edges_and_observables`.
- `scripts/decoder_claim_check.py:125` called `decode_edges_and_observables(graph, det[i])`
  directly, passing the raw length-$N_{\text{det}}$ boolean array `det[i]` where a list of
  integer detector indices was expected.
- Inside `decode_edges_and_observables`, `[int(d) for d in fired_detectors]` converted
  every `False` to `0` and every `True` to `1`, collapsing every non-empty syndrome on the
  entire surface code into a subset of detectors `{0, 1}`!

Replacing `det[i]` with `np.flatnonzero(det[i])` in `scripts/decoder_claim_check.py:125`
immediately raised total-weight agreement to **100.0%** (`647/647` at $d=3$, `2239/2239`
at $d=5$, `max gap 0.00`) and edge-set agreement to **100.0% / 99.7%**. This is the second
time in the project (§6.4 being the first) that a verification harness convicted a correct
algorithm because the harness itself violated an input invariant.

### 6.8 Six quiet physics and quantile-tail bugs caught by adversarial audit

During the ontology audit (§5.6), six defects were uncovered in existing modules that had
passed unit tests because their outputs remained plausible:

1. **Inverted quantile tail in `chance_placement.py`:** `margin_scenario` and
   `common_scenario` evaluated `1.0 - eps / 2.0` and `1.0 - eps` (the *optimistic* upper
   tail of $T_1, T_2$) instead of `eps / 2.0` and `eps` (the *pessimistic* lower tail),
   and `robust_placement` ordered worst-case scenarios by the product $T_1 \cdot T_2$
   rather than the harmonic effective coherence time $1/(1/T_1 + 1/T_2)$.
2. **Two-qubit dephasing coherence revival ("Lazarus bug") in `protocols/memory.py`:**
   passing $\gamma = 1 - e^{-t/T_2}$ into `dephasing_channel(gamma)` scaled single-qubit
   coherences by $1 - 2\gamma = 2e^{-t/T_2} - 1 \to -1$ as $t \to \infty$; on two qubits,
   $(-1)\times(-1) = +1$, causing a Bell pair's fidelity to dip to $0.5$ at $t = T_2\ln 2$
   and **rebound to $0.9999$ at $t = 500\text{ s}$**. Fixed by passing
   $p = \frac{1}{2}(1 - e^{-t/T_\varphi})$ so $1 - 2p = e^{-t/T_\varphi} \ge 0$ monotonically.
3. **Missing square root in Wootters concurrence (`core/qubit.py`):** `QubitState.concurrence()`
   omitted $\sqrt{\lambda_i}$ on the eigenvalues of $\rho\tilde{\rho}$ and used raw `PAULI_Y`
   without `.real` on $\sigma_y \otimes \sigma_y$, returning $C(\Phi^+) = 0.0$ instead of $1.0$.
4. **Post-measurement Hadamard and depolarising parameter in `protocols/distillation.py`:**
   DEJMPS/BBPSSW applied X-basis Hadamards *after* `measure()` (measuring $Z$ instead of $X$)
   and parameterised two-qubit Werner states with $p = 1 - F$ instead of $p = \frac{4}{3}(1 - F)$.
5. **Logical Bell Pauli-$Y$ and stabilizer indices in `core/logical_entanglement.py`:**
   the syndrome table mapped $(1, 1) \to I$ instead of `PAULI_Y` and entangled two
   $[[n, 1, d]]$ blocks via transversal $\text{CNOT}(H^{\otimes n}|0_L\rangle)$ (which creates
   a $2n$-qubit GHZ state for $n > 1$) rather than fault-tolerant Bell preparation.
6. **Linear fidelity mixture in `core/coupled.py`:** `effective_fidelity` still used the
   retracted linear combination $F_{\text{phys}}(1 - p_L) + (1 - F_{\text{phys}})p_L$ (§6.3)
   instead of the Werner product `compose_pair_fidelity`.

---

## 7. Limits

Stated as limits, not as future work.

**No hardware validation.** Nothing here has been compared against a physical
implementation. The outputs are model outputs.

**Decoder complexity and correlated-matching scope.** On the standard independent detector
graph at $d \in \{3, 5, 7\}$, `tjoin_decoder` agrees with PyMatching on **100.0% of total
matching weights** (§5.2). However, its component solver `_solve_component_max_saving` uses
an exact bitmask-DFS with a hard budget of `max_steps = 4000` per connected component: for
sub-threshold syndromes at $d \le 7$ components are small and the solution is exact, whereas
dense super-threshold components with $|U| \gtrsim 14$ odd vertices terminate at the best
matching found within 4,000 steps rather than running full $O(|V|^3)$ blossom shrinking.
Similarly, `decode_correlated` is a two-pass conditional-reweighting heuristic rather than
hypergraph belief-propagation + OSD.

**Calibration reproduces two of four published statements.** Both differences are
explained and neither is tuned; the test suite fails if either drifts toward *better*
agreement.

**Where the exact 1D $\Gamma_{\text{eff}}$ chance-constraint reduction holds and where it
breaks.** The reduction of $\Pr[F(\text{chain}; T_1, T_2) \ge F_{\text{req}}] \ge 1 - \varepsilon$
to the single 1D quantile $\gamma_{1-\varepsilon}$ of $\Gamma_{\text{eff}} = 1/T_1 + 1/T_2$
(§5.4) is exact when all nodes in a candidate chain share the same $(T_1, T_2)$ realization
and memory decay is Markovian ($\beta = 1$). For heterogeneous chains with independent
per-site priors $(T_{1,i}, T_{2,i})$ or non-Markovian stretched-exponential decay
($\beta > 1$), chain fidelity no longer factors through a single link-independent scalar
$\Gamma_{\text{eff}}$.

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

**Estimator scope.** The asymptotic decoy-state, BBM92, and Mode-Pairing paths use standard
asymptotic rate formulas, not finite-block composable-security proofs. The finite-key
decoy-state path implements the LCWX bound.

---

## 8. Availability

- Source: <https://github.com/KELLERBABG/QEL>
- Author ORCID: <https://orcid.org/0009-0009-5887-4257>
- Licence: Apache-2.0
- Citation metadata: `CITATION.cff`
- Documentation: `README.md`, covering usage, results, and the scope statement
- Verification: `py -m pytest -q` (1161 tests across 64 modules; 16,923 source lines and 13,060
  lines in `tests/`), `py -m quantumnet validate` (published comparisons, scored and explicitly
  unscored), `py scripts/claim_audit.py` (documentation drift), `py scripts/decoder_claim_check.py`
  (100.0% weight agreement and accuracy against PyMatching), `py scripts/ontology_audit.py`
  (5/5 ontology gaps)

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
