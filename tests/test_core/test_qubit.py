import numpy as np
import pytest
from quantumnet.core import QubitState
from quantumnet.core.noise import depolarizing_channel_2


def test_zero_state():
    q = QubitState.zero()
    assert q.rho.shape == (2, 2)
    assert np.isclose(q.rho[0, 0], 1.0)
    assert np.isclose(q.rho[1, 1], 0.0)
    assert q.is_pure


def test_one_state():
    q = QubitState.one()
    assert np.isclose(q.rho[1, 1], 1.0)
    assert q.is_pure


def test_plus_state():
    q = QubitState.plus()
    assert q.is_pure
    assert np.isclose(q.rho[0, 0], 0.5)


def test_bell_phi_plus():
    q = QubitState.bell_phi_plus()
    assert q.num_qubits == 2
    assert q.is_pure
    assert np.isclose(q.rho[0, 0], 0.5)
    assert np.isclose(q.rho[0, 3], 0.5)


def test_maximally_mixed():
    q = QubitState.maximally_mixed(1)
    assert not q.is_pure
    assert np.isclose(q.purity(), 0.5)


def test_fidelity():
    z = QubitState.zero()
    o = QubitState.one()
    assert np.isclose(z.fidelity(z), 1.0)
    assert np.isclose(z.fidelity(o), 0.0)


def test_partial_trace():
    bell = QubitState.bell_phi_plus()
    reduced = bell.partial_trace(1)
    assert reduced.num_qubits == 1
    assert np.isclose(reduced.purity(), 0.5)


def test_concurrence():
    bell = QubitState.bell_phi_plus()
    assert np.isclose(bell.concurrence(), 1.0)

    mixed = QubitState.maximally_mixed(2)
    assert np.isclose(mixed.concurrence(), 0.0)


def test_concurrence_werner_states():
    bell = QubitState.bell_phi_plus()
    werner_sep = depolarizing_channel_2((4.0 / 3.0) * (1.0 - 0.5)).apply(bell)
    assert werner_sep.concurrence() == pytest.approx(0.0, abs=1e-12)

    f = 0.7
    werner_ent = depolarizing_channel_2((4.0 / 3.0) * (1.0 - f)).apply(bell)
    assert werner_ent.concurrence() == pytest.approx(2.0 * f - 1.0)
