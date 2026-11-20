"""The 4-parameter X-state algebra, against topic 07 §1.4 row by row.

Three of the plan's expected values in this gate cannot be produced by the plan's own
algebra.  Each is retained as the plan's code path plus an exact derivation, and the
row of the cited table it actually belongs to is asserted beside it:

* ``psi_b.concurrence()``: the plan writes 0.059344; topic 07 §1.4 row 1 prints 0.0593
  for this row, and the exact closed form is 0.05930298.  The gate below uses the
  table's 0.0593 at the plan's 1e-5 (it passes by 3.0e-6).
* ``unprotected.concurrence() == 0.0``: 0.0 is row 3's *Werner* column.  The plan's own
  ``unprotected`` is |Phi+> under symmetric AD, whose exact concurrence is
  ``(1 - gamma)^2 = 0.09`` (topic 07 §1.4 states that identity explicitly), confirmed
  here by the density-matrix Wootters concurrence.
* the procrustean gate: the specified ``K0`` maps ``p_succ = 3/5``, ``F = 3/5`` and
  ``C = 1/3``, so it raises fidelity and *lowers* concurrence; the plan's "C increases"
  and "F > 0.65" do not follow from its own filter.
"""

from __future__ import annotations

import pytest

from quantumnet.core.xstate import XState


def test_xstate_closed_form_matches_density_matrix_concurrence_and_table_07():
    # Row 1: Post-swap symmetric AD (gamma = 0.40, 1 swap, Psi+/- branch)
    s_ad = XState.bell_phi_plus().apply_gad(0.40, 0.40)
    swap = s_ad.swap_with(s_ad)
    psi_b = swap["psi_branch"]
    assert psi_b.fidelity_phi_plus == pytest.approx(0.497143, abs=1e-5)
    assert psi_b.werner_concurrence_estimate() == 0.0  # F < 0.5 -> Werner thinks it's dead!
    # Table 07 row 1 value (0.0593); the exact closed form is 0.05930298.
    assert psi_b.concurrence() == pytest.approx(0.0593, abs=1e-5)
    assert psi_b.to_density_matrix().concurrence() == pytest.approx(psi_b.concurrence(), abs=1e-9)
    # Table 07 row 1 also reports C_avg = 0.0081 and p_Psi = 0.420 = 2 * p_Psi^each.
    assert swap["averaged"].concurrence() == pytest.approx(0.0081, abs=1e-4)
    assert 2.0 * swap["p_psi_each"] == pytest.approx(0.420, abs=1e-12)

    # Causal scar / no-signaling invariant (denker-1 Gedankenexperiment 1):
    # Even for symmetric links (beta=0), post-swap averaged state MUST have beta' != 0
    avg = swap["averaged"]
    assert avg.beta != 0.0
    assert avg.alpha + avg.beta == pytest.approx(s_ad.alpha + s_ad.beta, abs=1e-12)

    # Row 2: One-sided AD ("Cathedral and Tent", gamma_A = 0.80, gamma_B = 0.0)
    s_asym = XState.bell_phi_plus().apply_gad(0.80, 0.0)
    assert s_asym.fidelity_phi_plus == pytest.approx(0.523607, abs=1e-5)
    assert s_asym.werner_concurrence_estimate() == pytest.approx(0.047214, abs=1e-5)
    assert s_asym.concurrence() == pytest.approx(0.447214, abs=1e-5)  # 9.5x Werner!

    # Procrustean filter before BSM.  Exact arithmetic for the specified K0: the
    # one-sided state has (a, b, c, d, w) = (1/2, 2/5, 0, 1/10, sqrt(5)/10); K0 with
    # g = 4/5 scales b, d by 1/5 and w by 1/sqrt(5), so p_succ = 3/5 and the
    # post-selected state is (5/6, 2/15, 0, 1/30, 1/6), giving F = 3/5 and C = 1/3.
    filtered, p_succ = s_asym.procrustean_filter_one_sided(0.80)
    assert p_succ > 0.15
    assert p_succ == pytest.approx(0.6, abs=1e-12)
    assert filtered.fidelity_phi_plus == pytest.approx(0.6, abs=1e-12)
    assert filtered.concurrence() == pytest.approx(1.0 / 3.0, abs=1e-12)
    assert filtered.fidelity_phi_plus > s_asym.fidelity_phi_plus

    # The plan's two filter claims ("F > 0.65" and "C increases") do not both hold
    # under its own construction.  Three readings, computed here:
    #   (a) plan's input state, one application  -> F = 0.6000, C = 0.3333 (above)
    #   (b) iterated to convergence              -> F -> 0.5000, C -> 0
    #   (c) ideal |Phi+> input instead           -> F = 0.8727, C = 0.7454
    # Only (c) satisfies both claims, and (c) contradicts the plan's own test line,
    # which filters the damped state s_asym.  (a) is what the plan's Kraus operator
    # applied to the plan's input actually produces, so the gate above pins (a).
    converged = s_asym
    for _ in range(40):
        converged, _p = converged.procrustean_filter_one_sided(0.80)
    assert converged.fidelity_phi_plus == pytest.approx(0.5, abs=1e-2)
    assert converged.concurrence() < 0.01

    ideal_filtered, p_ideal = XState.bell_phi_plus().procrustean_filter_one_sided(0.80)
    assert p_ideal == pytest.approx(0.6, abs=1e-12)
    assert ideal_filtered.fidelity_phi_plus == pytest.approx(0.872678, abs=1e-6)
    assert ideal_filtered.concurrence() == pytest.approx(0.745356, abs=1e-6)
    assert ideal_filtered.fidelity_phi_plus > 0.65
    assert ideal_filtered.concurrence() > s_asym.concurrence()

    # Row 3: Pauli-X Sleep-Suit (|Phi+> -> |Psi+> -> AD gamma=0.70 -> |Phi+>)
    unprotected = XState.bell_phi_plus().apply_gad(0.70, 0.70)
    protected = (
        XState.bell_phi_plus()
        .apply_pauli_x_sleep_suit()
        .apply_gad(0.70, 0.70)
        .apply_pauli_x_sleep_suit()
    )
    # |Phi+> under symmetric AD, two-sided, symbolically at gamma = 7/10:
    #   a = (1+g^2)/2 = 149/200, d = (1-g)^2/2 = 9/200, b = c = g(1-g)/2 = 21/200,
    #   w = (1-g)/2 = 3/20, z = 0   ->  F = 109/200 = 0.545,
    #   C = 2(|w| - sqrt(bc)) = 2(3/20 - 21/200) = 9/100 = (1-g)^2 = 0.09.
    # The Werner estimate 2F - 1 is also 0.09.  C = 0 requires gamma = 1, so no reading of
    # this construction gives 0.0 at gamma = 0.70; the full Wootters concurrence of the
    # density matrix agrees to 1e-9.
    assert unprotected.concurrence() == pytest.approx(0.09, abs=1e-12)
    assert unprotected.to_density_matrix().concurrence() == pytest.approx(0.09, abs=1e-9)
    assert XState.bell_phi_plus().apply_gad(1.0, 1.0).concurrence() == pytest.approx(0.0, abs=1e-12)
    # Topic 07 §1.4 row 3 is |Psi+> under symmetric AD; its columns are exactly the
    # plan's three numbers: F = 0.3000, Werner C = 0.0000, exact C = 0.3000.
    psi_row3 = XState.bell_psi_plus().apply_gad(0.70, 0.70)
    assert psi_row3.fidelity_psi_plus == pytest.approx(0.3000, abs=1e-4)
    assert psi_row3.werner_concurrence_estimate() == 0.0
    assert psi_row3.concurrence() == pytest.approx(0.3000, abs=1e-6)

    assert protected.fidelity_phi_plus == pytest.approx(0.300000, abs=1e-6)
    assert protected.concurrence() == pytest.approx(0.300000, abs=1e-6)  # survives!
    assert protected.concurrence() > unprotected.concurrence()


def test_four_hop_psi_branch_matches_table_07_multihop_paragraph():
    """4-hop chain (3 swaps), gamma = 0.15, eta_phi = 0.95: table 07's three states.

    Werner product: F_Werner,4 = 0.4999 (dead, C = 0).  Averaged feed-forward:
    F_avg,4 = 0.5002, C_avg,4 = 0.0031.  On the all-Psi branch -- the Psi branch at the
    first two swaps and the Phi branch at the third, which is what the accumulated
    Pauli relabelling makes the Psi-conditioned chain -- F_Psi,4 = 0.5054 and
    C_Psi,4 = 0.0108, all as printed in topic 07 §1.4.
    """

    def link() -> XState:
        return XState.bell_phi_plus().apply_gad(
            0.15, 0.15, eta_phi_a=0.95, eta_phi_b=0.95)

    base = link()
    assert base.fidelity_phi_plus == pytest.approx(0.8198, abs=1e-4)
    assert base.concurrence() == pytest.approx(0.6396, abs=1e-4)

    w_link = (4.0 * base.fidelity_phi_plus - 1.0) / 3.0
    f_werner = (1.0 + 3.0 * w_link ** 4) / 4.0
    assert f_werner == pytest.approx(0.4999, abs=1e-4)
    assert max(0.0, 2.0 * f_werner - 1.0) == 0.0

    averaged = base
    for _ in range(3):
        averaged = averaged.swap_with(link())["averaged"]
    assert averaged.fidelity_phi_plus == pytest.approx(0.5002, abs=1e-4)
    assert averaged.concurrence() == pytest.approx(0.0031, abs=1e-4)

    psi_chain = base.swap_with(link())["psi_branch"]
    psi_chain = psi_chain.swap_with(link())["psi_branch"]
    psi_chain = psi_chain.swap_with(link())["phi_branch"]
    assert psi_chain.fidelity_phi_plus == pytest.approx(0.5054, abs=1e-4)
    assert psi_chain.concurrence() == pytest.approx(0.0108, abs=1e-4)
    # Entangled where the Werner approximation says dead.
    assert psi_chain.concurrence() > 0.0
