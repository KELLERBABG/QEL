# Quantum Entanglement Link (QEL)

A quantum communication network simulation stack: qubits, gates, noise and
error correction at the bottom; the standard protocols in the middle; repeater
placement and fidelity-constrained entanglement routing at the top. Everything
runs in Python on a laptop — no hardware, no optics, no network sockets.

```
122 tests passing · 15 CLI commands · 13 protocols and codes · 9 core primitives
```

## What it is

QEL is the quantum layer underneath a mesh network. Where Vantablack routes
packets, QEL asks the harder question: *if the links were quantum, where do you
put the repeaters, and what fidelity survives the trip?*

It models the whole path honestly. Quantum states are density matrices, so
decoherence is real rather than decorative: depolarising, dephasing and
amplitude-damping channels act on them, links attenuate with distance, memories
relax on T1 and lose phase on T2, and entanglement must be distilled back to
something usable before a key can be extracted. Nothing is hand-waved into
working.

## The stack

| Layer | Modules | What it does |
|---|---|---|
| **Core** | `qubit`, `gate`, `measurement`, `noise`, `channel`, `physical`, `stabilizer`, `scheduler`, `ipc_node` | Density-matrix states and quantum information metrics; unitary gates and Pauli algebra; projective and POVM measurement with collapse; depolarising/dephasing/amplitude-damping noise; distance-dependent channel attenuation; hardware-level impairment models; Clifford tableau simulation; an asynchronous discrete-event scheduler; and a multi-process node architecture |
| **Protocols** | `bb84`, `e91`, `bell`, `teleportation`, `superdense`, `swapping`, `distillation`, `memory`, `shor`, `steane` | QKD with an intercept-resend eavesdropper; Ekert entanglement-based QKD; Bell preparation and CHSH inequality tests; teleportation; superdense coding; entanglement swapping; BBPSSW and Deutsch distillation; T1/T2 memory dynamics; the Shor 9-qubit and Steane 7-qubit CSS error-correcting codes |
| **Topology** | `graph`, `routing`, `schedule`, `visualize`, `ghostnet` | Quantum network graphs with physical fidelity models; fidelity-constrained entanglement routing over Bell-state swaps; a time-aware distribution schedule; dependency-free ASCII visualisation; and the bridge that imports a live Ghost Net topology export and routes entanglement over it |

## Bridging to the classical mesh

`topology/ghostnet.py` takes a **live Global Ghost Net topology export** and
routes quantum entanglement across the nodes it describes. A route's end-to-end
fidelity is the scheduled value after every swap and memory decay on the path;
if that fidelity is too low for QKD to extract a key, the route is distilled
(BBPSSW rounds over 256 pairs) until it is, and then a real BB84 exchange runs
at the route's noise level to produce key material.

That closes the loop: classical mesh discovery in, quantum key material out,
with the same topology underneath both.

## Run it

```bash
py -m pip install -e ".[dev]"

py -m pytest -q                     # 122 tests, ~80 s
py -m quantumnet all                # every protocol demo
py -m quantumnet topology --help    # build / route / visualise a topology
py -m quantumnet ghost-net --help   # route entanglement over a Ghost Net export
py -m quantumnet qkd-derive --help  # key material at an explicit fidelity
```

The 15 commands: `bb84`, `e91`, `teleport`, `superdense`, `swap`, `shor`,
`steane`, `distill`, `memory`, `all`, `stabilizer`, `physical`, `topology`,
`ghost-net`, `qkd-derive`.

## What is real and what is simulated

- **Real:** the quantum mechanics. States, gates, measurement collapse, noise
  channels, the stabilizer formalism, the error-correcting codes, the
  distillation algorithms, and the fidelity arithmetic all behave as written.
- **Simulated:** the hardware and the network. There are no photons, no fibre
  and no sockets; `ipc_node` uses real processes, but the links between them are
  modelled rather than physical.
- **Not a claim:** nothing here asserts that a physical implementation would
  hit these numbers. It is a simulator for reasoning about placement and
  fidelity, not a hardware specification.

## Layout

```
src/quantumnet/core/        states, gates, measurement, noise, channels, stabiliser, scheduler
src/quantumnet/protocols/   QKD, teleportation, superdense, swapping, distillation, memory, QEC
src/quantumnet/topology/    graphs, fidelity routing, schedules, visualisation, Ghost-Net bridge
src/quantumnet/cli.py       the 15-command interface, JSON on stdout, everything else on stderr
tests/                      122 tests across core, protocols and topology
notebooks/demo.ipynb        worked demonstration
Quantum Entanglement Link.canvas   the concept map the project was built from
```

## Provenance

QEL began inside [Vantablack](https://github.com/KELLERBABG/Vantablack) as the
quantum layer for the same mesh, and now lives here as its own system. Part of
[Keller Systems](https://kellersystems.dev).
