"""MainWindow_v2 — Faz 5MVP-3.

Clean, template-independent main window for static analysis.

Layout:
  ┌──────────────┬─────────────────┬──────────────────┐
  │              │  [Compile btn]  │                  │
  │  ModelPanel  │  EquationPanel  │  AnalysisPanel   │
  │  (canvas +   │  (state-space,  │  (step, bode,    │
  │   palette)   │   TF display)   │   pole-zero)     │
  │              │                 │                  │
  └──────────────┴─────────────────┴──────────────────┘

Workflow:
  1. User drags components from palette, wires them on canvas
  2. Assigns I/O roles (right-click → mark as input/output)
  3. Clicks "Compile & Analyze"
  4. Service: canvas → SystemGraph → StaticAnalysisResult
  5. UI updates: equation summary, step/bode/pole-zero plots

No real-time simulation — static analysis only for MVP.
The old MainWindow (main_window.py) remains untouched; switching
the entry point is deferred to 5MVP-5.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.core.state.app_state_v2 import AppStateV2
from app.services.compile_analyze_service import CompileAnalyzeService
from app.services.static_analysis_backend import GenericStaticBackend
from app.ui.panels.analysis_panel import AnalysisPanel
from app.ui.panels.equation_panel import EquationPanel
from app.ui.panels.model_panel import ModelPanel, default_saved_layouts_path

logger = logging.getLogger(__name__)


class MainWindowV2(QMainWindow):
    """Template-independent main window with static analysis.

    Uses AppStateV2 + CompileAnalyzeService + GenericStaticBackend.
    No dependency on QuarterCarModel, simulation_service, or signal_catalog.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Controller Editor — v2")
        self.resize(1720, 980)

        # State & services
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)

        # Panels
        self.model_panel = ModelPanel(saved_layouts_path=default_saved_layouts_path())
        self.equation_panel = EquationPanel()
        self.analysis_panel = AnalysisPanel()

        # Build UI
        self._build_layout()
        self._wire_events()

        # Initial state
        self.model_panel.load_default_model()
        self._update_status("Ready — drag components from palette, wire them, and click Compile.")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)

        # Toolbar row
        toolbar = QHBoxLayout()
        self.compile_btn = QPushButton("⟳ Compile && Analyze")
        self.compile_btn.setStyleSheet(
            "QPushButton {"
            "  background: #0b84f3; color: white;"
            "  font-weight: 600; font-size: 14px;"
            "  padding: 8px 20px; border-radius: 6px;"
            "}"
            "QPushButton:hover { background: #0a75d9; }"
            "QPushButton:pressed { background: #0966bf; }"
        )
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color: #546e7a; font-size: 12px; padding-left: 12px;"
        )
        toolbar.addWidget(self.compile_btn)
        toolbar.addWidget(self.status_label, 1)
        outer.addLayout(toolbar)

        # Middle column: equation panel
        middle_column = QWidget()
        middle_layout = QVBoxLayout(middle_column)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.addWidget(self.equation_panel, 1)

        # Main 3-column splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.model_panel)
        main_splitter.addWidget(middle_column)
        main_splitter.addWidget(self.analysis_panel)
        main_splitter.setChildrenCollapsible(False)
        main_splitter.setStretchFactor(0, 6)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setStretchFactor(2, 5)
        main_splitter.setSizes([760, 430, 650])

        self.model_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.analysis_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(main_splitter, 1)

    # ------------------------------------------------------------------
    # Event wiring
    # ------------------------------------------------------------------

    def _wire_events(self) -> None:
        self.compile_btn.clicked.connect(self._on_compile_clicked)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_compile_clicked(self) -> None:
        """Compile canvas → analyze → update UI."""
        canvas = self.model_panel.canvas
        components = canvas._components
        wires = canvas._wires

        if not components:
            self._update_status("Nothing to compile — add components first.")
            self.equation_panel.show_empty_state("Canvas is empty.")
            self.analysis_panel.show_empty_state("Canvas is empty.")
            return

        self._update_status("Compiling...")
        ok = self.service.compile_and_analyze(components, wires)

        if not ok:
            error = self.state.compile_error or self.state.analysis_error or "Unknown error"
            self._update_status(f"Error: {error}")
            self.equation_panel.show_empty_state(f"Analysis failed: {error}")
            self.analysis_panel.show_empty_state(f"Analysis failed: {error}")
            return

        self._update_status(
            f"Done — {self.state.n_states} states, "
            f"{len(self.state.analysis_result.transfer_functions)} TFs, "
            f"stable={'Yes' if self.state.is_stable else 'No'}"
        )
        self._update_equation_panel()
        self._update_analysis_panel()

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------

    def _update_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _update_equation_panel(self) -> None:
        """Build and display equation/state-space summary."""
        result = self.state.analysis_result
        if result is None:
            self.equation_panel.show_empty_state("No analysis result.")
            return

        ss = result.state_space
        summary = {
            "state_variables": ", ".join(ss.state_variables),
            "input_variables": ", ".join(ss.input_variables),
            "output_variables": ", ".join(ss.output_variables),
            "a_matrix": self._format_matrix(ss.a_matrix),
            "b_matrix": self._format_matrix(ss.b_matrix),
            "c_matrix": self._format_matrix(ss.c_matrix),
            "d_matrix": self._format_matrix(ss.d_matrix),
            "transfer_functions": self._format_tfs(result),
            "stability": "Stable" if result.is_stable else "Unstable / No TFs",
        }
        self.equation_panel.update_summary(summary)

    def _update_analysis_panel(self) -> None:
        """Compute and display step response, Bode, and pole-zero plots."""
        result = self.state.analysis_result
        if result is None or not result.transfer_functions:
            self.analysis_panel.show_empty_state(
                "No transfer functions available for plotting."
            )
            return

        try:
            self._plot_step_response(result)
            self._plot_bode(result)
            self._plot_pole_zero(result)
        except Exception as exc:
            logger.warning("Plot update failed: %s", exc, exc_info=True)
            self.analysis_panel.show_empty_state(
                f"Plot generation failed: {exc}"
            )

    def _plot_step_response(self, result) -> None:
        """Plot step response for all supported TFs."""
        import numpy as np
        from app.core.symbolic.tf_builder import s as S

        ax = self.analysis_panel.step_axes
        ax.clear()

        t_end = 5.0
        dt = 0.01
        t = np.arange(0, t_end, dt)

        output_specs = []
        for tf in result.transfer_functions:
            num_coeffs = self._tf_to_num_coeffs(tf)
            den_coeffs = self._tf_to_den_coeffs(tf)
            if not den_coeffs:
                continue
            try:
                from numpy.polynomial import polynomial as P
                # scipy signal for step response
                import scipy.signal as sig
                system = sig.TransferFunction(num_coeffs, den_coeffs)
                t_out, y_out = sig.step(system, T=t)
                label = f"{tf.input_id} → {tf.output_id}"
                ax.plot(t_out, y_out, label=label)
                output_specs.append((tf.output_id, label, "#0b84f3"))
            except Exception:
                continue

        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Response")
        ax.set_title("Step Response")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        self.analysis_panel.step_canvas.draw()

    def _plot_bode(self, result) -> None:
        """Plot Bode diagram for all supported TFs."""
        import numpy as np

        mag_ax = self.analysis_panel.bode_mag_axes
        phase_ax = self.analysis_panel.bode_phase_axes
        mag_ax.clear()
        phase_ax.clear()

        for tf in result.transfer_functions:
            num_coeffs = self._tf_to_num_coeffs(tf)
            den_coeffs = self._tf_to_den_coeffs(tf)
            if not den_coeffs:
                continue
            try:
                import scipy.signal as sig
                system = sig.TransferFunction(num_coeffs, den_coeffs)
                w, mag, phase = sig.bode(system)
                label = f"{tf.input_id} → {tf.output_id}"
                mag_ax.semilogx(w, mag, label=label)
                phase_ax.semilogx(w, phase, label=label)
            except Exception:
                continue

        mag_ax.set_ylabel("Magnitude [dB]")
        mag_ax.set_title("Bode Diagram")
        mag_ax.legend(fontsize=7)
        mag_ax.grid(True, alpha=0.3)
        phase_ax.set_xlabel("Frequency [rad/s]")
        phase_ax.set_ylabel("Phase [deg]")
        phase_ax.grid(True, alpha=0.3)
        self.analysis_panel.bode_canvas.draw()

    def _plot_pole_zero(self, result) -> None:
        """Plot pole-zero map."""
        import sympy

        ax = self.analysis_panel.pole_zero_axes
        ax.clear()

        poles_re, poles_im = [], []
        zeros_re, zeros_im = [], []

        for tf in result.transfer_functions:
            for p in tf.poles:
                poles_re.append(float(sympy.re(p)))
                poles_im.append(float(sympy.im(p)))
            for z in tf.zeros:
                zeros_re.append(float(sympy.re(z)))
                zeros_im.append(float(sympy.im(z)))

        if poles_re:
            ax.plot(poles_re, poles_im, "rx", markersize=10, label="Poles")
        if zeros_re:
            ax.plot(zeros_re, zeros_im, "bo", markersize=8, label="Zeros")

        ax.axhline(y=0, color="k", linewidth=0.5)
        ax.axvline(x=0, color="k", linewidth=0.5)
        ax.set_xlabel("Real")
        ax.set_ylabel("Imaginary")
        ax.set_title("Pole-Zero Map")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        self.analysis_panel.pz_canvas.draw()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_matrix(matrix: list[list[float]]) -> str:
        if not matrix:
            return "[]"
        rows = []
        for row in matrix:
            rows.append("  [" + ", ".join(f"{v:10.4f}" for v in row) + "]")
        return "[\n" + "\n".join(rows) + "\n]"

    @staticmethod
    def _format_tfs(result) -> str:
        lines = []
        for tf in result.transfer_functions:
            lines.append(
                f"{tf.input_id} → {tf.output_id}: "
                f"order={tf.order}, "
                f"poles={len(tf.poles)}, "
                f"proper={'yes' if tf.is_proper else 'no'}"
            )
        for u in result.unsupported_outputs:
            lines.append(
                f"{u.input_id} → {u.output_id}: UNSUPPORTED "
                f"({u.unsupported_reason})"
            )
        return "\n".join(lines) if lines else "No transfer functions."

    @staticmethod
    def _tf_to_num_coeffs(tf) -> list[float]:
        """Extract numerator polynomial coefficients [highest → lowest order]."""
        import sympy
        from app.core.symbolic.tf_builder import s as S
        poly = sympy.Poly(tf.numerator_expr, S)
        return [float(c) for c in poly.all_coeffs()]

    @staticmethod
    def _tf_to_den_coeffs(tf) -> list[float]:
        """Extract denominator polynomial coefficients [highest → lowest order]."""
        import sympy
        from app.core.symbolic.tf_builder import s as S
        poly = sympy.Poly(tf.denominator_expr, S)
        return [float(c) for c in poly.all_coeffs()]
