#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from controls.lqr_controller import LQRController
from models import (
    MODEL_PENDULUM,
    get_default_lqr_weights,
    get_default_state_feedback_gains,
    get_linear_state_space,
)


class ControlSelectionPanel(QFrame):
    control_changed = Signal(dict)
    play_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(420)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.current_physical_model = None
        self._initializing = True

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
            QComboBox, QDoubleSpinBox {
                color: #22313f;
                background-color: #ffffff;
                border: 1px solid #8ea0b2;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QComboBox QAbstractItemView {
                color: #22313f;
                background-color: #ffffff;
                selection-color: #22313f;
                selection-background-color: #d8e7f5;
            }
            QCheckBox {
                spacing: 8px;
                color: #22313f;
                background-color: transparent;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QPushButton {
                color: #22313f;
                background-color: #ffffff;
                border: 1px solid #8ea0b2;
                border-radius: 4px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dfeaf4;
            }
            """
        )

        self.lqr_controller = LQRController()
        self.current_lqr_gain = self.lqr_controller.K.flatten().tolist()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(14)

        title = QLabel("Kontrol Algoritmasi")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        outer_layout.addWidget(title)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["PID", "Zustandsraum", "LQR"])
        outer_layout.addWidget(self.algorithm_combo)

        analysis_label = QLabel("Root Locus Analizi")
        analysis_label.setStyleSheet("font-weight: bold;")
        outer_layout.addWidget(analysis_label)

        analysis_form = QFormLayout()
        analysis_form.setContentsMargins(0, 0, 0, 0)
        analysis_form.setSpacing(10)
        self.damping_ratio_input = self._create_gain_spinbox(0.50, 0.05, 1.00, 0.05)
        analysis_form.addRow("Damping Ratio (zeta)", self.damping_ratio_input)
        outer_layout.addLayout(analysis_form)

        self.algorithm_stack = QStackedWidget()
        self.algorithm_stack.addWidget(self._create_pid_panel())
        self.algorithm_stack.addWidget(self._create_state_space_panel())
        self.algorithm_stack.addWidget(self._create_lqr_panel())
        outer_layout.addWidget(self.algorithm_stack)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        self.play_button.clicked.connect(self.play_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        button_row.addWidget(self.play_button)
        button_row.addWidget(self.stop_button)
        outer_layout.addLayout(button_row)
        outer_layout.addStretch()

        self.algorithm_combo.currentIndexChanged.connect(self.algorithm_stack.setCurrentIndex)
        self.algorithm_combo.currentIndexChanged.connect(self.emit_control_changed)
        self.damping_ratio_input.valueChanged.connect(self.emit_control_changed)

        self._initializing = False
        self.set_physical_model(MODEL_PENDULUM)
        self.emit_control_changed()

    def _create_pid_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        mode_label = QLabel("PID Bilesen Secimi")
        mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(mode_label)

        component_row = QHBoxLayout()
        component_row.setContentsMargins(0, 0, 0, 0)
        component_row.setSpacing(16)
        self.p_checkbox = QCheckBox("P")
        self.i_checkbox = QCheckBox("I")
        self.d_checkbox = QCheckBox("D")
        self.p_checkbox.setChecked(True)
        component_row.addWidget(self.p_checkbox)
        component_row.addWidget(self.i_checkbox)
        component_row.addWidget(self.d_checkbox)
        component_row.addStretch()
        layout.addLayout(component_row)

        self.selection_label = QLabel()
        self.selection_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.selection_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        self.p_input = self._create_gain_spinbox(35.0)
        self.i_input = self._create_gain_spinbox(0.8)
        self.d_input = self._create_gain_spinbox(6.0)
        form_layout.addRow("P Degeri", self.p_input)
        form_layout.addRow("I Degeri", self.i_input)
        form_layout.addRow("D Degeri", self.d_input)
        layout.addLayout(form_layout)

        info_label = QLabel("PID ayarlari secili fiziksel modele uygulanir.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(info_label)
        layout.addStretch()

        for checkbox in (self.p_checkbox, self.i_checkbox, self.d_checkbox):
            checkbox.toggled.connect(self.update_pid_fields)
        for spinbox in (self.p_input, self.i_input, self.d_input):
            spinbox.valueChanged.connect(self.emit_control_changed)
        self.update_pid_fields()
        return panel

    def _create_state_space_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Zustandsraum Regler")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.state_space_label = QLabel("Aktif kontrol tipi: Zustandsraum")
        self.state_space_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.state_space_label)

        self.state_space_model_label = QLabel()
        self.state_space_model_label.setWordWrap(True)
        self.state_space_model_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.state_space_model_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        self.k1_input = self._create_gain_spinbox(1.6, -5000.0, 5000.0, 0.1)
        self.k2_input = self._create_gain_spinbox(2.4, -5000.0, 5000.0, 0.1)
        self.k3_input = self._create_gain_spinbox(34.0, -5000.0, 5000.0, 0.5)
        self.k4_input = self._create_gain_spinbox(7.5, -5000.0, 5000.0, 0.1)
        form_layout.addRow("K1", self.k1_input)
        form_layout.addRow("K2", self.k2_input)
        form_layout.addRow("K3", self.k3_input)
        form_layout.addRow("K4", self.k4_input)
        layout.addLayout(form_layout)
        layout.addStretch()

        for spinbox in (self.k1_input, self.k2_input, self.k3_input, self.k4_input):
            spinbox.valueChanged.connect(self.emit_control_changed)
        return panel

    def _create_lqr_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("LQR Regler")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        self.lqr_label = QLabel("Aktif kontrol tipi: LQR")
        self.lqr_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.lqr_label)

        self.lqr_model_label = QLabel()
        self.lqr_model_label.setWordWrap(True)
        self.lqr_model_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.lqr_model_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)
        self.lqr_q1_input = self._create_gain_spinbox(1.0, 0.0, 10000.0, 1.0)
        self.lqr_q2_input = self._create_gain_spinbox(1.0, 0.0, 10000.0, 1.0)
        self.lqr_q3_input = self._create_gain_spinbox(100.0, 0.0, 10000.0, 1.0)
        self.lqr_q4_input = self._create_gain_spinbox(10.0, 0.0, 10000.0, 1.0)
        self.lqr_r_input = self._create_gain_spinbox(0.01, 0.001, 1000.0, 0.01)
        form_layout.addRow("Q1", self.lqr_q1_input)
        form_layout.addRow("Q2", self.lqr_q2_input)
        form_layout.addRow("Q3", self.lqr_q3_input)
        form_layout.addRow("Q4", self.lqr_q4_input)
        form_layout.addRow("R", self.lqr_r_input)
        layout.addLayout(form_layout)

        self.lqr_gain_label = QLabel()
        self.lqr_gain_label.setWordWrap(True)
        self.lqr_gain_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.lqr_gain_label)

        self.lqr_note_label = QLabel()
        self.lqr_note_label.setWordWrap(True)
        self.lqr_note_label.setStyleSheet("color: #51606d; font-size: 12px;")
        layout.addWidget(self.lqr_note_label)
        layout.addStretch()

        for spinbox in (self.lqr_q1_input, self.lqr_q2_input, self.lqr_q3_input, self.lqr_q4_input, self.lqr_r_input):
            spinbox.valueChanged.connect(self.update_lqr_fields)
        return panel

    def _create_gain_spinbox(self, value, minimum=-500.0, maximum=500.0, step=0.1, suffix=""):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(step)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        return spinbox

    def set_physical_model(self, model_name):
        if model_name == self.current_physical_model and not self._initializing:
            return
        self.current_physical_model = model_name
        A, B, _, _ = get_linear_state_space(model_name)
        self.lqr_controller.update_model(A, B)

        state_gains = get_default_state_feedback_gains(model_name)
        q_diag, r_value = get_default_lqr_weights(model_name)

        widgets = [self.k1_input, self.k2_input, self.k3_input, self.k4_input, self.lqr_q1_input, self.lqr_q2_input, self.lqr_q3_input, self.lqr_q4_input, self.lqr_r_input]
        for widget in widgets:
            widget.blockSignals(True)
        self.k1_input.setValue(state_gains[0])
        self.k2_input.setValue(state_gains[1])
        self.k3_input.setValue(state_gains[2])
        self.k4_input.setValue(state_gains[3])
        self.lqr_q1_input.setValue(q_diag[0])
        self.lqr_q2_input.setValue(q_diag[1])
        self.lqr_q3_input.setValue(q_diag[2])
        self.lqr_q4_input.setValue(q_diag[3])
        self.lqr_r_input.setValue(r_value)
        for widget in widgets:
            widget.blockSignals(False)

        self.state_space_model_label.setText(f"Model: {model_name}\nRegelgesetz: u = -Kx")
        self.lqr_model_label.setText(f"Model: {model_name}\nJ = integral(x^T Q x + u^T R u) dt")
        self.update_lqr_fields()
        if not self._initializing:
            self.emit_control_changed()

    def build_pid_mode_label(self):
        parts = []
        if self.p_checkbox.isChecked():
            parts.append("P")
        if self.i_checkbox.isChecked():
            parts.append("I")
        if self.d_checkbox.isChecked():
            parts.append("D")
        return "".join(parts)

    def lqr_q_diag(self):
        return [self.lqr_q1_input.value(), self.lqr_q2_input.value(), self.lqr_q3_input.value(), self.lqr_q4_input.value()]

    def update_lqr_fields(self):
        try:
            self.current_lqr_gain = self.lqr_controller.update_weights(self.lqr_q_diag(), self.lqr_r_input.value())
            gain_text = ", ".join(f"{value:.3f}" for value in self.current_lqr_gain)
            self.lqr_gain_label.setText(f"Berechnetes K = [{gain_text}]")
            self.lqr_note_label.setText("LQR kazanci secili fiziksel modelin A ve B matrislerinden yeniden hesaplanir.")
        except Exception as exc:  # pragma: no cover
            self.current_lqr_gain = [0.0, 0.0, 0.0, 0.0]
            self.lqr_gain_label.setText("Berechnetes K = [hesaplanamadi]")
            self.lqr_note_label.setText(f"LQR hesaplama hatasi: {exc}")
        if not self._initializing:
            self.emit_control_changed()

    def update_pid_fields(self):
        pid_mode = self.build_pid_mode_label()
        for checkbox, spin_box in ((self.p_checkbox, self.p_input), (self.i_checkbox, self.i_input), (self.d_checkbox, self.d_input)):
            spin_box.setEnabled(checkbox.isChecked())
        self.selection_label.setText(f"Aktif kontrol tipi: {pid_mode}" if pid_mode else "En az bir bilesen secilmelidir.")
        if not self._initializing:
            self.emit_control_changed()

    def emit_control_changed(self):
        config = {
            "algorithm": self.algorithm_combo.currentText(),
            "components": {"P": self.p_checkbox.isChecked(), "I": self.i_checkbox.isChecked(), "D": self.d_checkbox.isChecked()},
            "gains": {"P": self.p_input.value(), "I": self.i_input.value(), "D": self.d_input.value()},
            "state_space": {"K": [self.k1_input.value(), self.k2_input.value(), self.k3_input.value(), self.k4_input.value()]},
            "lqr": {"Q_diag": self.lqr_q_diag(), "R": self.lqr_r_input.value(), "K": self.current_lqr_gain},
            "analysis": {"damping_ratio": self.damping_ratio_input.value()},
        }
        self.control_changed.emit(config)
