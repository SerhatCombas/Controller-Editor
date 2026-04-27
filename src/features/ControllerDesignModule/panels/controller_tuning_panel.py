"""ControllerTuningPanel — Faz UI-3.

Tabbed configuration panel for the "System Controlling" module.
Designed to sit inside a CollapsibleSidebar on the left side.

Tabs:
  1. Controller — type selector (PID/LQR/Zustandsregler/MPR) + stacked params
  2. I/O Selection — input source, input profile, output checkboxes
  3. Simulation Settings — duration, sample time, solver, backend, tolerances
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


def _spinbox(
    value: float,
    minimum: float,
    maximum: float,
    step: float,
    decimals: int = 3,
) -> QDoubleSpinBox:
    """Create a pre-configured QDoubleSpinBox."""
    field = QDoubleSpinBox()
    field.setRange(minimum, maximum)
    field.setSingleStep(step)
    field.setValue(value)
    field.setDecimals(decimals)
    return field


class ControllerTuningPanel(QWidget):
    """3-tab controller configuration panel.

    Attributes
    ----------
    controller_tabs : QTabWidget
        The main tab widget with Controller / I/O / Simulation tabs.
    controller_type : QComboBox
        Controller type selector (PID, LQR, Zustandsregler, MPR).
    parameter_stack : QStackedWidget
        Stacked parameter forms for each controller type.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ControllerTuningPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.controller_tabs = QTabWidget()
        self.controller_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.controller_tabs.addTab(self._build_controller_tab(), "Controller")
        self.controller_tabs.addTab(self._build_io_selection_tab(), "I/O Selection")
        self.controller_tabs.addTab(self._build_simulation_settings_tab(), "Simulation Settings")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.addWidget(self.controller_tabs, 1)

    # ------------------------------------------------------------------
    # Tab 1 — Controller
    # ------------------------------------------------------------------

    def _build_controller_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.controller_type = QComboBox()
        self.controller_type.addItems(["PID", "LQR", "Zustandsregler", "MPR"])

        self.parameter_stack = QStackedWidget()
        self.parameter_stack.addWidget(self._build_pid_parameters())
        self.parameter_stack.addWidget(self._build_lqr_parameters())
        self.parameter_stack.addWidget(self._build_zustandsregler_parameters())
        self.parameter_stack.addWidget(self._build_mpr_parameters())

        self.controller_type.currentIndexChanged.connect(self.parameter_stack.setCurrentIndex)

        selector_form = QFormLayout()
        selector_form.addRow("Controller type", self.controller_type)

        layout.addLayout(selector_form)
        layout.addWidget(self.parameter_stack, 1)
        return tab

    def _build_pid_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.pid_enabled = QCheckBox()
        self.pid_enabled.setChecked(True)
        self.pid_kp = _spinbox(850.0, -100000.0, 100000.0, 1.0)
        self.pid_ki = _spinbox(45.0, -100000.0, 100000.0, 1.0)
        self.pid_kd = _spinbox(180.0, -100000.0, 100000.0, 1.0)
        self.pid_output_limit = _spinbox(1000.0, 0.0, 100000.0, 10.0)
        form.addRow("Enable PID", self.pid_enabled)
        form.addRow("Kp", self.pid_kp)
        form.addRow("Ki", self.pid_ki)
        form.addRow("Kd", self.pid_kd)
        form.addRow("Output limit", self.pid_output_limit)
        return panel

    def _build_lqr_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.lqr_q1 = _spinbox(1.0, 0.0, 100000.0, 0.1)
        self.lqr_q2 = _spinbox(1.0, 0.0, 100000.0, 0.1)
        self.lqr_r = _spinbox(0.1, 0.0001, 100000.0, 0.1)
        self.lqr_integral = QCheckBox()
        form.addRow("State weight q1", self.lqr_q1)
        form.addRow("State weight q2", self.lqr_q2)
        form.addRow("Control weight r", self.lqr_r)
        form.addRow("Integral action", self.lqr_integral)
        return panel

    def _build_zustandsregler_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.zr_k1 = _spinbox(10.0, -100000.0, 100000.0, 0.1)
        self.zr_k2 = _spinbox(5.0, -100000.0, 100000.0, 0.1)
        self.zr_k3 = _spinbox(1.0, -100000.0, 100000.0, 0.1)
        self.zr_l1 = _spinbox(20.0, -100000.0, 100000.0, 0.1)
        self.zr_l2 = _spinbox(20.0, -100000.0, 100000.0, 0.1)
        form.addRow("K1", self.zr_k1)
        form.addRow("K2", self.zr_k2)
        form.addRow("K3", self.zr_k3)
        form.addRow("Observer gain L1", self.zr_l1)
        form.addRow("Observer gain L2", self.zr_l2)
        return panel

    def _build_mpr_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        self.mpr_prediction = _spinbox(20.0, 1.0, 500.0, 1.0)
        self.mpr_control = _spinbox(5.0, 1.0, 500.0, 1.0)
        self.mpr_tracking = _spinbox(1.0, 0.0, 100000.0, 0.1)
        self.mpr_effort = _spinbox(0.1, 0.0, 100000.0, 0.1)
        self.mpr_constraint = _spinbox(100.0, 0.0, 100000.0, 1.0)
        form.addRow("Prediction horizon", self.mpr_prediction)
        form.addRow("Control horizon", self.mpr_control)
        form.addRow("Tracking weight", self.mpr_tracking)
        form.addRow("Control effort weight", self.mpr_effort)
        form.addRow("Input constraint", self.mpr_constraint)
        return panel

    # ------------------------------------------------------------------
    # Tab 2 — I/O Selection
    # ------------------------------------------------------------------

    def _build_io_selection_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.input_source = QComboBox()
        self.input_source.addItems([
            "Road displacement",
            "Reference signal",
            "External force",
            "Workspace input",
        ])

        self.input_profile = QComboBox()
        self.input_profile.addItems(["Step", "Sine", "Ramp", "Impulse", "Custom"])

        self.output_position = QCheckBox()
        self.output_position.setChecked(True)
        self.output_velocity = QCheckBox()
        self.output_acceleration = QCheckBox()
        self.output_control_effort = QCheckBox()
        self.output_error_signal = QCheckBox()

        form.addRow("Input source", self.input_source)
        form.addRow("Input profile", self.input_profile)
        form.addRow("Body position", self.output_position)
        form.addRow("Body velocity", self.output_velocity)
        form.addRow("Body acceleration", self.output_acceleration)
        form.addRow("Control effort", self.output_control_effort)
        form.addRow("Error signal", self.output_error_signal)
        return tab

    # ------------------------------------------------------------------
    # Tab 3 — Simulation Settings
    # ------------------------------------------------------------------

    def _build_simulation_settings_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.sim_duration = _spinbox(12.0, 0.1, 1000.0, 0.5)
        self.sim_sample_time = _spinbox(0.01, 0.0001, 10.0, 0.001)

        self.sim_solver = QComboBox()
        self.sim_solver.addItems(["RK45", "RK23", "DOP853", "BDF", "Radau"])

        self.sim_backend = QComboBox()
        self.sim_backend.addItems(["Numeric", "State space", "Transfer function"])

        self.sim_rtol = _spinbox(0.001, 0.000001, 1.0, 0.001, decimals=6)
        self.sim_atol = _spinbox(0.000001, 0.000000001, 1.0, 0.000001, decimals=9)

        form.addRow("Duration [s]", self.sim_duration)
        form.addRow("Sample time [s]", self.sim_sample_time)
        form.addRow("Solver", self.sim_solver)
        form.addRow("Backend", self.sim_backend)
        form.addRow("Relative tolerance", self.sim_rtol)
        form.addRow("Absolute tolerance", self.sim_atol)
        return tab

    # ------------------------------------------------------------------
    # Public API — read current configuration
    # ------------------------------------------------------------------

    def get_pid_config(self) -> dict[str, float | bool]:
        """Return current PID parameters as a dict."""
        return {
            "enabled": self.pid_enabled.isChecked(),
            "kp": self.pid_kp.value(),
            "ki": self.pid_ki.value(),
            "kd": self.pid_kd.value(),
            "output_limit": self.pid_output_limit.value(),
        }

    def get_simulation_config(self) -> dict[str, object]:
        """Return current simulation settings as a dict."""
        return {
            "duration": self.sim_duration.value(),
            "sample_time": self.sim_sample_time.value(),
            "solver": self.sim_solver.currentText(),
            "backend": self.sim_backend.currentText(),
            "rtol": self.sim_rtol.value(),
            "atol": self.sim_atol.value(),
        }

    def current_controller_type(self) -> str:
        """Return the currently selected controller type string."""
        return self.controller_type.currentText()
