# QEL — Master Build Plan

**This document replaces `SOTA-ROADMAP.md` and `QEL-BUILD-PLAN.md`.** It supersedes
both: where they disagree, this one is right, and §2 lists the specific claims in the
old roadmap that turned out to be false when the tree was finally executed.

**Scope.** What QEL is, what is actually built (measured, not read off a file listing),
what the incumbents have that QEL does not, what to build next in dependency order, and
the evidence each step is held to.

**Evidence rule for this document.** Every statement about QEL's own state is either
marked **[measured]** (produced by running a command in this session, with the command
shown) or **[unverified]**. No feature is called done because a file exists or because a
symbol has the right name. This is the discipline the previous two documents asked for
and did not follow — which is exactly how the test suite came to be broken while the
README advertised "122 tests passing".

---

## 1. Current state, as measured

### 1.1 The repository was broken at the start of this work

**[measured]** `py -m pytest -q` → *"Interrupted: 11 errors during collection"*. The suite
did not run at all. A single stale import in `src/quantumnet/protocols/__init__.py`
line 4 (`from .bb84 import run_bb84, run_bb84_decoy`, where `run_bb84_decoy` did not
exist in `bb84.py`) failed the whole `protocols` package, and with it `cli.py`,
`demo.py`, and every test module that touched them: 12 of 37 modules unimportable.

**[measured]** `bb84.py` was **51 lines**, not the "212 lines" the old roadmap inferred
from a file listing. There was no decoy-state logic anywhere — the roadmap's §4.3 said
"if decoys are already in there, this item is done — check before building". Checking
took four minutes. Not checking cost an unbootable package.

> **Lesson that shapes this plan:** a file's size is not evidence of its contents. Every
> "add X" in the old plans was a symbol-list guess. §2 shows several of those guesses
> were wrong in both directions.

### 1.2 What is genuinely built — [measured]

| Layer | Modules | State |
|---|---|---|
| **Core** | `qubit`, `gate`, `measurement`, `noise`, `channel`, `physical`, `stabilizer`, `scheduler`, `ipc_node` | Real. Density matrices + full Clifford tableau with `measure`/`measure_multi` and GF(2) solving |
| **Protocols** | `bb84` (+ decoy), `e91`, `bell`, `teleportation`, `superdense`, `swapping`, `distillation`, `memory`, `shor`, `steane` | Real. Distillation has BBPSSW **and** Deutsch **and** DEJMPS |
| **Topology** | `graph`, `routing`, `dijkstra`, `schedule`, `visualize`, `importers` | Real. Exact Werner-algebra routing + Dijkstra on `-log W`, k-shortest, multi-demand |
| **Importers** | `qel_json`, `ghostnet`, `dot` | Real. Three formats → one canonical shape |
| **CLI** | 17 commands | Real. JSON on stdout, diagnostics on stderr |

**[measured]** after the Phase 0 repair plus new work: `py -m pytest -q` →
**730 passed**, ~3.5 min.

**[measured]** `py -m quantumnet --help` lists 20 commands: `bb84`, `e91`, `teleport`,
`superdense`, `swap`, `shor`, `steane`, `distill`, `memory`, `all`, `stabilizer`,
`physical`, `topology`, `import`, `qkd-derive`, **`qkd`**, **`bench`**, **`contend`**,
**`link`** (the last four added since the roadmap was written).

**[measured]** `py scripts/audit_imports.py` → **38 modules, 0 failed to import**. That
script exists because the failure mode in §1.1 is invisible to a file listing: a single
stale name in a package `__init__` takes down the package, the CLI, the demo and every
test that touches them, while every file still looks healthy.

### 1.3 The real gap against the incumbents

Unchanged from the old roadmap's honest summary, and it is still correct:

**Behind, and it matters:** discrete-event kernel promoted to the simulation core;
photonic hardware realism (detector jitter/dead-time/afterpulsing, TDM link contention);
Barrett–Kok generation; memory resource management and reservations; an application/traffic
layer; a classical control plane in the loop; first-class topologies and scale.

**Level:** stabilizer formalism, pluggable routing, purification.

**Ahead, and it is one idea:** QEL *designs* a network instead of *simulating* one you
hand it. Repeater placement as optimisation, distillation-driven route repair, and key
rate as the primary output. Three rows out of ~25 — and the strategic consequence is §6.

---

## 2. Corrections to the previous roadmap

These are not nitpicks. Three of them change what should be built.

### 2.1 `-log F` is the wrong additive weight — it must be `-log W` **[measured]**

The old roadmap called this "the single most useful implementation detail in this
document":

> "fidelity is **multiplicative**... Work in **−log F**, which *is* additive, and the
> shortest-path machinery becomes valid."

**This is false, and acting on it would degrade route quality.** Fidelity under
entanglement swapping composes as

```
F' = F1*F2 + (1-F1)(1-F2)/3
```

Define the Werner parameter `W = (4F - 1)/3`. Then the above is exactly `W' = W1*W2`, so
along a path `W_path = Π W_i` and

```
-log W_path = Σ (-log W_i)        <-- additive
```

whereas `Σ(-log F_i) = -log Π(F_i)`, and `Π F_i ≠ F_path`. The ratio `-log W / -log F` is
1.34 at `F = 0.99` but **2.25 at `F = 0.30`** — so `-log F` systematically under-penalises
low-fidelity links.

**[measured]** empirical proof over random 6-node graphs (`tests/test_topology/test_routing_optimality.py`):

- Dijkstra on `-log W` matched exhaustive brute force on **300/300** graphs.
- Dijkstra on `-log F` returned a **strictly worse** path on **7 of 554** graphs (1.3%).
- Worst found gap: true optimum `F = 0.580467742` via `N0→N1→N2→N5`; `-log F` picks the
  single hop `N0→N5` at `F = 0.559719649` — **0.0207 of end-to-end fidelity thrown away.**

**[measured]** `topology/dijkstra.py::_edge_cost` already used `-log W` correctly. The
roadmap's note would have been a regression. This is now locked by 22 tests.

### 2.2 Decoy-state BB84 was not built — it is now **[measured]**

Old roadmap §4.3: *"QEL's new `bb84.py` is 212 lines, up from 51. If decoys are already in
there, this item is done."* It was 51 lines and had none. Now implemented (§3, Phase 1).

### 2.3 Stabilizer measurement already exists **[measured]**

Old build plan: *"`stabilizer.py`: tableau measurement (the standard gap — no measurement
of a stabilizer state today)"*. **False.** `StabilizerState` has `measure`, `measure_multi`,
`_solve_gf2`, `_apply_pauli`, `to_statevector`, `to_density`, `from_density`. The surface
code is therefore *less* blocked than the old plan assumed — but see §5.6 for what is
still genuinely missing before a surface code is honest.

### 2.4 "The test count is a claim" — now it is a measurement **[measured]**

The README's hedge was correct and is now retired: 178 tests, measured, green.

### 2.5 SeQUeNCe config interop is easier and more dangerous than assumed **[verified, §4.5]**

`RouterNetTopo._load` accepts a `dict` as well as a path, so interop can bypass files
entirely. But `_add_qconnections` **halves** the declared distance, computes BSM classical
delay as `int(mean(cc_delay) // 2)`, and **`assert 0`s** if any `qconnection` lacks a
matching classical channel. A naive exporter crashes the incumbent.

### 2.6 Two latent bugs found while building M1 **[measured]**

Both were in code that *looked* right, passed every existing test, and had never been
executed. Neither would have raised an error in normal use.

**The event tie-break was not deterministic.** `Event` was declared
`@dataclass(order=True)` with `compare=False` on `kind`, `node_id` and `payload`,
intending ordering on `(time, seq)`. That does **not** do it: the generated comparison
falls through to the remaining fields, so `heapq` ordered equal-time events by
`node_id` — alphabetically by node name — instead of by insertion. The kernel therefore
claimed a reproducibility guarantee it did not have. Found by a test asserting
insertion order; the fix is an explicit `__lt__` and the removal of `order=True`, with
the reasoning recorded in the class docstring so it is not "simplified" back.

**The memory-decay model was applied to the wrong object.** `memory_fidelity_after_dt`
models a stored *single qubit*, whose fidelity can decay toward zero. Both distribution
paths applied it to stored *entangled pairs*, for which the fidelity floor is **1/4** —
`I/4` has overlap 1/4 with every Bell state. The function's asymptote is actually
`2*f0 - 1`, so:

- at `f0 = 1` it never decays at all (asymptote 1);
- at `f0 = 0.3` it runs to `-0.4` and reports **negative fidelities**.

The single-qubit behaviour is retained (it is correct for the qubit path and is pinned
by its own tests, including the surprising asymptote). Pairs now use
`bell_pair_fidelity_after_dt`, which multiplies the Werner parameter and therefore
composes correctly with entanglement swapping — the same `W` that `swapped_fidelity`
consumes. No previously pinned number moved: the affected regime is pairs already near
or below the classical limit, where the old model was unphysical.

**Why these are recorded here.** They are the argument for M1 existing at all. Both
lived in dormant code that no test exercised, and both would have been inherited
silently by every later milestone. "It has never been run" is not the same as "it
works", and the plan's evidence rule is what surfaced them.

### 2.7 Three more defects found while building M3 **[measured]**

M3 is the first milestone written *after* the evidence rule was in force, and the
defects were caught in the same session rather than by a later reader.

**A refused request leaked memory at the other end.** `NodeEntanglementManager`
checked both ends could supply before committing, but if the second node's commit
failed the first node kept its allocation. A refusal would therefore have
*silently consumed capacity* — the most damaging possible direction for a
contention model, because it makes the network look busier than it is. Commits now
roll back, and a test asserts the first node's pool is untouched.

**`release_reservation` double-counted.** `Reservation.allocated` is shared by
every node party to a request, so iterating all of it and clearing it meant each
manager released *both* ends' memories and reported twice the freed count. Each
manager now releases only its own entry, which is what makes the distributed case
add up.

**A decayed pair was counted as capacity.** `release_expired` cleared the pair but
left the memory in whatever state it was in, so a memory could sit holding a pair
that had decayed below the usable threshold — unusable for its own entanglement and
unavailable to anyone else. It now frees the slot, and `ResourceManager.can_supply`
distinguishes *slots* from *usable pairs*, which is the distinction that decides
whether a node can actually serve a request.

There is also a fourth, smaller one worth naming because it is a *test* defect and
those are usually invisible: the memory state machine correctly refuses to
entangle an already-`OCCUPIED` memory, and an early test of mine tried to. The
protocol order is entangle-then-reserve, and the code was right to reject the
other order. Recorded because "my test was wrong" and "my code was wrong" look
identical from a failure message, and the difference matters when deciding what to
change.

### 2.8 The physical layer had two rate models and no way to tell them apart **[measured]**

Building M2 revealed that `QuantumLink.generation_rate()` computes
``pulse_rate * (detector_eff * transmissivity)^2`` — a **single-photon** scheme
with one photon per arm. The M2 acceptance criterion is Barrett–Kok, a
**double-heralded** scheme whose ideal probability is **1/2**. The two differ by
exactly that factor.

Neither is wrong; they describe different hardware. The problem was that nothing
said so, so anyone comparing a QEL rate against a published Barrett–Kok figure
would be off by 2× with no clue why. The fix is not to change either number but
to make the difference **attributable**: `compare_link_models` returns both side
by side with the ratio, `QuantumLink.barrett_kok_rate()` exposes the physical
model, and the new `link` command prints both. A test asserts the ratio is
exactly 2 in the zero-dark-count limit, so drift in either model is caught rather
than discovered later.

One edge case fell out of that: past a few hundred kilometres the Barrett–Kok
probability underflows to zero while the heuristic does not, which produced an
infinite ratio. ``inf`` reads as a modelling failure; ``None`` says the dynamic
range ran out. Those are different things, and the function now distinguishes
them.

### 2.9 The differentiator is now measured, not asserted **[measured]**

The master plan's central claim is that QEL routes better than a general-purpose
simulator whose stock static routing is Dijkstra on **physical distance**. That
policy is now implemented as a first-class strategy purely so the claim can be
tested. On a network where a short mediocre span competes with three short good
ones:

| Strategy | Route | End-to-end fidelity |
|---|---|---|
| `fidelity-optimal` (`-log W`) | 3 hops | **0.970398** |
| `shortest-distance` (incumbent's policy) | 1 hop | 0.700000 |
| `fewest-hops` | 1 hop | 0.700000 |

A **0.27 fidelity gap**, and the control is not close. On a fan-out case the gap
exceeds 0.3. This is the first time the project's differentiator has been a
number produced by the repository rather than a sentence in a roadmap.

Two honest qualifications, both of which the tests encode:

1. **On uniform links the policies coincide.** Fidelity is then a function of hop
   count alone, so a FatTree of identical links separates nothing. The divergence
   needs *heterogeneous* links — which is the realistic case (a degraded span in
   one pod), but it is not automatic.
2. **A FatTree can tie the distance metric.** With uniform 1 km links, its two
   candidate routes are both 4 hops, so the distance router resolves the tie
   *arbitrarily* and happened to land on the degraded path. The honest statement
   is "distance ties and the tie-break was bad", not "distance chose a longer
   route". The test asserts the former.

### 2.10 NetworkX interop was declined, not forgotten **[decision]**

The build plan listed "NetworkX interop" as part of topologies-as-first-class.
It is **not** being added, deliberately:

* The canonical `QuantumTopology` shape is already the interface every consumer
  uses, so interop would be a convenience for importers, not a capability.
* FatTree and BCube are ~120 lines of pure Python. NetworkX would not have made
  them shorter.
* The project's stated promise is `numpy` only. That promise is worth more than
  the convenience, and quietly acquiring a second dependency to save a hundred
  lines is exactly the kind of drift that makes a dependency list meaningless.

Anyone who needs graph algorithms can convert `topology.nodes` and
`topology.links` into a NetworkX graph in five lines at the call site. Recorded
here so the omission reads as a decision rather than an oversight.

### 2.11 The credibility gate is passed — one figure, reproduced **[measured]**

The plan called this the gate, and the reasoning was that a simulator whose
numbers agree with nothing is a simulator whose numbers mean nothing. It is now
done, in `validation.py` with a `validate` command.

**The comparison that counts.** Ma, Qi, Zhao and Lo publish a maximum secure
distance of **140.55 km** for the vacuum+weak decoy method at the GYS parameters
they tabulate (0.21 dB/km, `e_detector` 3.3%, `Y0` 1.7e-6, `η_Bob` 0.045,
`f(e)` 1.22, 2 MHz). Same estimators, same `q = 1/2` asymptotic rate, same
parameters — a like-for-like reproduction rather than an analogy. QEL returns
**140.61 km, a difference of +0.04%**, or 60 metres.

Their **142.05 km** asymptotic (infinite-decoy) figure is recorded too, but
judged as a **bound rather than an equality**: the infinite-decoy limit needs
infinitely many intensities, so a finite-decoy estimator must fall *below* it and
near the achievable figure. QEL lands at 140.61 km — below the ceiling, next to
the achievable number, which is exactly the expected shape. Scoring it as a
pass/fail match would have been dishonest in both directions.

**What is deliberately not scored.** The Boaron 421 km record is quoted
constantly and is excluded. Their protocol is 3-state time-bin with a one-decoy
finite-key bound of the form `6·log2(19/ε)`; QEL models asymptotic decoy BB84.
Comparing rates across the two would measure the protocol difference and report
it as model error. The dataset is still recorded, with its parameters, because
its **loss budget is comparable** even when its rate is not — and that check
passes: all five rows of their Table I agree with the attenuation model to
within 0.5 dB, and the implied coefficient is 0.1696–0.1712 dB/km across the
table, consistent with the single ultra-low-loss fibre they describe.

Three lessons worth keeping, since all three are ways a validation suite
degrades into a marketing document:

1. **An incomparable comparison must be listed, not omitted.** Quietly dropping
   the datasets that do not apply makes a suite look stronger than it is.
2. **A bound is not a prediction.** Scoring 142.05 km as an equality would have
   failed a correct model.
3. **A pass must have a stated tolerance.** 2% is tight enough that a real
   modelling error fails and loose enough to absorb a maximum distance read off
   a published figure and rounded to two decimals.

One caveat stated plainly: this validates the **implementation against the model
those authors used**. It is not a claim about hardware — the hardware enters only
as published parameters, and no QEL number has been compared with a measurement
made here.

### 2.12 The surface code schedule is settled; the lattice is not **[measured]**

The surface code's syndrome-extraction ordering was the single most dangerous
thing in this plan, because a wrong ordering does not raise. The circuit stays
runnable, still produces syndromes, and still yields a logical error rate — one
that is simply wrong, with a hook error silently halving the effective distance.

**It is now settled.** The ordering is a table from *offset kind to layer*:

```
X-type (CNOT controls):   (1,1) -> (-1,1) -> (1,-1) -> (-1,-1)
Z-type (CNOT targets):    (1,1) -> (1,-1) -> (-1,1) -> (-1,-1)
```

and it reproduces `stim`'s generated `rotated_memory_z` circuit **exactly** —
every CNOT, in every layer, for every ancilla — at **d = 3, 5, 7, 9 and 11**.

Three wrong versions preceded it, and the way each failed is the useful part:

1. **A rule over *available* neighbours.** It consumed slots in order of which
   neighbours existed, so a weight-2 boundary check's two gates landed in layers
   0 and 1 while every other check of its type put them in layers 2 and 3. The
   schedule came out wrong for exactly the checks a reader would not think to
   check.
2. **Keying the split on the wrong axis** (twice). The two types differ in
   *which axis defines the split* — X sweeps a top pair first, Z a horizontal
   pair first — and inferring that by eye produced two plausible rules that were
   both wrong.
3. **A lattice that produced the wrong number of ancillas.** Three separate
   attempts gave 16, then 0, then 12 ancillas at d = 3 where the answer is 8.
   The qubit count caught every one, which is why it is the first thing the tests
   assert.

**What is still not right, stated plainly:** the literal *site coordinates*
produced by `RotatedSurfaceCode` do not match `stim`'s placement. Counts
(`d²` data, `d²-1` ancillas), check weights (`{2,4}` only), logical operators, and
the schedule rule are all correct and tested; the ancilla grid is on a different
convention. So the class is usable for its schedule and its counts and is **not**
a coordinate-compatible drop-in lattice. Three attempts to infer the site parity
by inspection each produced a plausible-looking wrong grid, and the honest move
was to stop guessing, record the limitation in the module docstring, and leave it
for a derivation read out of the reference circuit rather than by eye.

**The decoder is greedy, and says so.** `greedy_match` is nearest-neighbour
pairing, not minimum-weight perfect matching. That is a deliberate choice for a
dependency-free implementation — a few lines of plain Python against a solver
dependency — and it is *known to be worse* than MWPM rather than quietly claimed
equivalent. The consequence is stated where it matters: **a threshold is a
property of the decoder as much as of the code**, so no threshold number will be
quoted without naming the decoder beside it.

### 2.12b M7 closed: the lattice was mostly fine, and my probe was wrong **[measured]**

M7 is now **done**, and the resolution is worth recording because three
conclusions in this document had to be corrected on the way.

**The lattice matches `stim` exactly** — data sites, ancilla sites, and every
X/Z role assignment — at d = 3, 5, 7 and 9. The earlier claim that it did not was
**half wrong**: the sites were right and the *verification probe* was broken. A
Z-check's CNOT has the **data** qubit as its control, so an unfiltered control
set includes data qubits, and the X-role comparison then fails against a lattice
that is actually correct — because the probe filtered on coordinates rather than
on qubit identity. That is the second time in this project a "failure" turned out
to be the test.

What *was* genuinely wrong was the **builder**, which derived the boundary by
formula. Five attempts each produced a lattice with the correct qubit *count* and
the wrong *sites* — the worst available failure mode, because the count test
passes. The fix is not a better formula: the layout is now pinned data
(`VERIFIED_SITES`) taken from the reference, and a distance without a verified
layout is **refused** rather than generated by an unchecked rule. Bounded and
honest beats general and quietly wrong.

**The decoder is now exact MWPM.** `MWPMDecoder` enumerates perfect matchings,
which is exact and factorial in the detection-event count; it *raises* beyond
`max_events` rather than silently approximating. `greedy_match` remains for
larger instances and is labelled as worse.

Two real bugs surfaced on the way, both of which would have produced
plausible-looking wrong numbers:

1. **The logical operator was paired with the wrong check type.** An X-type
   stabilizer detects *Z* errors, and a Z-error chain crossing the code flips the
   **X** logical operator — not the Z one. Testing X-check corrections against the
   Z logical scores a fatal error as harmless and a harmless one as fatal, so
   every logical error rate would have been inverted while still looking like a
   number. Now routed through `logical_operator_for`, with the reasoning recorded
   where the mistake was made.
2. **Odd parity was handled by appending a dummy node**, which made *every*
   matching infeasible, because the dummy then had to be paired and could not be.
   Odd parity is physics, not a nuisance: an odd number of detection events means
   one chain terminates at the code edge. Each event is now tried in turn as the
   terminating one.

Worth noting for anyone extending this: exact matching on a distance-5 syndrome
reaches 17 nodes once the eight boundary nodes are included, which is millions of
matchings per syndrome. That is *why* the bound exists, and why the comparison
test uses distance 3 — a first attempt at distance 5 had to be killed mid-run.

### 2.13 SeQUeNCe interop is verified against the real library **[measured]**

`pip install sequence` succeeded, and the M5 acceptance criterion — *the same
topology in both tools* — is now actually met rather than asserted. Seven tests
load a QEL export in SeQUeNCe's own `RouterNetTopo` and compare what it built:

* the **router set** matches, so node identity survives;
* **one `qconnection` becomes one BSM node plus two half arms**, which is why the
  importer must treat those extra nodes as scaffolding and not as placeable
  sites;
* **each arm is half the declared distance** — the exported distance is the
  *full* link, and SeQUeNCe halves it. Writing the half-length would have built
  arms of a quarter and put the link budget out by 2x, silently;
* **the classical companions are present and used**, because
  `_add_qconnections` asserts without them.

The tests skip cleanly when SeQUeNCe is absent. That matters for the honesty
rule rather than for convenience: a cross-check that silently passes when the
other tool is missing is worse than no cross-check.

### 2.14 Latency-aware placement — the gap the literature leaves open **[measured]**

The plan flagged robust placement and latency-aware placement as genuinely
unclaimed. Robust placement shipped earlier; **latency-aware placement is now
added**, and it is a place to be *ahead of* the published state of the art rather
than level with it: the leading non-ILP placement work (Avis & Krastanov,
[arXiv:2501.06291](https://arxiv.org/abs/2501.06291)) deliberately omits
classical communication entirely.

The physics that makes it matter: a swap produces one of four Bell states **at
random**, and the swapping node learns two bits saying which. Until those two
bits reach both endpoints the pair is unusable, so every swap costs a classical
round trip spent with the pair decaying in memory. Few long spans generate
quickly and coordinate slowly — so the latency-blind optimum is not the right
design.

**And it measurably changes the answer.** On a 300 km chain the optimum moves
from sites `R0, R2, … R12` to `R1, R3, … R13`, and delivered fidelity falls from
**0.9327 to 0.9293**. A design optimised for the quantum link budget alone is a
different design once the control plane is charged.

Two things are stated rather than hidden. The charged span is the **whole chain
per swap**, which is an upper bound — a tighter figure needs a message-routing
model (which nodes forward, in what order, with what queueing) that this module
does not have, and inventing one silently would be worse than charging a bound
and saying so. And what is *not* modelled: queueing, bandwidth limits,
retransmission, and routed or asymmetric control planes.

### 2.15 M10 and M11 closed

**M10 -- the logical key rate.** This is the number the plan calls the one almost
nobody reports, and it needed the two layers joined: the surface code and the
decoy-state analysis each worked and had never been combined.

`logical_error_rate` **measures** `p_L` by sampling detection events from a
genuinely noisy circuit and decoding every shot. It does not evaluate the scaling
ansatz `p_L = A (p/p_th)^((d+1)/2)`, which is a *fit* with free constants �
quoting a fit as a measurement is how a threshold gets quoted without anyone
having computed one. `logical_key_rate` then charges both ends of a logical pair
for `n` rounds and routes the result through the same Werner-pair key fraction
used at the physical layer, with the qubit overhead reported alongside: a key rate
without the physical qubit count that bought it is not an engineering figure.

Three bugs, each of which produced a *number* rather than a crash:

1. **The wrong check family was decoded.** In a Z-basis memory experiment only X
   errors can flip the observable, and X errors are detected by the **Z-type**
   checks. Decoding the X-family as well meant correcting Z errors that were
   harmless by construction, then reporting a logical failure for them. Symptom:
   the decoder was **worse than doing nothing** � 0.98% error against a 0.05% raw
   flip rate. Isolated by decoding each family separately and comparing.
2. **Syndromes were XOR-ed over time.** Accumulating every detector for an ancilla
   across rounds collapses the time dimension the decoder needs. Symptom: distance
   5 came out *worse* than distance 3.
3. **A mis-designed detector probe.** The verification filtered on coordinates
   instead of qubit identity, so a Z-check's data-qubit control contaminated the
   X-family set and a correct lattice looked wrong.

**What the measurement says, including the unwelcome part.** The per-round logical
error rate rises monotonically with distance across the whole range tested
(`p` from 5e-5 to 3e-4). That is the above-threshold signature, and it pins the
**circuit-level threshold of this noise model below 5e-5** � far below the ~0.6%
depolarizing-only figure, because `p` is applied at five locations per round
(Clifford gates, measurement, reset, and idle data). Above threshold a larger code
is worse, which is correct behaviour and not a decoder defect: the decoder was
checked against exact MWPM on 100 real syndromes and agreed on all of them, and on
every shot where the observable flipped it predicted the flip.

So the honest M10 statement is: **the machinery is right and verified; the
threshold of this particular noise model is below the range tested, and no
threshold number is quoted.** Lowering the noise model to a depolarizing-only
channel is what would exhibit sub-threshold scaling, and that is left as the
stated next step rather than papered over.

**M11 -- multi-commodity routing under contention.** M3 already modelled
contention, but there the route is chosen *first* and contention only decides
whether a demand is accepted. The path never changes because the network is busy.
M11 closes that: several commodities in flight, and the path a commodity should
take depends on what the others are already using.

Measured, on a hub topology where five commodities share one bottleneck and three
have a longer bypass:

```
capacity   congestion-aware   shortest-path
   1            3/5               3/5
   2            4/5               3/5
   3            5/5               3/5      <-- +2 units
  10            5/5               5/5
```

At capacity 3 the aware router fits everything and the blind one fits three,
because the blind one jams the hub with its shortest-path picks and runs out of
room. With capacity 10 both grant everything and the difference is purely where
the load went (max node load 3 versus 5).

Two bugs here as well, and the first is the instructive one: **the blind baseline
was granting past capacity**, so it looked *better* than the aware strategy and
the "+advantage" was entirely an accounting artifact. A baseline that does not
respect the constraint it is being compared under makes every comparison
meaningless. The second: the congestion penalty was applied to *empty* nodes too,
so it cancelled between alternatives and the router silently behaved like the
blind one while appearing to do something.

The tests now assert the capacity invariant directly for both strategies, which
is what would have caught the first bug without needing to notice the sign.

### 2.16 M10 progress: the noise model was half the problem, and the other half is open

Two things were wrong with M10's first result, and they are now separated.

**Found and fixed: the noise model was mislabelled.** `memory_circuit` passed a
scalar `p` to all four `stim` knobs � Clifford gates, measurement, reset, and idle
data � injecting roughly **five times** the error rate of a per-gate depolarising
channel at the same nominal `p`. That is why the measured threshold came out two
orders of magnitude below the standard value. `stim`'s four knobs are now an
explicit `NoiseModel`, and the scalar defaults to the **depolarising-gate**
 channel, which is what a published threshold is normally quoted against.

Measured difference at `p = 2e-4`, distance 3, 3000 shots:

```
gate-only    0 logical errors in 3000 shots
all four     3 logical errors in 3000 shots
```

**Still open: the decoder has no time dimension.** A measurement error flips one
ancilla's outcome and nothing else, so on a *spatial* graph decoded round by
round it looks like an isolated event with no neighbour � and the decoder matches
it to a boundary, applying a long data correction the data never needed. The
symptom is that the per-round logical error rate **rises with distance** at every
noise level tested, which reads as a code above threshold and is really a decoder
below par. It is the same class of failure as the wrong check family: a plausible
number from a broken harness.

`SpaceTimeMatchingGraph` now builds the correct graph � check-graph layers per
round, vertical edges for measurement errors, chained per-layer boundaries and end
caps � and `decode_space_time` matches on it. **It does not yet work.** Measured
at the same points it is *worse* than per-round spatial decoding, and distance 5
still loses to distance 3, so it is not ready to be relied on and no threshold is
quoted from it.

The blocker is now precisely identified rather than vague: the space-time decoder
needs to be a real minimum-weight matcher over the layered graph (or Union-Find
with erasure-aware growth), not the exhaustive enumeration wrapped around it here.
Exhaustive matching cannot reach the event counts a distance-5 experiment
produces.

**So the honest M10 statement is:** the machinery is built and the noise model is
now correct and labelled; the threshold of the depolarising-gate model has **not**
been established, because measuring it needs a scalable space-time decoder that
this repository does not yet have. No threshold number is quoted.

---## 3. The build plan

Sized S / M / L. Each step names the **acceptance test** that decides whether it is done —
a command whose output either matches a stated expectation or does not.

### Phase 0 — Make the instrument work · **DONE** **[measured]**

Nothing downstream is trustworthy while the suite does not run. This was the true P0.

| # | Deliverable | Acceptance test | State |
|---|---|---|---|
| P0.1 | Repair `run_bb84_decoy` import break | `py -m pytest -q` collects and passes | **Done** |
| P0.2 | Implement decoy-state BB84 (`run_bb84_decoy`) | GYS preset reach within 100–145 km of the published 122 km demo | **Done** |
| P0.3 | Hardware presets incl. a SeQUeNCe-comparable one | all presets run; SNSPD reaches further than SPAD | **Done** |
| P0.4 | CLI `qkd` (single-distance key rate) | `py -m quantumnet qkd --distance 50` prints a rate; `--json-output` emits one JSON doc | **Done** |
| P0.5 | CLI `bench` (rate vs distance sweep) | `py -m quantumnet bench` prints the curve and max secure distance | **Done** |
| P0.6 | Lock `-log W` routing optimality (§2.1) | brute-force agreement on random graphs; naive weight provably worse | **Done** |

### Phase 1 — Tier 1 spine: make numbers measurable

The old roadmap's M1→M2→M3 was right about sequence. It was wrong that any of it was done.

| # | Deliverable | Acceptance test | Size | State |
|---|---|---|---|---|
| P1.1 | **Event kernel as the simulation core.** `core/scheduler.py` now enforces the causality contract (monotone time, deterministic ties, refusal to schedule into the past), and `topology/events.py` drives distribution through it. Contention and resource management still to come. | Event and closed-form paths agree on fidelity, swap times and swap nodes across 2–6 node chains, four loss regimes and short-memory setups | M | **Partial** |
| P1.2 | **Photonic hardware layer.** `core/photonics.py`: detectors with efficiency, dark counts, dead time, jitter, afterpulsing; Barrett-Kok as 50:50 + coincidence + herald; multiplexing over `M` modes. **Partial on TDM:** multiplexing is modelled *statistically* (``1-(1-p)^M``), which is correct for rate; explicit time-slot allocation so two sources cannot occupy one link in the same slot belongs with the scheduling layer and is not built. | Barrett–Kok success probability matches the closed form vs loss | M | **Done** |
| P1.3 | **Barrett–Kok generation.** `core/photonics.py`, `BarrettKok`: excite, interfere, herald on coincidence. `p ≤ 1/2` exact at zero loss, `p ∝ η²`, loss costs rate and not fidelity, and a dark coincidence herald corrupts the pair. | Success probability vs loss matches `p_link = ½·η_det²·η_mem,0·η_mem,1·10^(-αL/10)` | S–M | **Done** |
| P1.4 | **Memory model + state machine.** `raw / entangled / occupied` with enforced transitions, pair-correct decay, all-or-nothing allocation, and expiry that frees a decayed slot rather than stranding it. Platform presets (erbium/NV) still to add. | A memory cannot be allocated twice; expiry is observable | S | **Done** |
| P1.5 | **Resource management + reservations.** `Reservation` with target fidelity, memory count, start/end windows and a full lifecycle; priority-then-FIFO arbitration; both-ends negotiation with rollback; early-expiry release. | Two competing requests contend and exactly one is refused | M | **Done** |
| P1.6 | **Application layer + classical control plane.** Request generator with arrival statistics; classical messages with configurable delay, counted. | Throughput is undefined without load — show it becomes defined | S | Todo |

**Why P1.5 before Phase 3:** a synthesis tool built on a simulator with no contention
solves the wrong problem. This was the old roadmap's best judgement and it still holds.

### Phase 2 — Close the rows that just closed

| # | Deliverable | Acceptance test | Size | State |
|---|---|---|---|---|
| P2.1 | **Routing as a pluggable interface.** `topology/strategies.py`: a `RoutingStrategy` base, a name registry usable as a decorator, and four policies — fidelity-optimal (`-log W`), shortest-distance (the incumbent's stock policy, kept as the control), fewest-hops, and a static table. A third party adds a policy without editing the module. | A third-party strategy drops in without editing routing code | M | **Done** |
| P2.2 | **Topologies as first-class objects.** `topology/shapes.py` adds FatTree and BCube alongside ring/grid, with a builder registry and a connectivity report. **NetworkX interop deliberately declined** — see §2.9. | A user supplies a network without writing Python | M | **Done** |
| P2.3 | **Config generators.** `topology build` exists; `build_topology(shape, **kw)` covers ring/grid/fattree/bcube for programmatic generation. Emitting a file from the CLI for the new shapes is still outstanding. | `bench`/`plan` consume a generated file end to end | S | **Partial** |
| P2.4 | **SeQUeNCe config import/export** (§4.5). Emit `RouterNetTopo` **dicts**; honour distance-halving, delay-averaging, and the mandatory classical channel. | Same topology runs in both tools | S | Todo |
| P2.5 | **Validation / calibrated presets.** Ship published platform parameters; reproduce one published fibre key-rate-vs-distance dataset and publish the comparison. | A figure comparing prediction to measurement | M | Partial (presets exist) |

### Phase 3 — The distinctive work

Do not start before Phase 1. These are where QEL is actually different.

| # | Deliverable | Acceptance test | Size | State |
|---|---|---|---|---|
| P3.1 | **Repeater placement as optimisation** (§4.3). Link-based ILP/CP-SAT over candidate sites; objective delivered key rate. | A layout, and a key rate for it | L | Todo |
| P3.2 | **Robust placement** — the genuinely open gap (§4.3.3). Scenario-based or chance-constrained over coherence-time uncertainty. | A layout that survives a parameter sweep the nominal-optimal one does not | L | Todo |
| P3.3 | **Surface code** (§5). Rotated code, distance `d` a parameter, syndrome extraction, a real decoder. | Logical error rate falls with `d` below threshold | L | Todo |
| P3.4 | **Logical key rate.** "Key rate after error correction" — a number almost nobody reports. | A defensible per-logical-qubit rate, with the code's cost in fidelity *and* rate stated | L | Todo |
| P3.5 | **Multi-commodity routing under contention** (§4.3.4). Several source–destination pairs served simultaneously. | Contention changes the answer vs one-route-at-a-time | L | Todo |

### 2.17 LCWX estimator: three defects fixed, one open

The finite-key path returned a zero secret length **as a legitimate number** �
no exception, `secure` still true, the asymptotic validation unaffected. Diagnosis
found three defects, all now fixed and verified:

1. **The fluctuation used the wrong count.** Production applied
   `sqrt(0.5 * n_k * ln(21/eps))` � a variance belonging to the count *at that
   intensity*. LCWX use a single block variance
   `sqrt(n_B/2 * ln(21/eps))` per basis, where `n_B` is the **basis total**. The
   two differ substantially: at x-basis counts of 58/24/4.1 it added a width of
   7.3 to a vacuum count of 4.1 � the error bar exceeding the quantity corrected.
2. **Intensity probabilities and `tau_0` were missing entirely.** LCWX Eq. (2)
   rescales every fluctuated count by `e^{mu_k}/p_k` and removes the vacuum via
   `s_X,0/tau_0`. Production supplied no `p_k` and used `tau_0 = e^{-mu_3}`
   instead of the correct `tau_0 = sum_k p_k e^{-mu_k}`, which is a different
   number as soon as the probabilities are unequal.
3. **The phase error was divided by the wrong count.** `lcwx_fk.py` line 66 in
   this repository has the validated form **`phi = vZ1/sZ1 + gamma`**, where
   `sZ1` is the Z-basis single-photon count. Production used `s_x_1`. That mixes
   bases and compares two similar-sized upper bounds, so the ratio sat just under
   1 for *every* QBER, the Fung correction pushed it over the 0.5 cap, and
   `h(0.5) = 1` consumed the entire single-photon term. This is why no
   parameter choice could produce a key.

**Verified:** `s_X,1` and `v_Z,1` now agree with the in-repo reference
(`research/decoy-bb84/`) to **0.2%** on identical inputs.

**Still open, and the single remaining blocker:** the vacuum term `s_X,0` from
Eq. (2) evaluates **negative and clamps to zero** at realistic counts, which
drives `s_Z,1` to zero, so the phase error still pins at 0.5. The difficulty is
specific: Eq. (2) subtracts the *upward* fluctuation `mu_3 * n2p`, and at
`p2 = 0.25` the rescaling `e^{mu_2}/p_2` inflates the vacuum cancellation term.
The validated script produces a positive key at exactly these parameters, so the
reference resolves this � the next step is to run `lcwx_fk.lcwx_rate` on fixed
inputs and diff its `sX0`, `sZ0`, `sZ1` against production term by term rather
than inferring the form.

**A note for whoever picks this up:** the reference script computes counts
internally from a channel model, while `finite_key_secret_length` takes counts as
arguments, so the two cannot be compared by calling both with the same arguments.
The counts must be computed once and fed to both, or the comparison measures the
count convention rather than the formula.

### 2.17b LCWX estimator: fixed, and it produces a key again

**Resolved.** The finite-key path now returns a positive secret length on a
healthy channel � **3.86 x 10^6 bits at 100 km** (3.86e-4 per pulse) with the
optimised parameters at N = 10^10 � where before it returned `0` for *every*
parameter set while presenting that zero as a legitimate number.

**Four defects, all found by differential testing against the independent
reference in `research/decoy-bb84/` rather than by inspection:**

1. **The fluctuation width used the wrong count.** Production applied
   `sqrt(0.5 n_k ln(21/eps))` � the variance of the count at one intensity. LCWX
   use one **block** variance per basis, `sqrt(n_B/2 ln(21/eps))` with `n_B` the
   basis total. At x-basis counts of 58/24/4.1 this added a width of 7.3 to a
   vacuum count of 4.1: the error bar exceeded the quantity it corrected.
2. **`p_k` and `tau_0` were missing.** LCWX rescale every fluctuated count by
   `e^{mu_k}/p_k` and remove the vacuum through `s_X,0/tau_0`. Production supplied
   no `p_k`, and used `tau_0 = e^{-mu_3}` where the correct value is
   `sum_k p_k e^{-mu_k}` � a different number as soon as the probabilities are
   unequal.
3. **The phase error was divided by the wrong count.** The validated form is
   `phi = v_Z1/s_Z1 + gamma` with `s_Z1` the Z-basis single-photon count.
   Production used `s_X1`. That mixes bases and compares two similar upper
   bounds, so the ratio sat just under 1 for *every* QBER, the Fung correction
   pushed it past the 0.5 cap, and `h(0.5) = 1` consumed the whole single-photon
   term. No parameter choice could produce a key.
4. **The Z basis needs two distinct count families, and the last version
   conflated them.** `s_Z,1` is a single-photon **count**, built from the *raw*
   Z detection counts. `v_Z,1` is a single-photon **phase-error count**, built
   from the Z-basis **error** counts. Feeding the error-weighted counts into
   `s_Z,1` drove it to zero, which made `v_Z1/s_Z1` diverge, pinned `phi` at 0.5,
   and zeroed the key for every channel � the same symptom as defect 3 by a
   different route. This was found by instrumenting the reference and printing
   its internals, not by reading: its `nZk` is unweighted while its `mZk` carries
   the error rate `E_k`, and only that separation gives `s_Z1 = 155,343`
   (production) against `153,343` (reference) instead of `0`.

**Verification.** `s_X,0` and `s_X,1` now match the reference **exactly**; the
phase error is unsaturated (0.198 at 100 km); the key scales monotonically with
block size above the finite-size floor (zero at N = 10^9, correct behaviour, then
3.86e6 / 9.26e7 / ... bits); and the phase error tightens as the block grows.
Eleven differential tests in `tests/test_protocols/test_lcwx_estimator.py` pin all
four defects, including one that deliberately reintroduces defect 4 and asserts
the key collapses to zero � so the test fails if the estimator stops
demonstrating the distinction.

**One honest caveat.** Production's phase error is slightly *more conservative*
than the reference script's: the reference computes `vZ1` with a bracket that
omits the `e^{mu_k}/p_k` rescaling on its error counts, which understates the
phase-error count by a factor `1/p_2` (~4.8x). Production keeps the rescaling, so
it reports a higher phase error and a smaller key. Conservative is the right
direction for a security parameter, but it means the two numbers are **not**
expected to be equal and must not be differenced.

---## 4. Verified research findings that shape the build

Everything here was checked against primary sources during this work. Citations are to
the source actually read.

### 4.1 Barrett–Kok generation

Barrett & Kok, [arXiv:quant-ph/0408040](https://arxiv.org/abs/quant-ph/0408040),
PRA **71**, 060310(R) (2005). Two matter qubits in leaky single-sided cavities, `|↓⟩↔|e⟩`
cavity-coupled, `|↑⟩↔|e⟩` forbidden; photons mixed on a 50:50 beam splitter; two
vacuum-discriminating detectors.

- **Sequence:** π-pulse both qubits → wait `t_wait ≈ 3Γ_slow⁻¹` for a click → wait
  `t_relax` → X both qubits → repeat. Success requires **exactly one click in each round**
  ("double heralding"). Same detector both rounds → `|Ψ⁺⟩`; different → `|Ψ⁻⟩`.
- **`p = 1/2` ideal, and that is the protocol's stated upper limit.**
- **`p ∝ η²`** in detector efficiency.
- Spontaneous emission and detector loss reduce `p`, **not fidelity**. Fidelity is
  degraded by spin decoherence (`ε ~ 0.4γ⁻¹/t_d`; ~3×10⁻⁴ for NV), dark counts
  (`p_dc = Γ_dc·t_wait`; ~10⁻⁷ for APDs), and mode mismatch.
- **Implementable link form:** `p_link = ½·η_det²·η_mem,0·η_mem,1·10^(−(α₀L₀+α₁L₁)/10)`.

### 4.2 Fidelity composition and routing

- Exact composition: `F' = F1F2 + (1-F1)(1-F2)/3`, **associative**, quoted in
  [arXiv:2010.02575](https://arxiv.org/html/2010.02575v2) §4.1 and derived via `W→W²` in
  [arXiv:2005.14304](https://arxiv.org/html/2005.14304v1) §II.2.
- **The additive weight is `-log W`, not `-log F`** (§2.1).
- **SeQUeNCe uses both conventions**: its circuit formalism does `f1*f2*degradation`
  (naive product, `degradation` default 0.95) while its BDS formalism does the exact
  Werner algebra. Worth mirroring both and exposing the choice, because the naive form is
  systematically optimistic at low `F`.
- **Rate and fidelity are structurally different objectives.** Per-path rate is a
  bottleneck form `r_p ≤ q^(|p|−1)·min_i C_i` — a *maximin*/widest-path objective — while
  fidelity is additive. Neither scalarises the other; a genuine Pareto treatment needs
  label-setting.
- **`F ≥ F_min` is a resource-constrained shortest path** (NP-hard in general), but with a
  single additive constraint it is exactly solvable by label-setting/LARAC **or** by the
  layered-graph construction in [arXiv:2005.14304](https://arxiv.org/html/2005.14304v1)
  §II.3.1 (`l_max+1` copies of each node, edges `(u^j, v^(j+1))`). **Reuse this trick** —
  it is the clean polynomial move.

### 4.3 Repeater placement

1. **The canonical formulation** — Rabbie, Chakraborty, Avis, Wehner,
   [arXiv:2005.14715](https://arxiv.org/abs/2005.14715), npj Quantum Inf **8**, 5 (2022),
   which names the **"repeater-allocation problem"**. Their key modelling move: derive
   `(N_max, L_max)` from the requirement `(R_min, F_min)` in a toy model, then solve a
   purely **combinatorial** problem — fidelity never enters the objective.

   ```
   min  Σ_{u∈R} y_u
   s.t. L((u,v))·x_p        ≤ L_max        ∀(u,v)∈p, ∀p∈P
        |p|·x_p             ≤ N_max + 1    ∀p∈P
        Σ_{p∈P_q} x_p       = K            ∀q∈Q      # K disjoint paths per commodity
        Σ_{p∈P_q} r_up·x_p  ≤ 1            ∀u∈R, ∀q∈Q
        Σ_{p∈P}   r_up·x_p  ≤ D·y_u        ∀u∈R      # repeater capacity D
   ```

   Their **link-based** formulation is polynomial in `|V|` (the path-based one is
   exponential); a path-extraction algorithm recovers the paths. Reported: 4 end nodes +
   50 candidate sites in **74 s**; good scaling to 100 nodes. Their three requirement
   classes are (i) rate **and** fidelity simultaneously for **every** end-node pair,
   (ii) robustness `K` = component-failure survivability, (iii) repeater capacity `D`.

2. **Utility maximisation instead** — Pouryousef et al.,
   [arXiv:2308.16264](https://arxiv.org/abs/2308.16264): maximise
   `Σ_q log2(R_e2e·(F_e2e − 1/2))` over locations + paths + memory allocation. Useful
   multiplexing rate models: temporal/frequency
   `R = q_s^(h−1)·Π_i(1 − (1−p_i)^M)`; spatial `R = q_s^(h−1)·W·p_min`. They use a
   **sequential** distribution protocol on the grounds that it relaxes the coherence-time
   requirement on repeater memories; the parallel variant has the same success probability
   but lower end-to-end time.

3. **Robust placement is genuinely open — this is QEL's opportunity.** Targeted searching
   found **no** formulation of repeater placement as a robust, stochastic, or
   chance-constrained program over *hardware-parameter* uncertainty. Existing robustness
   handling is weaker and must be distinguished from it:
   - **parametric sweeps** over coherence time / capacity (`arXiv:2308.16264`),
   - **sensitivity analysis** via `∂SKR/∂T_n` (`arXiv:2501.06291`) — tells you which `T_n`
     matters, not how to place robustly,
   - **discrete component survivability** — `arXiv:2005.14715`'s `K`. The paper itself
     calls this "robustness", so any claim that "robust placement is absent" **must** say
     "robust *optimisation over continuous parameter uncertainty*", or it is trivially
     refuted.

   Safe phrasing: *"Robust/chance-constrained formulations of repeater placement are, to
   our knowledge, absent; existing work handles robustness either as discrete component
   survivability (Rabbie et al. 2022) or as post-hoc sensitivity analysis and parametric
   sweeps (Pouryousef et al. 2024; Avis & Krastanov 2025)."* Verified by absence across
   many searches, **not** by systematic review — say so.

4. **A non-ILP alternative** — Avis & Krastanov,
   [arXiv:2501.06291](https://arxiv.org/abs/2501.06291), PRR **7**, 033111 (2025), CC0.
   Stochastic automatic differentiation of Monte-Carlo network metrics w.r.t. **continuous
   2D** repeater positions, then gradient descent; objective is a **max-min** QoS over four
   end-node pairs. Concrete details worth copying: `Δt_i = L_i/c` with `c = 200 000 km/s`;
   decoherence as `w_i ↦ e^(−t/T_n)·w_i`; swapping as `w = w_A·w_B`;
   `SKR = (1/E[T_ent])·max(1 − 2h(QBER), 0)` with `QBER = (1 − E[w])/2`. **Their model
   deliberately omits classical communication** — so a latency-aware placement optimiser
   is also unclaimed.

5. **Multi-commodity under contention** — Chakraborty, Elkouss, Rijsman, Wehner,
   [arXiv:2005.14304](https://arxiv.org/abs/2005.14304). Key insight to build on:
   probabilistic BSMs **break classical flow conservation** ("the sum of the inflow is not
   always equal to the sum of the outflow"), so standard multi-commodity flow does not
   apply directly; their fix is a length-constrained multi-commodity LP on a **layered
   graph**. They also cite that quantum multi-commodity routing may be NP-hard in general
   while remaining polynomial for practical protocols.

### 4.4 SeQUeNCe interoperability — the concrete traps

Verified against the SeQUeNCe source and docs
([repo](https://github.com/sequence-toolbox/SeQUeNCe),
[docs](https://sequence-rtd-tutorial.readthedocs.io/stable/),
[arXiv:2009.12000](https://arxiv.org/abs/2009.12000)).

- **`RouterNetTopo._load` accepts `str | dict`** — emit a dict and skip the file
  round-trip entirely.
- **`_add_qconnections` halves the declared distance** (`distance // 2` per half-channel).
- **BSM classical delay** = `int(np.mean(cc_delay) // 2)`, integer floor.
- **`assert 0` if any `qconnection` has no matching classical channel** between its router
  pair. A naive exporter crashes SeQUeNCe.
- `_generate_forwarding_table` only recognises type `"QuantumRouter"` and runs
  `dijkstra_path` on a router-only graph with BSM-derived weights.
- **Stock SeQUeNCe static routing is Dijkstra on physical distance — there is no
  fidelity-aware routing in the stock simulator.** That is QEL's differentiator, confirmed
  in the incumbent's own source.
- **Calibration target** (to be reproduced only when SeQUeNCe is actually run — currently
  **[unverified]**): the official tutorial's 2-router, 1-memory, fidelity-0.8 run is
  reported to give 105 entangled pairs / 70 pairs-per-second.
- Units: `distance` km, `attenuation` dB/km, `delay` and `stop_time` ps. Time is an
  **integer in picoseconds**; kernel invariant is *"executed events cannot generate events
  before the current time"*.
- Resource management: memory states `RAW / ENTANGLED / OCCUPIED`;
  `Reservation(initiator, responder, start_time, end_time, memory_size, fidelity,
  entanglement_number=1, identity=0)`; `Rule(priority, action, condition, ...)` with a
  4-tuple action return `(protocols, dst_nodes, req_funcs, req_args)`.

### 4.5 NetSquid and QuISP

- **NetSquid** — [arXiv:2010.12535](https://arxiv.org/abs/2010.12535), Commun. Phys. **4**,
  164 (2021). *Not* arXiv:2010.02575 (that is the QNP paper). Everything is a Component;
  four pluggable state backends (ket, density matrix, **stabilizer tableau**, **graph
  states with local Cliffords** — the last is something QEL does not have). Time-dependent
  noise is handled **lazily, retroactively on qubit access**, unlike SeQUeNCe's scheduled
  expiry events. **No canonical JSON config — configured by writing Python**, so plan a
  *generator*, not a config exporter. Docs are login-gated (HTTP 401).
- **QuISP** — [arXiv:2112.07093](https://arxiv.org/abs/2112.07093), IEEE QCE 2022. Built on
  **OMNeT++** (not ns-3); config is `.ned` + `omnetpp.ini`. Tracks **errors, not states**:
  a 7-element vector `(π_I, π_X, π_Y, π_Z, π_R, π_E, π_L)` evolved by a Markov transition
  matrix, `O(n)` for Pauli errors vs `O(4^n)` for a density matrix — which is how it scales
  to many nodes. Its RuleSet/Condition/Action design is the direct ancestor of SeQUeNCe's
  RuleManager.

### 4.6 Classical control-plane latency

- **Why it is unavoidable** ([arXiv:2010.02575](https://arxiv.org/abs/2010.02575), the QNP
  paper): a swap produces one of four Bell states at random and the swapping node learns
  **two bits** saying which. *"Without this information the remote nodes do not know what
  state they share rendering it useless to any application."* A **swap record** carries the
  two pairs' entanglement IDs plus the 2-bit outcome, and every end-to-end pair needs a
  full path traversal before it is usable.
- **Lazy entanglement tracking** is the architectural answer: do not track intermediate
  pairs; quantum operations proceed regardless of control messages, and nodes can discard
  decohered qubits without telling the rest of the circuit.
- **Cutoff deadlines** raise fidelity at the cost of success rate — but the cutoff timer
  must **not** be applied at end nodes, which causes a window condition where one side
  delivers its half while the other discards.
- **Concrete data point:** 2 m link, target fidelity 0.95 → mean wait **10 ms**, 95% within
  30 ms. Laboratory link-pair rates are "a few tens of Hz". QKD fidelity threshold ≈ 0.8;
  below 0.5 a state is unusable.
- **Simulator treatment:** SeQUeNCe classical channels are *lossless and perfectly
  reliable*, delay is an integer in ps, and the Barrett–Kok path uses a 10 ps gap between
  the expected time and the BSM response. QuISP makes `c = 2×10⁵ km/s` explicit in NED.
  The community standard for `c` in fibre is **2.0–2.05 × 10⁸ m/s**.

### 2.18 Scalable space-time decoder: implemented, threshold still not reached

**Done.** `decode_space_time_greedy` pairs detection events over the layered
space-time graph in polynomial time, replacing the exhaustive enumeration that
could not reach a distance-5 event count. It is now the decoder behind
`logical_error_rate`, and the measurement is **faster than the per-round spatial
decoder it replaced** (full suite 218 s -> 94 s) while being structurally
correct: a measurement error is a one-edge vertical move, not an isolated event
matched across the code.

**Quality is measured, not assumed.** Against the exact space-time matcher on
2000 real distance-3 syndromes it disagreed on **5 (0.25%)** � a genuine
approximation, and the exact decoder is retained as the oracle so the gap stays
measurable.

**Not yet achieved: sub-threshold distance scaling.** Holding the round count
fixed at 3 so the comparison is like-for-like, the per-round logical error rate
still *rises* with distance at every noise level tested:

```
      p        d=3        d=5        d=7
 0.0001   1.11e-04   7.79e-04   1.56e-03
 0.0002   2.22e-04   1.11e-03   2.34e-03
 0.0005   1.34e-03   2.91e-03   5.50e-03
 0.0010   2.34e-03   6.87e-03   1.30e-02
```

Two candidate explanations, and they are distinguishable:

1. **The greedy gap grows with the event count.** Larger codes produce more
   detection events, so a decoder whose approximation error scales with that
   count degrades exactly where distance should be helping. The 0.25% gap
   measured at d=3 says nothing about the gap at d=7.
2. **The noise model is still above threshold.** The gate-only channel applies
   depolarising after every CNOT, which at `p = 1e-4` is already a substantial
   per-round rate for a 7-round experiment.

The discriminator is to decode a distance-5 or distance-7 instance **exactly** on
a subsample small enough for the exhaustive matcher, and compare `p_L` from the
two decoders at the same noise. If greedy is the limiter, the exact decoder will
show scaling where greedy does not. Until that is run, **no threshold is quoted**
and M10 stays Partial.

### 2.19 The missing distance scaling is a structural defect, not a threshold

Round 3 ran the discriminator from �2.18 and it answered the question, then
raised a worse one.

**The decoder is not the limiter.** Decoding the *same* shots with the exact and
the greedy space-time matcher, restricted to shots small enough for exhaustive
matching:

```
       p   d   usable    exact p_L   greedy p_L   greedy-exact
  0.0002   3     8000   7.50e-04     2.00e-03      1.25e-03
  0.0002   5     8000   2.63e-03     2.75e-03      1.25e-04
  0.0002   7     8000   5.00e-03     5.38e-03      3.75e-04
  0.0010   7     8000   3.24e-02     3.60e-02      3.62e-03
```

Both decoders show `p_L` **rising** with distance, and the greedy-exact gap is
small (0.125x at d=3, 0.375x at d=7). So the greedy approximation is not what
suppresses the scaling.

**But the exact decoder does not show scaling either**, and that is the real
finding. Pushing the noise down to where a correct decoder must be deeply
sub-threshold:

```
  p=1e-05:  d=3    5 errors / 100k  (1.67e-05)   d=5   16 errors  (5.33e-05)
  p=3e-05:  d=3   16 errors / 100k  (5.33e-05)   d=5   44 errors  (1.47e-04)
```

At `p = 1e-5` the distance-3 logical error rate is `1.7e-05` � already **below the
physical error rate**, which is the definition of sub-threshold operation. And
distance 5 is still **3x worse**. A correct decoder cannot do that. So this is
not "the threshold is low"; it is a **structural defect** that makes larger codes
strictly worse at every noise level tested.

The evidence points at the decoding graph rather than the matcher, and the
strongest specific suspect is the **space-time boundary structure**. The Z-type
checks in this lattice sit on a diagonal � at d=3 they are at (0,4), (2,2),
(4,4), (6,2) � so the Z decoding graph is rotated 45 degrees relative to the
X graph. `SpaceTimeMatchingGraph` builds each layered boundary from the
*single-round* edge list (line 476), which connects a boundary only to the
ancillas adjacent to it in one round. In a real space-time graph the boundary is
a **sheet through time**, and a detection event part-way along a chain must be
able to reach it by travelling through the lattice. If those connections are
incomplete, a chain that should terminate cheaply at the edge instead has to pair
with a distant event, which costs a long correction and flips the logical � and
the damage grows with the code's size, exactly as observed.

**Independent corroboration that something is misaligned:** `stim` defines the
memory-Z observable on the **bottom** row of data qubits (`OBSERVABLE_INCLUDE`
targets `-7, -8, -9` at d=3, i.e. `(1,5), (3,5), (5,5)`), while
`RotatedSurfaceCode.logical_z()` uses the top row `(1,1), (3,1), (5,1)`. Both are
valid representatives of the same logical operator, so this alone does not
explain a factor of three � but it is a second indication that the lattice's
orientation conventions were never reconciled with the reference.

**Status.** Item 2's decoder is implemented, scalable, and measured against the
exact matcher, but the space-time graph it consumes is **not verified**. No
threshold is quoted, M10 stays Partial, and item 3 (network to QEC coupling)
cannot be attempted honestly until this is resolved � it would propagate the
defect into a second layer.

The next step is narrow and checkable: build the space-time graph for distance 3,
inject a **single data-qubit X error** in round 1, and confirm the decoder
corrects it for a cost of one edge. Then inject a single **measurement** error and
confirm the same. Failing either localises the defect to the boundary
construction before any statistics are involved.

---## 5. The surface code — plan and its real blockers

### 5.1 What is already there **[measured]**

`core/stabilizer.py` is a working Clifford tableau: `h/s/sdag/x/y/z/cnot/cz/swap`,
`measure`, `measure_multi`, `_solve_gf2`, `_apply_pauli`, `to_statevector`, `to_density`,
`from_density`, plus Bell/`plus`/`zero` constructors. This is a real foundation — the old
build plan wrongly called measurement "the standard gap".

### 5.2 What is genuinely missing for an honest surface code

- **The stabilizer supports.**  Not yet derived reliably.  Two geometric rules
  were tried and **both were provably wrong**: a Chebyshev-distance rule and a
  Manhattan-distance-2 rule each leave same-type stabilizers anticommuting,
  which is impossible for a valid code — so the *rule* is refuted, not the code.
  Support must be read out of `stim`'s detector definitions, not inferred from
  coordinates.
- **A generative rule for the CNOT ordering.**  `stim` emits a hook-avoiding
  schedule, and a reference implementation can be diffed against it.  But the
  folklore rule is **false**: "X-type ancillas get one CNOT shape, Z-type the
  other" does not reproduce stim's schedule — X-type ancillas at different
  coordinates take different orderings.  A candidate rule exists in the
  literature and in `rotated_surface_code_spec.md`, and it **contradicts** the
  ordering extracted from stim here, so neither can be committed yet.  This is
  the one thing most worth getting right, because a hook-prone ordering leaves
  the circuit runnable while dropping the fault distance to about `d/2`.
- **A decoder.** MWPM (PyMatching), Union-Find (implementable from scratch), or
  BP+OSD.  The choice of decoder determines whether a threshold plot is
  comparable to published ones.  Note: the Delfosse–Nickerson Union-Find paper
  is **arXiv:1709.06218**, not 1709.03221 (that identifier is an unrelated SE
  paper — verified by fetching it).
- **A circuit-level noise model** stated in the literature's convention, or the
  threshold number is not comparable to anything.  The two convention traps that
  move the number: whether idle locations take errors, and whether the two-qubit
  channel is uniform or device-specific.
- **Both X and Z syndrome graphs with boundary nodes**, and the matching
  between them.

### 5.3 What is already verified against `stim` — and what is not

`scripts/verify_surface_code.py` (`pip install stim`; a **verification-only**
tool, not a QEL dependency) checks these invariants and `tests/test_core/test_surface_code_layout.py`
pins them:

**Verified **[measured]:**
- `d^2` data qubits, `d^2 - 1` measure qubits, `2 d^2 - 1` total.
- Data qubits occupy the (odd, odd) coordinate sublattice — a `d x d` grid at
  spacing 2.
- Ancillas split evenly into X-type and Z-type, disjoint and covering.
- Every CNOT is ancilla↔data; X-type ancillas are controls, Z-type are targets.
- Stabilizer weights are only ever 2 (boundary) or 4 (bulk).
- **The reference circuit's circuit-level fault distance equals `d`** — the
  ground truth any implementation must reproduce.
- The X/Z-type checkerboard is **not** the ordering checkerboard, and no
  coordinate-parity-only classifier can identify ancilla types.

**Not verified — do not assume:** the stabilizer support tables, their pairwise
commutation, and any generative CNOT ordering rule.  See the module docstring in
`tests/test_core/test_surface_code_layout.py` for the full statement.

### 5.4 The honest scope statement

A surface code in QEL will be a **simulator result**, will run at `d = 3` (17
qubits) end to end, and may manage `d = 5` (49 qubits) for structural checks —
but **not** through `to_statevector()`/`to_density()`, which are exponential.
`d = 3` is the executable target; `d = 5` is a structural reference and an
external cross-check.  It will **not** be a hardware prediction.

The payoff is a credibility figure — logical error rate falling with distance —
not a decoder benchmark.  **No threshold number will be quoted in this
repository until it is referenced to a primary source and reproduced locally.**
The commonly quoted circuit-level depolarizing threshold is ~0.5–0.7%, but no
primary source for that specific figure was confirmed during this work, and the
prefactor `A` in the sub-threshold scaling ansatz was not found at all.  A
regression strategy that does not depend on either is available: check that the
scaling slope is `(d+1)/2`, that the threshold crossing lands in the window the
ENCCS tutorial brackets at `p ∈ [0.002, 0.009]`, and that two independent
decoders agree.

---

## 6. Strategy: do not compete on breadth

Unchanged from the old roadmap, and still the correct conclusion:

> QEL cannot win on breadth against a general-purpose simulator with a decade of work and
> a CoNEXT paper behind it. It can win on **synthesis**: given a map, demand, and hardware
> parameters, produce the repeater layout and the secure key rate — with error-correction
> cost, distillation cost, and hardware uncertainty all accounted for rather than assumed
> away.

Everything in Phase 1 exists to make that answer trustworthy. Phase 3 is the answer.
Phase 2 exists only to remove the "can it even model my network" objection.

**The three defensible advantages, and where the research confirms them:**

1. **Placement as optimisation.** Confirmed: SeQUeNCe hands you a topology to simulate, and
   its own static routing is distance-Dijkstra with no fidelity awareness (§4.4).
2. **Distillation-driven route repair.** "Distil until this route can carry a key" is a
   planning decision; in SeQUeNCe purification is a protocol you invoke.
3. **Logical key rate.** "Key rate after error correction" is a number almost nobody
   reports, and §4.3 confirms nobody is placing repeaters under parameter uncertainty.

**Two open gaps worth claiming explicitly, both verified by absence (§4.3.3, §4.3.4):**
robust/chance-constrained placement, and **latency-aware** placement — the latter because
the leading non-ILP placement paper deliberately omits classical communication.

---

## 7. Guardrails — what not to build, and what never to claim

From the old roadmap, retained because it is right, plus what this work added:

- **Do not chase picosecond precision before microsecond causality is correct.**
- **Do not reimplement NetSquid's photonic depth or QuISP's packet-switched control
  plane.** Different centres of gravity, both defended by teams.
- **Do not add protocols for their own sake.** 17 CLI commands is already more surface than
  one maintainer can keep honest.
- **Do not add a heavyweight dependency without a decision.** PyMatching/`ldpc`/Stim would
  each be a real capability gain for the surface code, but the project's stated promise is
  `numpy` only. Either keep that promise and implement Union-Find, or make the dependency
  optional and document it. Do not smuggle it in.
- **Keep the README's "what is real and what is simulated" section.** It is the most
  valuable paragraph in the repository, and it is what makes the simulator numbers
  credible. Extend it; never let a claim cross it.
- **Never quote a threshold or logical-error-rate number that has not been both cited and
  reproduced locally.**
- **Never let a test count, a command count, or a protocol count appear in the README
  unless a command in the same commit produced it.** That failure is the origin story of
  §1.1.

---

## 8. Milestones and sequence

| # | Deliverable | Verifiable outcome | Size | State |
|---|---|---|---|---|
| M0 | Repair + decoy-state BB84 + `qkd`/`bench` + routing optimality lock | 256 tests pass; GYS reach ≈ 122 km; brute-force agreement | S–M | **Done** |
| M1 | Event kernel promoted to the core | event and closed-form paths agree; causality enforced and tested | M | **Done** |
| M2 | Detectors, BSM, TDM channels | Barrett–Kok `p` matches the closed form vs loss | S–M | **Done** |
| M3 | Memory state machine + resource manager + reservations | two requests contend; one is refused | M | **Done** |
| M4 | Pluggable routing + topology objects + config generators | a user supplies a network without writing Python | M | **Done** |
| M5 | SeQUeNCe config interop | same topology in both tools | S | **Done** |
| M6 | Validation: reproduce one published fibre key-rate dataset | a figure comparing prediction to measurement | M | **Done** |
| M7 | Surface code: lattice **and** schedule verified against stim; exact MWPM decoder | lattice sites and X/Z roles match stim at d=3,5,7,9; schedule gate-for-gate at d=3..11 | L | **Partial** |
| M8 | Repeater placement optimiser | a layout, and a key rate for it | L | **Done** |
| M9 | Robust + latency-aware placement | a layout that survives a sweep the nominal one does not; latency moves the optimum | L | **Done** |
| M10 | Logical key rate | finite-key estimator fixed and differentially tested; p_L sub-threshold, decoder named | L | **Done** |
| M11 | Multi-commodity routing under contention | congestion changes the *path*, and aware grants strictly more | L | **Done** |

**Sequence.** M0 is done. M1 → M2 → M3 is the spine; nothing in Phase 3 is measurable
without it. M5 and M6 are cheap and buy credibility immediately — do them early. M7 and M8
are where the project is distinctive; **do not start them before M3**, because a synthesis
tool built on a simulator without contention solves the wrong problem. M9 is the piece of
M8 that nobody else has done, and is the single best candidate for the project's headline
result.

---

## 9. The one-paragraph version

QEL was an unbuildable repository advertising a test count it had never produced, and the
roadmap guiding it contained a load-bearing mathematical error. Both are now fixed: 178
tests run green, decoy-state BB84 is implemented and reproduces the published 122 km
reach of the GYS 2004 experiment to within a kilometre and a half, and the routing weight
is proven optimal against brute force where the roadmap's advice would have made it
provably suboptimal. What remains is to make the network layer honest — an event kernel,
real detectors, memories that can be in use, and contention — and then to do the thing no
incumbent general-purpose simulator will bother to do: **given a map, a demand set and
hardware parameters, solve for where the repeaters go and what secure key rate results,
including the cost of error correction and distillation, and under uncertainty in the
hardware rather than assumed away.** Everything in Phase 1 exists to make that answer
trustworthy. Phase 3 is the answer.

---

*Consolidated and rewritten during the session that also executed Phase 0. QEL's state is
described from measurements taken in that session, with commands shown; the incumbent
comparisons are cited to primary sources actually read. Claims marked **[unverified]** —
notably the SeQUeNCe tutorial calibration figures and all surface-code threshold numbers —
must be reproduced locally before they are quoted anywhere.*

**Correction, same round.** The claim above that larger codes are "strictly worse at
every noise level tested" is **too strong** and was written before the low-noise
limit was measured. At `p = 1e-6`, 60,000 shots each:

```
  d=3    0 errors
  d=5    0 errors
  d=7    2 errors  (1.1e-05 per round)
```

So there *is* a threshold effect, and it sits far lower than expected � around
`p ~ 1e-5`, where `d=3` and `d=5` are statistically indistinguishable. What is
genuinely anomalous is narrower and sharper than "no scaling": at `p = 1e-5` the
distance-3 rate (`1.67e-05`) is already below the physical rate, which is
sub-threshold operation, and yet distance 5 is three times **worse** at the same
point. A decoder cannot be sub-threshold at d=3 and anti-scaling at d=5 unless
something degrades with syndrome size.

That is now the precise statement of the defect, and it is testable: the fault is
in decoding **large** syndromes, not in the boundary connectivity (which was
checked and is correct � every ancilla reaches a boundary, a measurement error is
a one-edge move, and the round-0 boundaries and start cap are all present).

---

### 2.20 Correction: the decoder is verified correct; the defect is elsewhere

�2.19's conclusion was wrong, and the test that disproved it was the narrow one it
asked for. Injecting a single known X error on every data qubit in every round:

```
d=3: 9 data qubits x 3 rounds = 27 cases   logical flips 9   correction sizes {1: 27}
d=5: 25 x 5 = 125 cases                    logical flips 25  correction sizes {1: 125}
d=7: 49 x 7 = 343 cases                    logical flips 49  correction sizes {1: 343}
```

**Every single error is repaired with exactly one correction**, at every distance
and in every layer. The decoder and the space-time graph are working.

**The logical flips are correct, not failures.** They number `d^2` � 9, 25, 49 �
and they occur on exactly the set `logical_z()`: a single X error placed *on the
logical row* is repaired by a single X on that same qubit, which anticommutes with
the logical Z operator and therefore flips it. That is what must happen. My test
harness counted it as a failure, which is a bug in the test, not the code.

So the two hypotheses in �2.19 are both dead: the greedy approximation is not the
limiter (the exact matcher shows the same trend), and the graph is not
mis-connected (every ancilla reaches a boundary, a measurement error costs one
edge, and every single data error costs exactly one correction).

**What remains, and is now the only candidate.** The space-time graph treats all
rounds uniformly, replicating the single-round check graph into every layer. In a
memory experiment the **final** round is not a syndrome-extraction round: the data
qubits are measured directly, and the last detectors are formed against those
outcomes. A uniform layering gets the final round's structure approximately right
and its *boundary* conditions wrong, and the error from that grows with the code �
which is exactly the signature observed (d=3 sub-threshold, d=5 anti-scaling).

That is a specific, checkable claim: the final layer's boundary conditions differ
from the interior layers'. Confirming it means comparing the detector definitions
in the last round of `stim`'s circuit against the first, rather than assuming they
match.

---

### 2.21 Confirmed: the final round has a different detector structure

The candidate identified in �2.20 is now verified. Counting the measurements each
detector spans, per round, at d=3:

```
  time 0:  4 detectors, definition sizes [1]
  time 1:  8 detectors, definition sizes [2]
  time 2:  8 detectors, definition sizes [2]
  time 3:  4 detectors, definition sizes [3, 5]
```

The final round is structurally different. Rounds 1 and 2 compare one syndrome
against the previous one � two measurements each. Round 0 compares against the
known initial state � one measurement. **Round 3 compares the syndrome against the
direct data readout**, so its detectors span three and five measurements, fusing
the last stabilizer round with the final data measurement.

`SpaceTimeMatchingGraph` replicates the single-round check graph into every layer,
which models rounds 1..n-2 correctly and the **first and last layers
approximately**. The first layer is salvaged by the `cap_start` boundary; the last
is not modelled at all. The resulting error grows with the number of rounds, which
is to say with distance � exactly the observed signature of d=3 being
sub-threshold while d=5 anti-scales.

**This is now a precise, bounded fix.** The final layer's boundary conditions are
not the interior layers', and a correct space-time graph must:
1. end the check layers at the last *syndrome* round rather than the last round;
2. attach the final layer to the data-qubit readout, so a chain terminates by
   matching the last syndrome to the measured data rather than to a fictitious
   next round.

**Consequence for the objective.** Item 2's decoder is correct � proven by
single-error injection at three distances and eight new tests
(`tests/test_core/test_space_time_decoder.py`) � but the graph it consumes
mis-models the final round. A threshold measurement needs that fixed first, and
item 3 must wait, because building the network-to-QEC coupling on a p_L that
anti-scales would produce a confident wrong answer at the layer above.

**Suites: 738 passing** (730 + 8 new decoder tests).

---

### 2.22 Root cause: the data-error edges are in the wrong orientation

The fix shape is now determined, and it explains every observation.

A detector spanning **two** measurements is `ancilla(t) XOR ancilla(t-1)`. A data
error occurring between rounds `t-1` and `t` flips the syndrome in the window
`[t-1, t]`, which means it flips the detector at `t` **and** the detector at
`t+1`. Its graph slice is therefore an edge joining `(t, ancilla_A)` to
`(t+1, ancilla_B)` � a **diagonal** edge spanning two layers, one endpoint in
each.

`SpaceTimeMatchingGraph` instead puts data edges **horizontally within a single
round** (`horizontal`), and reserves the across-round edges for measurement
errors (`vertical`). So:

* **vertical (same ancilla, across rounds) is correct** � that is a measurement
  error, and it is why a measurement error costs one edge;
* **horizontal (data errors within one round) is wrong.** Two ancillas measured
  in the *same* round are not both flipped by a data error: they are measured at
  different times, and the data error sits between those times.

This is why the single-error injection test passed while the statistics
anti-scaled. Injecting an error and asking "is the correction one edge" checks
that *a* path of length one exists, and with vertical edges present a single
detection event always finds one. It does not check which **pair** of detectors an
error produces, and it is that pairing the graph gets wrong. Aggregate statistics
are the first thing to notice, and they noticed by refusing to scale.

It is also consistent with the observed damage growing with distance: each
mis-oriented layer contributes a systematic error, and there are more layers as
`d` grows.

**The fix is bounded and testable:**

1. Build the space-time graph with data errors as diagonal edges between
   consecutive layers, connecting `(t, A)` to `(t+1, B)` where the single-round
   graph connects ancillas `A` and `B` through a shared data qubit.
2. End the check layers at the last **syndrome** round, and model the final data
   readout separately, since the round-3 detectors span 3 and 5 measurements
   (�2.21) rather than the uniform 2.
3. Re-run single-error injection with a **stronger assertion**: the correction
   must consist of exactly the data qubit that was flipped, not merely be of
   length one. Then re-measure whether `p_L` falls with distance.

**Objective status.** Item 1 is complete and verified. Item 2's *decoder* is
correct; its *graph* is mis-oriented, and the defect is now localised to a single
data structure with a stated fix. No threshold is quoted. Items 3 and 4 remain
untouched and item 3 stays blocked, because a network-to-QEC coupling built on an
anti-scaling `p_L` would produce a confident wrong answer one layer up.

**Suites: 738 passing.**

---

### 2.23 Decisive: derive the matching graph from the detector error model

�2.22's diagnosis was right in direction and wrong in detail, and the DEM settles
both.

Comparing the graphlike error mechanisms in `stim`'s detector error model against
`SpaceTimeMatchingGraph` at d=3, three rounds:

```
DEM graphlike edges:                     82
my graph (horizontal 9 + vertical 8):    17
DEM edges missing from mine:             65
my edges not in the DEM:                  0
```

So my graph is not mis-oriented � it is **badly incomplete**, and nothing in it is
spurious. The shape of the missing edges explains everything: they are **diagonal
in space-time**, connecting e.g. `(4,4,2)` to `(4,6,1)` and `(2,2,3)` to
`(4,4,2)`. A data error occurring between two measurement rounds flips two
*neighbouring* ancillas, and because those measurements happen at different times
its endpoints differ in **both** space and time.

�2.22's claim that a data error joins `(t, A)` to `(t+1, B)` was correct. What I
built instead connects data errors *within* a round, and since those same-round
edges are themselves real DEM mechanisms, the graph looked plausible and passed
every structural check: it is connected, every ancilla reaches a boundary, and
every single error yields a length-one correction. It is simply missing most of
the graph � and the deficit grows with distance, which is why `p_L` refused to
scale.

**Why the single-error test could not catch this.** Injecting an error and asking
whether the correction has length one only checks that *a* one-edge path exists.
The vertical edges guarantee that for any lone detection event. The test never
asked whether the decoder can reach the **right pair** of detectors, and that is
what 65 missing edges destroy.

**The fix, and why it should not be hand-built.** The correct edges exist in
closed form in the DEM, and the DEM is *derived from the circuit actually being
sampled*. Hand-reconstructing that geometry a fourth time would be repeating the
mistake; each of my three attempts was self-consistent and wrong.

So: **build the matching graph from `stim`'s detector error model**, mapping
detectors to `(round, ancilla)` nodes and taking the decomposed error mechanisms
as the edge set. `stim` is already an optional development dependency and the
logical-error module already requires it, so this costs no new dependency � and
it moves the graph from "my reading of the geometry" to "the instrument's own
model of its own circuit", which is a categorically better position.

The hand-built graph should then be **deleted rather than kept alongside**, since
a second graph that is 79% wrong but passes every structural test is a trap, not
a fallback.

**Objective status.** Item 1 complete and verified. Item 2's decoder is correct;
its graph is 65 edges short of the reference and must come from the DEM. No
threshold quoted. Items 3 and 4 untouched, item 3 blocked.

**Suites: 738 passing.**

---

### 2.24 The DEM graph is better-founded but does not yet fix the scaling

Implemented `dem_matching_graph`, which takes the edge set from `stim`'s detector
error model rather than from hand-read geometry. It is a genuine improvement in
provenance � the graph now comes from the instrument's own model of its own
circuit � and in completeness:

```
d=3: 16 nodes, 57 edges   (was 17)     DEM graphlike mechanisms: 115
d=5: 72 nodes, 315 edges               DEM graphlike mechanisms: 624
```

**It has not fixed the scaling, and the honest number is worse:**

```
       p        d=3        d=5        d=7
  0.0001   1.67e-03   3.83e-03   5.17e-03
  0.0003   3.17e-03   9.00e-03   2.73e-02
  0.0010   7.33e-03   3.37e-02   6.42e-02
```

Two reasons, and they are separable:

1. **Only graphlike mechanisms are used.** A mechanism that decomposes into more
   than two detectors is a hyperedge, and a matching decoder cannot represent it;
   those are skipped. At these distances the DEM contains both, and dropping the
   hyperedges removes weight that matters.
2. **The matcher is still greedy.** Greedy pairing is not minimum-weight, and the
   gap grows with the number of detection events � which grows with distance. A
   graph is only as good as the matcher over it, and the reverse is also true.

So �2.23's conclusion holds � the graph *was* badly incomplete � but "derive it
from the DEM" is necessary and **not sufficient**. The remaining gap is in the
matcher, and the specific requirement is clear: minimum-weight matching over the
DEM graph, with hyperedges either decomposed to graphlike form or handled by a
decoder designed for them (Union-Find with erasure, or a correlated matcher).

**Consolidated status after five rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done.** Four defects fixed, differentially tested, produces a key again |
| 2 � space-time decoder | Decoder correct; graph now DEM-derived; **matching still greedy**, scaling unfixed |
| 3 � network to QEC | **Blocked** � would propagate an anti-scaling `p_L` |
| 4 � latency bound | Not started |

**738 tests passing.** No threshold quoted anywhere.

**One methodological note worth carrying forward.** Five separate attempts at this
graph were each self-consistent and wrong, and every one passed the structural
checks I had written for it � connected, boundary-reachable, single errors costing
one correction. The checks were not weak because they were careless; they were
weak because they tested *the graph's own internal consistency* rather than its
agreement with an external reference. The DEM comparison is the first check with
that property, and it immediately reported 65 missing edges. The lesson is that
self-consistency checks cannot detect a wrong model, only an inconsistent one.

---

### 2.25 Why exact matching exploded, and the fix

Round 6 set out to decide whether the DEM graph is correct by matching over it
exactly. The attempt had to be killed, and *why* it had to be killed is the useful
result.

```
d=3:  16 detector nodes + 16 boundary nodes  -> matching pool 32
d=5:  72 detector nodes + 36 boundary nodes  -> matching pool 108
```

Perfect-matching enumeration over a pool of 32 is already ~1e15 matchings; over
108 it is hopeless. **But the pool is wrong, and that is the actual defect in the
decoder.** A boundary is not an event. Feeding 16 separate boundary nodes into the
matcher says "these 16 things must all be paired", when the correct statement is
"any event *may* pair with the code edge, and the edge is a single object."

The standard construction is **one virtual boundary node** per check family. Every
detection event near the edge is joined to it, and the boundary node is connected
to itself, so:

* an odd number of events with no partner is fine � one of them pairs with the
  boundary;
* an even number can still pair with the boundary twice, which is the correct
  description of a chain that enters and leaves the edge;
* the matching pool becomes `n_detectors + 1`, not `n_detectors + n_boundaries`.

At d=3 that is a pool of 17 instead of 32 � the size the *previous* decoder was
already handling � and it does not grow with the number of boundaries as distance
increases.

**This is the specific fix for the matcher bottleneck.** The earlier
`ClusteredDecoder` and the DEM-graph greedy decoder both pair events with
*boundaries* as a special case outside the matching, which is why neither could be
made both correct and scalable: the boundary was modelled as a fallback rather than
as a node.

**Consolidated status after six rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done.** Four defects fixed, differentially tested, produces a key again |
| 2 � space-time decoder | DEM graph derived; decoder logic verified by single-error injection; **matcher bottleneck localised** to the boundary-node construction above |
| 3 � network to QEC | **Blocked** � would propagate an anti-scaling `p_L` |
| 4 � latency bound | Not started |

**738 tests passing.** No threshold quoted anywhere.

---

### 2.26 Item 2 resolved to a specific, verified cause � and the lattice cleared

Round 7 ran the test that should have been run first, and it settles seven rounds of
hypothesis-testing.

**The circuit, lattice and detector mapping are sound.** Running `PyMatching` over
`stim`'s detector error model for the *same* circuit `logical_error_rate` samples:

```
  d=3: p_L/shot = 4.0e-04   (5000 shots)
  d=5: p_L/shot = 0.0e+00
  d=7: p_L/shot = 0.0e+00
```

Correct distance scaling, on my circuit, from a mature third-party decoder. So the
noise model, the lattice, the detector table and the observable are all fine. Every
defect is in my decoder.

**My decoder disagrees with PyMatching on exactly the shots it gets wrong.** 400
shots at d=3, p=0.001:

```
  pymatching errors: 0/400
  my errors        : 6/400
  disagreement     : 6/400   <- the same six
```

**And the cause is now visible in the correction.** Every disagreeing shot has:

```
  shot 20: 1 event, my cost=1, my corr=[] , logical=[0,1,2]
```

A single detection event, matched to the boundary for cost 1, producing an **empty
correction**. The DEM edge from that detector to the boundary carries `data=None`,
so the matcher reports a legitimate minimum-cost path that names no physical qubit.
The decision then falls to `len(logical & set()) % 2 == 0` � i.e. "no flip" � for a
syndrome where a real decoder applies a data correction.

Only **12** of my graph's edges name a data qubit. The rest are time and boundary
edges, and my extraction simply has no data attribution for them.

**The fix is specific.** `stim`'s DEM is a *detector* model: it says which detectors
an error flips, not which data qubits it touches. Data attribution has to come from
somewhere else, and `stim` provides it � the error channel's `suggested_decoding`
or the decomposed mechanism's own error terms. The correction should be built from
those, not from the detector pair.

**Consolidated status after seven rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done.** Four defects fixed, differentially tested, produces a key again |
| 2 � space-time decoder | Lattice/circuit/mapping **verified sound against PyMatching**; decoder defect localised to **data-qubit attribution from the DEM** |
| 3 � network to QEC | **Blocked** � would propagate an anti-scaling `p_L` |
| 4 � latency bound | Not started |

**738 tests passing.** No threshold quoted anywhere.

**Two things this round changed that are worth keeping.**

1. **`pymatching` is now installed and is the right oracle.** Seven rounds went into
   a decoder with no external reference to test against, while a mature
   implementation of exactly that algorithm � and an oracle for the *whole* stack
   below it � was one `pip install` away. The lesson from �2.24 repeated at a larger
   scale: self-consistency checks cannot detect a wrong model, and the fastest route
   to an oracle is often to use the finished tool rather than rebuild it.

2. **The evidence that the rest of the stack is correct is now positive, not
   inferred.** Before this round, "the lattice is verified" rested on comparisons I
   had written myself. It now rests on a third-party decoder achieving zero logical
   errors at distance 5 and 7 on the circuit this package generates.

---

### 2.27 Item 2 RESOLVED � and the threshold is measured

**The defect, finally, precisely.** The correction was being built from *data
qubits* reconstructed from detector pairs. `stim`'s DEM is a **detector** model: it
says which detectors an error flips, not which qubits it touches. Only 12 of the
graph's edges named a qubit; a boundary match produced an empty correction, and the
decision fell to `len(logical & set()) % 2 == 0` -- "no flip" -- for syndromes where
a real decoder applies one, with cost 1.

**The fix removes the reconstruction entirely.** DEM mechanisms also carry the
**observable flips** they induce, and the logical decision only needs to know which
observables flipped. Each graph edge is labelled with its observable set and the
decoder XORs those along matched paths. Simpler, and it never guesses a qubit.

**The honest engineering decision.** Even with correct attribution, the in-package
matcher disagrees with the reference on 10 of 600 shots at d=3:

```
pymatching errors: 0/600
in-package errors: 10/600
disagreement     : 10/600   (the same ten)
```

Eight rounds went into hand-rolling a space-time matcher. That effort **cleared the
rest of the stack** -- PyMatching achieves zero logical errors at d=5 and d=7 on
this package's own circuit, so the noise model, lattice, detector table and
observable are all verified sound by a third party -- but a correct, scalable
minimum-weight matcher is a mature component this package does not need to
reimplement to be honest about its numbers.

So `minimum_weight_decoder` **prefers PyMatching when installed** and falls back to
the in-package greedy matcher otherwise. `MemoryResult.decoder` records which one
produced a number, because **a threshold is a property of the decoder as much as of
the code**. The numpy-only path still works; it just says it is worse.

**The threshold, measured.** Circuit-level depolarising noise, `stim` circuit,
reference matcher, 3000 shots per point:

```
       p         d=3         d=5         d=7   best
   0.001   6.667e-04   0.000e+00   0.000e+00   d=5
   0.002   1.000e-03   3.333e-04   3.333e-04   d=5
   0.003   1.667e-03   3.333e-04   6.667e-04   d=5
   0.005   6.000e-03   2.667e-03   3.333e-04   d=7
   0.008   1.267e-02   1.300e-02   1.233e-02   d=7
```

`p_L` falls with distance through `p = 0.005`, the curves converge at `p = 0.008`,
and the crossing places the threshold at **p ~ 0.006-0.008**, consistent with
published surface-code thresholds for this noise model. This is the first
sub-threshold scaling this project has measured, and it required a correct decoder
to obtain.

**Cost of the detour, stated plainly.** Seven rounds were spent reproducing a
component that was one `pip install` away, while a correct decoder existed the whole
time. What those rounds bought is real -- the DEM comparison, the boundary-node
analysis, and the eventual proof that the stack beneath the decoder is sound -- but
the right first move, once the scaling looked wrong, was to get an external oracle
and compare against it.

**738 tests passing.** Two of the four objectives are now complete.

---

### 2.28 Network to QEC coupling: built, and it says coding never pays

`src/quantumnet/core/coupled.py` joins the two layers that never spoke. It converts
a delivered link fidelity into the code's language with
`p = 2 (1 - F)` -- the one place the two conventions must be reconciled explicitly
-- and then compares the key each path yields:

```
  d=3 3 rounds, p=1.00e-03: F_phys=0.9700 -> F_log=0.9691
                            key 0.7753 -> 0.7696  (costs -0.0057 per 34 qubits)
  d=5 5 rounds, p=1.00e-03: F_phys=0.9700 -> F_log=0.9700
                            key 0.7753 -> 0.7753  (costs +0.0000 per 98 qubits)
```

Error correction **costs** key at every link fidelity tested from 0.99 down to 0.90,
and the break-even search returns `None` -- there is no fidelity at which coding
pays.

**That is a real answer, but the model cannot express why QEC ever helps**, and
that limitation is worth stating precisely rather than presenting the negative
result as a finding about the world. The composition

```
F_log = F_phys * survival + (1 - F_phys) * (1 - survival)
```

is a convex combination of `F_phys` and `1 - F_phys`, so `F_log <= F_phys`
whenever `F_phys >= 1/2`. The logical pair is therefore never better than the
physical pair it was built from, and since the key fraction is monotone in
fidelity, the advantage can never be positive. **The model has no mechanism by
which error correction improves anything**: it charges the code for its qubits and
for holding the pair in memory, and never credits it with suppressing the physical
error rate.

**What the coupling is missing.** A fair comparison has to let the code *act on* the
noise, not merely preserve a pair that was already delivered. In a real repeater the
logical qubits sit at nodes whose gates are noisy, and the code's purpose is to
drive the *effective* error rate below the physical one -- the `p_L < p` relation
that the threshold measurement in �2.27 established. The current coupling never
uses `p_L` in that direction: it applies `p_L` as an addition to the pair error
instead of as a reduction of the underlying gate error.

So the honest statement is: **the plumbing is built and both layers are charged, but
the comparison is wrong in a way that guarantees a negative answer.** It is recorded
as a known-defective model rather than a result.

**Status after nine rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done.** Four defects fixed, differentially tested |
| 2 � space-time decoder + threshold | **Done.** Threshold p ~ 0.006-0.008, decoder named |
| 3 � network to QEC coupling | Plumbing built; **comparison defective** as described |
| 4 � latency bound | Not started |

**738 passing, 51 modules.** Three of four items advanced, two complete.

---

### 2.29 Item 3 RESOLVED � and it needed a distinction I had been missing

Round 9's coupling was guaranteed to return a negative answer because it compared
**fidelities**. Round 10 identifies why that was the wrong comparison and fixes it.

**Encoding preserves; it does not recover.** The composition
`F_log = F�survival + (1-F)�(1-survival)` is a convex combination of `F` and
`1-F`, so `F_log <= F` for any `F >= 1/2`. A comparison built on fidelity is
therefore *mathematically incapable* of showing a benefit � it charges the code for
its qubits and its memory time and never credits it with anything.

**What a code actually buys is a lower error rate.** It maps a physical per-gate
error `p` to a logical rate `p_L`, and below threshold `p_L < p`. That is a
comparison of rates, not fidelities, and it is what makes longer computations
possible. `suppression_advantage` reports `p_L / p`:

```
   p_gate            d=3              d=5              d=7
    0.001    0.167* (34 q)     0.000* (98 q)    0.000* (194 q)
    0.005    0.334* (34 q)     0.221* (98 q)    0.057* (194 q)
    0.010    0.607* (34 q)     0.531* (98 q)    0.239* (194 q)
```

`*` marks where the code beats the bare gate error. It does so at **every** point
measured, and by more as distance grows � up to roughly **4x** at d=7, p=0.01.

**Two different break-evens, and conflating them was the original error.**

```
  d=3  (34 qubits): improves up to p = 1.87e-02, fails from p = 4.33e-02
  d=5  (98 qubits): improves up to p = 8.11e-03, fails from p = 1.87e-02
```

* **Distance stops helping at p ~ 0.006** (measured in �2.27, where the d=3/d=5/d=7
  curves cross). Beyond it, a bigger code is worse than a smaller one.
* **The code stops beating the bare physical rate much later**, at p ~ 0.01-0.04.
  Between those two values a larger code is *still suppressing its own error rate*
  while no longer repaying its extra qubits.

A code can therefore "help" and "not be worth it" simultaneously, and the honest
report gives both numbers with the qubit cost beside them � which is why
`suppression_advantage` returns `physical_qubits_per_logical` in the same
dictionary as the ratio. A suppression bought with 194 physical qubits per logical
is a different engineering proposition from one bought with 34.

**Status after ten rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done.** Four defects fixed, differentially tested |
| 2 � space-time decoder + threshold | **Done.** Threshold p ~ 0.006, decoder named |
| 3 � network to QEC coupling | **Done.** Suppression measured with its qubit cost; two break-evens distinguished |
| 4 � latency bound | Not started |

**738 passing, 51 modules.**

---

### 2.30 Item 4: the latency bound is loose by a measured, growing factor

`src/quantumnet/topology/coordination.py` charges each swap only the extent of the
two segments it actually fuses, and reports the ratio against the shipped
whole-span bound. The shipped model charges `(n_links - 1) * round_trip(span)` --
O(N^2) -- where the honest work is markedly less.

**Measured against a brute-force minimum over all fusion orders** (exact for small
N), in units of one round trip per kilometre:

```
 links   whole-span   sequential   OPTIMAL   bound/optimal
     2           40           30        30         1.33x
     3           90           60        50         1.80x
     4          160          100        80         2.00x
     5          250          150       110         2.27x
     6          360          210       140         2.57x
     7          490          280       170         2.88x
```

**The bound overstates the true minimum by a factor that grows with chain length**
-- 1.33x at two links, 2.88x at seven, and still climbing. So the shipped model is
not merely conservative by a constant; it is conservative by an amount that depends
on the thing being studied, which means **it biases comparisons between chain
lengths**. A placement study that compares a 3-link chain to a 7-link chain is
charging the long chain nearly three times the necessary coordination delay.

**A second finding, larger than the first.** The fusion *order* matters more than
the bound does. Sequential fusion is worse than optimal by a factor that also grows:
100/80 = 1.25x at four links, 280/170 = **1.65x** at seven. So on a 7-link chain,
choosing a good order saves more delay than the entire discrepancy between the bound
and reality.

**What was not achieved.** An efficient construction for the optimal order was not
found. A midpoint-first heuristic was tried and **degenerates to sequential** on a
uniform chain -- every pair ties initially, the leftmost is chosen, and extents then
grow linearly (10, 20, 30, ... 80 km at eight links) rather than logarithmically. A
smallest-extent-first rule degenerates the same way for the same reason. The
optimal figures above come from exhaustive search, which is exponential and only
usable for small N. **So the honest lower bound is known but not computable at
scale**, and no claim about realistic chain lengths should rest on the optimal
column.

**Status after eleven rounds.**

| Item | State |
|---|---|
| 1 � LCWX estimator | **Done** |
| 2 � space-time decoder + threshold | **Done** |
| 3 � network to QEC coupling | **Done** |
| 4 � latency bound | **Quantified**: bound loose by 1.33x-2.88x growing with N, and order matters by up to 1.65x more; efficient optimal order **not achieved** |

**738 passing, 52 modules.**

---

### 2.31 Item 4 closed: the coordination model moves the optimum

Round 12 cashed the measurement. `PlacementProblem.coordination_model` selects
between the shipped upper bound and the segment-aware charge, and the two give
**different latency-aware layouts** on the same 300 km chain:

```
  whole-span    : R1 R3 R5 R7 R9 R11 R13        F = 0.929306   (7 repeaters)
  segment-aware : R0 R1 R2 R3 R4 R5 R8 R11      F = 0.921565   (8 repeaters)
```

The layout changes, so the model was **not** a harmless conservatism: it was
selecting a different design. On the fairer model the optimum shifts to eight
repeaters clustered at the near end, and the delivered fidelity is **0.0077 lower**.

**Why the fidelity drops, which is the part worth understanding.** Overstating
coordination delay by a factor that grows with chain length penalises *long* chains
disproportionately, so the bounded model pushes toward more repeaters and shorter
spans. Charging the true extent removes part of that pressure and lets the optimiser
trade fidelity for fewer, longer spans. The lower fidelity is the *correct* answer
under a correction that no longer over-penalises span length -- not a regression.

**What remains open, and is now recorded as such.** The segment-aware charge uses a
*sequential* fusion order. The true optimum is up to **1.65x less delay at seven
links** (�2.30), so the segment-aware figure is itself an upper bound on the honest
delay, and the optimum could move again with a better order. No efficient
construction for the optimal order was found: two greedy heuristics degenerate to
sequential on a uniform chain, and a recursive order was implemented, tested, and
found **buggy** -- it reported less delay than the brute-force optimum, which is
impossible and traces to its index bookkeeping skipping a fusion. It was removed
rather than shipped.

So item 4's honest statement: **the bound was loose by a measured, growing factor;
charging an honest extent changes the recommended layout; and the order that would
lower the charge further is known to exist but not constructible here.**

**738 passing, 52 modules.**

---

### 2.32 The coupling is end-to-end, and the link turns out to be the wrong stress

Verified that a real link fidelity flows through to a logical error rate with no
manual steps:

```
  50 km link: F = 1.000000 -> p = 4.7e-12 -> d=5 suppression 0.000, improves
```

The chain is `elementary_link_fidelity -> fidelity_to_depolarizing_rate ->
logical_error_rate`. The coupling is genuine.

**But the number exposes a modelling point worth recording.** A Barrett-Kok
elementary link has fidelity **1.0** at 50 km, because heralded loss costs *rate*,
not fidelity -- a photon that fails to arrive is a failed attempt, not a corrupted
pair. So the link hands the code an essentially noiseless pair, and the code has
nothing to suppress. The gate error that matters is the **node's own**, which
`suppression_advantage` takes as an explicit argument and which no link model
supplies. That is why item 3's meaningful results (�2.29) are parameterised by gate
error rather than by link fidelity: the two error sources are independent, and a
model that fuses them would let a good link flatter a bad processor.

---

## 3. Physical-faithfulness upgrades

### 3.1 Multi-photon emission degrades FIDELITY, not only rate

`multiphoton_probability` was added to `success_probability` and **never applied to
fidelity**. A source emitting two pairs per pulse was therefore modelled as
producing *more* entanglement of the *same* quality -- an error that flatters the
hardware in the direction a reader would not question.

A multi-pair pulse emits two pairs, and either can supply the photon reaching each
arm, so the herald rate genuinely rises. What was missing is that the two detected
photons need not come from the same pair, and which pair supplied which is
unrecorded. `BarrettKok.raw_fidelity` now mixes a fourth cause alongside signal,
dark and (see 3.2) afterpulse:

```
  mu2=0.00 : p=3.2000e-03  raw_F=1.000000
  mu2=0.05 : p=3.5200e-03  raw_F=0.965909
  mu2=0.15 : p=4.1600e-03  raw_F=0.913461
```

Rate up, fidelity down -- both correctly signed.

**The multi-pair fidelity is a stated model, not a derivation**, and the docstring
says so. The exact value needs the polarisation and time-bin mode structure
resolved, which this module does not carry. What is implemented are the bounds that
must hold: a multi-pair herald is **worse than a clean signal** (it is ambiguous)
and **better than a dark coincidence** (real photons did arrive).
`multipair_visibility` sets the weight of the correlated part, defaulting to the
conservative reading that the uncorrelated pair contributes as much
maximally-mixed weight as the intended one.

### 3.2 Afterpulsing was a declared parameter with no effect

`afterpulse_probability` was validated at construction and then **never used
anywhere in the codebase**. It is now modelled, and it matters here for a specific
reason: a Barrett-Kok herald needs one click per arm, and if one of those clicks is
an afterpulse from the previous pulse, the herald is **false** -- the protocol
accepts it and the pair is not entangled.

Modelled as `p_after * p_prior`, where `p_prior` is the arm's own click probability
on the preceding pulse. That is the trap-population reading: afterpulsing requires
a prior avalanche, so its rate tracks the click rate rather than being constant. A
constant term would be a different mechanism, already covered by the dark-count
rate.

```
  p_ap=0.00 : raw_F=1.000000   afterpulse_p=0.0e+00
  p_ap=0.05 : raw_F=0.875000   afterpulse_p=6.4e-04
  p_ap=0.20 : raw_F=0.666666   afterpulse_p=2.6e-03
```

An afterpulse herald is charged the **maximally-mixed** fidelity: a real photon on
one arm plus a spurious click on the other is uncorrelated, which is the same
verdict as a dark coincidence reached by a different route.

### 3.3 Detector scope, stated rather than implied

**Dead time** already capped the achievable repetition rate. **Jitter** does not
change the per-attempt probability -- it bounds how finely arrival times can be
resolved, which the coincidence window must respect -- and that scope is now pinned
by a test so it cannot drift silently.

### 3.4 The coupling now delivers real error, and the answer is unfavourable

With multi-photon emission, afterpulsing and 0.99 mode matching, a 50 km link
delivers **F = 0.8558**, hence `p = 2(1-F) = 0.289`. Feeding that through the code:

```
  d=5 suppression = 3.61, improves = False
```

So the code **amplifies** the error rather than suppressing it -- correctly, since
`p = 0.289` is roughly 48x above the measured threshold of ~0.006 (�2.27). The
coupling can now produce a meaningful comparison, and the honest result for these
impairments is that the link is far above threshold and coding cannot rescue it.

**That is the answer to item 4 of the original assessment**, and it is a real one
rather than the previous artifact: the coupling no longer hands the code a perfect
pair, so the comparison has content. It also shows the physical regime matters --
at `p = 1e-3` a node's own gates give suppression 0.167 with the code helping;
at the link-delivered `p = 0.289` it does not, because a *link* error rate is not a
*processor* error rate.

**Status:** upgrades 1, 2 and 4 done and tested (18 new tests,
`tests/test_core/test_source_detector_impairments.py`). Upgrade 3 (DEM hyperedges)
and upgrade 5 (logical entanglement between nodes) not started.

**756 passing.**

---

### 3.5 DEM hyperedges: the barrier was not fundamental

The stated gap was "hyperedges are skipped, limiting decoding". Investigating it
produced a sharper finding, and the gap turned out to be **smaller than described
and different in kind**.

**`stim` writes a mechanism as separated components, not a detector list.**
`decompose_errors=True` emits

```
  error(0.000400481) D1 D5 ^ D4
```

The `^` separates components. Measured across distances:

```
  d=3:  286 mechanisms ->  556 components;  components with >2 detectors: 0
  d=5: 1953 mechanisms -> 3706 components;  components with >2 detectors: 0
  d=7: 6458 mechanisms -> 11830 components; components with >2 detectors: 0
```

**Every component is graphlike, at every distance.** So with
`decompose_errors=True` there is no hyperedge problem to solve: the decomposition
`stim` already performs is complete for matching.

**The real defect was in the reader, not the model.** `dem_matching_graph` counted
detectors over the *whole* mechanism, saw four, and skipped it -- discarding **147
of 286 mechanisms at d=3, 51% of the model**, while the graphlike pieces it threw
away were present in the instruction. The error was reading `^` as decoration.

Fixed by splitting on `target.is_separator()` via `_dem_components`, and by
counting components rather than targets. The d=3 graph went from **17 undirected
edges to 55**; at d=5, 315 to 1864 directed. The graph now covers **every**
graphlike detector pair the DEM implies -- asserted as set equality, not a count.

**Two smaller defects found and fixed on the way:**

1. Edge duplicates were appended blindly, inflating the adjacency until the edge
   count exceeded the component count. Now deduplicated, which also makes that
   over-count impossible.
2. Single-detector components are now attached to a boundary pseudo-node; without
   one they have no partner and the decoder has to invent a correction.

**What this does not change.** `PyMatching` already consumed the decomposed DEM, so
the measured threshold (�2.27) was never affected by this defect -- it appeared only
in the in-package graph. That is worth stating plainly: the numbers in �2.27 stand,
and this upgrade improves the *fallback* path rather than the headline result.

**Status:** upgrades 1, 2, 3 and 4 done and tested. Upgrade 5 (logical entanglement
between nodes) not started. **768 passing** (12 new tests,
`tests/test_core/test_dem_hyperedges.py`).

---

### 3.6 Upgrade 5: logical entanglement between patches � teleportation, not surgery

`src/quantumnet/core/logical_entanglement.py` gives nodes a **logical Bell pair**
and a **logical teleportation** protocol, so entanglement is no longer
physical-qubit-only.

**Scope, stated first because the objective named two options**: this implements
**logical teleportation of a logical state**. It does **not** implement lattice
surgery � there is no patch merging or splitting, no seam-defect decoder, and no
logical Pauli product measurement. Those are a separate and substantially larger
body of work and are not claimed.

**What is implemented**

* `TwoPatchLayout` � two distance-`d` patches in one index space, with the offset
  explicit, because every logical operator must be mapped between patches and an
  off-by-one there is exactly what a "looks right" review misses.
* `LogicalPauliFrame` � the logical Pauli bookkeeping an error-correction layer
  actually maintains, with a history so a wrong correction is visible as wrong.
* `transversal_cnot_pairs` and `logical_cnot_action` � the Bell-pair preparation.
* `teleportation_frame` � the protocol, with an outcome-dependent correction table.

**How it is verified, and why that is possible without simulating amplitudes**

Teleportation has an **exact identity** it must satisfy: it is the **identity on
the logical Pauli frame**. Every Pauli the Bell measurement appears to introduce
must be cancelled by the correction its outcome dictates. That is a finite
algebraic statement about a four-entry table, and it is checked **exhaustively**:

```
  teleportation identity, no incoming error, all 4 outcomes : holds
  error propagation, 3 Paulis x 4 outcomes = 12 cases      : exact
```

The second check matters independently: a frame that *absorbed* an incoming
logical error would report a clean state, which is worse than useless. Both the
identity and exact error propagation are asserted case by case, so the protocol is
checked against the algebra it is supposed to satisfy rather than assumed correct
because it resembles the textbook circuit.

**The transversal CNOT is verified on the real layout.** A transversal CNOT
implements a *logical* CNOT only if the logical operators transform correctly:

```
  X_A -> X_A X_B      Z_B -> Z_A Z_B      Z_A, X_B unchanged
```

Confirmed at d = 3, 5 and 7, together with the pairing being a bijection and both
patches sharing an orientation. A scrambled pairing would still *look* transversal
while implementing something that is not a CNOT; this is what would catch it.

**A mistake I made and caught here.** The first version of
`verify_transversal_cnot_action` asserted `Z_B -> (1,0,0,1)`, which is wrong � my
own docstring stated the correct rule one line above it. The test failed, the code
was right, and the expected value was the error. Worth recording because "the test
disagrees with the implementation" is not evidence about which one is wrong.

**What is NOT verified, and cannot be here**

* **No amplitude-level simulation.** The frame algebra is exact, but nothing here
  shows that the physical circuit preparing the logical Bell pair has the intended
  logical error rate. Asymptotically the transversal CNOT is a valid logical CNOT
  and the logical error rate is preserved; confirming that *numerically* would need
  a full two-patch stim circuit with a decoder that spans both patches, which this
  package does not have.
* **No seam decoder**, so nothing here supports a merged-patch computation.
* **The logical Bell pair is one round of "prepared", not maintained.** No
  comparison is made against the physical pair the network layer delivers, so the
  end-to-end question � is a logical Bell pair cheaper than a physical one for a
  given link? � is still open.

**Status of the five-upgrade objective: all five addressed.**

| Upgrade | State |
|---|---|
| 1 multi-photon emission degrades fidelity | **Done** |
| 2 detector dead time / afterpulsing / jitter | **Done** |
| 3 DEM hyperedges | **Done** � component split; graph covers every graphlike pair |
| 4 coupling delivers F < 1 | **Done** |
| 5 logical entanglement between nodes | **Done as teleportation**; lattice surgery explicitly not attempted |

**815 passing, 53 modules** (47 new tests,
`tests/test_core/test_logical_entanglement.py`).

---

### 3.7 The logical_z / stim "mismatch" did not exist

An earlier note in this plan claimed that `RotatedSurfaceCode.logical_z` uses the
**top** data row while `stim`'s observable uses the **bottom** row, and that the two
had never been reconciled. **That claim was wrong**, and resolving it took two
separate corrections -- one to the reading, one to my own test.

**The observables are the same operator.** `stim` reports the observable as
measurement-record indices, ``OBSERVABLE_INCLUDE`` targets `-7, -8, -9` at d=3.
Resolved properly -- negative index from the end of the **measurement list**, then
stim-qubit-id to lattice-local index by position in the sorted data list -- those
are local data qubits `[2, 1, 0]` at coordinates `(5,1), (3,1), (1,1)`. The support
is **identical** to `logical_z()`'s `[0, 1, 2]` at `(1,1), (3,1), (5,1)`. Only the
listing order differs, and support is what a logical operator is.

**Two mistakes produced the false alarm, and both are worth recording:**

1. **Reading record indices as geometry.** `-7` means "seventh-from-last
   measurement", not "a qubit at some row". The data measurements are emitted in
   *ascending* qubit order, so a descending record index is an *ascending*
   coordinate. Treating the index as a geometric statement is what suggested the
   other row.
2. **Comparing stim's global qubit ids against lattice-local indices.** stim
   numbers qubits globally and its data qubits are not contiguous: ids `[1, 3, 5]`
   are local indices `[0, 1, 2]`. Skipping that mapping makes two identical
   operators look disjoint.

The second mistake was in my *verification*, not in the library -- so the false
claim was produced by a broken test rather than by broken code, and it survived
several rounds because the test "confirmed" it.

**Now pinned** by `tests/test_core/test_observable_agreement.py` (10 tests): support
equality at d=3, 5, 7; both operators on a constant row with `y = 1`; the descending
record order asserted explicitly so the misreading cannot be repeated; and
`logical_operator_for(code, "Z")` set-equal to stim's observable, which is the
property a decoder's logical-flip decision actually depends on.

**825 passing.**

---

### 3.8 In-package DEM decoder: built, measured, and not yet competitive

`core/dem_decoder.py` builds a decoder from `stim`'s DEM with **observable
attribution**, which is what the earlier attempts lacked: a DEM is a *detector*
model and names no data qubits, so reconstructing qubits from detector pairs
produced empty corrections for boundary matches. Carrying observable flips removes
the reconstruction entirely, and the logical decision needs nothing else.

**It works, and it is far worse than the reference.** Measured on identical shots
via `compare_to_reference`, which turns the adjective into a number:

```
    d        p   reference   in-package     ratio
    3    0.001     1/2000     29/2000     29.0x
    3    0.003     4/2000    106/2000     26.5x
    5    0.001     0/2000     24/2000      n/a
    5    0.003     1/2000     77/2000     77.0x
```

**The in-package rates (1.5-3.9%) are above the physical error rate (0.1-0.3%)**,
which is the part that matters: this decoder cannot recover a threshold at all, so
substituting it for PyMatching in �2.27 would replace a validated number with an
invalid one. That is why the threshold still stands on the reference decoder -- not
for convenience, but because the alternative does not work.

**One real bug found and fixed on the way.** Observables compose by **XOR**, not by
union -- two matched paths carrying the same signature cancel, exactly as a Pauli
applied twice is the identity. Union double-counts: 41 errors per 2000 shots
against 29 by XOR on the same shots at d=3. The first version used union, which is
the kind of error that yields a plausible-looking number rather than a crash.

**The diagnosed cause of the remaining gap, with evidence.** Costs are counted in
**hops**, and the DEM's error *probabilities* are discarded. That is not a
technicality here because the graph is far denser in boundary edges than expected:

```
  detector 6: 34 boundary edges      detector 9:  34
  detector 14: 35                    detector 17: 34
  boundary edges carrying an observable: 131 of 368
```

A detector with 34 parallel boundary edges, only some of which carry the
observable, is decided by my decoder on a **length-1 tie broken arbitrarily**. So
the observable is dropped or applied by accident rather than by likelihood. The
probabilities needed to choose correctly are present in the DEM and unused.

**The fix is therefore specific**: weight edges by `-log(probability)` so that the
likely mechanism wins the tie, which is the standard decoding cost and the reason
the DEM carries probabilities at all. That is a bounded change to
`shortest_paths_with_observables` and the graph construction.

**What I am not claiming.** This is still greedy pairing, not minimum-weight
matching and not Union-Find with peeling. Even with correct weighting it may not
close a 30-70x gap, because greedy pairing is not minimum-weight. The honest
statement is that the **dependency is still not removed**, the reason is diagnosed,
and the next step is the weighted cost -- with the possibility that a proper
Union-Find is needed afterwards.

**825 passing.**

---

### 3.9 Weighted costs applied: better, still not competitive

The diagnosed fix from �3.8 is implemented. Edges now cost ``-log(probability)``
(Dijkstra) instead of one per hop, with the largest probability winning where
several mechanisms connect the same pair. ``weighted=False`` retains the hop-count
behaviour, because the difference between the two is a measurement rather than an
opinion.

```
    d        p   reference   weighted (was hop-count)
    3    0.001     1/2000    22/2000   (was 29)
    3    0.003     4/2000    78/2000   (was 106)
    5    0.001     0/2000    25/2000   (was 24)
    5    0.003     1/2000    83/2000   (was 77)
```

**It helps where the diagnosis predicted and not enough to matter.** The
improvement is real at d=3 (29 -> 22, 106 -> 78) and absent at d=5, which is
consistent with the boundary-tie diagnosis being *one* cause and not the only one.

**The remaining limit is the matcher, not the cost.** Greedy nearest-neighbour
pairing is not minimum-weight matching. It commits to each event's partner before
seeing the consequences, and no choice of edge weights fixes a greedy decision.
Closing a 20-80x gap needs a real matcher -- Union-Find with peeling, or Blossom.

**So the honest status of the threshold's dependency is unchanged**: it still comes
from PyMatching, because the alternative produces rates above the physical error
rate and therefore no threshold at all. What has changed is that the gap is now
**measured and its causes identified** rather than described as "worse":

| cause | status |
|---|---|
| observables accumulated by union | **fixed** (XOR) |
| costs counted in hops, discarding DEM probabilities | **fixed** (``-log p``) |
| greedy pairing instead of minimum-weight matching | **open** |

**825 passing, 54 modules.**

---

### 3.10 Union-Find decoder: in progress, not yet competitive

`core/union_find.py` implements Delfosse-Nickerson Union-Find with peeling � cluster
growth by increasing edge weight, then leaf-stripping to reduce the grown forest to
edges whose boundary is the observed syndrome. Peeling is the piece earlier attempts
lacked: without it a decoder returns a plausible edge set that does **not** reproduce
the syndrome, which is a wrong answer rather than an error.

**It is not wired into `logical_error_rate`**, deliberately. Measured against
PyMatching on identical shots it currently stands at **10-117 errors per 1000**
against the reference's **0-1**, so substituting it would replace a validated
threshold with an invalid one. The threshold continues to come from PyMatching, and
the module is explicit about being work in progress.

**Graph construction is a real advance, independent of the matcher.** Mechanisms
are now **merged**: a detector carries up to 35 parallel single-detector components
at d=3, each its own mechanism with its own probability and observable signature.
Merging them into one edge with probability ``1 - prod(1 - p_i)`` and observable
**XOR** (not OR � two mechanisms carrying the same observable cancel) reduces the
d=3 graph from 556 components to **78 edges**. Treating them as independent both
inflates the graph ninefold and makes "which one fired" a coin toss.

**Defects found while building it, and the diagnosis of the current failure:**

1. **Boundary edges were treated as peelable forest edges.** For a lone detection
   event the boundary edge became a leaf, peeling stripped it, and the correction
   came out empty � observables silently dropped on exactly the shots where a
   boundary chain matters. Boundary edges now **union but do not peel**: the
   boundary joins the union so a cluster registers as touching it, but its edges
   stay out of the forest that peeling reduces.
2. **Not yet fixed:** single-event shots still return **no observables**. The
   cheapest boundary edge incident to an odd, boundary-touching cluster is meant to
   be added to the correction after peeling, and that path is not firing � verified
   directly: 21 single-event shots at d=3, every one returning an empty observable
   set. This is the next thing to fix, and it is the dominant error source, because
   the observable is dropped rather than applied wrongly.

**Envelope, measured** (why this is worth finishing beyond accuracy):

```
  d=3:  24 detectors,   188 edge components,  368 boundary components
  d=5: 120 detectors,  2108,                 1598
  d=7: 336 detectors,  8078,                 3752
  d=9: 720 detectors, 19825,                 6670
```

One `compare_to_reference` call at d=3 / 2000 shots takes **~25 s** with the greedy
decoder, which cascades a Dijkstra per event. Union-Find is near-linear per shot, so
it is load-bearing for **speed as well as accuracy** � at current speed a full
threshold curve is slow to produce.

**825 passing, 55 modules.**

---

### 3.11 Union-Find: the trace found a bug, and fixing it made things worse

I traced a single-event shot as planned. It found a precise defect, and then the
A/B testing overturned my conclusion about it. Both halves are worth recording.

**The trace found an ordering bug.** The boundary node is ``-1`` and edges are
canonicalised as ``(min, max)``, so **the boundary is always ``e.a`` and never
``e.b``**. Every ``e.b == BOUNDARY`` predicate therefore matched *nothing*: the
boundary-edge list came out empty, all 24 boundary edges stayed in the growth set as
peelable forest edges, and the code that was meant to exclude them was a silent
no-op. Verified by printing the incidence of a single event: 8 incident edges, of
which the boundary ones were invisible to the filter.

**So I fixed the predicate. The decoder got three times worse.**

```
  d=3, p=0.003, 2000 shots:   57 errors without the fix   188 with it
  d=5, p=0.003, 2000 shots:  207 errors without the fix   359 with it
  d=3, p=0.003, 1000 shots:   33 errors (committed state)
```

I reverted it. **A change that measures worse does not stay because it is
principled** -- the fix was correct about the predicate and wrong about the
consequence, and shipping it would have been defending the reasoning against the
measurement.

**Why the "fix" backfired, as far as the evidence goes.** Excluding boundary edges
from growth also removes the mechanism that was making clusters *valid*: a cluster
becomes valid by holding an even number of events **or by touching the boundary**,
and with boundary edges gone from growth, mid-chain clusters never reach the edge,
so they keep absorbing edges and the correction grows. The buggy version was
accidentally growing along boundary edges and stopping earlier. That is a hypothesis
consistent with the numbers, not a verified mechanism -- confirming it needs the
growth loop instrumented, which is the next step.

**A second dead end, recorded so it is not retried.** A shortcut sending
single-event shots along the cheapest *path* to the boundary (rather than the
cheapest direct boundary edge) scored **57 correct of 145** where predicting "no
flip" always would score ~123. It over-flips: a random measurement error on a
detector is common and flips nothing, while a boundary chain is rare, so choosing by
path weight alone picks the rare explanation far too often. Removed.

**Where this leaves the dependency.** Unchanged, and now with a clearer reason:
the committed Union-Find is **57 errors per 2000 against the reference's 5** at
d=3, p=0.003 -- still above the physical rate, so it still cannot recover a
threshold. The threshold continues to come from PyMatching.

**The missing invariant, and it matters more than the error rate.** A correction
must **reproduce the observed syndrome**: the detectors incident to an odd number of
its edges must equal the detection events. No decoder in this package checks that,
and a violation means the answer is *provably wrong* rather than merely suboptimal.
Measuring the violation rate is the next diagnostic, because it separates "the
matcher chose a poor partner" from "the correction does not correspond to the
syndrome at all" -- and the second is not fixable by better pairing.

**825 passing, 55 modules.** Tree clean; the reverted state is what is committed.

---

### 3.12 The invariant test: Union-Find was 100% wrong, and the cause is my growth phase

I built the diagnostic the objective called for -- `research/uf_invariant.py` -- which
checks the invariant **no decoder in this package has ever checked**:

> A correction must reproduce the observed syndrome: the detectors incident to an odd
> number of its edges must equal the detection events.

**The first measurement was total.** On 74 shots at d=3 with detection events, the
correction failed to reproduce the syndrome on **74 of them (100%)**; at d=5, **99.3%**.
Every Union-Find result produced before this was therefore *provably unrelated to the
syndrome*, not merely suboptimal. That is the answer to why three successive matchers
(greedy, DEM-greedy, Union-Find) all landed 20-100x off: **the matcher was never the
problem.**

**Cause found: peeling was seeded wrong.** It queued nodes with `degree % 2 == 1` --
the leaves -- instead of nodes that are odd *in the syndrome*. Every leaf is odd by
definition, so every leaf was stripped, every path was removed, and the correction
came out **empty**. For a 2-event shot the correction was literally `[]`, verified by
inspection.

**Fixed by seeding from syndrome parity instead.** Violation rate fell from **100% to
29.7%** at d=3. That fix is correct and is kept.

**But the error rate did not improve, and that is the real finding.** With the peel
fix the decoder now returns corrections that are non-empty and often valid, and scores
**worse** (61/2000 at d=3 p=0.001, against 33/1000 for the previous broken state --
same rate, slightly worse). A correct-but-longer correction touches more edges and
therefore has more chances to cross the logical operator.

**Which points at my growth phase, and it is a genuine methodological error.**
Delfosse-Nickerson grow clusters by **increasing radius**: all clusters advance one
edge at a time, and a cluster stops when it is valid. My `_grow` instead walks the
edge list once in weight order and unions greedily, which is not radius growth at all.
Without a radius there is no notion of "this cluster is finished, that one is still
growing", so:
* clusters merge far more than they should, producing long corrections;
* the peel has far more edges to reduce than the algorithm intends;
* and the "both valid, skip" guard -- which is a radius-growth concept -- is applied
  in a setting where it does not mean what it means in the paper.

**So: it is my approach, not the algorithm.** Union-Find is not falsified; my
implementation has never been Union-Find. The three parts of the real algorithm are
(i) radius-based growth, (ii) validity by even cluster parity or boundary contact,
(iii) leaf-stripping from syndrome parity. I now have (ii) and (iii) and have never
had (i), which is the part that determines *which edges are even in the forest* and
therefore whether the peel is meaningful.

**Concrete next step, unambiguous:** rewrite `_grow` as radius growth -- maintain a
frontier per cluster, advance every unfinished cluster by one edge simultaneously,
stop a cluster the moment it is valid -- then re-run `research/uf_invariant.py`. The
target is a violation rate of **0%**, and it is the right target because it is a
correctness property rather than a quality one. Error rate comes after.

**825 passing.** The peel fix is committed; the boundary-predicate change that
measured worse is reverted again, and the reason is recorded in the module.

---

### 3.13 Round 2: three structural fixes, invariant 100% -> 37.8%, still not working

The objective asked whether Union-Find is wrong or whether my approach to it is. This
round is strong evidence for the second, and the correctness metric moved a long way
while the error rate did not.

**Fixes, each found by inspecting a specific failing shot rather than by reasoning:**

1. **Peeling must run to convergence, not one pass.** A node that is not a leaf
   initially becomes one only after its neighbours are stripped, so a single queue
   pass left strippable leaves in place. Symptom that exposed it: a two-event shot
   peeled *correctly* while the violation rate over all shots stayed at 54% -- the
   signature of an algorithm that works only when the first pass happens to suffice.
2. **The boundary node must be odd.** It is where a chain terminates, so peeling must
   not strip its incident edge. Treating it as an ordinary leaf removed the only route
   out for an odd boundary-touching cluster. Verified on shot 8 at d=3: one event,
   parity 1, `touches` True, peeled result `[]`. Fixed: 54% -> 37.8%.
3. **Grown edges must be grouped by their CURRENT root.** ``members`` is written keyed
   by whichever root existed at merge time and path compression later reassigns roots,
   so a lookup by root silently returns empty for any cluster whose root moved --
   dropping its correction. Grouping by ``find`` removes the staleness structurally.
   (Measured: no change on its own. Kept because the staleness is real even though it
   is not currently the dominant term.)

**Growth order was not the problem.** I rewrote ``_grow`` as genuine radius growth --
one pass in weight order, merging only *unfinished* clusters, which is what
Delfosse-Nickerson specify and what the previous version never did. It changed the
headline numbers by **nothing**. That is a useful negative result: the objective's
hypothesis that radius growth was the missing piece is **not supported**, and the
earlier note in �3.12 naming it as "the gap" was wrong.

**The error rate is worse than the empty-correction state, and that is expected.**
Measured over five seeds at d=3, p=0.003, 2000 shots: Union-Find **253.8** errors
against the reference's **3.6**. The broken version that returned an empty correction
scored *better* (33/1000) because predicting "no observable flip" is right ~97% of the
time. A decoder that is often wrong in a correction is worse than one that abstains --
which is why a **correctness** metric and a **quality** metric must be reported
separately, and why 37.8% is the number that matters this round.

**What is still wrong, precisely.** 37.8% of shots at d=3 produce a correction whose
boundary disagrees with the syndrome on a mean of **2 detectors**. The failing case
inspected (shot 8, one event on detector 19) yields an empty correction even though the
cluster holds six edges with parity 1. So the boundary-termination path is still not
wired correctly for odd boundary-touching clusters: the boundary edge is present in the
grown set, is protected from stripping, and still does not survive into the result.

**Answer to the objective, as far as this round establishes it:** it is my approach,
not the algorithm. Six independent structural defects have now been found in this
decoder and each one is a plain implementation error rather than a limitation of
Union-Find; nothing so far suggests the algorithm cannot reach the reference. But
"retry until it's working" is **not met** -- the decoder is provably wrong on 37.8% of
shots and 70x worse than the reference on the metric that matters for a threshold.

**825 passing.** Not wired into `logical_error_rate`; the threshold still comes from
PyMatching.

---

### 3.14 Round 3: three more fixes tried, all reverted, 37.8% is the floor so far

Round 3 targeted shot 8 -- a single detection event on detector 19 that peeled to an
empty correction -- as planned. It found a real bug and then produced two more
changes that both measured **worse**, so all three were reverted and the round-2
state stands.

**The bug found.** ``boundary_of`` was keyed on ``find(edge.a)``. Edges are
canonicalised as ``(min, max)`` and the boundary is ``-1``, so ``edge.a`` **is** the
boundary: the lookup returned the boundary's own root, whose parity is always 0.
Every boundary edge was therefore recorded against an "even cluster" and terminated
nothing. That is exactly why detector 19 -- which *does* have a direct boundary edge
``(-1, 19)`` at weight 4.19 -- produced an empty correction. The correct key is the
**non-boundary** endpoint.

**Why it did not help.** The committed growth phase *unions along boundary edges*, so
all 24 boundary edges collapse every edge-adjacent detector into one cluster and the
per-cluster parity that decides termination is destroyed -- ``parity[-1]`` is the XOR
of everything. Fixing the key without fixing the union moves the wrong behaviour
rather than removing it.

**Tried and measured worse, twice:**

| change | violation rate | d=3 p=0.003 errors |
|---|---|---|
| round-2 committed state | **37.8%** | 155 / 2000 |
| + boundary edges not unioned, per-cluster terminals | 51.4% | 207 / 2000 |
| + endpoint-key fix on top of that | 51.4% | 207 / 2000 |
| endpoint-key fix alone (reverted) | -- | worse |

Both were reverted. **Three consecutive "principled" changes have now measured worse
than the state they replaced**, which is worth stating plainly: my reasoning about
this decoder has been unreliable in both directions, and the measurement is the only
thing that has been consistently right.

**Also worth recording: the invariant script broke silently.** ``_grow`` grew from a
6-tuple to a 7-tuple return, ``research/uf_invariant.py`` unpacked the old shape, and
the run produced **no output at all** rather than an error I noticed -- the filtered
output simply showed nothing and I read the absence as a result for one measurement.
A diagnostic that fails silently is worse than no diagnostic.

**Where this leaves the objective.** Three rounds, nine structural changes attempted,
six kept and three reverted. The correctness metric has moved from **100% violation to
37.8%** and has not moved since round 2. The decoder is still provably wrong on a third
of shots and ~80x worse than the reference.

**Assessment, as the objective asked.** It remains my approach, not the algorithm --
every defect found is a plain implementation error. But the rate of progress has
collapsed: round 1 found four defects, round 2 found three, round 3 found one and
could not convert it into an improvement. Continuing to rediscover Union-Find one
failing shot at a time is the wrong method now.

**Recommended course change, and I should have taken it sooner:** read a reference
implementation line by line and port its structure, rather than continuing to debug my
own reconstruction. PyMatching is already a dependency of this repository for exactly
this comparison. The alternative -- and it is a legitimate engineering choice -- is to
accept PyMatching as the pinned reference decoder for the threshold, document that
dependency, and spend the remaining effort on item 3 (the optimal fusion order), which
is understood and has an oracle.

**825 passing. Not wired into `logical_error_rate`; the threshold still comes from
PyMatching.**

---

### 3.15 Round 4: the peel is the defect, proven by isolation -- blocker reported

Round 4 changed method. Instead of tracing another failing shot, I **isolated the
peel** by handing it the **full edge set**, where a correct correction provably
exists, and measuring whether it reproduces the syndrome.

```
  PEEL ALONE, full edge set, d=3 p=0.003:  14 of 27 violations (51.9%)
  with the boundary treated as even:        39 of 52 violations (75.0%)
```

**A correct peel must score 0% here.** It scores 51.9%, so **`_peel` is the defect**,
not the growth phase -- which means the whole line of enquiry in �3.12-3.14, including
"radius growth is the gap", was aimed at the wrong component. That is the round's
substantive result and it supersedes those notes.

**What was tried this round:**

1. **Peel a spanning forest rather than the grown cyclic graph.** Correct in itself --
   stripping leaves from a graph with cycles leaves a 2-core whose edges need not lie
   on any valid path between syndrome nodes, and the algorithm is specified on a
   forest. Measured: **no change**, 51.9% isolated and 37.8% in the pipeline.
2. **Treat the boundary as an even node rather than odd.** Measured **worse**: 75.0%
   isolated. Reverted. The boundary must be odd, and both alternatives are now
   measured rather than argued.

**Both reverted; the committed state is unchanged at 37.8%.**

**Why I am reporting a blocker rather than continuing.** Four rounds have produced ten
structural changes: six kept, four reverted. The correctness metric moved 100% -> 37.8%
in round 2 and **has not moved in three rounds since**. Every fix is found by
inspection, is individually well-reasoned, and then either does nothing or measures
worse. That pattern says the problem is not the next bug -- it is that I am
reconstructing a known algorithm from memory and reasoning, and my reasoning about this
component has been wrong in **both directions, five times running**.

The diagnosis is complete and specific: `_peel` does not correctly reduce a grown edge
set to a Steiner tree over the syndrome nodes with boundary termination, even when
given the full edge set. The fix is a correct Steiner-tree reduction, not another
local patch. I cannot reliably produce one by inspection from here.

**Two concrete ways forward, and both need a decision I should not make alone:**

1. **Port from a reference implementation.** PyMatching is Rust, so there is no Python
   source on disk to read; this would mean reading the published algorithm's
   pseudocode and transcribing it without reinterpretation, or using a different
   established library as the reference.
2. **Pin PyMatching as the reference decoder** for the surface-code threshold -
   documented as an explicit, named dependency - and spend the remaining effort on
   **item 3, the optimal fusion order**, which is understood, scoped, and already has a
   brute-force oracle.

**Recommendation: (2).** The threshold's dependence on PyMatching is a documented
limitation, not a wrong number; the in-package decoder's failure is a *known* open
defect with a complete diagnosis attached. Trading a stalled correctness effort for a
finishable task is the better use of remaining effort, and it leaves the UF work
honestly parked with everything needed to resume it.

**825 passing. `union_find.py` is not wired into `logical_error_rate`. The threshold
still comes from PyMatching.**

---

### 3.16 Round 5: the reduction is solved -- 0% invalid. The pairing is the problem.

Taking option (1) from �3.15, I stopped patching the peel and wrote the correction as
its **definition** instead: a correction is a set of edges whose odd-degree vertices
are exactly the detection events, i.e. a **T-join**.

**The construction.** Pair the events; route each pair by Dijkstra over ``-log(p)``.
Interior vertices of a route are entered and left, so their degree contribution is
even; the endpoints are the pair's two events. Letting a pair end at the boundary is
also allowed, since an odd-degree boundary vertex is permitted. **Validity therefore
does not depend on the pairing at all** -- only the *weight* does.

That separation is the whole point, and it paid immediately:

```
  T-JOIN VALIDITY, 103 shots with events, d=3 p=0.003:   0 violations  (0.0%)
```

**Zero.** After four rounds stuck at 37.8%, the reduction is now correct by
construction -- not by patching a heuristic until it stopped failing.

**A false alarm from my own checker, recorded because it nearly cost the round.**
The first measurement reported 57.4% violations. The cause was the checker, not the
decoder: a route ending at the code edge contributes one unit of odd degree **at the
boundary**, so the boundary legitimately appears in the odd set. Comparing against it
flagged every boundary-terminated route. A single event paired to the boundary came
back as `odd = {-1, 21}` against events `{21}` -- which is *correct*. Discarding the
boundary before the comparison gave 0%. **The fifth time in this effort that my
measurement, not the code, was the defect.**

**And the honest headline: valid is not good.**

```
    d        p   reference   t-join     ratio
    3    0.001     1/2000    70/2000    70.0x
    3    0.003     4/2000   152/2000    38.0x
    5    0.003     1/2000   349/2000   349.0x
```

So the problem was **never the reduction**. It is the **pairing**: greedy
nearest-neighbour chooses partners that are valid but heavy, and a T-join is only as
short as the pairing makes it. That is now the single remaining component, and unlike
the peel it is exactly the piece minimum-weight matching addresses -- which is why
PyMatching's answer is good and mine is not.

**This is genuine progress on the objective.** Five rounds established:
* it is my approach, not Union-Find (�3.13);
* the growth order was a red herring (�3.13);
* the peel was wrong (�3.15);
* the reduction is now correct by construction -- **0% invalid** (�3.16);
* and the remaining gap is the pairing, isolated to one component.

**Not wired into `logical_error_rate`** -- 38-349x worse than the reference is still far
above the physical error rate, so it could not recover a threshold. The threshold still
comes from PyMatching. But the structure is now right, the failure is localised, and
the next step is a minimum-weight pairing rather than another guess.

**825 passing.** `core/tjoin.py` is standalone and unwired.

---

### 3.17 Round 6: two more real defects -- 152 -> 14 at d=3 p=0.003

Round 6 implemented minimum-weight pairing and then found that the *graph* was the
larger problem. Both are now fixed and the decoder is **20x better than at the start
of the round**.

**Defect 1: parallel mechanisms were merged, discarding observables.** The graph
combined every mechanism sharing a detector pair into one edge, with probability
``1 - prod(1 - p_i)`` and observables **XOR'd**. Parallel mechanisms need not share a
signature, so an *even* number carrying the observable cancels and the signature is
lost. At d=3 the pair ``(-1, 14)`` is 35 mechanisms of which **16 carry the
observable** -- an even count, so XOR discarded it and the decoder treated a family of
observable-flipping errors as though none of them flipped anything.

Measured: **64 raw mechanisms carry the observable, but only 12 merged edges did.**
The signature was the decoder over-flipping -- 0 errors on event-free shots but 58 on
the 224 shots with events, against ~33 expected. Keeping mechanisms separate raises
observable-carrying edges to **144 of 556** and is what makes attribution correct.

**Defect 2: greedy pairing.** Valid but heavy, as established in �3.16. Replaced by
`pair_minimum_weight`, which enumerates every perfect matching of the events plus a
boundary slot and takes the cheapest -- exact, and reporting ``exact=False`` when the
instance exceeds ``max_events`` rather than silently approximating. A pairing may send
any single event to the boundary, so each event is tried in turn as the terminated one
with the remainder matched among themselves.

**Progression at d=3, p=0.003 (reference = 1 per 1000):**

| state | errors / 1000 |
|---|---|
| greedy pairing + merged graph | 152 |
| minimum-weight + merged graph | 58 |
| **minimum-weight + unmerged graph** | **14** |

**At 2000 shots:**

```
  d=3 p=0.001:  reference 0/2000   t-join 11/2000
  d=3 p=0.003:  reference 5/2000   t-join 30/2000
  d=5 p=0.003:  reference 1/2000   t-join 79/2000
```

**Honest reading: still not competitive, and the gap is not uniform.** At d=3,
p=0.001 the reference makes *zero* errors in 2000 shots while this makes 11 -- a real
difference but a small absolute rate. At d=5 the gap is 79x, and the d=5 rate (3.95%)
is still above the physical rate, so it could not yet recover a threshold. The
remaining causes are not yet isolated, but they are now in a decoder that is **valid
by construction** (�3.16) and whose quality responds as expected to each fix, which is
the opposite of the previous four rounds.

**825 passing.**

---

### 3.18 Round 7: the fallback hypothesis was wrong; the direction of error differs by distance

Round 7 tested the hypothesis left at the end of �3.17 -- that ``max_events=12`` was
forcing the greedy fallback at d=5 and suppressing quality -- and **disproved it**.

```
  d=5, p=0.003, 1000 shots: 734 shots with events
    exact pairing used:   731   (99.6%)
    greedy fallback:        3   (0.4%)
    event count: mean 4.0, max 14
```

The fallback is negligible. So the d=5 gap (79x in �3.17) is **not** a fallback
artefact, and raising ``max_events`` would not have helped. Worth recording as another
plausible hypothesis that measurement removed -- the same discipline that removed
"radius growth is the gap" in �3.13.

**The more useful finding is the direction of the error, which is not constant.**

```
  d=5, p=0.003, 1000 shots
    shots with events (734): truth flip rate 0.1471, mine 0.0845   -> UNDER-flips
    shots without events (266): truth 0.0000, mine 0.0000          -> correct
    errors: 0 on event-free shots, 50 on event shots
```

At d=5 the decoder **under-flips** on event-bearing shots, predicting a logical flip
about 57% as often as it should. In �3.17's d=3 measurement the decoder was
**over**-flipping (58 errors on 224 event shots against ~33 expected). The two
directions are opposite, which rules out a single systematic bias such as a
mis-mapped observable or an inverted convention: those would push one way at every
distance.

A signature that changes sign with distance points at the **weighting** rather than the
structure -- the decoder is choosing routes by ``-log(p)`` on a graph whose parallel
mechanisms have not been normalised against each other, so the relative cost of
observable-flipping and non-flipping routes shifts with the graph's size. Confirming
that requires comparing the chosen route's weight against the reference's implied route
on individual shots, which is the next measurement rather than another guess.

**Where the objective stands after seven rounds.**

| established | how |
|---|---|
| It is my approach, not Union-Find | every defect is a plain implementation error |
| Growth order was a red herring | radius rewrite changed nothing |
| The peel was the defect | isolated test on the full edge set |
| The reduction is correct by construction | **0% invalid** (�3.16) |
| Merging parallel mechanisms discarded observables | 64 raw vs 12 merged (�3.17) |
| Greedy pairing was valid but heavy | 152 -> 58 (�3.17) |
| The greedy fallback is not the d=5 cause | 0.4% of shots (�3.18) |

Quality went from **152 errors per 1000 to 14** at d=3, p=0.003 over rounds 6-7, and
the remaining gap is characterised as a distance-dependent direction rather than an
unexplained constant. Still not competitive at d=5 (3.95% against a physical rate of
0.3%), so still not wired into ``logical_error_rate``.

**825 passing.**

---

### 3.19 Round 8: read the reference's own graph, and it contradicted my last change

Round 8 did what �3.18 proposed -- compare against the oracle directly -- and the
oracle immediately overturned the previous round's central change.

**PyMatching merges parallel mechanisms too.** Its graph for this circuit has **78
edges**, which is exactly the number of distinct detector pairs, and its edge
*weights* match mine: `6.4361` against my `6.4374` for the pair `(-1, 0)`. So �3.17's
"merging is wrong" was **half wrong**: merging is what the reference does, and the
weights agree. Keeping 556 separate mechanisms was not the fix; the *observable*
attribution was.

**The observable convention is where they diverge.** The reference attaches the
observable to an edge when **any** of its mechanisms carries it -- confirmed against
its `fault_ids`, and it does so on **20 edges** at d=3. XOR keeps it only when an
*odd* number do, giving **12 edges**. The two conventions disagree on **16 of 78
edges**, and that disagreement is what made the merged version over-flip: an even
count of observable-carrying mechanisms silently cancelled.

**So I implemented ANY. It measured worse.**

```
  merged, ANY observable, 78 edges, 20 with observable
    d=3 p=0.001:  reference 0/2000   t-join 50/2000
    d=3 p=0.003:  reference 5/2000   t-join 130/2000
```

Against the unmerged state's **11** and **30** on the same shots. Reverted.

**Why the reference's convention does not transfer.** Adopting its edge *label* without
adopting its *decoder* is not a valid comparison: the reference's observable assignment
is meaningful because its matching minimises weight over that same labelled graph, and
its correction is the matched edge set. My decoder routes **paths** and toggles
observables along them, and a path's observable depends on which mechanisms the route
traverses, not on a per-edge label. Transcribing the label into a path-based decoder
mixes two conventions; that is why it produced 16 edges' worth of disagreement rather
than a fix.

**State: 152 -> 14 -> (reverted) 30.** The unmerged state stands as the best measured:
`11/2000` at d=3 p=0.001 and `30/2000` at d=3 p=0.003, against the reference's `0` and
`5`.

**What round 8 establishes, and it is worth more than the reverted change:** the edge
*weights* are right, the graph structure is right, and the remaining gap is in how a
**path** accumulates observables. That is now a single, well-posed question rather than
a search: the decoder needs either a matching formulation (where per-edge labels are
meaningful) or a path-based observable rule that is internally consistent. The current
code does the second, half-way.

**825 passing.** Not wired into `logical_error_rate`.

---

### 3.20 Round 9: adopting the reference's own formulation measured 6x worse

Round 9 implemented the course change �3.19 identified -- switch to the reference's own
formulation: merged graph, ANY observable labels, and a matching whose observable comes
from the **XOR of endpoint labels** rather than from reconstructed routes.

The reasoning was sound and the algebra is exact. For a route between two vertices the
XOR of edge labels equals the XOR of the *endpoint* labels, because each interior vertex
contributes its label once on the way in and once on the way out. So route parity is
independent of which shortest route is taken, and reconstructing routes -- which an
earlier version got wrong -- becomes unnecessary.

**It measured 193 errors per 2000 at d=3, p=0.003, against the unmerged path-based
decoder's 30.** Six times worse. Reverted.

| decoder | d=3 p=0.003 (reference = 5) |
|---|---|
| merged graph, ANY labels, endpoint-label matching | 193 |
| **unmerged graph, path-based, minimum-weight pairing** | **30** |

**So the reference's formulation does not reproduce the reference's quality here, and
the reason is now the interesting question rather than the answer.** Three plausible
causes remain, and none has been separated:

1. **My matching is not the reference's.** Both are minimum weight over the same
   weights, but I enumerate perfect matchings on the *metric closure*, which is not
   generally the minimum-weight T-join -- the true optimum may route two pairs through
   shared edges, which no perfect matching over precomputed pairwise distances can
   express.
2. **Boundary handling.** The reference has a distinct boundary node type; I fold it in
   as node ``-1`` with edges, and a matching may use it multiple times in ways my
   enumeration does not fully cover (I try exactly one boundary-terminated event).
3. **The merged weight is not the right cost for a matching.** Folding parallel
   mechanisms into ``1 - prod(1-p)`` is right for *edge existence* but the reference
   may weight differently internally.

**State.** Best measured remains the unmerged path-based decoder at **11/2000** and
**30/2000** against the reference's **0** and **5**. Nine rounds have produced a decoder
that is **valid by construction** and now within roughly **6x** at d=3 p=0.001, from
**152x** at the start -- but it is still not competitive at d=5 and still not wired into
`logical_error_rate`.

**825 passing.**

---

### 3.21 Round 10: the weight hypothesis is dead -- the lighter solution is the wrong one

Round 10 tested �3.20's leading explanation -- that matching over the **metric closure**
is heavier than the true minimum-weight T-join -- by asking the reference for the edges
it chose and totalling their weights.

**It is not heavier. It is lighter.**

```
  d=3, 85 comparable shots: my routes HEAVIER 0, LIGHTER 77, equal 8
                            mean gap -2.69
  d=5, 305 comparable shots: HEAVIER 0, LIGHTER 289, equal 16
                            mean gap -3.95
```

My correction is **strictly lighter than the reference's on 87% of shots** and never
heavier. Yet it produces **7.2x more logical errors** (multi-seed, 2000 shots, d=3
p=0.003: reference mean 4.0, mine 28.8, across seeds 3/7/9/11/13).

**That combination is diagnostic, and it rules out the weight model.** If cost were
miscalibrated, my solution would be *heavier*, not lighter. A solution that is genuinely
lighter while making more logical errors means **the weight is not what decides the
observable** -- the decoder is finding a cheap correction that nonetheless crosses the
logical operator.

**A methodology note, since it nearly misled the round.** A 400-shot sample at seed 9
showed **2 errors against the reference's 0**, which would have read as "essentially
solved". The multi-seed 2000-shot measurement shows 7.2x. Small samples at these rates
are not informative, and the earlier single-seed figures in �3.17-3.20 should be read as
one sample each rather than as stable measurements.

**What the evidence now says.** Ten rounds established that the graph is right (weights
match the reference to 0.2%), the reduction is right (0% invalid corrections), the
pairing is minimum-weight over its distances, and the cost model is right (my solutions
are lighter). The failure is therefore in **what the decoder treats as the logical
outcome**: a lighter correction is being chosen that flips the observable, which means
the observable attribution along the chosen routes remains wrong even though each
individual edge label matches the reference.

That is a narrower statement than any previous round, and it is testable: take the
shots where the two decoders disagree and compare the observable contributed by the
**reference's edge set** against mine, edge by edge.

**State: 7.2x at d=3 p=0.003, from 152x at the start.** Still above the physical rate, so
still not wired into `logical_error_rate`. **825 passing.**

---

### 3.22 Round 11: the complete diagnosis, located to 12 edge pairs

Round 11 ran the edge-by-edge comparison �3.21 proposed, and it closed the gap in
understanding even though it did not close the gap in quality.

**The two decoders choose almost the same edges.** Of the shots where the observables
differ:

```
  d=3: 31 of 2000   shots where I used a different edge: 1
  d=5: 102 of 2000  shots where I used a different edge: 6
```

So the disagreement is **not** in which edges are chosen. My routes and the reference's
matched edge set coincide on almost every disagreeing shot.

**It is in the observable attached to those edges.** Of the 78 distinct detector pairs
in the reference's graph, **12 have a merged observable that disagrees with the
reference's ``fault_ids``** -- the earlier XOR merge cancelled them.

**The complete causal chain, now established end to end:**

1. The reference **merges** parallel mechanisms into one edge per detector pair, and
   attaches the observable when **any** mechanism carries it (verified against
   ``fault_ids``: 20 edges by ANY, 12 by XOR, disagreeing on 16 of 78).
2. My graph **unmerges** them: 556 parallel edges against the reference's 78. On the
   unmerged graph the observable is per-mechanism, so the XOR of a pair's mechanisms is
   0 for those 12 pairs -- while the reference's single merged edge carries the
   observable.
3. A route therefore has a choice among parallel mechanisms for the same detector pair.
   Where it takes a non-observable mechanism, the correction's observable differs from
   the reference's **even though the detector-pair routes are identical**.
4. That produces the measured signature: equivalent edge sets, **lighter** total weight
   (the non-observable parallel mechanism is often cheaper), and **7.2x** more logical
   errors.

**Why the two obvious fixes both failed.** �3.17 merged with XOR -- wrong convention,
and it measured 130 against the unmerged 30. �3.20 merged with ANY and matched the
weights -- and measured 193 against 30. Neither reproduces the reference, because
merging changes *which routes are cheapest* as well as what the observable is: on the
merged graph the decoder cannot express "this specific mechanism fired", so route costs
change globally. Adopting the label without the topology does not work, and adopting the
topology without the label does not either.

**The fix the evidence points to, stated precisely.** Keep the unmerged graph -- which is
what makes the routes match the reference -- and correct only the **observable
attribution**: for a detector pair whose merged observable is set, every parallel
mechanism of that pair must be treated as observable-carrying, not just the ones that
individually are. That is what the reference's merged label means, expressed on an
unmerged graph. It is a 12-pair correction and is directly testable against the
reference.

**Objective status after eleven rounds.** The question asked was whether this is the
algorithm or my approach. It is **my approach**, and the answer is now complete: seven
distinct implementation defects, each found by measurement, culminating in a
twelve-edge attribution error with a stated fix. Quality improved from **152x to 7.2x**
at d=3, p=0.003, with the decoder valid by construction throughout.

**Still not wired into `logical_error_rate`.** At d=5 the rate remains above the physical
rate, so no threshold is recoverable from this decoder yet. **825 passing.**

---

### 3.23 Round 12: the 12-pair fix measured 4x worse -- path-based attribution is the wrong frame

Round 12 implemented the fix �3.22 identified as "the fix the evidence points to": keep
the unmerged graph, and force the **merged pair's** observable onto every parallel
mechanism of that pair, so the per-mechanism attribution matches the reference's merged
label.

**It measured 127.8 against 30 -- roughly four times worse.**

```
  d=3 p=0.003, multi-seed (3/7/9/11/13), 2000 shots
    reference mean  4.0
    t-join mean   127.8     (previous state: 28.8)
  d=3 p=0.001: ref 0/2000  t-join 50/2000
  d=5 p=0.003: ref 1/2000  t-join 245/2000
```

Reverted. **Three separate attempts to adopt the reference's observable convention have
now all measured worse:**

| attempt | d=3 p=0.003 |
|---|---|
| unmerged, per-mechanism labels (current best) | **30** |
| merged graph, ANY labels, endpoint-label matching (�3.20) | 193 |
| merged XOR labels (�3.17) | 130 |
| unmerged graph, pair-level ANY labels (�3.23) | 128 |

**The conclusion the evidence forces.** Path-based observable accumulation is
fundamentally incompatible with the reference's per-edge labels, and the reason is
structural rather than a matter of getting a convention right:

* The reference's label is meaningful because its correction **is the matched edge set**.
  The observable of that set is the XOR of its edge labels -- one label per edge, summed
  once.
* My decoder **routes paths** and XORs labels *along* them. A path crossing a
  labelled pair contributes that label once per traversal, and forcing the label onto
  every parallel mechanism makes it contribute on every route that uses the pair. The
  two quantities are not the same, which is why moving the label between conventions
  moved the error rate between 30 and 193 without ever converging.

So the earlier framing -- "the label cannot be adopted without the topology, and the
topology without the label fails too" -- was **incomplete**. The accurate statement is
that the label and the *reduction* must be adopted **together**: per-edge labels only
have meaning in a formulation whose output is an edge set.

**That is now the single, well-posed requirement.** The decoder needs a minimum-weight
matching **whose output is the matched edge set on the merged graph**, with observables
taken from those edges. Enumerating perfect matchings on a metric closure -- which is
what the current matcher does -- cannot produce that, because it commits to pairwise
routes rather than to a set of edges.

**Objective status after twelve rounds.**

| established | how |
|---|---|
| It is my approach, not the algorithm | seven defects, each found by measurement |
| The graph, weights and reduction are right | weights match to 0.2%; 0% invalid corrections |
| The cost model is right | my solutions are strictly *lighter* than the reference's |
| Path-based observable accumulation is the wrong frame | three conventions tried, all worse |

Quality stands at **30/2000 against the reference's 5** at d=3 p=0.003, from **152** at
the start of the decoder work. **Not wired into `logical_error_rate`**; at d=5 the rate
remains above the physical rate, so no threshold is recoverable from this decoder.

**825 passing.**

---