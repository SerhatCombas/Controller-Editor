#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math

import pygame
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QSplitter,
)

from controls.lqr_controller import LQRController
from controls.state_space_controller import StateSpaceController
from models import MODEL_PENDULUM, create_model, get_model_names
from models.pendulum_model import PendulumModel
from models.rendering import fit_model_to_rect


class PygameAnimationWidget(QLabel):
    info_changed = Signal(dict)
    simulation_data_changed = Signal(dict)
    model_changed = Signal(str)

    def __init__(self, width=500, height=300, parent=None):
        super().__init__(parent)
        self.base_width = width
        self.base_height = height
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #f4f4f4; border: 1px solid #999;")

        pygame.init()
        self.surface = pygame.Surface((self.base_width, self.base_height))

        self.running_animation = False
        self.dt = 1 / 60
        self.speed_multiplier = 1.0
        self.integral_error = 0.0
        self.sim_time = 0.0
        self.last_force = 0.0
        self.last_control_force = 0.0
        self.status_text = "Hazir - Play ile baslat"
        self.control_config = {
            "physical_model": MODEL_PENDULUM,
            "algorithm": "PID",
            "components": {"P": True, "I": False, "D": False},
            "gains": {"P": 35.0, "I": 0.8, "D": 6.0},
            "state_space": {"K": [1.6, 2.4, 34.0, 7.5]},
            "lqr": {"Q_diag": [1.0, 1.0, 100.0, 10.0], "R": 0.01},
            "excitation": {
                "mode": "Baslangic Acisi",
                "angle_deg": 8.0,
                "angular_velocity": 0.0,
                "step_force": 2.0,
                "step_time": 1.0,
            },
        }

        self.model = create_model(MODEL_PENDULUM)
        self.state_space_controller = StateSpaceController()
        A, B, _, _ = self.model.linear_state_space()
        self.lqr_controller = LQRController(A=A, B=B)
        self.reset_simulation(reset_status=False)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(int(self.dt * 1000))
        self.update_frame()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        if self.base_width <= 0:
            return super().heightForWidth(width)
        return max(180, int(width * self.base_height / self.base_width))

    def minimumSizeHint(self):
        return self.sizeHint()

    def sizeHint(self):
        return QSize(self.base_width, self.base_height)

    def current_model_name(self):
        return self.control_config.get("physical_model", MODEL_PENDULUM)

    def current_info_labels(self):
        return self.model.info_labels

    def set_control_config(self, config):
        merged = dict(self.control_config)
        merged.update(config)
        previous_model = self.current_model_name()
        self.control_config = merged
        new_model = self.current_model_name()

        if new_model != previous_model:
            self.model = create_model(new_model)
            A, B, _, _ = self.model.linear_state_space()
            self.lqr_controller.update_model(A, B)
            self.model_changed.emit(new_model)
        else:
            A, B, _, _ = self.model.linear_state_space()
            self.lqr_controller.update_model(A, B)

        state_gains = self.control_config.get("state_space", {}).get("K", [1.6, 2.4, 34.0, 7.5])
        self.state_space_controller.set_gains(state_gains)
        lqr_cfg = self.control_config.get("lqr", {})
        self.lqr_controller.update_weights(lqr_cfg.get("Q_diag", [1.0, 1.0, 100.0, 10.0]), lqr_cfg.get("R", 0.01))
        self.stop_animation()
        self.reset_simulation()

    def reset_simulation(self, reset_status=True):
        self.integral_error = 0.0
        self.last_force = 0.0
        self.last_control_force = 0.0
        self.sim_time = 0.0
        self.model.reset(self.control_config.get("excitation", {}))
        if reset_status:
            self.status_text = "Hazir - Play ile baslat"
        self.emit_info_changed()
        self.emit_simulation_data_changed()

    def start_animation(self):
        self.running_animation = True
        self.status_text = "Simulasyon calisiyor"
        self.emit_info_changed()
        self.emit_simulation_data_changed()

    def stop_animation(self):
        self.running_animation = False
        if self.status_text == "Simulasyon calisiyor":
            self.status_text = "Duraklatildi"
        self.emit_info_changed()
        self.emit_simulation_data_changed()

    def set_speed_multiplier(self, value):
        self.speed_multiplier = max(0.25, min(2.0, float(value)))
        self.emit_info_changed()

    def build_pid_mode_label(self):
        components = self.control_config.get("components", {})
        parts = []
        if components.get("P", False):
            parts.append("P")
        if components.get("I", False):
            parts.append("I")
        if components.get("D", False):
            parts.append("D")
        return "".join(parts) or "None"

    def active_control_mode_label(self):
        algorithm = self.control_config.get("algorithm", "PID")
        if algorithm == "PID":
            return self.build_pid_mode_label()
        return algorithm

    def compute_control_force(self, dt):
        algorithm = self.control_config.get("algorithm", "PID")
        state = self.model.get_state_vector()
        if algorithm == "PID":
            force, self.integral_error = self.model.compute_pid_control(
                self.control_config.get("components", {}),
                self.control_config.get("gains", {}),
                self.integral_error,
                dt,
            )
        elif algorithm == "Zustandsraum":
            force = self.state_space_controller.compute_control(state)
        elif algorithm == "LQR":
            force = self.lqr_controller.compute_control(state)
        else:
            force = 0.0
        self.last_control_force = max(min(force, self.model.control_limit), -self.model.control_limit)
        return self.last_control_force

    def _apply_pendulum_limits(self):
        if isinstance(self.model, PendulumModel):
            max_s = self.model.max_travel_m()
            if self.model.s >= max_s:
                self.model.s = max_s
                if self.model.s_dot > 0:
                    self.model.s_dot = 0.0
            elif self.model.s <= -max_s:
                self.model.s = -max_s
                if self.model.s_dot < 0:
                    self.model.s_dot = 0.0

    def _update_status(self):
        if isinstance(self.model, PendulumModel):
            if abs(self.model.phi) > math.radians(100):
                self.status_text = "Denge kaybedildi - cubuk dustu"
            else:
                self.status_text = "Simulasyon calisiyor"
        else:
            if abs(self.model.z2) > 0.14:
                self.status_text = "Ride comfort lost"
            else:
                self.status_text = "Simulasyon calisiyor"

    def current_info(self):
        display = self.model.display_values()
        return {
            "status": self.status_text,
            "control_mode": self.active_control_mode_label(),
            "s": display.get("s", "-"),
            "phi": display.get("phi", "-"),
            "u_control": f"{self.last_control_force:.2f}",
            "u_total": f"{self.last_force:.2f}",
            "disturbance": display.get("disturbance", "-"),
            "speed": f"{self.speed_multiplier:.2f}x",
        }

    def current_signal_state(self):
        signal_values = self.model.signal_values()
        return {
            "time": self.sim_time,
            "primary_signal": signal_values.get("primary_signal", 0.0),
            "secondary_signal": signal_values.get("secondary_signal", 0.0),
            "u_control": self.last_control_force,
            "u_total": self.last_force,
            "model": self.current_model_name(),
            "algorithm": self.control_config.get("algorithm", "PID"),
            "signal_labels": self.model.signal_labels,
        }

    def emit_info_changed(self):
        self.info_changed.emit(self.current_info())

    def emit_simulation_data_changed(self):
        self.simulation_data_changed.emit(self.current_signal_state())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_frame()

    def update_frame(self):
        if self.running_animation:
            dt = self.dt * self.speed_multiplier
            control_force = self.compute_control_force(dt)
            total_force, _disturbance = self.model.step(dt, control_force, self.control_config.get("excitation", {}))
            self.last_force = total_force
            self.sim_time += dt
            self._apply_pendulum_limits()
            self._update_status()

        self.draw_scene()
        self.blit_to_label()
        self.emit_info_changed()
        self.emit_simulation_data_changed()

    def draw_scene(self):
        widget_width = max(self.contentsRect().width(), 1)
        widget_height = max(self.contentsRect().height(), 1)
        self.surface = pygame.Surface((widget_width, widget_height))
        viewport = fit_model_to_rect(
            (widget_width, widget_height),
            self.model.world_bounds(),
            padding_ratio=getattr(self.model, "viewport_padding_ratio", 0.08),
            min_padding_px=12,
        )
        self.model.render(self.surface, viewport)

    def blit_to_label(self):
        widget_width = max(self.contentsRect().width(), 1)
        widget_height = max(self.contentsRect().height(), 1)
        if self.surface.get_size() != (widget_width, widget_height):
            self.draw_scene()
        raw_str = pygame.image.tostring(self.surface, "RGB")
        image = QImage(raw_str, widget_width, widget_height, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(image))


class AnimationInfoPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setMinimumHeight(132)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #eef2f5;
                border: 1px solid #9aa7b2;
                border-radius: 6px;
            }
            QLabel {
                color: #22313f;
                background-color: transparent;
                font-size: 14px;
            }
            QLabel[role="title"] {
                font-weight: bold;
                font-size: 15px;
            }
            """
        )

        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setHorizontalSpacing(12)
        self.layout.setVerticalSpacing(6)
        self.value_labels = {}
        self.title_labels = {}
        fields = [
            ("Status", "status", 0, 0),
            ("Control Mode", "control_mode", 1, 0),
            ("s", "s", 2, 0),
            ("phi", "phi", 0, 2),
            ("U_control", "u_control", 1, 2),
            ("U_total", "u_total", 2, 2),
            ("Disturbance", "disturbance", 3, 0),
            ("Speed", "speed", 3, 2),
        ]
        for title, key, row, col in fields:
            title_label = QLabel(f"{title}:")
            title_label.setProperty("role", "title")
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            self.layout.addWidget(title_label, row, col)
            self.layout.addWidget(value_label, row, col + 1)
            self.title_labels[key] = title_label
            self.value_labels[key] = value_label
        self.layout.setColumnStretch(1, 1)
        self.layout.setColumnStretch(3, 1)

    def set_field_titles(self, mapping):
        for key, title in mapping.items():
            if key in self.title_labels:
                self.title_labels[key].setText(f"{title}:")

    def update_info(self, info):
        for key, label in self.value_labels.items():
            label.setText(info.get(key, "-"))


class SimulationControlsPanel(QFrame):
    settings_changed = Signal(dict)
    speed_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initializing = True
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            """
            QFrame {
                background-color: #eef2f5;
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
            QRadioButton {
                spacing: 8px;
                color: #22313f;
                background-color: transparent;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Global Simulation Controls")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        model_form = QFormLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(get_model_names())
        model_form.addRow("Physical Model", self.model_combo)
        layout.addLayout(model_form)

        excitation_label = QLabel("Baslangic / Uyarim Secimi")
        excitation_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(excitation_label)

        excitation_row = QHBoxLayout()
        excitation_row.setContentsMargins(0, 0, 0, 0)
        excitation_row.setSpacing(14)
        self.excitation_group = QButtonGroup(self)
        self.initial_angle_radio = QRadioButton("Baslangic Acisi")
        self.initial_velocity_radio = QRadioButton("Baslangic Acisal Hiz")
        self.step_input_radio = QRadioButton("Dis Girdi")
        self.initial_angle_radio.setChecked(True)
        for index, button in enumerate((self.initial_angle_radio, self.initial_velocity_radio, self.step_input_radio)):
            self.excitation_group.addButton(button, index)
            excitation_row.addWidget(button)
        excitation_row.addStretch()
        layout.addLayout(excitation_row)

        self.excitation_stack = QStackedWidget()
        self.excitation_stack.addWidget(self._create_initial_angle_page())
        self.excitation_stack.addWidget(self._create_initial_velocity_page())
        self.excitation_stack.addWidget(self._create_step_input_page())
        layout.addWidget(self.excitation_stack)

        speed_label = QLabel("Simulasyon Hizi")
        speed_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(speed_label)

        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(25, 200)
        self.speed_slider.setValue(100)
        self.speed_value_label = QLabel("1.00x")
        self.speed_value_label.setMinimumWidth(56)
        speed_row.addWidget(self.speed_slider)
        speed_row.addWidget(self.speed_value_label)
        layout.addLayout(speed_row)

        for spinbox in (self.initial_angle_input, self.initial_velocity_input, self.step_force_input, self.step_time_input):
            spinbox.valueChanged.connect(self.emit_settings_changed)
        self.model_combo.currentIndexChanged.connect(self.emit_settings_changed)
        self.excitation_group.idClicked.connect(self.excitation_stack.setCurrentIndex)
        self.excitation_group.idClicked.connect(lambda _: self.emit_settings_changed())
        self.speed_slider.valueChanged.connect(self._emit_speed_changed)
        self._initializing = False
        self._emit_speed_changed(self.speed_slider.value())
        self.emit_settings_changed()

    def _create_initial_angle_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        self.initial_angle_input = self._create_spinbox(8.0, -45.0, 45.0, 0.5, " deg")
        layout.addRow("theta(0)", self.initial_angle_input)
        return page

    def _create_initial_velocity_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        self.initial_velocity_input = self._create_spinbox(1.0, -20.0, 20.0, 0.1, " rad/s")
        layout.addRow("theta_dot(0)", self.initial_velocity_input)
        return page

    def _create_step_input_page(self):
        page = QWidget()
        layout = QFormLayout(page)
        self.step_force_input = self._create_spinbox(2.0, -30.0, 30.0, 0.5, " N")
        self.step_time_input = self._create_spinbox(1.0, 0.0, 10.0, 0.1, " s")
        layout.addRow("Step Kuvveti", self.step_force_input)
        layout.addRow("Step Zamani", self.step_time_input)
        return page

    def _create_spinbox(self, value, minimum, maximum, step, suffix=""):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(step)
        spinbox.setValue(value)
        spinbox.setSuffix(suffix)
        return spinbox

    def selected_excitation_mode(self):
        if self.initial_angle_radio.isChecked():
            return "Baslangic Acisi"
        if self.initial_velocity_radio.isChecked():
            return "Baslangic Acisal Hiz"
        return "Dis Girdi (Step)"

    def current_settings(self):
        return {
            "physical_model": self.model_combo.currentText(),
            "excitation": {
                "mode": self.selected_excitation_mode(),
                "angle_deg": self.initial_angle_input.value(),
                "angular_velocity": self.initial_velocity_input.value(),
                "step_force": self.step_force_input.value(),
                "step_time": self.step_time_input.value(),
            },
        }

    def emit_settings_changed(self):
        if not self._initializing:
            self.settings_changed.emit(self.current_settings())

    def _emit_speed_changed(self, value):
        speed = value / 100.0
        self.speed_value_label.setText(f"{speed:.2f}x")
        self.speed_changed.emit(speed)


class AnimationPanel(QWidget):
    simulation_data_changed = Signal(dict)
    simulation_settings_changed = Signal(dict)
    model_changed = Signal(str)

    def __init__(self, width=520, height=320, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.animation_widget = PygameAnimationWidget(width=width, height=height)
        self.info_panel = AnimationInfoPanel()
        self.simulation_controls = SimulationControlsPanel()
        self.animation_widget.setMinimumHeight(220)

        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self.info_panel)
        controls_layout.addWidget(self.simulation_controls)
        controls_layout.addStretch()

        self.controls_scroll = QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QFrame.NoFrame)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setWidget(controls_container)
        self.controls_scroll.setMinimumHeight(250)

        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.vertical_splitter.addWidget(self.animation_widget)
        self.vertical_splitter.addWidget(self.controls_scroll)
        self.vertical_splitter.setStretchFactor(0, 5)
        self.vertical_splitter.setStretchFactor(1, 4)
        self.vertical_splitter.setSizes([340, 300])

        layout.addWidget(self.vertical_splitter, stretch=1)

        self.animation_widget.info_changed.connect(self.info_panel.update_info)
        self.animation_widget.simulation_data_changed.connect(self.simulation_data_changed.emit)
        self.animation_widget.model_changed.connect(self._handle_model_changed)
        self.simulation_controls.settings_changed.connect(self.simulation_settings_changed.emit)
        self.simulation_controls.speed_changed.connect(self.animation_widget.set_speed_multiplier)
        self.info_panel.set_field_titles(self.animation_widget.current_info_labels())
        self.info_panel.update_info(self.animation_widget.current_info())

    def _handle_model_changed(self, model_name):
        self.info_panel.set_field_titles(self.animation_widget.current_info_labels())
        self.model_changed.emit(model_name)

    def set_control_config(self, config):
        self.animation_widget.set_control_config(config)
        self.info_panel.set_field_titles(self.animation_widget.current_info_labels())

    def start_animation(self):
        self.animation_widget.start_animation()

    def stop_animation(self):
        self.animation_widget.stop_animation()

    def reset_simulation(self):
        self.animation_widget.reset_simulation()
