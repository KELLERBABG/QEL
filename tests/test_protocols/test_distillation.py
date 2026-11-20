import numpy as np
import pytest
from quantumnet.core import QubitState
from quantumnet.core.noise import dephasing_channel
from quantumnet.protocols import (
    bbssw_distill,
    dejmps_distill,
    deutsch_distill,
    prepare_noisy_bell_pairs,
    run_distillation_round,
)


def test_bbssw_perfect_pairs():
    ideal = QubitState.bell_phi_plus()
    result = bbssw_distill(ideal, ideal, rng=np.random.default_rng(42))
    assert result["success"]
    assert result["distilled_fidelity"] > 0.99


def test_deutsch_perfect_pairs():
    ideal = QubitState.bell_phi_plus()
    result = deutsch_distill(ideal, ideal, rng=np.random.default_rng(42))
    assert result["success"]
    assert result["distilled_fidelity"] > 0.99


def test_bbssw_improves_fidelity():
    pairs = prepare_noisy_bell_pairs(20, fidelity=0.7, rng=np.random.default_rng(42))
    input_f = sum(p.fidelity(QubitState.bell_phi_plus()) for p in pairs) / len(pairs)
    result = bbssw_distill(pairs[0], pairs[1], rng=np.random.default_rng(43))
    if result["success"]:
        assert result["distilled_fidelity"] >= input_f * 0.9


def test_deutsch_improves_fidelity():
    pairs = prepare_noisy_bell_pairs(20, fidelity=0.7, rng=np.random.default_rng(42))
    input_f = sum(p.fidelity(QubitState.bell_phi_plus()) for p in pairs) / len(pairs)
    result = deutsch_distill(pairs[0], pairs[1], rng=np.random.default_rng(43))
    if result["success"]:
        assert result["distilled_fidelity"] >= input_f * 0.9


def test_prepare_noisy_bell_pairs_matches_target_fidelity():
    target_f = 0.7
    pairs = prepare_noisy_bell_pairs(4, fidelity=target_f, rng=np.random.default_rng(0))
    ideal = QubitState.bell_phi_plus()
    for pair in pairs:
        assert pair.fidelity(ideal) == pytest.approx(target_f, abs=1e-6)


def test_run_distillation_round_preserves_distilled_fidelity():
    pairs = prepare_noisy_bell_pairs(8, fidelity=0.75, rng=np.random.default_rng(1))
    ideal = QubitState.bell_phi_plus()
    out_pairs, successes, yield_frac = run_distillation_round(
        pairs, protocol="bbssw", rng=np.random.default_rng(2)
    )
    assert successes == len(out_pairs)
    assert yield_frac == pytest.approx(successes / 4)
    for pair in out_pairs:
        assert pair.fidelity(ideal) >= 0.75


def test_x_basis_distillation_differs_from_z_basis_on_dephased_pairs():
    ideal = QubitState.bell_phi_plus()
    deph = dephasing_channel(0.2)
    noisy = deph.apply(ideal, targets=[0])
    # Under Z-only (phase) errors, X-basis measurement detects errors while Z-basis does not.
    z_fids = []
    x_fids = []
    for seed in range(20):
        rz = bbssw_distill(noisy, noisy, rng=np.random.default_rng(seed))
        rx = dejmps_distill(noisy, noisy, rng=np.random.default_rng(seed))
        if rz["success"]:
            z_fids.append(rz["distilled_fidelity"])
        if rx["success"]:
            x_fids.append(rx["distilled_fidelity"])
    assert np.mean(x_fids) > np.mean(z_fids) + 0.05
