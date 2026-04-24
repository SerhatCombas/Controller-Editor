#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QPlainTextEdit, QSizePolicy, QVBoxLayout

from controls.lqr_controller import LQRController
from models import MODEL_PENDULUM, get_linear_state_space


class TransferFunctionPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(320)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #e9eef3;
                border: 1px solid #9aa7b2;
                border-radius: 6px;
            }
            QLabel {
                color: #22313f;
                background-color: transparent;
            }
            QPlainTextEdit {
                background-color: #f8fbff;
                color: #22313f;
                border: 1px solid #aab8c4;
                border-radius: 5px;
                padding: 8px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        title = QLabel("Transfer Functions")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.open_loop_title = QLabel("Open-Loop")
        self.open_loop_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.open_loop_title)
        self.open_loop_view = self._create_formula_view()
        layout.addWidget(self.open_loop_view)

        self.closed_loop_title = QLabel("Closed-Loop")
        self.closed_loop_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.closed_loop_title)
        self.closed_loop_view = self._create_formula_view()
        layout.addWidget(self.closed_loop_view)
        self.update_transfer_functions()

    def _create_formula_view(self):
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMinimumHeight(95)
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view.setFont(QFont("Menlo", 11))
        return view

    def update_transfer_functions(self, control_config=None):
        config = control_config or {}
        algorithm = config.get("algorithm", "PID")
        if algorithm == "PID":
            open_loop_text, closed_loop_text = self._build_pid_text(config)
        elif algorithm == "Zustandsraum":
            open_loop_text, closed_loop_text = self._build_state_feedback_text(config)
        elif algorithm == "LQR":
            open_loop_text, closed_loop_text = self._build_lqr_text(config)
        else:
            open_loop_text = "Open-loop function is not defined for the selected mode."
            closed_loop_text = "Closed-loop function is not defined for the selected mode."
        self.open_loop_view.setPlainText(open_loop_text)
        self.closed_loop_view.setPlainText(closed_loop_text)

    def _build_pid_text(self, config):
        model_name = config.get("physical_model", MODEL_PENDULUM)
        A, B, C, D = get_linear_state_space(model_name)
        components = config.get("components", {})
        gains = config.get("gains", {})
        kp = gains.get("P", 0.0) if components.get("P", False) else 0.0
        ki = gains.get("I", 0.0) if components.get("I", False) else 0.0
        kd = gains.get("D", 0.0) if components.get("D", False) else 0.0

        controller_line = f"C(s) = ({kd:.3f}) s + ({kp:.3f}) + ({ki:.3f})/s"
        if model_name == MODEL_PENDULUM:
            plant_num = np.array([1.0], dtype=float)
            plant_den = np.array([1.0, 3.0, 2.0, 0.0], dtype=float)
            controller_num = np.array([kd, kp, ki], dtype=float)
            controller_den = np.array([1.0, 0.0], dtype=float)
            while controller_num.size > 1 and np.isclose(controller_num[0], 0.0):
                controller_num = controller_num[1:]
            if np.allclose(controller_num, 0.0):
                controller_num = np.array([0.0], dtype=float)
                controller_den = np.array([1.0], dtype=float)
            open_loop_num = np.polymul(controller_num, plant_num)
            open_loop_den = np.polymul(controller_den, plant_den)
            closed_loop_den = self._poly_add(open_loop_den, open_loop_num)
            open_loop = self._format_rational(open_loop_num, open_loop_den)
            closed_loop = self._format_rational(open_loop_num, closed_loop_den)
            return (
                f"Model: {model_name}\n\n{controller_line}\nG(s) = {self._format_rational(plant_num, plant_den)}\n\nOpen-loop:\nG_ol(s) = {open_loop}",
                f"Model: {model_name}\n\nClosed-loop:\nT(s) = {closed_loop}",
            )

        open_loop_block = (
            f"Model: {model_name}\n\n"
            f"{controller_line}\n\n"
            "Plant state-space model:\n"
            f"A =\n{self._format_matrix(A)}\n\n"
            f"B =\n{self._format_matrix(B)}\n\n"
            f"C =\n{self._format_matrix(C)}\n\n"
            f"D =\n{self._format_matrix(D)}\n\n"
            "Open-loop form:\n"
            "x_dot = A x + B u\n"
            "y = C x + D u\n"
            "u = C_pid(s) e"
        )
        closed_loop_block = (
            f"Model: {model_name}\n\n"
            "Closed-loop interpretation:\n"
            "PID acts on the selected output while the plant remains in state-space form.\n"
            "Equivalent SISO form:\n"
            "T(s) = C_pid(s) G(s) / (1 + C_pid(s) G(s))\n"
            "For this 4th-order quarter-car plant, the state-space representation above is used directly in simulation."
        )
        return open_loop_block, closed_loop_block

    def _build_state_feedback_text(self, config):
        model_name = config.get("physical_model", MODEL_PENDULUM)
        A, B, C, D = get_linear_state_space(model_name)
        K = np.array(config.get("state_space", {}).get("K", [1.6, 2.4, 34.0, 7.5]), dtype=float).reshape(1, 4)
        A_cl = A - B @ K
        return self._state_space_blocks(model_name, A, B, C, D, K, A_cl, "Zustandsraum")

    def _build_lqr_text(self, config):
        model_name = config.get("physical_model", MODEL_PENDULUM)
        A, B, C, D = get_linear_state_space(model_name)
        lqr_cfg = config.get("lqr", {})
        q_diag = lqr_cfg.get("Q_diag", [1.0, 1.0, 100.0, 10.0])
        r_value = lqr_cfg.get("R", 0.01)
        controller = LQRController(q_diag=q_diag, r_value=r_value, A=A, B=B)
        A_cl = controller.closed_loop_matrix()
        open_loop_block = (
            f"Model: {model_name}\n\n"
            "Open-loop state-space model:\n"
            f"A =\n{self._format_matrix(A)}\n\n"
            f"B =\n{self._format_matrix(B)}\n\n"
            f"C =\n{self._format_matrix(C)}\n\n"
            f"D =\n{self._format_matrix(D)}\n\n"
            f"Q =\n{self._format_matrix(controller.Q)}\n\n"
            f"R =\n{self._format_matrix(controller.R)}\n\n"
            f"K =\n{self._format_matrix(controller.K)}\n\n"
            "LQR design equations:\n"
            "J = integral(x^T Q x + u^T R u) dt\n"
            "A^T P + P A - P B R^(-1) B^T P + Q = 0\n"
            "u = -Kx"
        )
        closed_loop_block = (
            f"Model: {model_name}\n\n"
            "Closed-loop dynamics:\n"
            "x_dot = (A - BK) x\n"
            f"A_cl =\n{self._format_matrix(A_cl)}\n\n"
            f"P =\n{self._format_matrix(controller.P)}\n\n"
            f"det(sI - A_cl) = {self._format_polynomial(np.poly(A_cl))}"
        )
        return open_loop_block, closed_loop_block

    def _state_space_blocks(self, model_name, A, B, C, D, K, A_cl, mode_label):
        open_char_poly = np.poly(A)
        closed_char_poly = np.poly(A_cl)
        open_loop_block = (
            f"Model: {model_name}\n\n"
            f"{mode_label} state-space model:\n"
            f"A =\n{self._format_matrix(A)}\n\n"
            f"B =\n{self._format_matrix(B)}\n\n"
            f"C =\n{self._format_matrix(C)}\n\n"
            f"D =\n{self._format_matrix(D)}\n\n"
            f"K =\n{self._format_matrix(K)}\n\n"
            "Open-loop equations:\n"
            "x_dot = A x + B u\n"
            "y = C x + D u\n"
            "u = -Kx\n"
            f"det(sI - A) = {self._format_polynomial(open_char_poly)}"
        )
        closed_loop_block = (
            f"Model: {model_name}\n\n"
            "Closed-loop equations:\n"
            "x_dot = (A - BK) x\n"
            "y = C x\n\n"
            f"A_cl =\n{self._format_matrix(A_cl)}\n\n"
            f"det(sI - A_cl) = {self._format_polynomial(closed_char_poly)}"
        )
        return open_loop_block, closed_loop_block

    def _poly_add(self, first, second):
        length = max(len(first), len(second))
        first_padded = np.pad(first, (length - len(first), 0))
        second_padded = np.pad(second, (length - len(second), 0))
        return first_padded + second_padded

    def _format_rational(self, numerator, denominator):
        return f"({self._format_polynomial(numerator)}) / ({self._format_polynomial(denominator)})"

    def _format_polynomial(self, coefficients):
        coeffs = np.array(coefficients, dtype=float)
        terms = []
        for index, coeff in enumerate(coeffs):
            if np.isclose(coeff, 0.0):
                continue
            power = len(coeffs) - index - 1
            sign = "-" if coeff < 0 else "+"
            coeff_abs = self._format_coeff(abs(coeff))
            if power == 0:
                term_core = coeff_abs
            elif power == 1:
                term_core = "s" if np.isclose(abs(coeff), 1.0) else f"{coeff_abs} s"
            else:
                term_core = f"s^{power}" if np.isclose(abs(coeff), 1.0) else f"{coeff_abs} s^{power}"
            if not terms:
                terms.append(term_core if coeff >= 0 else f"- {term_core}")
            else:
                terms.append(f" {sign} {term_core}")
        return "".join(terms) if terms else "0"

    def _format_matrix(self, matrix):
        rows = []
        for row in np.atleast_2d(matrix):
            formatted = ", ".join(f"{value:8.3f}" for value in row)
            rows.append(f"  [{formatted}]")
        return "\n".join(rows)

    def _format_coeff(self, value):
        if np.isclose(value, round(value)):
            return str(int(round(value)))
        return f"{value:.3f}".rstrip("0").rstrip(".")
