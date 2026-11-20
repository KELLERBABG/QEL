"""Adversarial physics engine: the five ontology gaps, plus ceiling assertions.

Runs five deterministic checks that probe where a simplified model and the deeper
physical model disagree, and fails (exit 1) if any model violates the physical bound
the check is built on. Companion to ``scripts/claim_audit.py``: that one measures the
documentation, this one measures the physics.

Every expected value below is the one the plan states for that gap, and the
``own-research/topics`` table it came from.

Exit code 0 iff all five checks hold.
"""

from __future__ import annotations

import sys

from quantumnet.core.physical import bell_pair_fidelity_non_markovian
from quantumnet.core.photonics import BarrettKok, Detector, PhotonicLink
from quantumnet.core.xstate import XState
from quantumnet.protocols.bb84 import mode_pairing_qkd_rate
from quantumnet.topology.graph import QuantumLink, QuantumNode, QuantumTopology
from quantumnet.topology.strategies import make_strategy, path_secret_key_rate

TOL = 1e-4


def gap_1_werner_vs_xstate() -> tuple[bool, list[str]]:
    gamma, eta_phi = 0.15, 0.95

    def link() -> XState:
        return XState.bell_phi_plus().apply_gad(
            gamma, gamma, eta_phi_a=eta_phi, eta_phi_b=eta_phi)

    # Werner model: fidelity alone, multiplied through four ideal swaps.
    w_link = (4.0 * link().fidelity_phi_plus - 1.0) / 3.0
    f_werner_4 = (1.0 + 3.0 * w_link ** 4) / 4.0
    c_werner_4 = max(0.0, 2.0 * f_werner_4 - 1.0)

    # XState, feed-forward averaged over the BSM outcomes.
    averaged = link()
    for _ in range(3):
        averaged = averaged.swap_with(link())["averaged"]

    # XState on the Psi branch: Psi at the first two swaps and Phi at the third, which
    # is what the accumulated Pauli relabelling makes the Psi-conditioned chain.
    psi = link().swap_with(link())["psi_branch"]
    psi = psi.swap_with(link())["psi_branch"]
    psi = psi.swap_with(link())["phi_branch"]

    # One-sided AD: "Cathedral and Tent".
    asym = XState.bell_phi_plus().apply_gad(0.80, 0.0)

    checks = {
        "F_Werner,4 = 0.4999": abs(f_werner_4 - 0.4999) < TOL,
        "C_Werner,4 = 0": c_werner_4 == 0.0,
        "F_avg,4 = 0.5002": abs(averaged.fidelity_phi_plus - 0.5002) < TOL,
        "C_avg,4 = 0.0031": abs(averaged.concurrence() - 0.0031) < TOL,
        "F_Psi,4 = 0.5054": abs(psi.fidelity_phi_plus - 0.5054) < TOL,
        "C_Psi,4 = 0.0108": abs(psi.concurrence() - 0.0108) < TOL,
        "C_1-sided = 0.4472": abs(asym.concurrence() - 0.4472) < TOL,
        "C_1-sided Werner = 0.0472": abs(asym.werner_concurrence_estimate() - 0.0472) < TOL,
    }
    lines = [
        f"4-hop chain (gamma={gamma}, eta_phi={eta_phi}):",
        f"  Werner : F_4 = {f_werner_4:.4f}  C = {c_werner_4:.4f}   (dead)",
        f"  XState : F_avg,4 = {averaged.fidelity_phi_plus:.4f}  "
        f"C_avg,4 = {averaged.concurrence():.4f}",
        f"           F_Psi,4 = {psi.fidelity_phi_plus:.4f}  C_Psi,4 = {psi.concurrence():.4f}",
        "one-sided AD (gamma_A=0.80, gamma_B=0):",
        f"  Werner estimate C = {asym.werner_concurrence_estimate():.4f}",
        f"  XState  C         = {asym.concurrence():.4f}   "
        f"({asym.concurrence() / asym.werner_concurrence_estimate():.1f}x)",
    ]
    return all(checks.values()), lines


# ---------------------------------------------------------------------------
# Gap 2: -log W fidelity routing vs skr-optimal routing
# ---------------------------------------------------------------------------

def _link_at_fidelity(a: str, b: str, target_fidelity: float, rate_hz: float,
                      dark_hz: float) -> QuantumLink:
    """A span whose ``QuantumLink.fidelity()`` equals ``target_fidelity``.

    Deterministic bisection; the pulse rate feeds back into the dark-count probability
    and therefore into fidelity, so length has no closed form.  Detector efficiency is
    at its ceiling, since loss in the depolarising channel caps link fidelity at
    ``1 - 0.75 (1 - eta_det)`` and would otherwise make F = 0.92 / 0.985 unreachable.
    """

    def build(length: float) -> QuantumLink:
        eta = 10.0 ** (-0.2 * length / 10.0)
        return QuantumLink(a, b, length_km=length, dark_count_hz=dark_hz,
                           detector_eff=1.0, pulse_rate_hz=rate_hz / (eta ** 2))

    lo, hi = 1e-7, 100.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if build(mid).fidelity() > target_fidelity:
            lo = mid
        else:
            hi = mid
    return build(0.5 * (lo + hi))


def _routing_topology() -> QuantumTopology:
    topo = QuantumTopology()
    for nid in ("S", "R1", "R2", "T"):
        topo.add_node(QuantumNode(nid))
    topo.add_link(_link_at_fidelity("S", "T", 0.9200, 5.0e4, 50.0))
    for a, b in (("S", "R1"), ("R1", "R2"), ("R2", "T")):
        topo.add_link(_link_at_fidelity(a, b, 0.9850, 4.0e5, 10.0))
    return topo


def gap_2_fidelity_vs_skr_routing() -> tuple[bool, list[str]]:
    topo = _routing_topology()
    r_fid = make_strategy("fidelity-optimal").select(topo, "S", "T")
    r_skr = make_strategy("skr-optimal", p_bsm=0.5, swap_fidelity=0.99).select(topo, "S", "T")

    skr_fid = path_secret_key_rate(topo, r_fid.path, p_bsm=0.5, swap_fidelity=0.99)
    skr_skr = path_secret_key_rate(topo, r_skr.path, p_bsm=0.5, swap_fidelity=0.99)
    gain = skr_skr["skr_hz"] / max(skr_fid["skr_hz"], 1e-300)

    checks = {
        "-log W picks the 3-hop path": r_fid.path == ["S", "R1", "R2", "T"],
        "skr-optimal picks the 1-hop path": r_skr.path == ["S", "T"],
        "F_B = 0.9372": abs(skr_fid["e2e_fidelity"] - 0.9372) < 1e-3,
        "+20% higher secret bits/s": abs(gain - 1.20) < 0.02,
    }
    lines = [
        f"-log W picks {' -> '.join(r_fid.path)} (F_B = {skr_fid['e2e_fidelity']:.4f}, "
        f"{skr_fid['skr_hz']:.0f} bits/s)",
        f"skr-optimal picks {' -> '.join(r_skr.path)} "
        f"(F_A = {skr_skr['e2e_fidelity']:.4f}, {skr_skr['skr_hz']:.0f} bits/s)",
        f"Path A secret-bit gain: {(gain - 1.0) * 100:+.1f}% over the -log W route",
    ]
    return all(checks.values()), lines


# ---------------------------------------------------------------------------
# Gap 3: O(p_d^2) vs O(eta p_d) Barrett-Kok -- the smiling DoS
# ---------------------------------------------------------------------------

def gap_3_barrett_kok_smiling_dos() -> tuple[bool, list[str]]:
    def link(dark_hz: float) -> BarrettKok:
        def arm() -> PhotonicLink:
            return PhotonicLink(
                length_km=150.0,
                detector=Detector(efficiency=0.8, dark_count_rate_hz=dark_hz))
        return BarrettKok(arm_a=arm(), arm_b=arm(), coincidence_window_s=1e-9)

    quiet = link(1e4)    # p_d = 1e-5, the honest reading
    honest = link(1e5)   # p_d = 1e-4, the attacked reading
    flooded = honest.smiling_dos_report(1e7)

    raw = honest.raw_fidelity()
    exact = honest.exact_fidelity()

    checks = {
        "raw_fidelity 0.9773": abs(raw - 0.9773) < 1e-3,
        "exact_fidelity 0.6031": abs(exact - 0.6031) < 1e-3,
        "exact_fidelity 0.9311 at p_d = 1e-5": abs(quiet.exact_fidelity() - 0.9311) < 1e-3,
        "herald rises as p_d rises": honest.success_probability() > quiet.success_probability(),
        "fidelity falls as p_d rises": exact < quiet.exact_fidelity(),
        "flood raises herald": flooded["success_probability"] > honest.success_probability(),
        "flood lowers fidelity": flooded["exact_fidelity"] < flooded["honest_fidelity"],
    }
    lines = [
        f"150 km, p_d = 1e-4: legacy raw_fidelity = {raw:.4f} (above BBM92 0.835)",
        f"                    exact_fidelity    = {exact:.4f} (zero key)",
        f"p_d 1e-5 -> 1e-4   exact_fidelity    {quiet.exact_fidelity():.4f} -> {exact:.4f}",
        f"                   herald probability {quiet.success_probability():.3e} -> "
        f"{honest.success_probability():.3e}",
        f"dark flood (1e7/s) herald {flooded['success_probability']:.3e} with "
        f"F = {flooded['exact_fidelity']:.4f} (honest F = {flooded['honest_fidelity']:.4f})",
    ]
    return all(checks.values()), lines


# ---------------------------------------------------------------------------
# Gap 4: Markov beta=1 vs spin-bath beta=3 memory
# ---------------------------------------------------------------------------

def gap_4_markov_vs_spin_bath() -> tuple[bool, list[str]]:
    f_b1 = bell_pair_fidelity_non_markovian(1.0, 0.1, t1=0.0, t2_hahn=1.0, beta=1.0)
    f_b3 = bell_pair_fidelity_non_markovian(1.0, 0.1, t1=0.0, t2_hahn=1.0, beta=3.0)
    ratio = (1.0 - f_b1) / (1.0 - f_b3)

    fresh = bell_pair_fidelity_non_markovian(1.0, 0.5, t1=0.0, t2_hahn=1.0, beta=3.0,
                                             previous_age_s=0.0)
    aged = bell_pair_fidelity_non_markovian(1.0, 0.5, t1=0.0, t2_hahn=1.0, beta=3.0,
                                            previous_age_s=0.5)

    checks = {
        "95.2x short-hold advantage": abs(ratio - 95.2) / 95.2 < 0.02,
        "cumulative-age penalty": aged < fresh,
    }
    lines = [
        f"t/T2 = 0.1: coherence lost {1 - f_b1:.3e} (beta=1) vs {1 - f_b3:.3e} (beta=3)"
        f"  -> {ratio:.1f}x short-hold advantage",
        f"cumulative age penalty: F(dt=0.5 | age 0.5) = {aged:.6f} < F(fresh) = {fresh:.6f}",
    ]
    return all(checks.values()), lines


# ---------------------------------------------------------------------------
# Gap 5: the Valley of Repeater Shame -- post-PLOB mode pairing vs ceilings
# ---------------------------------------------------------------------------

def gap_5_valley_of_repeater_shame() -> tuple[bool, list[str]]:
    res = mode_pairing_qkd_rate(380.0, dark_count_hz=0.5, detector_efficiency=0.85,
                                l_max=40_000, laser_linewidth_hz=500.0)
    k_plob = res["plob_bound_per_use"]
    k2 = res["k2_repeater_bound_per_use"]
    rate = res["key_rate_per_pulse"]

    checks = {
        "beats K_PLOB": res["beats_plob"] is True and rate > k_plob > 0.0,
        "below K_2": rate < k2,
    }
    lines = [
        f"380 km mode-pairing: R = {rate:.4e} bits/pulse",
        f"  K_PLOB(eta) = {k_plob:.4e}  -> beaten by {rate / max(k_plob, 1e-300):.0f}x",
        f"  K_2(eta)    = {k2:.4e}  -> ceiling respected ({rate / k2:.3f} of K_2)",
    ]
    return all(checks.values()), lines


CHECKS = [
    ("Gap 1  Werner vs XState (non-Pauli noise & swapping)", gap_1_werner_vs_xstate),
    ("Gap 2  -log W fidelity routing vs skr-optimal routing", gap_2_fidelity_vs_skr_routing),
    ("Gap 3  O(p_d^2) vs O(eta p_d) Barrett-Kok smiling DoS", gap_3_barrett_kok_smiling_dos),
    ("Gap 4  Markov beta=1 vs spin-bath beta=3 memory", gap_4_markov_vs_spin_bath),
    ("Gap 5  Valley of Repeater Shame / ceiling assertions", gap_5_valley_of_repeater_shame),
]


def main() -> int:
    failures = 0
    for title, check in CHECKS:
        try:
            ok, lines = check()
        except Exception as exc:  # a check that raises is a failed check
            ok, lines = False, [f"raised {type(exc).__name__}: {exc}"]
        print(f"[{'OK  ' if ok else 'FAIL'}] {title}")
        for line in lines:
            print(f"       {line}")
        if not ok:
            failures += 1
    print()
    print(f"{len(CHECKS) - failures}/{len(CHECKS)} ontology gaps reproduce; "
          f"{failures} failed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
