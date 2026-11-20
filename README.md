# Quantum Entanglement Link (QEL)

[![licence](https://img.shields.io/badge/licence-Apache--2.0-blue)](LICENSE)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![more work](https://img.shields.io/badge/more_work-kellersystems.dev-16222c?labelColor=7a2e2e)](https://kellersystems.dev)

A quantum communication network simulation stack: qubits, gates, noise and
error correction at the bottom; the standard protocols in the middle;
repeater placement and fidelity-constrained entanglement routing at the
top. Everything runs in Python on a laptop. No hardware, no optics, no
network sockets.

```text
1161 tests passing · 21 CLI commands · 10 protocols and codes · 64 modules
```

> These counts are measurements, not claims: `1161` is the output of
> `py -m pytest -q` and `21` is the top-level command count from
> `py -m quantumnet --help`, both re-run whenever this line changes. If you change
> the code, re-run them and update this line in the same commit. `py scripts/claim_audit.py`
> prints all four beside what they currently measure.
>
> The "core primitives" figure that used to sit here (9, then omitted) was never
> reproducible from a command, so it has been replaced by the module count, which
> is. A number nobody can regenerate is how this line drifted to a test count of
> 668 while the suite actually ran 1036. Do not estimate this line. Regenerate it.

## Reproduce every claim in this repository

Each command prints what it measured beside what the text claims, so you can check the
documents against the code rather than taking either on trust.

```bash
py -m pytest -q                  # 1161 tests, about 6 minutes
py -m quantumnet validate        # every published comparison, scored or explicitly unscored
py scripts/claim_audit.py        # every numeric claim in the docs, beside what is measured
py scripts/ontology_audit.py     # five checks where a one-parameter model diverges from the full one
```

`validate` is the one that matters for the results: it re-derives each published figure,
scores the comparisons that apply, and lists the ones that do not alongside the reason.
Scored comparisons carry a **2% tolerance** and the command exits **1** with the failing row
marked `[MISS]`, so a regression is a failed build rather than a number that drifted quietly.
`claim_audit` is the one that matters for the prose: it extracts every count the
documentation asserts and prints the measurement next to it, because a stale number is
indistinguishable from a correct one until someone recomputes it.

For the decoder, before trusting any threshold it prints:

```bash
py validation/demo.py            # self-validates the instrument first, then benchmarks
py validation/demo.py --full     # five seeds and three distances, several minutes
```

The demo validates its own syndrome checker against known-good and known-bad corrections
before measuring anything, and stops if that fails. An instrument only ever shown to accept
is indistinguishable from one that always accepts.

**Where this repository disagrees with its sources, the disagreement is published.** Two of
four statements transcribed from the decoy-state literature do not reproduce, and both are
reported as results in §4.4 of `WHITEPAPER.md` with the reason. The test suite fails if
either drifts toward *better* agreement, because closing that gap would mean a bound had
been loosened.

## What it is

QEL is a simulator for quantum communication networks. It asks a question a classical
mesh never has to: *if the links were quantum, where do the repeaters go, and what
fidelity survives the trip?*

It models the whole path rather than a link budget. Quantum states are density
matrices, so decoherence is simulated directly: depolarising, dephasing and
amplitude-damping channels act on them, links attenuate with distance, memories relax
on T1 and lose phase on T2, and entanglement must be distilled back to something
usable before a key can be extracted. Above that sit resource contention, topology
routing, repeater placement, and a surface code with its own decoder.

### What this is for, and what it is not

**It is a research instrument.** Every number in this README is reproducible from a
command, and the places where the model *disagrees* with published work are kept and
explained rather than tuned away. The negative results are part of the record: a
calibration that reproduces two of four published statements says so, and a conclusion
that turned out to be wrong is marked as retracted rather than deleted.

**It is not a hardware model.** Nothing here has been validated against physical
hardware, and the outputs do not predict what hardware would achieve. A modelled
123 km reach for a preset calibrated to a 122 km experiment is a consistency check on
the model, not a measurement, and not a claim about a real link.

That distinction governs how to read everything below. Where a figure is a
reproduction of someone else's published result, it says so and cites it. Where it is
a property of this simulator, it says that instead.

### The results that are specific to this work

Five pieces go beyond assembling published methods:

1. **The routing weight is `-log W`, not `-log F` — and key-rate routing (`skr-optimal`)
   reverses it when the swap tax dominates.** Entanglement swapping multiplies the Werner
   parameter, so `-log W` is *exactly* additive for end-to-end fidelity and shortest-path
   search is optimal rather than approximate. The common substitute `-log F`
   under-penalises low-fidelity links and picks a strictly worse path about 1.3% of the
   time. When the objective is secret bits/s rather than fidelity, each swap also pays the
   linear-optics Bell-state-measurement efficiency `p_BSM <= 1/2`, and a stratified `h`-hop
   search (`skr-optimal`) picks a 1-hop path (`19,822 bits/s`) delivering 19.4% more secret
   key than the 3-hop `-log W` winner (`16,608 bits/s`). See
   [Routing strategies](#routing-strategies).
2. **An in-package surface-code decoder, with no third-party matcher on the threshold
   path.** It computes an exact minimum-weight T-join, matches PyMatching on both accuracy
   (24 against 26 logical errors over 18,000 shots at d=3, 5, 7, recovering a threshold
   near p ≈ 0.007) and total matching weight (647 of 647 non-trivial shots at d=3 and 2,239
   of 2,239 at d=5, max gap 0.00), and includes optional two-pass correlated reweighting
   (`decode_correlated`) and heralded erasure support (`w = 0`). See
   [Surface code and its decoder](#surface-code-and-its-decoder).
3. **Repeater placement as a chance constraint over continuous uncertainty**, a reliability
   target expressed on coherence-time distributions rather than a hand-picked scenario
   list. For a homogeneous chain, memory survival depends on `(T1, T2)` only through the
   sum `Gamma_eff = 1/T1 + 1/T2`, so the two-parameter continuous chance constraint reduces
   without approximation to the 1D `(1 - eps)`-quantile of `Gamma_eff` (`exact_1d=True`).
   See [Repeater placement](#repeater-placement).
4. **Five direct comparisons (`scripts/ontology_audit.py`) between one-parameter
   approximations and the full models in this package:** four-parameter Bell-diagonal
   `XState` swapping under `T1/T2` against one-parameter Werner states; `-log W` against
   `skr-optimal`; the `O((η_A + η_B) p_d)` single-photon-plus-dark Barrett–Kok false herald
   against `O(p_d²)`; stretched-exponential (`beta = 3`) spin-bath memory against Markovian
   `exp(-t/T2)`; and asynchronous Mode-Pairing QKD (`O(sqrt(η))`) against the repeaterless
   PLOB bound and one-repeater capacity `K_2`. See
   [Where a one-parameter model gives the wrong answer](#where-a-one-parameter-model-gives-the-wrong-answer).
5. **A logical key rate**, meaning "key rate after error correction", which almost nobody
   reports, with the code's cost in both fidelity and physical qubits stated alongside the
   number.

Each of those has a section below, including its limits.


## The layers

| Layer | Modules | What it does |
|---|---|---|
| **Core** | `qubit`, `xstate`, `gate`, `measurement`, `noise`, `channel`, `physical`, `photonics`, `stabilizer`, `scheduler`, `ipc_node`, `surface_code`, `tjoin_decoder`, `logical` | Density-matrix states, Wootters concurrence, and the four-parameter Bell-block-diagonal `XState` algebra for non-Pauli `T1/T2` swapping; unitary gates and Pauli algebra; projective and POVM measurement with collapse; depolarising/dephasing/amplitude-damping noise; distance-dependent channel attenuation; hardware-level impairment models and four-branch Barrett–Kok false-herald accounting; Clifford tableau simulation; an asynchronous discrete-event scheduler; a multi-process node architecture; the rotated surface code with its space-time detector model; **an in-package minimum-weight T-join decoder**; and the logical-error-rate measurement that uses it |
| **Protocols** | `bb84` (+ decoy state, PLOB/`K_k`, Mode-Pairing), `e91`, `bell`, `teleportation`, `superdense`, `swapping`, `distillation`, `memory`, `shor`, `steane` | QKD with an intercept-resend eavesdropper; **decoy-state BB84 with a finite-key penalty** (analytic, on a lossy link), Werner BBM92 key fraction (`2(1-F)/3`), PLOB / `k`-repeater capacities, and asynchronous Mode-Pairing QKD; Ekert entanglement-based QKD; Bell preparation and CHSH inequality tests; teleportation; superdense coding; entanglement swapping; BBPSSW, Deutsch and DEJMPS distillation; T1/T2 memory dynamics; the Shor 9-qubit and Steane 7-qubit CSS error-correcting codes |
| **Topology** | `graph`, `routing`, `dijkstra`, `strategies`, `placement`, `chance_placement`, `shapes`, `schedule`, `events`, `resources`, `visualize`, `importers` | Quantum network graphs with physical fidelity models; exact Werner-algebra swapping; **pluggable routing strategies (`fidelity-optimal` and `skr-optimal`)**; Pareto-exact and chance-constrained repeater placement; ring/grid/FatTree/BCube topology builders; a time-aware and an event-driven distribution schedule; memory resource management with contention; dependency-free ASCII visualisation; and a pluggable import surface |
| **Importers** | `topology/importers` | QEL's versioned native schema (`qel-json`), the legacy Ghost-Net bridge (`ghostnet`), a strict Graphviz subset (`dot`), and SeQUeNCe `RouterNetTopo` interop. All produce the same canonical shape; nothing in routing, scheduling or visualisation knows where a topology came from |

## Routing strategies

Routing is a pluggable policy, not a function. Five ship, and a third party can
register another without editing QEL:

```python
from quantumnet.topology import make_strategy, compare_strategies, fat_tree

topo = fat_tree(4)
comparison = compare_strategies(topo, "host0_0_0", "host3_1_1")
print(comparison.describe())          # every strategy, side by side
make_strategy("fidelity-optimal").forwarding_table(topo)
make_strategy("skr-optimal").route(topo, "host0_0_0", "host3_1_1")
```

| Strategy | Weight | Notes |
|---|---|---|
| `fidelity-optimal` | `-log W`, `W = (4F-1)/3` | The default. **Provably** the highest-fidelity route |
| `skr-optimal` | stratified `h`-hop search on `-log W` | **Provably** the highest BBM92 secret-key-rate route under bottleneck rate, linear-optics `p_BSM^(h-1)`, and Werner QBER `2(1-F)/3` |
| `shortest-distance` | link km | The incumbent simulator's stock policy, kept as the control |
| `fewest-hops` | 1 per link | The obvious naive choice |
| `static` | a supplied table | Reproduces a fixed deployment |

**Why `-log W` and not `-log F`.** Entanglement swapping multiplies the Werner
parameter, so `W_path = Π W_i` and `-log W` is *exactly* additive, which is what
makes shortest-path search optimal rather than approximate. `-log F` is the common
substitute and it is wrong: it under-penalises low-fidelity links, by 1.34× at
`F = 0.99` and 2.25× at `F = 0.30`. On random graphs, `-log F` picks a strictly
worse path about 1.3% of the time, with observed losses up to **0.02 fidelity**.
`tests/test_topology/test_routing_optimality.py` contains a worked counterexample.

**What the difference is worth.** On a network where a short mediocre span
competes with three short good ones:

```text
shortest-distance   F = 0.700000   1 hop
fidelity-optimal    F = 0.970398   3 hops
```

**When `skr-optimal` picks a different path.** Each intermediate swap in linear optics
succeeds with probability `p_BSM <= 1/2`, so an `h`-hop chain's synchronous secret-key rate
scales as `(min_{e in P} R_gen(e) / h) * p_BSM^(h-1) * max(0, 1 - 2 H_2(2(1-F_e2e)/3))`.
No single edge weight can optimise that product, because it couples a bottleneck minimum,
a hop count, and `Π W_e`. There are at most `|E|` distinct bottleneck rates and at most
`|V| - 1` hops, though, and once `(R_min, h)` is fixed the remaining question is again
shortest path on `-log W` over links with `R_e >= R_min`. `SKROptimalRouting` checks every
`(R_min, h)` pair in `O(|E| h_max (|E| + |V| log |V|))` time:

```text
fidelity-optimal (-log W)   3 hops (S -> R1 -> R2 -> T)   F = 0.9372   16,608 bits/s
skr-optimal                 1 hop  (S -> T)               F = 0.9200   19,822 bits/s (+19.4%)
```

`tests/test_topology/test_strategies.py` confirms `fidelity-optimal` against exhaustive
brute force on random graphs and checks the `skr-optimal` inversion against the closed-form
rate, so "provably" is checked rather than claimed.

## Topologies

`ring`, `grid`, `fat_tree(k)` and `bcube(n, k)` are first-class builders, with a
registry so a shape can be selected by name.

```python
from quantumnet.topology import fat_tree, bcube, topology_report

report = topology_report(fat_tree(4))   # nodes, links, connected, degree stats
```

FatTree and BCube are included for a specific reason: unlike a symmetric grid,
their path redundancy is **non-uniform**, so they can separate routing policies
that a grid cannot. `topology_report` includes connectivity, because an
unreachable pair and a routing failure look identical in most outputs and are
different problems.

**NetworkX interop is deliberately not provided.** The canonical `QuantumTopology`
is already the interface every consumer uses, and the project's promise is
`numpy` only, because a second dependency is not worth saving a hundred lines.


## Routing over a parsed topology

`topology/importers` turns any topology file into one shape, then the exact
same routing, scheduling and visualisation layers take over::

    from quantumnet.topology.importers import parse
    from quantumnet.topology.routing import best_route
    from quantumnet.topology.schedule import distribute

    doc = parse("mesh.qel.json", schema_id="qel-json")   # or "ghostnet", "dot"
    route = best_route(doc, "A", "D", min_fidelity=0.0)
    dist = distribute(doc, route)

That is the whole contract. The import layer only *produces* `nodes` and
`links`; the routing layer only *consumes* them.

## Run it

```bash
py -m pip install -e ".[dev]"

py -m pytest -q                     # 1161 tests, ~6m
py -m quantumnet all                # every protocol demo
py -m quantumnet topology --help    # build / route / visualise a topology
py -m quantumnet import --help      # route over a parsed topology export
py -m quantumnet qkd-derive --help  # key material at an explicit fidelity
py -m quantumnet qkd --help         # decoy-state key rate over a fibre link
py -m quantumnet bench --help       # key rate vs distance sweep
py -m quantumnet contend --help     # competing demands for finite memory
py -m quantumnet link --help        # physical-layer budget for one span
py -m quantumnet validate           # recompute published key-rate figures

py scripts/audit_imports.py         # every module must import cleanly
py scripts/verify_surface_code.py   # surface-code invariants vs stim (dev-only)
py scripts/decoder_claim_check.py   # in-package decoder vs the reference (needs both)
py scripts/ontology_audit.py        # five one-parameter vs multi-parameter model checks
```

The 21 commands: `bb84`, `e91`, `teleport`, `superdense`, `swap`, `shor`,
`steane`, `distill`, `memory`, `all`, `stabilizer`, `physical`, `topology`,
`import`, `ghost-net`, `qkd-derive`, `qkd`, `bench`, `contend`, `link`,
`validate`.

## Physical layer

`link` reports the optical budget for one fibre span, including the Barrett–Kok
entanglement-generation probability.

```bash
py -m quantumnet link --distance 50
py -m quantumnet link --distance 150 --detector-efficiency 0.045 --dark-count 10
```

The model follows Barrett and Kok (PRA **71**, 060310(R), 2005) and holds to the
two published properties of double heralding:

- **the ideal success probability is 1/2**, which the paper states as the
  protocol's theoretical upper limit, and the model returns it exactly at zero loss;
- **it is quadratic in detector efficiency** (`p ∝ η²`), because both photons must
  survive and both must be detected.

The consequence worth knowing when reading any number it prints: **loss costs
rate, not fidelity.** A photon that fails to arrive is a failed attempt, not a
corrupted pair. What *does* degrade fidelity is a **dark-count false herald**,
indistinguishable from a real two-photon event, and it contributes a maximally mixed
pair (fidelity 1/4), along with mode mismatch and memory decoherence. In
`core/photonics.py`, `BarrettKokResult` provides both the legacy `O(p_d²)` two-dark
expression (`raw_fidelity()`) and the full four-branch expression (`exact_fidelity()`),
which includes the `O((η_A + η_B) p_d)` event where one round is triggered by a real
photon and the other by a dark count. At 50–150 km `η` is much larger than `p_d`, so that
cross-term dominates the two-dark term by two to three orders of magnitude: at 150 km
(`η = 8e-4`), raising `p_d` from `1e-5` to `1e-4` drops `exact_fidelity()` from **0.9311
to 0.6031** (zero BBM92 key) while `raw_fidelity()` still reports **0.9773** and the
apparent herald rate rises from `3.28e-7` to `4.05e-7`.

`link` prints **two** generation rates deliberately. `QuantumLink.generation_rate()`
models a *single-photon* scheme (one photon per arm), while Barrett–Kok is
*double-heralded*; they differ by exactly the factor of 1/2. Both are correct for
their own hardware, and the command shows them side by side rather than letting
one be mistaken for the other.

## Multi-user contention

A quantum network is contended: two demands want the same memory at the same
time and one has to be refused. `contend` runs competing demands against a
finite memory pool on a single timeline, so a pool too small for the demand set
produces refusals rather than an optimistic answer.

```bash
py -m quantumnet contend                                    # 4 nodes, 2 memories each
py -m quantumnet contend --nodes 3 --memory 2 --demands 6   # forces contention
py -m quantumnet contend --memory 40 --demands 3            # control: all granted
```

What it models:

- **Memory states** `raw / entangled / occupied`, with illegal transitions
  rejected rather than silently allowed.
- **Reservations** carrying a target fidelity, a memory count and a start/end
  window, with a full lifecycle (pending, active, rejected, expired, fulfilled,
  released) and selectable slot-ordering policies (`"newest-first"` / LIFO to
  reduce hold-time decoherence, or `"oldest-first"` / FIFO).
- **Threshold grouping (`classify_entanglement_tiers`).** `MemoryArray` groups live
  entangled slots by the threshold they still clear: `F > 0.83496` for direct BBM92 key
  extraction, `0.78033 < F <= 0.83496` where Werner QBER `2(1-F)/3` yields zero BBM92 key
  but `S_CHSH = 2 sqrt(2) W > 2` still certifies a Bell violation, and
  `0.5 < F <= 0.78033` as input stock for distillation.
- **Both-ends negotiation.** A demand needs memories at each end; if either end
  cannot supply, the request is refused and **nothing is left allocated** at the
  other end.
- **Expiry in both senses.** A demand past its end time releases its memories,
  and a pair that decays below the usable threshold releases its slot early
  rather than being held to the deadline.
- **Deterministic arbitration:** higher priority first, then arrival order. An
  implicit tie-break would allocate the same scenario differently across runs.

## Decoy-state key rate

The `qkd` and `bench` commands compute the **analytic** decoy-state BB84 key
rate on a lossy fibre link. `protocols/bb84.py` also includes the Werner BBM92 key
fraction (`qber_model="werner"`, `e_Z = e_X = 2(1-F)/3`, zero-key threshold `F* = 0.83496`),
the Pirandola–Laurenza–Ottaviani–Banchi (PLOB) repeaterless capacity
`K_PLOB(η) = -log2(1 - η)`, the `k`-repeater capacity `K_k(η) = -log2(1 - η^(1/k))`, and
asynchronous Mode-Pairing QKD (`mode_pairing_qkd_rate`, scaling as `O(sqrt(η))` within a
pairing window `L_max`). No qubits are simulated for these numbers, because
the closed-form analysis is what the QKD literature reports and what makes a
quoted rate defensible against a photon-number-splitting attack.

```bash
py -m quantumnet qkd --distance 50            # 8.9e5 bits/s at 50 km
py -m quantumnet bench --stop 300             # rate vs distance, max reach
py -m quantumnet qkd --distance 50 --pulses 1e10   # with the finite-key penalty
```

What it does and does not account for:

- **Accounts for:** the vacuum + weak decoy estimator for the single-photon
  yield `Y1` and error rate `e1`; dark counts; detector efficiency and
  intrinsic misalignment; error-correction inefficiency `f_EC`; and basis
  reconciliation.
- **With `--pulses`,** switches to the finite-key accounting of
  Lim–Curty–Walenta–Xu ([arXiv:1311.7129](https://arxiv.org/abs/1311.7129)):
  an absolute block secrecy cost, statistical fluctuations applied to the
  observed counts inside the decoy estimators, and a separately bounded phase
  error rate.
- **Does not account for:** detector dead time and afterpulsing, source
  imperfections beyond intensity, and any hardware-specific deviation from the
  modelled channel. The asymptotic path is the standard
  asymptotic-plus-estimator analysis, not a composable-security proof.

Two things worth stating plainly, because both are easy to get wrong:

1. **The asymptotic and finite-key numbers use different estimators and are not
   comparable by subtraction.** The finite-key path can legitimately return a
   *higher* rate, because it uses a tighter phase-error bound and counts the
   vacuum contribution that the asymptotic expression drops. A tighter
   estimator yielding more key is not a bug.
2. **With no dark counts the asymptotic model has no maximum distance.** Both
   rate terms scale with the channel transmissivity, so the rate stays positive
   at every finite length; `bench` reports `inf` rather than a fabricated reach.

Five hardware presets ship, including `gobby-yuan-shields`, whose modelled reach
is ~123 km against the 122 km that experiment demonstrated, and
`sequencer_erlang`, parameterised to be comparable with SeQUeNCe's
erbium/atom-cavity numbers. Note that GYS predates practical decoy-state
implementations, so that agreement is a consistency check on the channel and
detector model, not a reproduction of a decoy-state experiment.

## Surface code and its decoder

`core/surface_code.py`, `core/tjoin_decoder.py` and `core/logical.py` form the
error-correction chain. The rotated code is built for d ∈ {3, 5, 7, 9}. Layouts are
**pinned per distance and verified against `stim`**, and any other distance is refused
rather than guessed, because a wrong ancilla layout still produces plausible numbers.

The decoder computes an **exact minimum-weight T-join** on the graph `stim`'s detector
error model defines. Measured on this package's own circuits:

```text
d=3 p=0.003, 5 seeds x 6000 shots:  0.00220  [0.00173, 0.00280]   66/30000
d=5 p=0.003, 5 seeds x 6000 shots:  0.00080  [0.00054, 0.00119]   24/30000
d=7 p=0.003, 5 seeds x 6000 shots:  0.00040  [0.00023, 0.00070]   12/30000
                                                     monotone in d, as a code must be
```

Those three values previously read `0.00100 / 0.00033 / 0.00000`, which was wrong: one
event in 6000 is 0.000167, so `0.00100` would be six events, and the measured counts were
10, 4 and 2. The error survived because the wrong numbers formed a cleaner monotone
sequence than the right ones. Guarded now by `core/uncertainty.py`, which reports the
interval each sample size can support, and by the arithmetic check in
`scripts/claim_audit.py`, which rejects any line whose stated rate is not an achievable
count at its own sample size.

```text
threshold sweep, 20 000 shots per point, decoder alone:
  p=0.005  d=3 0.00565  d=5 0.00355  d=7 0.00230
  p=0.006  d=3 0.00735  d=5 0.00645  d=7 0.00375
  p=0.007  d=3 0.00930  d=5 0.00900  d=7 0.00740
  p=0.008  d=3 0.01290  d=5 0.01350  d=7 0.01000   <- ordering reverses
```

**Threshold p ≈ 0.007.** The reversal above it is the point: a threshold is only a real
result if more distance eventually *hurts*, and a test asserts the ordering flips rather
than only checking the sub-threshold half.

**No third-party matcher is needed.** The decoding path imports `stim` for the circuit
and the DEM, and nothing else. Verified by blocking `pymatching` at the import system so
a hidden use becomes a hard error:

```text
HAVE_PYMATCHING = False,  pymatching in sys.modules: False
d=3 p=0.003: 4/2000    d=5: 1/2000    d=7: 0/2000    decoder='in-package'
```

**Its accuracy and total matching weight match PyMatching's.** Over 18,000 shots at d=3, 5
and 7 the two decoders make **24 and 26 logical errors** respectively, and across 1,000
shots per noise level at d=3 (647 non-trivial shots) and d=5 (2,239 non-trivial shots),
`py scripts/decoder_claim_check.py --shots 1000 --distances 3 5` measures **100.0%
total-weight agreement** (`647/647` at d=3, `2239/2239` at d=5, `max gap 0.00`) and
**100.0% / 99.7% edge-set agreement** (the 6 differing shots at d=5 have identical total
weight and are equal-weight ties on the lattice).

**Why an earlier version of this file reported a weight discrepancy.** A previous revision
stated that `tjoin_decoder` agreed with PyMatching on only `1/647` edge sets at d=3 and
`0/2239` at d=5 while returning a heavier matching in four cases out of five. The fault
was in `scripts/decoder_claim_check.py:125`, which passed the raw boolean syndrome row
`det[i]` instead of the fired detector indices `np.flatnonzero(det[i])` to
`decode_edges_and_observables()`, turning every non-empty syndrome into a subset of
detectors `{0, 1}`. Passing `np.flatnonzero(det[i])` closed the weight gap to `0.00`.

**Correlated reweighting and heralded erasures.** Two optional extensions sit on the same
graph builder in `core/tjoin_decoder.py` and `core/surface_code.py`:

- **`decode_correlated` (`parse_dem_correlations`):** reads compound `^`-separated DEM
  instructions (`Y`-error mechanisms that fire both `X`- and `Z`-type detectors), runs a
  first pass on the marginal graph, updates partner-edge weights to the conditional
  log-likelihood `log((1 - p(e2 | e1)) / p(e2 | e1))`, and runs a second pass.
- **`heralded_erasure_fraction` (`erasure_edges`):** sets flagged erasure edges to weight
  `log((1 - 0.5) / 0.5) = 0`.

**Two defects fixed in an earlier in-package attempt**, both worth knowing because
each produced plausible-looking wrong answers:

- **Observables must be parsed per `^`-separated component.** `stim` writes
  `error(p) D4 D6 ^ D5 L0`, where `L0` belongs to the `D5` component *only*. Reading
  observables across the whole instruction attaches `L0` to pair `(4, 6)` as well.
- **The edge weight is `log((1-p)/p)`, not `-log(p)`.** The two differ by 0.5–0.7% at
  the probabilities this code reaches, which is enough to change which path is chosen.

**Scope.** The component solver `_solve_component_max_saving` uses a bitmask depth-first
search capped at `max_steps = 4000` per connected component; at d ∈ {3, 5, 7}
sub-threshold components are small and solved exactly, whereas dense high-noise components
with roughly 14 or more odd vertices return the best matching found when the cap expires.
There is no `surface` CLI command yet. The decoder is reachable through the Python API
(`logical_error_rate`) and the tests, and `matcher="pymatching"` selects the reference for
comparison.

## Repeater placement

`topology/placement.py` answers the synthesis question directly: given candidate sites
along a span, which subset and what key rate?

```python
from quantumnet.topology.placement import PlacementProblem, CandidateSite, best_placement

best = best_placement(PlacementProblem(
    end_a=CandidateSite("A", 0.0), end_b=CandidateSite("B", 200.0),
    candidates=[CandidateSite(f"S{i}", 20.0 * (i + 1)) for i in range(8)]))
# 4 sites at 40/80/120/160 km -> 1.16e5 Hz, F = 0.96079, longest link 40 km
```

`best_placement` is a dynamic program over sites in position order carrying a **Pareto
frontier** of (rate, fidelity) per state, because the best rate per state is not
sufficient: two chains reaching the same site with the same repeater count are not
interchangeable. It is **exact**, verified against constraint-matched brute force on 25
random instances (0 suboptimal).

`topology/chance_placement.py` adds the piece a literature search found missing. Existing
formulations are *discrete*: choosing components from a catalogue, or greenfield siting,
plus post-hoc sensitivity analysis. This states the requirement as a chance constraint
over a **continuous** coherence-time prior:

```text
Pr[ F(chain; T1, T2) >= F_req ] >= 1 - eps
```

For a homogeneous repeater chain, every link hold time enters memory survival through
`exp(-t * (1/T1 + 1/T2))`, so chain fidelity depends on `(T1, T2)` only through the single
scalar rate `Gamma_eff = 1/T1 + 1/T2` and is strictly decreasing in it. By the isoquantile
principle, the two-parameter continuous chance constraint reduces **without approximation**
to evaluating the chain at the 1D `(1 - eps)`-quantile of `Gamma_eff`
(`exact_1d_scenario`, `exact_1d=True`) for any joint or independent prior on `(T1, T2)`.
The product-margin bound (lower `eps/2` tail per coordinate) and the common-factor bound
(lower `eps` tail) are kept alongside `exact_1d=True` for comparison and for heterogeneous
chains where a single scalar `Gamma_eff` no longer factors out.

## Logical key rate

"Key rate after error correction" is a number almost nobody reports, which is why it is
worth stating carefully. `logical_key_rate` composes the physical pair's fidelity with the
logical flip through the **Werner product** and reports the qubit cost alongside:

```text
F_phys = 0.99, p = 0.003, five syndrome rounds
  d=3:  F_log 0.98186   key fraction 0.8509    34 physical qubits per logical pair
  d=5:  F_log 0.98556   key fraction 0.8765    98
  d=7:  F_log 0.98926   key fraction 0.9035   194
```

**A bug worth recording, because it was mine and it was large.** An earlier version
combined the two error sources as a *weighted average of fidelities*,
`F = F_phys(1-q) + (1-F_phys)q`, which treats a bit-flip *probability* as a fidelity. The
correct composition is the Werner product above, and the two differ by up to **9%
absolute**, with the sign of the error not even consistent across inputs:

```text
F_phys  F_log     q      corrected      old      overstatement
 0.990  0.996  0.004      0.982114   0.986080      +0.003966
 0.950  0.900  0.050      0.815500   0.905000      +0.089500
```

It went unnoticed for as long as it did because at `F_phys = 1` the two forms agree, and
that is the input the other modules happened to use.

## Where a one-parameter model gives the wrong answer

Most network simulators compress link states to a single Werner scalar `F`, routing to a
single link weight, Barrett–Kok dark counts to `O(p_d²)`, memory dephasing to exponential
`exp(-t/T2)`, and point-to-point QKD to the repeaterless PLOB bound.
`py scripts/ontology_audit.py` runs each one-parameter approximation beside the full
calculation in QEL:

| Comparison | One-parameter approximation | Full model in QEL | Measured difference (`py scripts/ontology_audit.py`) |
|---|---|---|---|
| **1. Non-Pauli link state** | 1-parameter Werner state `rho_W(F)` | 4-parameter Bell-block-diagonal `XState(P_Phi, Delta_Phi, alpha, beta)` under `T1/T2` and swapping (`core/xstate.py`) | 4-hop chain (`gamma=0.15, eta_phi=0.95`): Werner `F_4=0.4999, C=0` vs `XState` `F_Psi,4=0.5054, C_Psi,4=0.0108`; one-sided damping (`gamma_A=0.80`): `XState C=0.4472` vs Werner `0.0472` (**9.5×**); `|Psi+⟩` pre-flip keeps `C=0.3000` at `gamma=0.70` |
| **2. Routing objective** | Additive `-log W` maximises end-to-end fidelity | Stratified `h`-hop Dijkstra (`skr-optimal`) with `p_BSM^(h-1)` and Werner BBM92 QBER `2(1-F)/3` | `-log W` picks 3-hop path (`F=0.9372`, `16,608 bits/s`); `skr-optimal` picks 1-hop path (`F=0.9200`, `19,822 bits/s`, **+19.4% secret key**) |
| **3. Barrett–Kok dark counts** | Two-dark `O(p_d²)` coincidence (`raw_fidelity`) | Four-branch trajectory including `O((η_A+η_B)p_d)` 1-photon + 1-dark false herald (`exact_fidelity`) | At 150 km (`p_d=1e-4`): `raw_fidelity` reports **0.9773** while `exact_fidelity` is **0.6031** (zero key) and apparent herald rate rises |
| **4. Spin-bath memory** | Markovian exponential `exp(-t/T2)` (`beta=1`) | Stretched-exponential `exp(-(t/T2(N))^beta)` (`beta=3`) with cumulative bath age (`core/physical.py`) | At `t/T2=0.1`: `beta=3` loses **95.2× less coherence** (`7.50e-4` vs `7.14e-2`); un-reset bath age penalises the next hold (`F=0.5626` vs fresh `0.9119`) |
| **5. Point-to-point vs 1-repeater** | Point-to-point QKD bounded by `K_PLOB(η) = -log2(1-η)` | Asynchronous Mode-Pairing QKD (`mode_pairing_qkd_rate`, `O(sqrt(η))`) checked against `K_PLOB(η)` and `K_2(η)` (`protocols/bb84.py`) | At 380 km: memoryless Mode-Pairing reaches `1.08e-5 bits/pulse`, **350× above** `K_PLOB` (`3.08e-8`) while staying below `K_2(η) = 2.11e-4` |

## What is real and what is simulated

- **Real:** the quantum mechanics. States, the four-parameter `XState` algebra, gates,
  measurement collapse, noise channels, the stabilizer formalism, the
  error-correcting codes, the distillation algorithms, and the fidelity and
  concurrence arithmetic all behave as written.
- **Real:** the decoy-state, BBM92, PLOB/`K_k`, and Mode-Pairing key-rate arithmetic.
  The estimators and rate formulas are the published ones, and the implementation is
  checked against them in the test suite rather than asserted.
- **Real, and self-contained:** the surface-code decoder. `tjoin_decoder`
  computes an exact minimum-weight T-join on the graph Stim's detector error
  model defines, with optional two-pass correlated reweighting and heralded
  erasure support. **No third-party matcher is needed to get a threshold**:
  measured at p ≈ 0.007 with `stim` and `numpy` alone, matching PyMatching on both
  accuracy (24 against 26 logical errors over 18,000 shots at d=3, 5, 7) and total
  matching weight (647 of 647 non-trivial shots at d=3 and 2,239 of 2,239 at d=5,
  max gap 0.00). PyMatching remains an optional **comparison** oracle, not a
  dependency. `matcher="pymatching"` selects it to check the in-package result, and
  nothing on the default path imports it.
- **Simulated:** the hardware and the network. There are no photons, no
  fibre and no sockets; `ipc_node` uses real processes, but the links between
  them are modelled.
- **Scope:** these are simulator results. They do not predict what physical
  hardware would achieve. A modelled 123 km reach for a preset calibrated to a
  122 km experiment is a consistency check on the model, **not** a measurement.

## Layout

```text
src/quantumnet/core/        states, xstate, gates, measurement, noise, channels, stabiliser, scheduler
                            surface_code, tjoin_decoder, logical  (the surface-code chain)
                            multiplexing, photonics, latency      (hardware-layer timing)
src/quantumnet/protocols/   QKD (incl. decoy state), teleportation, superdense, swapping, distillation, memory, QEC
src/quantumnet/topology/    graphs, fidelity & SKR routing, schedules, visualisation, import surface
                            placement, chance_placement, commodities, fusion_order, load
src/quantumnet/calibration/ library models checked against published datasets
src/quantumnet/cli.py       the 21-command interface, JSON on stdout, everything else on stderr
src/quantumnet/topology/importers/   QEL native JSON, legacy Ghost-Net bridge, Graphviz, SeQUeNCe
tests/                      1161 tests, 64 modules, across core, protocols, topology and the CLI
validation/                 decoder-agnostic instruments: syndrome invariant, benchmarking
scripts/                    six development tools, all listed below
notebooks/demo.ipynb        worked demonstration
WHITEPAPER.md               the research write-up: results, negative results, limits
```

The six tools in `scripts/`:

| tool | what it does |
|---|---|
| `audit_imports.py` | every module must import cleanly. Catches a stale import that would break collection |
| `verify_surface_code.py` | surface-code lattice and schedule checked against `stim` at d = 3, 5, 7 and 9 (dev-only; needs `stim`) |
| `claim_audit.py` | extracts every test/command/module/line count from the docs and prints it beside what the repository currently measures |
| `decoder_claim_check.py` | measures the in-package decoder against PyMatching: accuracy, edge-set agreement and weight. Exits non-zero if the accuracy claim fails |
| `ontology_audit.py` | checks the five one-parameter vs multi-parameter model differences (`XState`, `skr-optimal`, Barrett–Kok cross-term, `beta=3` memory, Mode-Pairing QKD). Exits non-zero if any check fails |
| `make_notebook.py` | regenerates `notebooks/demo.ipynb` |

`decoder_claim_check.py` exists for a specific reason. This repository first claimed without
a script that its corrections were identical to PyMatching's, then added the script with a
boolean-indexing bug (`det[i]` instead of `np.flatnonzero(det[i])`) that made the weights look
divergent (`1/647`), and finally caught the script bug when auditing the syndrome interface.
Both errors are why the comparison lives in an executable script rather than a paragraph.

`claim_audit.py` exists because this repository accumulated stale claims during
development: a README asserting a test count the suite had moved past, a website
asserting another. Each was correct when written and rotted silently.
It reports; it does not decide, because a tool that guessed which number was right would
produce exactly the confident-but-wrong output the rest of this project is built to avoid.

## Validation against published results

Nothing here has been checked against hardware, and the honest way to earn
credibility is to reproduce numbers other people published. `validate` does
that, and reports the comparisons that *don't* apply as well as the ones that do.

```text
VALIDATED  (same quantity, same estimators)
  [OK  ] ma-vacuum-weak-gys
          published 140.55 km   qel 140.61 km   delta +0.06 km (+0.04%)

UPPER BOUND (must fall below, and near)
  [OK  ] ma-asymptotic-gys
          published 142.05 km   qel 140.61 km   below the bound: True
```

Ma, Qi, Zhao and Lo publish **140.55 km** as the maximum secure distance of the
vacuum+weak decoy method at the GYS parameters they tabulate (0.21 dB/km,
`e_det` 3.3%, `Y₀` 1.7e-6, `η_Bob` 0.045, `f(e)` 1.22, 2 MHz). Same estimators,
same `q = 1/2` asymptotic rate, so this is a like-for-like reproduction. QEL returns
**140.61 km: a 60-metre difference.**

Three things this deliberately does *not* do:

1. **It does not score the 142.05 km asymptotic figure as an equality.** That is
   the infinite-decoy ceiling; a finite-decoy estimator must fall *below* it, and
   QEL does. Scoring it as a match would fail a correct model.
2. **It does not score the Boaron 421 km record**, which is quoted constantly.
   Their protocol is 3-state time-bin with a one-decoy finite-key bound
   (`6·log2(19/ε)`); QEL models asymptotic decoy BB84. Comparing rates across the
   two would measure the protocol difference.
3. **It does not hide either of the above.** Unscored comparisons are listed with
   their citations, because a suite that only shows what it passes is marketing.

The Boaron loss budget *is* comparable, since fibre loss is a property of the fibre,
and it checks out: all five rows of their Table I agree within 0.5 dB, and the
implied coefficient is 0.1696–0.1712 dB/km, consistent with the single
ultra-low-loss fibre they describe.

**The scope limit, stated plainly:** this validates the implementation against
the *model those authors used*. It is not a claim about hardware.

## Where the numbers come from

The rule this repository follows, and the standard to hold it to: **every claim about
QEL's own state is either backed by a command that produced it, or it is not stated.** No
feature is called done because a file exists or a symbol has the right name.

That rule is enforced rather than trusted. Where the code and the documentation disagree,
one of them is a bug. The three commands at the top of this file are how you find out
which, without reading either.

`claim_audit.py` reports and does not decide. It cannot know which number is right, and a
tool that guessed would produce exactly the confident-but-wrong output the rest of this
project is built to avoid.

**Where the model disagrees with its sources, the disagreement is kept.** Two of the four
statements transcribed from Lo–Ma–Chen do not reproduce, and both are reported with the
reason rather than tuned away. The test suite fails if the decoy reach drifts toward
*better* agreement, because that would mean a bound had been loosened.

## Is 1161 tests a lot?

Measured against comparable libraries rather than against intuition. The QEL row is
re-measured; the three comparator rows are from the original survey and were not
re-measured here:

| Project | Source lines | Test lines | Test:source |
|---|---|---|---|
| numpy | 117,552 | 121,462 | 1.03 |
| scipy | 340,112 | 234,272 | 0.69 |
| networkx | 116,857 | 74,878 | 0.64 |
| sympy | 492,618 | 260,744 | 0.53 |
| **QEL** | 16,923 | 13,060 | 0.77 |

QEL sits inside that range. The *absolute* count is large relative to the line count
because those 1161 tests come from **995 `def test_*` functions**, 57 of them parametrised and
expanding into many cases. One geometric invariant checked at five distances is five
tests from one function. The ratio, not the count, is the meaningful figure.

> Every figure in the table above was stale before this revision. An earlier heading still
> read 1036 (and then 1138) while the line counts read 15,351 / 11,529 (and then 16,182 /
> 12,358) as the tree grew to **16,923 source lines and 13,060 lines in `tests/`**. This is
> the same failure mode the headline count block warns about, recurring in a second place,
> which is why `py scripts/claim_audit.py` now measures all of them rather than leaving them
> to be noticed.

The shape differs from those libraries in one deliberate way: a large share of
QEL's tests check *physical identities and published values* rather than API
behaviour: `p = 1/2` exactly at zero loss, `p ∝ η²`, the `O((η_A + η_B) p_d)`
Barrett–Kok false-herald cross-term, gain matching the Poissonian identity,
`-log W` being exactly additive, `skr-optimal` routing inversion, the four-parameter
`XState` swapping recursion, the 1D `Gamma_eff` isoquantile reduction,
and brute-force agreement for the router and the placement optimiser. Those are the
tests that catch a model that has quietly become a *different* model, which is a
failure mode a coverage percentage cannot see.


## Provenance

QEL began inside [Vantablack](https://github.com/KELLERBABG/Vantablack) as
the quantum layer for the same mesh, and now lives here as its own system.
The legacy topology export format mentioned above is the only artefact of
that origin that survived: it is a single adapter in
`topology/importers/ghostnet.py` that produces the same canonical shape as
the new native format. Part of [Keller Systems](https://kellersystems.dev).
