from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMainWindow, QSizePolicy, QSplitter, QWidget, QVBoxLayout

from app.core.models.quarter_car_model import QuarterCarModel
from app.core.state.app_state import AppState
from app.services.equation_service import EquationService
from app.services.plotting_service import PlottingService
from app.services.signal_catalog import input_definition, output_definition, signal_catalog_for_template
from app.services.simulation_backend import QuarterCarNumericBackend, SymbolicStateSpaceBackend
from app.services.simulation_service import SimulationService
from app.ui.panels.analysis_panel import AnalysisPanel
from app.ui.panels.controller_panel import ControllerPanel
from app.ui.panels.equation_panel import EquationPanel
from app.ui.panels.model_panel import ModelPanel, default_saved_layouts_path


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Controller Editor")
        self.resize(1720, 980)

        self.app_state = AppState()
        self.model = QuarterCarModel(self.app_state.parameters)
        self.analysis_backend = QuarterCarNumericBackend(self.app_state.parameters)
        self.symbolic_backend = SymbolicStateSpaceBackend(self.app_state.parameters)
        self.simulation_service = SimulationService(self.app_state)
        self.plotting_service = PlottingService(self.analysis_backend)
        self.equation_service = EquationService()

        self.model_panel = ModelPanel(saved_layouts_path=default_saved_layouts_path())
        self.equation_panel = EquationPanel()
        self.analysis_panel = AnalysisPanel()
        self.controller_panel = ControllerPanel()
        self._has_simulation_run = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_simulation)

        self._build_layout()
        self._wire_events()
        self._sync_workspace_template(self.model_panel.canvas.workspace_template_hint())
        self._apply_config(
            {
                "parameters": self.controller_panel.parameters_config(),
                "controller": self.controller_panel.controller_config(),
                "road_profile": self.controller_panel.road_config(),
                "selection": self.controller_panel.selection_config(),
                "simulation": self.controller_panel.simulation_config(),
            }
        )
        self._refresh_canvas()

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)

        middle_column = QSplitter(Qt.Vertical)
        middle_column.addWidget(self.controller_panel)
        middle_column.addWidget(self.equation_panel)
        middle_column.setChildrenCollapsible(False)
        middle_column.setStretchFactor(0, 5)
        middle_column.setStretchFactor(1, 4)

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

    def _wire_events(self) -> None:
        self.controller_panel.config_changed.connect(self._apply_config)
        self.controller_panel.simulation_requested.connect(self.start_simulation)
        self.controller_panel.stop_requested.connect(self.stop_simulation)
        self.controller_panel.load_default_requested.connect(self._load_default_workflow)
        self.model_panel.canvas.workspace_template_changed.connect(self._sync_workspace_template)
        self.model_panel.canvas.io_roles_changed.connect(self._sync_scene_signal_selection)

    def _load_default_workflow(self) -> None:
        self.stop_simulation()
        self.model_panel.load_default_model()
        self.simulation_service.reset()
        self.plotting_service.reset_history()
        self._has_simulation_run = False
        self.analysis_panel.show_empty_state("Select inputs and outputs, then run the simulation.")
        self._refresh_canvas()

    def _sync_workspace_template(self, template_id: str) -> None:
        self.controller_panel.update_signal_catalog(template_id)
        if self.app_state.simulation.model_template != template_id:
            self.app_state.simulation.model_template = template_id
            self.simulation_service.app_state = self.app_state
            self.simulation_service.sync_config()
            self.controller_panel.set_runtime_status(self.simulation_service.runtime_diagnostics())
        self._sync_scene_signal_selection(self.model_panel.canvas.scene_signal_roles_snapshot())
        self._apply_config(
            {
                "parameters": self.controller_panel.parameters_config(),
                "controller": self.controller_panel.controller_config(),
                "road_profile": self.controller_panel.road_config(),
                "selection": self.controller_panel.selection_config(),
                "simulation": self.controller_panel.simulation_config(),
            }
        )

    def _sync_scene_signal_selection(self, payload: dict[str, object]) -> None:
        inputs = payload.get("inputs", []) if isinstance(payload, dict) else []
        outputs = payload.get("outputs", []) if isinstance(payload, dict) else []
        input_component_ids = [
            str(binding.get("component_id"))
            for binding in inputs
            if isinstance(binding, dict) and binding.get("component_id")
        ]
        input_component_names = [
            str(binding.get("component_name"))
            for binding in inputs
            if isinstance(binding, dict) and binding.get("component_name")
        ]
        input_signal_ids = [
            str(binding.get("signal_id"))
            for binding in inputs
            if isinstance(binding, dict) and binding.get("signal_id")
        ]
        output_component_ids = [
            str(binding.get("component_id"))
            for binding in outputs
            if isinstance(binding, dict) and binding.get("component_id")
        ]
        output_component_names = [
            str(binding.get("component_name"))
            for binding in outputs
            if isinstance(binding, dict) and binding.get("component_name")
        ]
        output_signal_ids = [
            str(binding.get("signal_id"))
            for binding in outputs
            if isinstance(binding, dict) and binding.get("signal_id")
        ]
        self.controller_panel.apply_scene_signal_selection(
            input_component_ids=input_component_ids,
            input_component_names=input_component_names,
            input_signal_ids=input_signal_ids,
            output_component_ids=output_component_ids,
            output_component_names=output_component_names,
            output_signal_ids=output_signal_ids,
        )

    def _apply_config(self, payload: dict) -> None:
        current_template = self.app_state.simulation.model_template
        self.app_state.parameters = payload["parameters"]
        self.app_state.controller = payload["controller"]
        self.app_state.road_profile = payload["road_profile"]
        self.app_state.selection = payload["selection"]
        self.app_state.simulation = payload["simulation"]
        self.app_state.simulation.model_template = current_template

        self.model = QuarterCarModel(self.app_state.parameters)
        self.analysis_backend = QuarterCarNumericBackend(self.app_state.parameters)
        self.symbolic_backend = SymbolicStateSpaceBackend(self.app_state.parameters)
        self.simulation_service.app_state = self.app_state
        self.simulation_service.road.reset(self.app_state.road_profile)
        self.simulation_service.sync_config()
        self.plotting_service.backend = self.analysis_backend
        self.plotting_service.configure_live_outputs(self.app_state.selection.output_signals, reset=True)
        self.timer.setInterval(int(self.app_state.simulation.sample_time * 1000))
        self.controller_panel.set_runtime_status(self.simulation_service.runtime_diagnostics())

        self._refresh_equations()
        if self._has_simulation_run and self._has_valid_simulation_selection():
            self._refresh_static_plots()
        else:
            self.analysis_panel.show_empty_state("Select inputs and outputs, then run the simulation.")
            self.controller_panel.status_widget.show_empty_state()
        self._refresh_canvas()

    def _refresh_equations(self) -> None:
        if not (self.app_state.selection.input_signals and self.app_state.selection.output_signals):
            self.equation_panel.show_empty_state()
            return
        try:
            summary = self.equation_service.build_summary(
                self.app_state,
                symbolic_backend=self.symbolic_backend,
                analysis_backend=self.analysis_backend,
            )
        except Exception:
            self.equation_panel.show_empty_state("Selected outputs are not yet available for equation/analysis export.")
            return
        self.equation_panel.update_summary(summary)

    def _refresh_static_plots(self) -> None:
        if not self._has_valid_simulation_selection():
            self.analysis_panel.show_empty_state("Select inputs and outputs, then run the simulation.")
            return
        input_channel = self.simulation_service.selected_input_channel()
        selected_outputs = list(self.app_state.selection.output_signals)
        output_specs = self._selected_output_specs()
        input_label = self._selected_input_label()
        duration = min(self.app_state.simulation.duration, 8.0)
        try:
            step_data = self.plotting_service.response_data(
                output_signals=selected_outputs,
                input_channel=input_channel,
                duration=duration,
            )
            bode_data = self.plotting_service.bode_data(output_signals=selected_outputs, input_channel=input_channel)
            pz_data = self.plotting_service.pole_zero_data(output_signals=selected_outputs, input_channel=input_channel)
            self.analysis_panel.update_step_response(step_data, selected_outputs=output_specs, input_label=input_label)
            self.analysis_panel.update_bode(bode_data, selected_outputs=output_specs, input_label=input_label)
            self.analysis_panel.update_pole_zero(pz_data, selected_outputs=output_specs, input_label=input_label)
        except Exception:
            self.analysis_panel.show_empty_state("Selected outputs are not yet available for static analysis.")
        self.analysis_panel.update_live_plot(self.plotting_service.live_output_data(), selected_outputs=output_specs)

    def _refresh_canvas(self) -> None:
        frame = self.simulation_service.visualization_frame()
        frame["template_id"] = self.app_state.simulation.model_template
        self.model_panel.canvas.update_visualization(frame)

    def start_simulation(self) -> None:
        if not self._has_valid_simulation_selection():
            self.analysis_panel.show_empty_state("Select inputs and outputs, then run the simulation.")
            self.controller_panel.status_widget.show_empty_state("Select outputs to inspect live values.")
            return
        self._has_simulation_run = True
        self.simulation_service.reset()
        self.plotting_service.configure_live_outputs(self.app_state.selection.output_signals, reset=True)
        self.plotting_service.reset_history()
        self.controller_panel.set_runtime_status(self.simulation_service.runtime_diagnostics())
        self._refresh_static_plots()
        self._refresh_canvas()
        self.timer.start()

    def stop_simulation(self) -> None:
        self.timer.stop()
        self.model_panel.canvas.reset_animation()

    def _advance_simulation(self) -> None:
        if not self._has_valid_simulation_selection():
            self.stop_simulation()
            self.analysis_panel.show_empty_state("Select inputs and outputs, then run the simulation.")
            return
        dt = self.app_state.simulation.sample_time
        snapshot = self.simulation_service.step(dt)
        frame = self.simulation_service.visualization_frame()
        live_data = self.plotting_service.append_live_sample(
            time_value=snapshot.time,
            outputs=snapshot.outputs,
            selected_outputs=self.app_state.selection.output_signals,
        )
        output_specs = self._selected_output_specs()
        self.analysis_panel.update_live_plot(live_data, selected_outputs=output_specs)
        self.controller_panel.status_widget.update_signal_values(
            [
                (label, self._format_output_value(signal_id, snapshot.outputs.get(signal_id, 0.0)))
                for signal_id, label, _color in output_specs
            ]
        )
        self.model_panel.canvas.update_visualization(
            {
                "template_id": self.app_state.simulation.model_template,
                "body_displacement": snapshot.outputs["body_displacement"],
                "wheel_displacement": snapshot.outputs["wheel_displacement"],
                "road_height": snapshot.road_height,
                "road_x": frame["road_x"],
                "road_y": frame["road_y"],
                "wheel_rotation": snapshot.wheel_rotation,
                "runtime_outputs": snapshot.outputs,
            }
        )
        self.controller_panel.set_runtime_status(self.simulation_service.runtime_diagnostics())
        if snapshot.time >= self.app_state.simulation.duration:
            self.stop_simulation()

    def _has_valid_simulation_selection(self) -> bool:
        runtime_input_available = any(
            input_definition(self.app_state.simulation.model_template, signal_id) is not None
            and input_definition(self.app_state.simulation.model_template, signal_id).channel_id is not None
            for signal_id in self.app_state.selection.input_signals
        )
        return bool(
            self.app_state.selection.input_component_ids
            and self.app_state.selection.input_signals
            and runtime_input_available
            and self.app_state.selection.output_signals
        )

    def _selected_output_specs(self) -> list[tuple[str, str, str]]:
        specs: list[tuple[str, str, str]] = []
        template_id = self.app_state.simulation.model_template
        for signal_id in self.app_state.selection.output_signals:
            definition = output_definition(template_id, signal_id)
            if definition is None:
                continue
            specs.append((signal_id, definition.label, definition.color or "#0b84f3"))
        return specs

    def _selected_input_label(self) -> str:
        catalog = signal_catalog_for_template(self.app_state.simulation.model_template)
        labels: list[str] = []
        for selected_input in self.app_state.selection.input_signals:
            for definition in catalog.inputs:
                if definition.signal_id == selected_input:
                    labels.append(definition.label)
                    break
        return ", ".join(labels) if labels else "Selected input"

    def _format_output_value(self, signal_id: str, value: float) -> str:
        definition = output_definition(self.app_state.simulation.model_template, signal_id)
        if definition is None:
            return f"{value:.4f}"
        suffix = f" {definition.unit}" if definition.unit else ""
        return f"{value:.4f}{suffix}"
