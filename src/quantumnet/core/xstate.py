"""Exact Bell-block-diagonal (X-state) algebra under non-Pauli noise and swapping."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .qubit import QubitState


@dataclass(frozen=True)
class XState:
    """Two-qubit Bell-block-diagonal state (P_phi, delta_phi, alpha, beta, delta_psi).

    Bell basis order: {|Phi+>, |Phi->, |Psi+>, |Psi->}.
    - lambda_1 = (p_phi + delta_phi) / 2   (fidelity with |Phi+>)
    - lambda_2 = (p_phi - delta_phi) / 2   (fidelity with |Phi->)
    - lambda_3 = (1 - p_phi + delta_psi) / 2 (fidelity with |Psi+>)
    - lambda_4 = (1 - p_phi - delta_psi) / 2 (fidelity with |Psi->)
    - alpha = (a - d) / 2                  (|Phi+><Phi-| off-diagonal)
    - beta  = (b - c) / 2                  (|Psi+><Psi-| off-diagonal)
    """

    p_phi: float = 1.0
    delta_phi: float = 1.0
    alpha: float = 0.0
    beta: float = 0.0
    delta_psi: float = 0.0

    @staticmethod
    def bell_phi_plus() -> "XState":
        return XState(p_phi=1.0, delta_phi=1.0, alpha=0.0, beta=0.0, delta_psi=0.0)

    @staticmethod
    def bell_psi_plus() -> "XState":
        return XState(p_phi=0.0, delta_phi=0.0, alpha=0.0, beta=0.0, delta_psi=1.0)

    @staticmethod
    def from_werner(fidelity: float) -> "XState":
        f = float(np.clip(fidelity, 0.0, 1.0))
        w = (4.0 * f - 1.0) / 3.0
        return XState(p_phi=(1.0 + w) / 2.0, delta_phi=w, alpha=0.0, beta=0.0, delta_psi=0.0)

    @property
    def fidelity_phi_plus(self) -> float:
        return float(0.5 * (self.p_phi + self.delta_phi))

    @property
    def fidelity_psi_plus(self) -> float:
        return float(0.5 * (1.0 - self.p_phi + self.delta_psi))

    @property
    def computational_elements(self) -> tuple[float, float, float, float, float, float]:
        """Return (a, b, c, d, w, z) in computational basis {|00>, |01>, |10>, |11>}."""
        a = 0.5 * self.p_phi + self.alpha
        d = 0.5 * self.p_phi - self.alpha
        b = 0.5 * (1.0 - self.p_phi) + self.beta
        c = 0.5 * (1.0 - self.p_phi) - self.beta
        w = 0.5 * self.delta_phi
        z = 0.5 * self.delta_psi
        return a, b, c, d, w, z

    def to_density_matrix(self) -> QubitState:
        a, b, c, d, w, z = self.computational_elements
        rho = np.array(
            [
                [a, 0.0, 0.0, w],
                [0.0, b, z, 0.0],
                [0.0, z, c, 0.0],
                [w, 0.0, 0.0, d],
            ],
            dtype=complex,
        )
        return QubitState(rho, dims=[2, 2])

    def concurrence(self) -> float:
        """Exact closed-form Wootters concurrence for an X-state (Yu & Eberly 2007)."""
        a, b, c, d, w, z = self.computational_elements
        c1 = abs(w) - np.sqrt(max(0.0, b * c))
        c2 = abs(z) - np.sqrt(max(0.0, a * d))
        return float(2.0 * max(0.0, c1, c2))

    def werner_concurrence_estimate(self) -> float:
        """What a 1-parameter Werner model wrongly predicts from fidelity alone."""
        f = max(self.fidelity_phi_plus, self.fidelity_psi_plus)
        return float(max(0.0, 2.0 * f - 1.0))

    def apply_pauli_x_sleep_suit(self) -> "XState":
        """Apply a local Pauli X on qubit B: swaps |Phi+/-> <-> |Psi+/->.

        Used before and after memory storage so a |Phi+> pair sleeps in |Psi+>
        (which has d = 0 and never suffers T1 entanglement sudden death).
        """
        return XState(
            p_phi=1.0 - self.p_phi,
            delta_phi=self.delta_psi,
            alpha=self.beta,
            beta=self.alpha,
            delta_psi=self.delta_phi,
        )

    def apply_gad(
        self,
        gamma_a: float,
        gamma_b: float | None = None,
        *,
        p_th_a: float = 1.0,
        p_th_b: float = 1.0,
        eta_phi_a: float = 1.0,
        eta_phi_b: float | None = None,
    ) -> "XState":
        """Exact transformation under local Generalized Amplitude Damping + Pure Dephasing."""
        ga = float(np.clip(gamma_a, 0.0, 1.0))
        gb = ga if gamma_b is None else float(np.clip(gamma_b, 0.0, 1.0))
        pa = float(np.clip(p_th_a, 0.0, 1.0))
        pb = float(np.clip(p_th_b, 0.0, 1.0))
        ea = float(np.clip(eta_phi_a, 0.0, 1.0))
        eb = ea if eta_phi_b is None else float(np.clip(eta_phi_b, 0.0, 1.0))

        p_new = (
            (1.0 - ga) * (1.0 - gb) * self.p_phi
            + (ga * (1.0 - gb) * (2.0 * pa - 1.0) + gb * (1.0 - ga) * (2.0 * pb - 1.0)) * self.alpha
            + (-ga * (1.0 - gb) * (2.0 * pa - 1.0) + gb * (1.0 - ga) * (2.0 * pb - 1.0)) * self.beta
            + 2.0 * ga * gb * pa * pb
            - ga * gb * (pa + pb)
            + 0.5 * (ga + gb)
        )
        coh_scale = float(np.sqrt((1.0 - ga) * (1.0 - gb)) * ea * eb)
        d_phi_new = coh_scale * self.delta_phi
        d_psi_new = coh_scale * self.delta_psi
        alpha_new = (
            (1.0 - 0.5 * (ga + gb)) * self.alpha
            + 0.5 * (gb - ga) * self.beta
            + 0.5 * ga * (pa - 0.5)
            + 0.5 * gb * (pb - 0.5)
        )
        beta_new = (
            0.5 * (gb - ga) * self.alpha
            + (1.0 - 0.5 * (ga + gb)) * self.beta
            + 0.5 * ga * (pa - 0.5)
            - 0.5 * gb * (pb - 0.5)
        )
        return XState(
            p_phi=float(p_new),
            delta_phi=float(d_phi_new),
            alpha=float(alpha_new),
            beta=float(beta_new),
            delta_psi=float(d_psi_new),
        )

    def apply_t1_tphi_hold(
        self,
        dt_s: float,
        t1_a_s: float,
        tphi_a_s: float,
        *,
        t1_b_s: float | None = None,
        tphi_b_s: float | None = None,
    ) -> "XState":
        """Hold qubit A and qubit B for dt_s under local T1 and pure-dephasing T_phi."""
        t1_b = t1_a_s if t1_b_s is None else t1_b_s
        tphi_b = tphi_a_s if tphi_b_s is None else tphi_b_s
        ga = 0.0 if t1_a_s <= 0 else float(1.0 - np.exp(-dt_s / t1_a_s))
        gb = 0.0 if t1_b <= 0 else float(1.0 - np.exp(-dt_s / t1_b))
        ea = 1.0 if tphi_a_s <= 0 else float(np.exp(-dt_s / tphi_a_s))
        eb = 1.0 if tphi_b <= 0 else float(np.exp(-dt_s / tphi_b))
        return self.apply_gad(ga, gb, eta_phi_a=ea, eta_phi_b=eb)

    def procrustean_filter_one_sided(self, gamma_damped: float) -> tuple["XState", float]:
        """Local Procrustean filtering on the undamped "Cathedral" qubit B when qubit A
        suffered amplitude damping gamma_damped.

        Applies Kraus filter K0 = |0><0| + sqrt(1 - gamma_damped)|1><1| to qubit B.
        Restores symmetric populations before a linear-optical BSM so the pair avoids
        the 25% Bell-like BSM penalty (denker-1 Kette 2 & denker-2 Widerrede 3).
        Returns (post_selected_state, success_probability).
        """
        g = float(np.clip(gamma_damped, 0.0, 1.0 - 1e-12))
        a, b, c, d, w, z = self.computational_elements
        # K0 acts on qubit B (|01> and |11> multiplied by sqrt(1 - g) in amplitude, (1 - g) in pop)
        a_p = a
        b_p = b * (1.0 - g)
        c_p = c
        d_p = d * (1.0 - g)
        w_p = w * np.sqrt(1.0 - g)
        z_p = z * np.sqrt(1.0 - g)
        p_succ = float(a_p + b_p + c_p + d_p)
        if p_succ <= 0.0:
            return self, 0.0
        a_n, b_n, c_n, d_n = a_p / p_succ, b_p / p_succ, c_p / p_succ, d_p / p_succ
        w_n, z_n = w_p / p_succ, z_p / p_succ
        return (
            XState(
                p_phi=float(a_n + d_n),
                delta_phi=float(2.0 * w_n),
                alpha=float(0.5 * (a_n - d_n)),
                beta=float(0.5 * (b_n - c_n)),
                delta_psi=float(2.0 * z_n),
            ),
            p_succ,
        )

    def swap_with(self, other: "XState") -> dict:
        """Exact Bell-state swap between self (link 1: A1-A2) and other (link 2: B1-B2)
        with BSM on (A2, B1) and standard Pauli feed-forward on B2.

        Returns outcome probabilities, BSM thermometer asymmetry Delta_P_BSM,
        outcome-conditioned branches (Phi+/- and Psi+/-), and the feed-forward averaged state.
        """
        p1, dp1, a1, b1, ds1 = self.p_phi, self.delta_phi, self.alpha, self.beta, self.delta_psi
        p2, dp2, a2, b2, ds2 = other.p_phi, other.delta_phi, other.alpha, other.beta, other.delta_psi

        # Non-uniform BSM outcome probabilities (07 §1.3)
        mag_product = (a1 - b1) * (a2 + b2)
        p_phi_each = float(0.25 * (1.0 + 4.0 * mag_product))
        p_psi_each = float(0.25 * (1.0 - 4.0 * mag_product))
        bsm_asymmetry = float(p_phi_each - p_psi_each)  # 2 * (a1 - b1) * (a2 + b2)

        def branch(s_k: float, p_k: float) -> "XState":
            if p_k <= 1e-15:
                return XState(0.5, 0.0, 0.0, 0.0, 0.0)
            denom = 4.0 * p_k
            p_out = (2.0 * p1 * p2 - p1 - p2 + 1.0 + 4.0 * s_k * (a1 * a2 - b1 * b2)) / denom
            d_phi_out = (dp1 * dp2 + ds1 * ds2) / denom
            d_psi_out = (dp1 * ds2 + ds1 * dp2) / denom
            alpha_out = (s_k * p1 * (a2 + b2) + p2 * (a1 - b1) + b1 - s_k * b2) / denom
            beta_out = (s_k * p1 * (a2 + b2) - p2 * (a1 - b1) + a1 - s_k * a2) / denom
            return XState(
                p_phi=float(p_out),
                delta_phi=float(d_phi_out),
                alpha=float(alpha_out),
                beta=float(beta_out),
                delta_psi=float(d_psi_out),
            )

        phi_branch = branch(+1.0, p_phi_each)
        psi_branch = branch(-1.0, p_psi_each)
        averaged = XState(
            p_phi=float(2.0 * p1 * p2 - p1 - p2 + 1.0),
            delta_phi=float(dp1 * dp2 + ds1 * ds2),
            alpha=float(p2 * (a1 - b1) + b1),
            beta=float(a1 - p2 * (a1 - b1)),
            delta_psi=float(dp1 * ds2 + ds1 * dp2),
        )
        return {
            "p_phi_each": p_phi_each,
            "p_psi_each": p_psi_each,
            "p_phi_total": 2.0 * p_phi_each,
            "p_psi_total": 2.0 * p_psi_each,
            "bsm_asymmetry": bsm_asymmetry,
            "phi_branch": phi_branch,
            "psi_branch": psi_branch,
            "averaged": averaged,
        }
