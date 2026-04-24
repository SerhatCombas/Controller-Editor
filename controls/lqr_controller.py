#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np

try:
    from scipy.linalg import solve_continuous_are
except ImportError:  # pragma: no cover - scipy may be unavailable in some envs
    solve_continuous_are = None


def build_cart_pendulum_state_space_matrices(
    cart_mass=1.2,
    pendulum_mass=0.25,
    pendulum_length=0.6,
    gravity=9.81,
):
    """Linearized cart-pendulum model around the upright equilibrium.

    State order:
        x = [s, s_dot, phi, phi_dot]^T
    """
    A = np.array([
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, -(pendulum_mass * gravity) / cart_mass, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, ((cart_mass + pendulum_mass) * gravity) / (cart_mass * pendulum_length), 0.0],
    ])
    B = np.array([
        [0.0],
        [1.0 / cart_mass],
        [0.0],
        [-1.0 / (cart_mass * pendulum_length)],
    ])
    C = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ])
    D = np.zeros((2, 1))
    return A, B, C, D


class LQRController:
    """Continuous-time LQR controller using u = -Kx."""

    def __init__(self, q_diag=None, r_value=0.01, A=None, B=None):
        self.A, self.B, _, _ = build_cart_pendulum_state_space_matrices() if A is None or B is None else (A, B, None, None)
        self.q_diag = np.array(q_diag or [1.0, 1.0, 100.0, 10.0], dtype=float)
        self.r_value = float(r_value)
        self.Q = np.diag(self.q_diag)
        self.R = np.array([[max(self.r_value, 1e-6)]], dtype=float)
        self.K = np.zeros((1, self.A.shape[0]), dtype=float)
        self.P = np.zeros_like(self.A)
        self.update_weights(self.q_diag, self.r_value)

    def update_model(self, A, B):
        self.A = np.array(A, dtype=float)
        self.B = np.array(B, dtype=float)
        self.compute_gain(self.A, self.B, self.Q, self.R)

    def update_weights(self, q_diag, r_value):
        self.q_diag = np.array(q_diag, dtype=float)
        if self.q_diag.shape != (4,):
            raise ValueError("LQR q_diag must contain 4 state weights.")
        self.r_value = max(float(r_value), 1e-6)
        self.Q = np.diag(self.q_diag)
        self.R = np.array([[self.r_value]], dtype=float)
        self.compute_gain(self.A, self.B, self.Q, self.R)
        return self.K.flatten().tolist()

    def compute_gain(self, A, B, Q, R):
        A = np.array(A, dtype=float)
        B = np.array(B, dtype=float)
        Q = np.array(Q, dtype=float)
        R = np.array(R, dtype=float)

        if solve_continuous_are is not None:
            P = solve_continuous_are(A, B, Q, R)
        else:
            P = self._solve_care_via_hamiltonian(A, B, Q, R)

        K = np.linalg.solve(R, B.T @ P)
        self.P = 0.5 * (P + P.T)
        self.K = np.real_if_close(K)
        return self.K.flatten().tolist()

    def compute_control(self, state):
        state_vector = np.array(state, dtype=float).reshape(-1)
        return float(-(self.K @ state_vector.reshape(-1, 1))[0, 0])

    def closed_loop_matrix(self):
        return self.A - self.B @ self.K

    def _solve_care_via_hamiltonian(self, A, B, Q, R):
        n = A.shape[0]
        R_inv = np.linalg.inv(R)
        hamiltonian = np.block([
            [A, -(B @ R_inv @ B.T)],
            [-Q, -A.T],
        ])
        eigenvalues, eigenvectors = np.linalg.eig(hamiltonian)
        stable_indices = [index for index, value in enumerate(eigenvalues) if np.real(value) < 0]
        if len(stable_indices) != n:
            raise RuntimeError("Unable to isolate stable invariant subspace for CARE solution.")

        stable_vectors = eigenvectors[:, stable_indices]
        v1 = stable_vectors[:n, :]
        v2 = stable_vectors[n:, :]
        if np.linalg.matrix_rank(v1) < n:
            raise RuntimeError("CARE solution failed because the stable subspace is singular.")

        P = np.real_if_close(v2 @ np.linalg.inv(v1))
        return 0.5 * (P + P.T)
