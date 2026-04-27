"""SystemDesignerShell — Faz UI-5.

Top-level application window.  Two-module layout:
  ┌─────────────────────────┬─────────────────────────────────┐
  │  System Modelling        │  System Controlling              │
  │  (SystemModelingView)    │  (SystemControllingView)         │
  │  - Library sidebar       │  - Config sidebar (PID/LQR/...) │
  │  - Canvas workspace      │  - Results 2×2 grid              │
  │  - Component inspector   │  - Equations sidebar             │
  │                          │  - [Run Simulation]              │
  └─────────────────────────┴─────────────────────────────────┘

Workflow:
  1. User drags components from library, wires them on canvas
  2. Assigns I/O roles (right-click → mark as input/output)
  3. Configures controller parameters in Configuration sidebar
  4. Clicks "Run Simulation"
  5. Pipeline: canvas → SystemGraph → StaticAnalysisResult
  6. UI updates: equations panel, step/bode/pole-zero plots
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.shared.state.app_state import AppStateV2
from app.services.compile_analyze_service import CompileAnalyzeService
from app.ui.views.system_modeling_view import SystemModelingView
from app.ui.views.system_controlling_view import SystemControllingView

logger = logging.getLogger(__name__)


# ======================================================================
# Dark Theme Stylesheet
# ======================================================================

APP_STYLESHEET = """
QMainWindow {
    background: #222426;
}
QWidget {
    font-size: 12px;
}
QSplitter::handle {
    background: #222426;
}
#SystemModelingArea {
    background: #2f3133;
    border: 1px solid #5a5d60;
    border-radius: 8px;
}
#SystemControllingArea {
    background: #2f3133;
    border: 1px solid #5a5d60;
    border-radius: 8px;
}
#ModuleTitle {
    color: #f5f7f8;
    font-size: 16px;
    font-weight: 700;
    padding: 0;
    background: transparent;
    border: none;
}
#ModelLibraryPanel {
    border: none;
    background: #3d3f41;
}
#ComponentInspectorPanel {
    background: #383b3e;
    border: 1px solid #555a5e;
    border-radius: 7px;
}
#InspectorFieldName {
    color: #f5f7f8;
    font-weight: 700;
}
#InspectorFieldValue {
    color: #d4dade;
}
#CollapsibleSidebar {
    background: #252729;
    border: 1px solid #464b50;
    border-radius: 7px;
}
#SidebarHeader {
    background: #2b2e31;
    border-bottom: 1px solid #3d4247;
}
#SidebarTitle {
    color: #f5f7f8;
    font-weight: 700;
}
#SidebarToggleButton {
    background: #30343a;
    color: #d8dde2;
    border: 1px solid #555d66;
    border-radius: 5px;
    min-height: 24px;
    max-height: 24px;
    min-width: 24px;
    max-width: 24px;
}
#SidebarToggleButton:hover {
    background: #3a4148;
    border-color: #6f7b86;
}
#ControllerTuningPanel {
    border: none;
    background: #444648;
}
#SimulationResultsPanel {
    border: 1px solid #555a5e;
    background: #343638;
}
#ModelEquationsPanel {
    border: none;
    background: #444648;
}
#RunSimulationButton {
    min-height: 36px;
    background: #2f6fb3;
    color: #f5f7f8;
    border: 1px solid #6aa5e8;
    border-radius: 4px;
}
#RunSimulationButton:hover {
    background: #3a7fc3;
}
QPlainTextEdit {
    background: #343638;
    color: #f5f7f8;
    border: 1px solid #555a5e;
}
QTreeWidget, QLineEdit, QTabWidget::pane {
    background: #343638;
    color: #f5f7f8;
    border: 1px solid #555a5e;
}
QTreeWidget::item {
    min-height: 26px;
}
QLabel {
    color: #f5f7f8;
}
QPushButton {
    min-height: 30px;
    background: #2f6fb3;
    color: #f5f7f8;
    border: 1px solid #6aa5e8;
    border-radius: 4px;
}
QTabWidget, QDoubleSpinBox, QCheckBox {
    color: #f5f7f8;
}
QDoubleSpinBox {
    background: #252729;
    border: 1px solid #6b7075;
    min-height: 24px;
}
QListWidget {
    background: #343638;
    color: #f5f7f8;
    border: 1px solid #555a5e;
}
QListWidget::item {
    min-height: 32px;
    padding: 2px 4px;
}
QListWidget::item:hover {
    background: #3a4148;
}
QListWidget::item:selected {
    background: #2f6fb3;
}
QComboBox {
    background: #343638;
    color: #f5f7f8;
    border: 1px solid #555a5e;
    min-height: 26px;
    padding: 2px 6px;
}
QComboBox::drop-down {
    border: none;
}
QScrollArea {
    border: none;
    background: transparent;
}
QGroupBox {
    color: #f5f7f8;
    border: 1px solid #555a5e;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 12px;
}
QGroupBox::title {
    color: #f5f7f8;
    subcontrol-origin: margin;
    padding: 0 6px;
}
QToolButton {
    color: #f5f7f8;
    border: 1px solid #5d6266;
    background: #303234;
    padding: 4px 6px;
}
QToolButton:checked {
    background: #3a4148;
}
"""


def _build_module_frame(
    title: str,
    content: QWidget,
    object_name: str,
) -> QFrame:
    """Wrap a view widget in a titled, styled frame."""
    frame = QFrame()
    frame.setObjectName(object_name)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    title_label = QLabel(title)
    title_label.setObjectName("ModuleTitle")
    title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)
    layout.addWidget(title_label)
    layout.addWidget(content, 1)
    return frame


class SystemDesignerShell(QMainWindow):
    """Top-level application window — 2-module layout with dark theme.

    Uses AppStateV2 + CompileAnalyzeService for the analysis pipeline.
    No dependency on QuarterCarModel, simulation_service, or signal_catalog.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("System Designer")
        self.resize(1800, 980)

        # State & services
        self.state = AppStateV2()
        self.service = CompileAnalyzeService(self.state)

        # Feature views
        self.modeling_view = SystemModelingView()
        self.controlling_view = SystemControllingView()

        # Wrap in titled frames
        modeling_frame = _build_module_frame(
            "System Modelling",
            self.modeling_view,
            "SystemModelingArea",
        )
        controlling_frame = _build_module_frame(
            "System Controlling",
            self.controlling_view,
            "SystemControllingArea",
        )

        # Main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(modeling_frame)
        main_splitter.addWidget(controlling_frame)
        main_splitter.setSizes([700, 1100])
        main_splitter.setChildrenCollapsible(False)

        self.setCentralWidget(main_splitter)
        self.setStyleSheet(APP_STYLESHEET)

        # Wire events
        self._wire_events()

        # Initial state
        self.modeling_view.load_default_model()
        self._update_status("Ready — drag components, wire them, then Run Simulation.")

    # ------------------------------------------------------------------
    # Event wiring
    # ------------------------------------------------------------------

    def _wire_events(self) -> None:
        self.controlling_view.run_button.clicked.connect(self._on_run_clicked)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_run_clicked(self) -> None:
        """Compile canvas → analyze → update UI."""
        canvas = self.modeling_view.canvas
        components = canvas._components
        wires = canvas._wires

        if not components:
            self._update_status("Nothing to compile — add components first.")
            self.controlling_view.show_empty_state("Canvas is empty.")
            return

        self._update_status("Compiling & analyzing...")
        ok = self.service.compile_and_analyze(components, wires)

        if not ok:
            error = self.state.compile_error or self.state.analysis_error or "Unknown error"
            self._update_status(f"Error: {error}")
            self.controlling_view.show_empty_state(f"Analysis failed: {error}")
            return

        self._update_status(
            f"Done — {self.state.n_states} states, "
            f"{len(self.state.analysis_result.transfer_functions)} TFs, "
            f"stable={'Yes' if self.state.is_stable else 'No'}"
        )
        self._update_equations()
        self._update_plots()

    # ------------------------------------------------------------------
    # UI update helpers
    # ------------------------------------------------------------------

    def _update_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _update_equations(self) -> None:
        """Push analysis results to the equations panel."""
        result = self.state.analysis_result
        if result is None:
            self.controlling_view.equations_panel.show_empty_state("No analysis result.")
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
        self.controlling_view.equations_panel.update_equations(summary)

    def _update_plots(self) -> None:
        """Compute and display step response, Bode, and pole-zero plots."""
        result = self.state.analysis_result
        rp = self.controlling_view.results_panel

        if result is None or not result.transfer_functions:
            rp.show_empty_state("No transfer functions available for plotting.")
            return

        try:
            self._plot_step_response(result, rp)
            self._plot_bode(result, rp)
            self._plot_pole_zero(result, rp)
        except Exception as exc:
            logger.warning("Plot update failed: %s", exc, exc_info=True)
            rp.show_empty_state(f"Plot generation failed: {exc}")

    def _plot_step_response(self, result, rp) -> None:
        import numpy as np
        ax = rp.step_axes
        ax.clear()
        t = np.arange(0, 5.0, 0.01)
        for tf in result.transfer_functions:
            num = self._tf_to_coeffs(tf.numerator_expr)
            den = self._tf_to_coeffs(tf.denominator_expr)
            if not den:
                continue
            try:
                import scipy.signal as sig
                system = sig.TransferFunction(num, den)
                t_out, y_out = sig.step(system, T=t)
                ax.plot(t_out, y_out, label=f"{tf.input_id} → {tf.output_id}")
            except Exception:
                continue
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Response")
        ax.set_title("Step Response")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        rp.step_canvas.draw()

    def _plot_bode(self, result, rp) -> None:
        mag_ax = rp.bode_mag_axes
        phase_ax = rp.bode_phase_axes
        mag_ax.clear()
        phase_ax.clear()
        for tf in result.transfer_functions:
            num = self._tf_to_coeffs(tf.numerator_expr)
            den = self._tf_to_coeffs(tf.denominator_expr)
            if not den:
                continue
            try:
                import scipy.signal as sig
                system = sig.TransferFunction(num, den)
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
        rp.bode_canvas.draw()

    def _plot_pole_zero(self, result, rp) -> None:
        import sympy
        ax = rp.pole_zero_axes
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
        rp.pz_canvas.draw()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_matrix(matrix: list[list[float]]) -> str:
        if not matrix:
            return "[]"
        rows = ["  [" + ", ".join(f"{v:10.4f}" for v in row) + "]" for row in matrix]
        return "[\n" + "\n".join(rows) + "\n]"

    @staticmethod
    def _format_tfs(result) -> str:
        lines = []
        for tf in result.transfer_functions:
            lines.append(
                f"{tf.input_id} → {tf.output_id}: "
                f"order={tf.order}, poles={len(tf.poles)}, "
                f"proper={'yes' if tf.is_proper else 'no'}"
            )
        for u in result.unsupported_outputs:
            lines.append(
                f"{u.input_id} → {u.output_id}: UNSUPPORTED ({u.unsupported_reason})"
            )
        return "\n".join(lines) if lines else "No transfer functions."

    @staticmethod
    def _tf_to_coeffs(expr) -> list[float]:
        """Extract polynomial coefficients [highest → lowest order]."""
        import sympy
        from src.shared.engine.tf_builder import s as S
        poly = sympy.Poly(expr, S)
        return [float(c) for c in poly.all_coeffs()]
