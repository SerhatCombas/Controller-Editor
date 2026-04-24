from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.models.quarter_car_model import QuarterCarParameters
from app.core.state.app_state import ControllerConfig, RoadProfileConfig, SignalSelection, SimulationConfig
from app.services.signal_catalog import TemplateSignalCatalog, input_definition, output_definition, signal_catalog_for_template
from app.ui.widgets.status_widget import LiveStatusWidget


class ControllerPanel(QWidget):
    simulation_requested = Signal()
    stop_requested = Signal()
    load_default_requested = Signal()
    config_changed = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        helper = QFrame()
        helper.setFrameShape(QFrame.StyledPanel)
        helper_layout = QVBoxLayout(helper)
        helper_title = QLabel("Ready-Made Suspension Workflow")
        helper_title.setStyleSheet("font-size: 17px; font-weight: 600;")
        helper_text = QLabel(
            "1. Load the default suspension model\n"
            "2. Adjust parameters and choose input/output\n"
            "3. Start the simulation\n"
            "4. Inspect time and frequency-domain results"
        )
        helper_text.setWordWrap(True)
        helper_layout.addWidget(helper_title)
        helper_layout.addWidget(helper_text)
        layout.addWidget(helper)

        self.load_default_button = QPushButton("Load Default Suspension Model")
        layout.addWidget(self.load_default_button)
        self._signal_catalog: TemplateSignalCatalog = signal_catalog_for_template("blank")
        self._scene_input_component_ids: tuple[str, ...] = ()
        self._scene_input_component_names: tuple[str, ...] = ()
        self._scene_input_signal_ids: tuple[str, ...] = ()
        self._scene_output_component_ids: tuple[str, ...] = ()
        self._scene_output_component_names: tuple[str, ...] = ()

        layout.addWidget(self._build_model_group())
        layout.addWidget(self._build_io_group())
        layout.addWidget(self._build_road_group())
        layout.addWidget(self._build_pid_group())

        self.status_widget = LiveStatusWidget()
        layout.addWidget(self.status_widget)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Start Simulation")
        self.stop_button = QPushButton("Stop")
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)
        layout.addLayout(button_row)
        layout.addStretch()

        self._wire_events()
        self.update_signal_catalog("blank")
        self._emit_config()

    def _build_model_group(self) -> QGroupBox:
        group = QGroupBox("Mechanical Parameters")
        form = QFormLayout(group)
        self.body_mass = self._double_spinbox(300.0, 50.0, 1500.0, 10.0, " kg")
        self.wheel_mass = self._double_spinbox(40.0, 5.0, 300.0, 1.0, " kg")
        self.suspension_spring = self._double_spinbox(15000.0, 1000.0, 100000.0, 500.0, " N/m", 0)
        self.suspension_damper = self._double_spinbox(1200.0, 10.0, 10000.0, 50.0, " Ns/m", 0)
        self.tire_stiffness = self._double_spinbox(180000.0, 10000.0, 500000.0, 5000.0, " N/m", 0)
        form.addRow("Body mass", self.body_mass)
        form.addRow("Wheel mass", self.wheel_mass)
        form.addRow("Suspension spring", self.suspension_spring)
        form.addRow("Suspension damper", self.suspension_damper)
        form.addRow("Tire stiffness", self.tire_stiffness)
        return group

    def _build_io_group(self) -> QGroupBox:
        group = QGroupBox("Input / Output Selection")
        form = QFormLayout(group)
        self.input_source = QComboBox()
        self.input_source.setEnabled(False)
        self.input_source.setToolTip("Use the scene context menu to mark the active input component.")
        self.input_profile = QComboBox()
        self.output_signal_list = QListWidget()
        self.output_signal_list.setEnabled(False)
        self.output_signal_list.setToolTip("Use the scene context menu to mark active output components.")
        self.output_signal_list.setMaximumHeight(140)
        self.input_amplitude = self._double_spinbox(0.03, 0.0, 20.0, 0.01, "", 3)
        self.input_frequency = self._double_spinbox(1.5, 0.1, 20.0, 0.1, " Hz", 2)
        self.input_start_time = self._double_spinbox(0.5, 0.0, 20.0, 0.1, " s", 2)
        self.scene_input_status = QLabel("No scene input selected.")
        self.scene_input_status.setWordWrap(True)
        self.scene_output_status = QLabel("No scene outputs selected.")
        self.scene_output_status.setWordWrap(True)
        self.selection_hint = QLabel("Select at least one input and one output before starting simulation.")
        self.selection_hint.setWordWrap(True)
        form.addRow("Input source", self.input_source)
        form.addRow("Scene input", self.scene_input_status)
        form.addRow("Input profile", self.input_profile)
        form.addRow("Observed outputs", self.output_signal_list)
        form.addRow("Scene outputs", self.scene_output_status)
        form.addRow("Input amplitude", self.input_amplitude)
        form.addRow("Input frequency", self.input_frequency)
        form.addRow("Start time", self.input_start_time)
        form.addRow("Simulation readiness", self.selection_hint)
        self._refresh_input_profiles()
        return group

    def _build_road_group(self) -> QGroupBox:
        group = QGroupBox("Road / Simulation Settings")
        form = QFormLayout(group)
        self.road_amplitude = self._double_spinbox(0.03, 0.001, 0.150, 0.005, " m", 3)
        self.road_roughness = self._double_spinbox(0.35, 0.0, 2.0, 0.05, "", 2)
        self.road_seed = QSpinBox()
        self.road_seed.setRange(0, 99999)
        self.road_seed.setValue(7)
        self.road_speed = self._double_spinbox(6.0, 0.5, 40.0, 0.5, " m/s", 1)
        self.road_smoothness = self._double_spinbox(1.4, 0.1, 10.0, 0.1, " Hz", 2)
        self.duration = self._double_spinbox(12.0, 1.0, 120.0, 1.0, " s", 1)
        self.sample_time = self._double_spinbox(0.04, 0.01, 0.20, 0.01, " s", 2)
        self.runtime_backend = QComboBox()
        self.runtime_backend.addItem("Numeric (default)", "numeric")
        self.runtime_backend.addItem("Symbolic (experimental)", "symbolic")
        self.runtime_backend_value = QLabel("Numeric (default)")
        self.runtime_template_value = QLabel("Quarter-Car Suspension")
        self.runtime_readiness_value = QLabel("runtime_ready=yes | diagnostics_ready=yes | symbolic_equations_ready=yes")
        self.runtime_symbolic_status = QLabel("Idle")
        self.runtime_fallback_reason = QLabel("None")
        self.runtime_source_summary = QLabel("Runtime: Numeric (default) | Equations: Symbolic backend | Analysis: Backend-neutral static analysis")
        self.runtime_recent_events = QLabel("No recent runtime events.")
        self.runtime_recent_events.setWordWrap(True)
        self.runtime_template_value.setWordWrap(True)
        self.runtime_readiness_value.setWordWrap(True)
        self.runtime_source_summary.setWordWrap(True)
        self.runtime_backend_value.setWordWrap(True)
        self.runtime_symbolic_status.setWordWrap(True)
        self.runtime_fallback_reason.setWordWrap(True)
        form.addRow("Road amplitude", self.road_amplitude)
        form.addRow("Roughness", self.road_roughness)
        form.addRow("Seed", self.road_seed)
        form.addRow("Road speed", self.road_speed)
        form.addRow("Smoothness / cutoff", self.road_smoothness)
        form.addRow("Simulation duration", self.duration)
        form.addRow("Update step", self.sample_time)
        form.addRow("Runtime backend", self.runtime_backend)
        form.addRow("Active template", self.runtime_template_value)
        form.addRow("Template readiness", self.runtime_readiness_value)
        form.addRow("Active backend", self.runtime_backend_value)
        form.addRow("Symbolic status", self.runtime_symbolic_status)
        form.addRow("Last fallback reason", self.runtime_fallback_reason)
        form.addRow("Backend summary", self.runtime_source_summary)
        form.addRow("Recent runtime events", self.runtime_recent_events)
        return group

    def _build_pid_group(self) -> QGroupBox:
        group = QGroupBox("Controller Settings")
        form = QFormLayout(group)
        self.enable_pid = QCheckBox("Enable PID controller")
        self.enable_pid.setChecked(True)
        self.kp = self._double_spinbox(850.0, 0.0, 10000.0, 25.0)
        self.ki = self._double_spinbox(45.0, 0.0, 2000.0, 5.0)
        self.kd = self._double_spinbox(180.0, 0.0, 5000.0, 10.0)
        self.reset_pid_button = QPushButton("Reset PID Defaults")
        form.addRow(self.enable_pid)
        form.addRow("Kp", self.kp)
        form.addRow("Ki", self.ki)
        form.addRow("Kd", self.kd)
        form.addRow(self.reset_pid_button)
        return group

    def _wire_events(self) -> None:
        watched = [
            self.body_mass,
            self.wheel_mass,
            self.suspension_spring,
            self.suspension_damper,
            self.tire_stiffness,
            self.input_amplitude,
            self.input_frequency,
            self.input_start_time,
            self.road_amplitude,
            self.road_roughness,
            self.road_seed,
            self.road_speed,
            self.road_smoothness,
            self.duration,
            self.sample_time,
            self.kp,
            self.ki,
            self.kd,
        ]
        for widget in watched:
            widget.valueChanged.connect(self._emit_config)
        self.enable_pid.toggled.connect(self._emit_config)
        self.input_source.currentIndexChanged.connect(self._handle_input_source_changed)
        self.input_profile.currentIndexChanged.connect(self._emit_config)
        self.output_signal_list.itemChanged.connect(self._emit_config)
        self.runtime_backend.currentIndexChanged.connect(self._emit_config)
        self.load_default_button.clicked.connect(self.load_default_requested.emit)
        self.start_button.clicked.connect(self.simulation_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.reset_pid_button.clicked.connect(self._reset_pid_defaults)

    def _handle_input_source_changed(self) -> None:
        self._refresh_input_profiles()
        self._emit_config()

    def _refresh_input_profiles(self) -> None:
        current_source = self.input_source.currentData()
        previous = self.input_profile.currentData()
        self.input_profile.blockSignals(True)
        self.input_profile.clear()
        definition = input_definition(self._signal_catalog.template_id, current_source)
        if definition is not None:
            for profile_id, profile_label in definition.profiles:
                self.input_profile.addItem(profile_label, profile_id)
        if previous is not None and self.input_profile.count():
            index = self.input_profile.findData(previous)
            if index >= 0:
                self.input_profile.setCurrentIndex(index)
        self.input_profile.blockSignals(False)

    def update_signal_catalog(self, template_id: str) -> None:
        self._signal_catalog = signal_catalog_for_template(template_id)
        previous_input = self.input_source.currentData()
        previous_outputs = set(self.selected_output_signals())

        self.input_source.blockSignals(True)
        self.input_source.clear()
        self.input_source.addItem("Select input...", None)
        for definition in self._signal_catalog.inputs:
            self.input_source.addItem(definition.label, definition.signal_id)
        if previous_input is not None:
            index = self.input_source.findData(previous_input)
            self.input_source.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.input_source.setCurrentIndex(0)
        self.input_source.blockSignals(False)

        self.output_signal_list.blockSignals(True)
        self.output_signal_list.clear()
        for definition in self._signal_catalog.outputs:
            item = QListWidgetItem(definition.label)
            item.setData(Qt.UserRole, definition.signal_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if definition.signal_id in previous_outputs else Qt.Unchecked)
            self.output_signal_list.addItem(item)
        self.output_signal_list.blockSignals(False)

        if self.input_source.findData(previous_input) < 0:
            self._scene_input_component_ids = ()
            self._scene_input_component_names = ()
            self._scene_input_signal_ids = ()
        self._update_scene_input_status()
        self._update_scene_output_status()
        self._refresh_input_profiles()
        self._update_simulation_actions()

    def apply_scene_signal_selection(
        self,
        *,
        input_component_ids: list[str] | tuple[str, ...],
        input_component_names: list[str] | tuple[str, ...],
        input_signal_ids: list[str] | tuple[str, ...],
        output_component_ids: list[str] | tuple[str, ...],
        output_component_names: list[str] | tuple[str, ...],
        output_signal_ids: list[str] | tuple[str, ...],
    ) -> None:
        normalized_input_signal_ids = tuple(input_signal_ids)
        self._scene_input_component_ids = tuple(input_component_ids)
        self._scene_input_component_names = tuple(input_component_names)
        self._scene_input_signal_ids = normalized_input_signal_ids
        self._scene_output_component_ids = tuple(output_component_ids)
        self._scene_output_component_names = tuple(output_component_names)
        self.input_source.blockSignals(True)
        primary_input = next(
            (
                signal_id
                for signal_id in normalized_input_signal_ids
                if input_definition(self._signal_catalog.template_id, signal_id) is not None
                and input_definition(self._signal_catalog.template_id, signal_id).channel_id is not None
            ),
            normalized_input_signal_ids[0] if normalized_input_signal_ids else None,
        )
        index = self.input_source.findData(primary_input)
        self.input_source.setCurrentIndex(index if index >= 0 else 0)
        self.input_source.blockSignals(False)

        selected_outputs = set(output_signal_ids)
        self.output_signal_list.blockSignals(True)
        for row in range(self.output_signal_list.count()):
            item = self.output_signal_list.item(row)
            signal_id = str(item.data(Qt.UserRole))
            item.setCheckState(Qt.Checked if signal_id in selected_outputs else Qt.Unchecked)
        self.output_signal_list.blockSignals(False)

        self._update_scene_input_status()
        self._update_scene_output_status()
        self._refresh_input_profiles()
        self._emit_config()

    def selected_output_signals(self) -> list[str]:
        selected: list[str] = []
        for index in range(self.output_signal_list.count()):
            item = self.output_signal_list.item(index)
            if item.checkState() == Qt.Checked:
                selected.append(str(item.data(Qt.UserRole)))
        return selected

    def selected_input_signals(self) -> list[str]:
        return list(self._scene_input_signal_ids)

    def has_valid_signal_selection(self) -> bool:
        return (
            bool(self._scene_input_component_ids)
            and any(
                input_definition(self._signal_catalog.template_id, signal_id) is not None
                and input_definition(self._signal_catalog.template_id, signal_id).channel_id is not None
                for signal_id in self._scene_input_signal_ids
            )
            and bool(self.selected_output_signals())
        )

    def available_signal_labels(self) -> dict[str, list[str]]:
        return {
            "inputs": [self.input_source.itemText(index) for index in range(1, self.input_source.count())],
            "outputs": [self.output_signal_list.item(index).text() for index in range(self.output_signal_list.count())],
        }

    def _update_simulation_actions(self) -> None:
        valid = self.has_valid_signal_selection()
        self.start_button.setEnabled(valid)
        self.selection_hint.setText(
            "Simulation I/O selection is ready."
            if valid
            else "Mark at least one runtime-driving input component and one output component before starting simulation."
        )

    def _update_scene_input_status(self) -> None:
        if not self._scene_input_component_ids or not self._scene_input_signal_ids:
            self.scene_input_status.setText("No scene input selected.")
            return
        component_names = self._scene_input_component_names or self._scene_input_component_ids
        component_labels = ", ".join(f'"{component_name}"' for component_name in component_names)
        signal_labels = ", ".join(
            (
                input_definition(self._signal_catalog.template_id, signal_id).label
                if input_definition(self._signal_catalog.template_id, signal_id) is not None
                else signal_id
            )
            for signal_id in self._scene_input_signal_ids
        )
        self.scene_input_status.setText(f"Selected input components: {component_labels} | Signals: {signal_labels}")

    def _update_scene_output_status(self) -> None:
        if not self._scene_output_component_ids:
            self.scene_output_status.setText("No scene outputs selected.")
            return
        component_names = self._scene_output_component_names or self._scene_output_component_ids
        component_labels = ", ".join(f'"{component_name}"' for component_name in component_names)
        signal_labels = ", ".join(
            (
                output_definition(self._signal_catalog.template_id, signal_id).label
                if output_definition(self._signal_catalog.template_id, signal_id) is not None
                else signal_id
            )
            for signal_id in self.selected_output_signals()
        ) or "None"
        self.scene_output_status.setText(f"Selected output components: {component_labels} | Signals: {signal_labels}")

    def _double_spinbox(self, value: float, minimum: float, maximum: float, step: float, suffix: str = "", decimals: int = 2) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def _reset_pid_defaults(self) -> None:
        self.kp.setValue(850.0)
        self.ki.setValue(45.0)
        self.kd.setValue(180.0)

    def parameters_config(self) -> QuarterCarParameters:
        return QuarterCarParameters(
            body_mass=self.body_mass.value(),
            wheel_mass=self.wheel_mass.value(),
            suspension_spring=self.suspension_spring.value(),
            suspension_damper=self.suspension_damper.value(),
            tire_stiffness=self.tire_stiffness.value(),
        )

    def controller_config(self) -> ControllerConfig:
        return ControllerConfig(
            kp=self.kp.value(),
            ki=self.ki.value(),
            kd=self.kd.value(),
            enabled=self.enable_pid.isChecked(),
        )

    def road_config(self) -> RoadProfileConfig:
        return RoadProfileConfig(
            road_type=self.input_profile.currentData() if self.input_source.currentData() == "road" else "flat",
            amplitude=self.road_amplitude.value(),
            roughness=self.road_roughness.value(),
            cutoff_hz=self.road_smoothness.value(),
            seed=self.road_seed.value(),
            speed_mps=self.road_speed.value(),
        )

    def selection_config(self) -> SignalSelection:
        self._update_simulation_actions()
        return SignalSelection(
            input_signals=tuple(self.selected_input_signals()),
            input_component_ids=self._scene_input_component_ids,
            input_profile=self.input_profile.currentData() if self.input_source.currentData() is not None else None,
            output_signals=tuple(self.selected_output_signals()),
            output_component_ids=self._scene_output_component_ids,
            input_amplitude=self.input_amplitude.value(),
            input_frequency_hz=self.input_frequency.value(),
            input_start_time=self.input_start_time.value(),
        )

    def simulation_config(self) -> SimulationConfig:
        return SimulationConfig(
            duration=self.duration.value(),
            sample_time=self.sample_time.value(),
            runtime_backend=self.runtime_backend.currentData(),
        )

    def set_runtime_status(self, diagnostics: dict[str, object]) -> None:
        requested_mode = str(diagnostics.get("requested_backend_mode", self.runtime_backend.currentData()))
        requested_index = self.runtime_backend.findData(requested_mode)
        if requested_index >= 0 and requested_index != self.runtime_backend.currentIndex():
            self.runtime_backend.blockSignals(True)
            self.runtime_backend.setCurrentIndex(requested_index)
            self.runtime_backend.blockSignals(False)
        self.runtime_template_value.setText(str(diagnostics.get("template_label", "Unknown template")))
        readiness = diagnostics.get("rollout_readiness", {})
        readiness_text = (
            f"status={readiness.get('current_rollout_status', 'unknown')} | "
            f"runtime_ready={'yes' if readiness.get('runtime_ready') else 'no'} | "
            f"backend_selectable={'yes' if readiness.get('backend_selectable') else 'no'}"
        )
        self.runtime_readiness_value.setText(readiness_text)
        self.runtime_backend_value.setText(str(diagnostics["active_backend_label"]))
        self.runtime_symbolic_status.setText(str(diagnostics["symbolic_status"]))
        self.runtime_fallback_reason.setText(str(diagnostics["last_fallback_reason"] or "None"))
        summary = diagnostics.get("source_summary", {})
        self.runtime_source_summary.setText(
            f"Runtime: {summary.get('runtime_backend', 'Unknown')} | "
            f"Equations: {summary.get('equation_source', 'Unknown')} | "
            f"Analysis: {summary.get('analysis_source', 'Unknown')} | "
            f"Health: {summary.get('symbolic_health', 'Unknown')}"
        )
        events = diagnostics.get("recent_events", [])
        if events:
            event_lines = []
            for event in events[-3:]:
                event_name = str(event.get("event", "unknown"))
                detail = str(event.get("reason") or event.get("note") or event.get("error") or "")
                event_lines.append(f"{event_name}: {detail}".strip(": "))
            self.runtime_recent_events.setText("\n".join(event_lines))
        else:
            self.runtime_recent_events.setText("No recent runtime events.")
        self._apply_runtime_capabilities(diagnostics.get("backend_options", {}))
        self._update_simulation_actions()

    def _apply_runtime_capabilities(self, backend_options: dict[str, object]) -> None:
        for mode in ("numeric", "symbolic"):
            index = self.runtime_backend.findData(mode)
            if index < 0:
                continue
            item = self.runtime_backend.model().item(index)
            if item is None:
                continue
            option = backend_options.get(mode, {}) if isinstance(backend_options, dict) else {}
            item.setEnabled(bool(option.get("enabled", True)))

    def _emit_config(self) -> None:
        self._update_simulation_actions()
        self.config_changed.emit(
            {
                "parameters": self.parameters_config(),
                "controller": self.controller_config(),
                "road_profile": self.road_config(),
                "selection": self.selection_config(),
                "simulation": self.simulation_config(),
            }
        )
