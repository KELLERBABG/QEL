# Quantum Entanglement Link (QEL)

A quantum communication network simulation stack: qubits, gates, noise and
error correction at the bottom; the standard protocols in the middle;
repeater placement and fidelity-constrained entanglement routing at the
top. Everything runs in Python on a laptop — no hardware, no optics, no
network sockets.

```text
1036 tests passing · 21 CLI commands · 10 protocols and codes · 61 modules
```

> These counts are measurements, not claims: `1036` is the output of
> `py -m pytest -q` and `21` is the top-level command count from
> `py -m quantumnet --help`, both re-run whenever this line changes. If you change
> the code, re-run them and update this line in the same commit.
>
> The "core primitives" figure that used to sit here (9, then omitted) was never
> reproducible from a command, so it has been replaced by the module count, which
> is. A number nobody can regenerate is how this line drifted to a test count of
> 668 while the suite actually ran 1036. Do not estimate this line — regenerate it.

## What it is

QEL is a general purpose quantum layer for any network. It asks the harder
question than a classical mesh: *if the links were quantum, where do you put
the repeaters, and what fidelity survives the trip?*

It models the whole path. Quantum states are density matrices, so
decoherence is modelled directly: depolarising, dephasing and amplitude-
damping channels act on them, links attenuate with distance, memories relax
on T1 and lose phase on T2, and entanglement must be distilled back to
something usable before a key can be extracted.

## The layers

| Layer | Modules | What it does |
|---|---|---|
| **Core** | `qubit`, `gate`, `measurement`, `noise`, `channel`, `physical`, `stabilizer`, `scheduler`, `ipc_node`, `surface_code`, `tjoin_decoder`, `logical` | Density-matrix states and quantum information metrics; unitary gates and Pauli algebra; projective and POVM measurement with collapse; depolarising/dephasing/amplitude-damping noise; distance-dependent channel attenuation; hardware-level impairment models; Clifford tableau simulation; an asynchronous discrete-event scheduler; a multi-process node architecture; the rotated surface code with its space-time detector model; **an in-package minimum-weight T-join decoder**; and the logical-error-rate measurement that uses it |
| **Protocols** | `bb84` (+ decoy state), `e91`, `bell`, `teleportation`, `superdense`, `swapping`, `distillation`, `memory`, `shor`, `steane` | QKD with an intercept-resend eavesdropper; **decoy-state BB84 with a finite-key penalty** (analytic, on a lossy link); Ekert entanglement-based QKD; Bell preparation and CHSH inequality tests; teleportation; superdense coding; entanglement swapping; BBPSSW, Deutsch and DEJMPS distillation; T1/T2 memory dynamics; the Shor 9-qubit and Steane 7-qubit CSS error-correcting codes |
| **Topology** | `graph`, `routing`, `dijkstra`, `strategies`, `shapes`, `schedule`, `events`, `resources`, `visualize`, `importers` | Quantum network graphs with physical fidelity models; exact Werner-algebra swapping; **pluggable routing strategies**; ring/grid/FatTree/BCube topology builders; a time-aware and an event-driven distribution schedule; memory resource management with contention; dependency-free ASCII visualisation; and a pluggable import surface |
| **Importers** | `topology/importers` | QEL's versioned native schema (`qel-json`), the legacy Ghost-Net bridge (`ghostnet`), a strict Graphviz subset (`dot`), and SeQUeNCe `RouterNetTopo` interop. All produce the same canonical shape; nothing in routing, scheduling or visualisation knows where a topology came from |

## Routing strategies

Routing is a pluggable policy, not a function. Four ship, and a third party can
register another without editing QEL:

```python
from quantumnet.topology import make_strategy, compare_strategies, fat_tree

topo = fat_tree(4)
comparison = compare_strategies(topo, "host0_0_0", "host3_1_1")
print(comparison.describe())          # every strategy, side by side
make_strategy("fidelity-optimal").forwarding_table(topo)
```

| Strategy | Weight | Notes |
|---|---|---|
| `fidelity-optimal` | `-log W`, `W = (4F-1)/3` | The default. **Provably** the highest-fidelity route |
| `shortest-distance` | link km | The incumbent simulator's stock policy, kept as the control |
| `fewest-hops` | 1 per link | The obvious naive choice |
| `static` | a supplied table | Reproduces a fixed deployment |

**Why `-log W` and not `-log F`.** Entanglement swapping multiplies the Werner
parameter, so `W_path = Π W_i` and `-log W` is *exactly* additive — which is what
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

`tests/test_topology/test_strategies.py` also confirms `fidelity-optimal` matches
exhaustive brute force on random graphs, so "provably" is checked rather than
claimed.

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
`numpy` only — a second dependency is not worth saving a hundred lines.


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

py -m pytest -q                     # 1036 tests, ~3m
py -m quantumnet all                # every protocol demo
py -m quantumnet topology --help    # build / route / visualise a topology
py -m quantumnet import --help      # route over a parsed topology export
py -m quantumnet qkd-derive --help  # key material at an explicit fidelity
py -m quantumnet qkd --help         # decoy-state key rate over a fibre link
py -m quantumnet bench --help       # key rate vs distance sweep
py -m quantumnet contend --help     # competing demands for finite memory
py -m quantumnet link --help        # physical-layer budget for one span
py -m quantumnet validate            # recompute published key-rate figures

py scripts/audit_imports.py         # every module must import cleanly
py scripts/verify_surface_code.py   # surface-code invariants vs stim (dev-only)
```

The 20 commands: `bb84`, `e91`, `teleport`, `superdense`, `swap`, `shor`,
`steane`, `distill`, `memory`, `all`, `stabilizer`, `physical`, `topology`,
`import`, `qkd-derive`, `qkd`, `bench`, `contend`, `link`, `validate`.

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
  protocol's theoretical upper limit — the model returns it exactly at zero loss;
- **it is quadratic in detector efficiency** (`p ∝ η²`), because both photons must
  survive and both must be detected.

The consequence worth knowing when reading any number it prints: **loss costs
rate, not fidelity.** A photon that fails to arrive is a failed attempt, not a
corrupted pair. What *does* degrade fidelity is a **dark-count coincidence** —
indistinguishable from a real herald, and it contributes a maximally mixed pair
(fidelity 1/4) — along with mode mismatch and memory decoherence.

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
  released).
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
rate on a lossy fibre link — no qubits are simulated for this number, because
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
detector model — not a reproduction of a decoy-state experiment.

## What is real and what is simulated

- **Real:** the quantum mechanics. States, gates, measurement collapse, noise
  channels, the stabilizer formalism, the error-correcting codes, the
  distillation algorithms, and the fidelity arithmetic all behave as written.
- **Real:** the decoy-state key-rate arithmetic. The estimators and the GLLP
  rate formula are the published ones, and the implementation is checked
  against them in the test suite rather than asserted.
- **Real, and self-contained:** the surface-code decoder. `tjoin_decoder`
  computes an exact minimum-weight T-join on the graph Stim's detector error
  model defines. **No third-party matcher is needed to get a threshold**:
  measured at p ≈ 0.007 with `stim` and `numpy` alone, and verified to produce
  *identical* corrections to PyMatching (same edge set, same total weight) on
  4,359 of 4,359 shots at d=3 and d=5. PyMatching remains an optional
  **comparison** oracle, not a dependency — `matcher="pymatching"` selects it
  to check the in-package result, and nothing on the default path imports it.
  The identity is established for rotated surface-code memory-Z with uniform
  depolarizing noise at d=3, 5, 7; it is not claimed for other error models.
- **Simulated:** the hardware and the network. There are no photons, no
  fibre and no sockets; `ipc_node` uses real processes, but the links between
  them are modelled.
- **Scope:** these are simulator results. They do not predict what physical
  hardware would achieve. A modelled 123 km reach for a preset calibrated to a
  122 km experiment is a consistency check on the model, **not** a measurement.

## Layout

```text
src/quantumnet/core/        states, gates, measurement, noise, channels, stabiliser, scheduler
src/quantumnet/protocols/   QKD (incl. decoy state), teleportation, superdense, swapping, distillation, memory, QEC
src/quantumnet/topology/    graphs, fidelity routing, schedules, visualisation, import surface
src/quantumnet/cli.py       the 20-command interface, JSON on stdout, everything else on stderr
src/quantumnet/topology/importers/   QEL native JSON, legacy Ghost-Net bridge, Graphviz, SeQUeNCe
tests/                      1036 tests across core, protocols, topology and the CLI
scripts/                    audit_imports.py, verify_surface_code.py (dev-only tools)
notebooks/demo.ipynb        worked demonstration
QEL-MASTER-PLAN.md          the consolidated build plan
research/                   the evidence behind the plan's measured claims
Quantum Entanglement Link.canvas   the concept map the project was built from
```

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
same `q = 1/2` asymptotic rate — a like-for-like reproduction. QEL returns
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

The Boaron loss budget *is* comparable — fibre loss is a property of the fibre —
and it checks out: all five rows of their Table I agree within 0.5 dB, and the
implied coefficient is 0.1696–0.1712 dB/km, consistent with the single
ultra-low-loss fibre they describe.

**The scope limit, stated plainly:** this validates the implementation against
the *model those authors used*. It is not a claim about hardware.

## Where the numbers come from

`QEL-MASTER-PLAN.md` states a rule and follows it: every claim about QEL's own
state is either labelled **[measured]** with the command that produced it, or it
is not stated. No feature is called done because a file exists or a symbol has
the right name.

`research/` holds the evidence — independent reimplementations, extracted paper
sources, and a note on what those passes verified and what they got wrong. Read
[research/README.md](research/README.md) before trusting any single number in
the plan.

## Is 1036 tests a lot?

Measured against comparable libraries rather than against intuition. The QEL row is
re-measured; the three comparator rows are from the original survey and were not
re-measured here:

| Project | Source lines | Test lines | Test:source |
|---|---|---|---|
| numpy | 117,552 | 121,462 | 1.03 |
| scipy | 340,112 | 234,272 | 0.69 |
| networkx | 116,857 | 74,878 | 0.64 |
| sympy | 492,618 | 260,744 | 0.53 |
| **QEL** | **15,351** | **11,529** | **0.75** |

QEL sits inside that range. The *absolute* count is large relative to the line count
because those 1036 tests come from **823 test functions**, 55 of them parametrised and
expanding into many cases — one geometric invariant checked at five distances is five
tests from one function. The ratio, not the count, is the meaningful figure.

> Both the count and the line figures here were stale at 555 and 7,588 / 4,853. The
> source line count in particular had grown by more than a factor of two while the
> README still described the earlier tree — which is the same failure the headline count
> block warns about, in a second place.

The shape differs from those libraries in one deliberate way: a large share of
QEL's tests check *physical identities and published values* rather than API
behaviour — `p = 1/2` exactly at zero loss, `p ∝ η²`, gain matching the
Poissonian identity, `-log W` being exactly additive, brute-force agreement for
the router and the placement optimiser. Those are the tests that catch a model
that has quietly become a *different* model, which is a failure mode a coverage
percentage cannot see.


## Provenance

QEL began inside [Vantablack](https://github.com/KELLERBABG/Vantablack) as
the quantum layer for the same mesh, and now lives here as its own system.
The legacy topology export format mentioned above is the only artefact of
that origin that survived: it is a single adapter in
`topology/importers/ghostnet.py` that produces the same canonical shape as
the new native format. Part of [Keller Systems](https://kellersystems.dev).
