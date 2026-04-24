from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np

from app.core.models.quarter_car_model import QuarterCarState
from app.core.state.app_state import AppState, RoadProfileConfig, SignalSelection
from app.services.controller_service import ControllerService
from app.services.signal_catalog import input_definition
from app.services.runtime_backend import (
    BackendCapabilities,
    QuarterCarNumericRuntimeBackend,
    SimulationRuntimeBackend,
    SingleMassNumericRuntimeBackend,
    SymbolicStateSpaceRuntimeBackend,
    TwoMassNumericRuntimeBackend,
    UnavailableRuntimeBackend,
)


@dataclass(slots=True)
class SimulationSnapshot:
    time: float
    road_height: float
    external_force: float
    state: QuarterCarState
    outputs: dict[str, float]
    travel_distance: float
    wheel_rotation: float
    runtime_backend_mode: str
    runtime_warning: str | None = None


@dataclass(slots=True)
class RuntimeEvent:
    event: str
    template_id: str
    active_backend_mode: str
    requested_backend_mode: str
    note: str | None = None
    reason: str | None = None
    error: str | None = None


@dataclass(slots=True)
class RuntimeSourceSummary:
    runtime_backend: str
    equation_source: str
    analysis_source: str
    symbolic_health: str
    fallback_status: str
    capability_summary: str


@dataclass(slots=True)
class RuntimeBackendOption:
    label: str
    enabled: bool
    experimental: bool
    reason: str


@dataclass(slots=True)
class RuntimeDiagnostics:
    template_id: str
    template_label: str
    active_backend_mode: str
    active_backend_label: str
    requested_backend_mode: str
    fallback_occurred: bool
    last_fallback_reason: str | None
    last_backend_error: str | None
    last_runtime_warning: str | None
    symbolic_runtime_healthy: bool
    symbolic_status: str
    equation_source: str
    analysis_source: str
    runtime_capabilities: dict[str, object]
    source_summary: RuntimeSourceSummary
    recent_events: list[RuntimeEvent]
    backend_options: dict[str, RuntimeBackendOption]
    recovery_available: bool


@dataclass(slots=True)
class TemplateRolloutReadiness:
    parity_ready: bool
    runtime_ready: bool
    diagnostics_ready: bool
    fallback_ready: bool
    backend_selectable: bool
    symbolic_equations_ready: bool
    smoke_test_ready: bool
    capability_declared: bool
    current_rollout_status: str


@dataclass(slots=True)
class TemplateRuntimeProfile:
    template_id: str
    label: str
    equation_source: str
    analysis_source: str
    supports_numeric_runtime: bool
    supports_symbolic_runtime: bool
    readiness: TemplateRolloutReadiness


class RuntimeEventLog:
    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []

    def append(self, event: RuntimeEvent) -> None:
        self._events.append(event)

    def recent(self, limit: int = 5) -> list[RuntimeEvent]:
        return list(self._events[-limit:])


class RuntimeLifecyclePolicy:
    """Shared rollout rules for backend switching, rebuild, fallback, and recovery."""

    @staticmethod
    def sync_reason(*, previous_signature: tuple[object, ...] | None, current_signature: tuple[object, ...], previous_mode: str, requested_mode: str) -> str | None:
        if previous_signature is None:
            return "initial_sync"
        if requested_mode != previous_mode:
            return "backend_switch"
        if current_signature != previous_signature:
            return "config_change"
        return None

    @staticmethod
    def symbolic_status(*, symbolic_runtime_healthy: bool, last_fallback_reason: str | None, requested_backend_mode: str) -> str:
        if symbolic_runtime_healthy:
            return "OK"
        if last_fallback_reason:
            return "Fallback"
        if requested_backend_mode == "symbolic":
            return "Warning"
        return "Idle"


TEMPLATE_RUNTIME_PROFILES: dict[str, TemplateRuntimeProfile] = {
    "quarter_car": TemplateRuntimeProfile(
        template_id="quarter_car",
        label="Quarter-Car Suspension",
        equation_source="Symbolic backend",
        analysis_source="Backend-neutral static analysis",
        supports_numeric_runtime=True,
        supports_symbolic_runtime=True,
        readiness=TemplateRolloutReadiness(
            parity_ready=True,
            runtime_ready=True,
            diagnostics_ready=True,
            fallback_ready=True,
            backend_selectable=True,
            symbolic_equations_ready=True,
            smoke_test_ready=True,
            capability_declared=True,
            current_rollout_status="experimental_runtime_enabled",
        ),
    ),
    "single_mass": TemplateRuntimeProfile(
        template_id="single_mass",
        label="Single Mass-Spring-Damper",
        equation_source="Symbolic backend",
        analysis_source="Backend-neutral static analysis",
        supports_numeric_runtime=True,
        supports_symbolic_runtime=False,
        readiness=TemplateRolloutReadiness(
            parity_ready=True,
            runtime_ready=True,
            diagnostics_ready=True,
            fallback_ready=False,
            backend_selectable=True,
            symbolic_equations_ready=True,
            smoke_test_ready=True,
            capability_declared=True,
            current_rollout_status="numeric_runtime_enabled",
        ),
    ),
    "two_mass": TemplateRuntimeProfile(
        template_id="two_mass",
        label="Two-Mass System",
        equation_source="Symbolic backend",
        analysis_source="Backend-neutral static analysis",
        supports_numeric_runtime=True,
        supports_symbolic_runtime=False,
        readiness=TemplateRolloutReadiness(
            parity_ready=True,
            runtime_ready=True,
            diagnostics_ready=True,
            fallback_ready=False,
            backend_selectable=True,
            symbolic_equations_ready=True,
            smoke_test_ready=True,
            capability_declared=True,
            current_rollout_status="numeric_runtime_enabled",
        ),
    ),
    "blank": TemplateRuntimeProfile(
        template_id="blank",
        label="Blank Workspace",
        equation_source="No active model",
        analysis_source="No active model",
        supports_numeric_runtime=False,
        supports_symbolic_runtime=False,
        readiness=TemplateRolloutReadiness(
            parity_ready=True,
            runtime_ready=False,
            diagnostics_ready=True,
            fallback_ready=False,
            backend_selectable=False,
            symbolic_equations_ready=False,
            smoke_test_ready=False,
            capability_declared=True,
            current_rollout_status="no_active_workspace_model",
        ),
    ),
}


class RoadProfileGenerator:
    def __init__(self, config: RoadProfileConfig) -> None:
        self.reset(config)

    def reset(self, config: RoadProfileConfig) -> None:
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.track_step = 0.025
        self.track_length = 240.0
        self.distance = 0.0
        self.profile = self._build_random_profile()

    def _build_random_profile(self) -> np.ndarray:
        sample_count = int(self.track_length / self.track_step) + 8
        white_noise = self.rng.normal(0.0, 1.0, sample_count)
        alpha = np.exp(-2.0 * np.pi * self.config.cutoff_hz * self.track_step / max(self.config.speed_mps, 0.2))
        filtered = np.empty_like(white_noise)
        filtered[0] = white_noise[0]
        for index in range(1, sample_count):
            filtered[index] = alpha * filtered[index - 1] + (1.0 - alpha) * white_noise[index]
        filtered /= max(np.std(filtered), 1e-6)
        return self.config.amplitude * (1.0 + self.config.roughness) * filtered

    def advance(self, dt: float) -> float:
        self.distance += self.config.speed_mps * dt
        return self.sample_at(self.distance)

    def sample_at(self, distance: float) -> float:
        wrapped_distance = distance % self.track_length
        left_index = int(wrapped_distance / self.track_step)
        fraction = (wrapped_distance / self.track_step) - left_index
        right_index = (left_index + 1) % len(self.profile)
        value = (1.0 - fraction) * self.profile[left_index] + fraction * self.profile[right_index]
        return float(value)

    def sine_value(self, distance: float, amplitude: float, frequency_hz: float) -> float:
        return amplitude * math.sin(2.0 * math.pi * frequency_hz * distance / max(self.config.speed_mps, 0.2))

    def step_bump_value(self, distance: float, amplitude: float, start_distance: float) -> float:
        return amplitude if distance >= start_distance else 0.0

    def sample_window(self, *, road_mode: str, amplitude: float, frequency_hz: float, start_time: float, span: float, sample_count: int) -> tuple[np.ndarray, np.ndarray]:
        x_values = np.linspace(-span / 2.0, span / 2.0, sample_count)
        heights = np.array(
            [self.value_for_mode(road_mode, self.distance + x, amplitude, frequency_hz, start_time) for x in x_values],
            dtype=float,
        )
        return x_values, heights

    def value_for_mode(self, road_mode: str, distance: float, amplitude: float, frequency_hz: float, start_time: float) -> float:
        if road_mode == "random":
            return self.sample_at(distance)
        if road_mode == "sine":
            return self.sine_value(distance, amplitude, frequency_hz)
        if road_mode == "step":
            start_distance = start_time * self.config.speed_mps
            return self.step_bump_value(distance, amplitude, start_distance)
        return 0.0


class SimulationService:
    def __init__(self, app_state: AppState) -> None:
        self.app_state = app_state
        self.controller = ControllerService()
        self.road = RoadProfileGenerator(app_state.road_profile)
        self.time = 0.0
        self.wheel_radius = 0.32
        self.runtime_backend: SimulationRuntimeBackend = QuarterCarNumericRuntimeBackend(app_state.parameters)
        self.active_runtime_backend_mode = "numeric"
        self.runtime_warning: str | None = None
        self.last_backend_error: str | None = None
        self.last_fallback_reason: str | None = None
        self.symbolic_runtime_healthy = False
        self.runtime_event_log = RuntimeEventLog()
        self._last_config_signature: tuple[object, ...] | None = None
        self._last_requested_backend_mode = app_state.simulation.runtime_backend
        self.sync_config()

    def sync_config(self) -> None:
        signature = self._config_signature()
        requested_mode = self.app_state.simulation.runtime_backend
        reason = RuntimeLifecyclePolicy.sync_reason(
            previous_signature=self._last_config_signature,
            current_signature=signature,
            previous_mode=self._last_requested_backend_mode,
            requested_mode=requested_mode,
        )
        if reason is not None:
            self._configure_runtime_backend(reason=reason, preserve_state=True)
        self._last_config_signature = signature
        self._last_requested_backend_mode = requested_mode

    def reset(self) -> None:
        self.app_state.state = QuarterCarState()
        self.controller.reset()
        self.road.reset(self.app_state.road_profile)
        self.time = 0.0
        self._configure_runtime_backend(reason="reset", preserve_state=False)
        self.runtime_backend.reset(initial_state=self.app_state.state)
        self._record_runtime_event("reset_runtime", note="Runtime backend reset with current configuration.")
        self._last_config_signature = self._config_signature()
        self._last_requested_backend_mode = self.app_state.simulation.runtime_backend

    def step(self, dt: float) -> SimulationSnapshot:
        road_height, user_force = self._selected_excitation(dt)
        pid_force = self.controller.compute_force(
            self.app_state.controller,
            body_displacement=self.app_state.state.body_displacement,
            body_velocity=self.app_state.state.body_velocity,
            dt=dt,
        )
        external_force = user_force + pid_force

        try:
            runtime_result = self.runtime_backend.step(
                dt,
                road_height=road_height,
                external_force=external_force,
            )
        except Exception as exc:
            if self.active_runtime_backend_mode == "symbolic":
                self.last_backend_error = str(exc)
                self.last_fallback_reason = f"Symbolic runtime failed during step: {exc}"
                self.runtime_warning = f"Symbolic runtime failed, fell back to numeric: {exc}"
                self._record_runtime_event("symbolic_runtime_error", error=str(exc))
                fallback = QuarterCarNumericRuntimeBackend(self.app_state.parameters)
                fallback.reset(initial_state=self.app_state.state)
                self.runtime_backend = fallback
                self.active_runtime_backend_mode = "numeric"
                self.symbolic_runtime_healthy = False
                self._record_runtime_event(
                    "fallback_to_numeric",
                    reason=self.last_fallback_reason,
                )
                runtime_result = self.runtime_backend.step(
                    dt,
                    road_height=road_height,
                    external_force=external_force,
                )
            else:
                raise

        self.app_state.state = runtime_result.state
        self.time += dt
        return SimulationSnapshot(
            time=self.time,
            road_height=road_height,
            external_force=external_force,
            state=runtime_result.state,
            outputs=runtime_result.outputs,
            travel_distance=self.road.distance,
            wheel_rotation=self.road.distance / self.wheel_radius,
            runtime_backend_mode=self.active_runtime_backend_mode,
            runtime_warning=self.runtime_warning,
        )

    def _selected_excitation(self, dt: float) -> tuple[float, float]:
        selection = self.app_state.selection
        road_height = 0.0
        external_force = 0.0
        template_id = self.app_state.simulation.model_template
        active_inputs = set(selection.input_signals)

        if template_id != "quarter_car":
            self.road.distance += self.app_state.road_profile.speed_mps * dt
            if "body_force" in active_inputs:
                external_force = self._body_force_value(selection)
            return road_height, external_force

        if "road" in active_inputs:
            self.road.distance += self.app_state.road_profile.speed_mps * dt
            road_height = self.road.value_for_mode(
                selection.input_profile,
                self.road.distance,
                selection.input_amplitude,
                selection.input_frequency_hz,
                selection.input_start_time,
            )
        else:
            self.road.distance += self.app_state.road_profile.speed_mps * dt
        if "body_force" in active_inputs:
            external_force = self._body_force_value(selection)
        return road_height, external_force

    def _body_force_value(self, selection: SignalSelection) -> float:
        if selection.input_profile == "step":
            return selection.input_amplitude * 1000.0 if self.time >= selection.input_start_time else 0.0
        if selection.input_profile == "sine":
            return selection.input_amplitude * 1000.0 * math.sin(2.0 * math.pi * selection.input_frequency_hz * self.time)
        return selection.input_amplitude * 1000.0

    def selected_input_channel(self) -> str:
        for selected_input in self.app_state.selection.input_signals:
            definition = input_definition(self.app_state.simulation.model_template, selected_input)
            if definition is not None and definition.channel_id is not None:
                return definition.channel_id
        return "body_force"

    def visualization_frame(self, *, span: float = 9.0, sample_count: int = 220) -> dict[str, object]:
        road_mode = self.app_state.selection.input_profile if "road" in self.app_state.selection.input_signals else "flat"
        road_x, road_y = self.road.sample_window(
            road_mode=road_mode,
            amplitude=self.app_state.selection.input_amplitude,
            frequency_hz=self.app_state.selection.input_frequency_hz,
            start_time=self.app_state.selection.input_start_time,
            span=span,
            sample_count=sample_count,
        )
        current_road_height = road_y[sample_count // 2] if sample_count else 0.0
        return {
            "body_displacement": self.app_state.state.body_displacement,
            "wheel_displacement": self.app_state.state.wheel_displacement,
            "road_height": float(current_road_height),
            "road_x": road_x.tolist(),
            "road_y": road_y.tolist(),
            "wheel_rotation": self.road.distance / self.wheel_radius,
        }

    def runtime_status_text(self) -> str:
        diagnostics = self.runtime_diagnostics()
        return (
            f"Runtime Backend: {diagnostics['active_backend_label']} | "
            f"Symbolic Runtime Status: {diagnostics['symbolic_status']}"
            + (
                f" | Last Fallback Reason: {diagnostics['last_fallback_reason']}"
                if diagnostics["last_fallback_reason"]
                else ""
            )
        )

    def source_summary(self) -> dict[str, str]:
        diagnostics = self.runtime_diagnostics()
        summary = diagnostics["source_summary"]
        return {
            "runtime": summary["runtime_backend"],
            "equations": summary["equation_source"],
            "analysis": summary["analysis_source"],
            "backend_health": summary["symbolic_health"],
            "fallback": summary["fallback_status"],
        }

    def runtime_diagnostics(self) -> dict[str, object]:
        profile = self._template_runtime_profile()
        active_label = (
            "Symbolic (experimental)"
            if self.active_runtime_backend_mode == "symbolic"
            else "Numeric (default)" if self.active_runtime_backend_mode == "numeric" else "Runtime not enabled"
        )
        symbolic_status = RuntimeLifecyclePolicy.symbolic_status(
            symbolic_runtime_healthy=self.symbolic_runtime_healthy,
            last_fallback_reason=self.last_fallback_reason,
            requested_backend_mode=self.app_state.simulation.runtime_backend,
        )
        capability_summary = self._capability_summary()
        source_summary = RuntimeSourceSummary(
            runtime_backend=active_label,
            equation_source=profile.equation_source,
            analysis_source=profile.analysis_source,
            symbolic_health=symbolic_status,
            fallback_status=self.last_fallback_reason or "None",
            capability_summary=capability_summary,
        )
        diagnostics = RuntimeDiagnostics(
            template_id=profile.template_id,
            template_label=profile.label,
            active_backend_mode=self.active_runtime_backend_mode,
            active_backend_label=active_label,
            requested_backend_mode=self.app_state.simulation.runtime_backend,
            fallback_occurred=self.last_fallback_reason is not None,
            last_fallback_reason=self.last_fallback_reason,
            last_backend_error=self.last_backend_error,
            last_runtime_warning=self.runtime_warning,
            symbolic_runtime_healthy=self.symbolic_runtime_healthy,
            symbolic_status=symbolic_status,
            equation_source=profile.equation_source,
            analysis_source=profile.analysis_source,
            runtime_capabilities=asdict(self.runtime_backend.capabilities()),
            source_summary=source_summary,
            recent_events=self.runtime_event_log.recent(),
            backend_options=self._backend_option_summary(),
            recovery_available=self.last_fallback_reason is not None,
        )
        payload = asdict(diagnostics)
        payload["recent_events"] = [asdict(event) for event in diagnostics.recent_events]
        payload["backend_options"] = {name: asdict(option) for name, option in diagnostics.backend_options.items()}
        payload["rollout_readiness"] = asdict(profile.readiness)
        return payload

    def _configure_runtime_backend(self, *, reason: str, preserve_state: bool = True) -> None:
        profile = self._template_runtime_profile()
        requested_mode = self.app_state.simulation.runtime_backend
        preserved_state = self.app_state.state if preserve_state else QuarterCarState()
        self.runtime_warning = None
        self.last_backend_error = None
        self.last_fallback_reason = None
        self.symbolic_runtime_healthy = False
        if not profile.supports_numeric_runtime and not profile.supports_symbolic_runtime:
            self.runtime_backend = UnavailableRuntimeBackend(profile.label)
            self.active_runtime_backend_mode = "unavailable"
            self.runtime_backend.reset(initial_state=preserved_state)
            self.runtime_warning = f"Live runtime is not enabled for template '{profile.label}' yet."
            self._record_runtime_event("runtime_unavailable", note=f"Runtime configured via {reason}.")
            return
        if requested_mode == "symbolic" and profile.supports_symbolic_runtime:
            try:
                backend: SimulationRuntimeBackend = SymbolicStateSpaceRuntimeBackend(self.app_state.parameters)
                self.runtime_backend = backend
                self.active_runtime_backend_mode = "symbolic"
                self.symbolic_runtime_healthy = True
                self.runtime_backend.reset(initial_state=preserved_state)
                self._record_runtime_event("switched_to_symbolic", note=f"Runtime configured via {reason}.")
                return
            except Exception as exc:
                self.last_backend_error = str(exc)
                self.last_fallback_reason = f"Symbolic runtime unavailable during initialization: {exc}"
                self.runtime_warning = f"Symbolic runtime unavailable, using numeric instead: {exc}"
                self._record_runtime_event("symbolic_runtime_error", error=str(exc))
                self._record_runtime_event(
                    "fallback_to_numeric",
                    reason=self.last_fallback_reason,
                )
        elif requested_mode == "symbolic":
            self.last_fallback_reason = f"Symbolic runtime is not enabled for template '{profile.label}'."
            self.runtime_warning = f"Symbolic runtime is not enabled for {profile.label}; using numeric instead."
            self._record_runtime_event(
                "fallback_to_numeric",
                reason=self.last_fallback_reason,
            )
        self.runtime_backend = self._numeric_runtime_backend_for_template()
        self.active_runtime_backend_mode = "numeric"
        self.runtime_backend.reset(initial_state=preserved_state)
        self._record_runtime_event("switched_to_numeric", note=f"Runtime configured via {reason}.")

    def _record_runtime_event(self, event_type: str, **payload: object) -> None:
        self.runtime_event_log.append(
            RuntimeEvent(
                event=event_type,
                template_id=self.app_state.simulation.model_template,
                active_backend_mode=self.active_runtime_backend_mode,
                requested_backend_mode=self.app_state.simulation.runtime_backend,
                note=str(payload.get("note")) if payload.get("note") is not None else None,
                reason=str(payload.get("reason")) if payload.get("reason") is not None else None,
                error=str(payload.get("error")) if payload.get("error") is not None else None,
            )
        )

    def _config_signature(self) -> tuple[object, ...]:
        parameters = self.app_state.parameters
        selection = self.app_state.selection
        road = self.app_state.road_profile
        simulation = self.app_state.simulation
        return (
            parameters.body_mass,
            parameters.wheel_mass,
            parameters.suspension_spring,
            parameters.suspension_damper,
            parameters.tire_stiffness,
            selection.input_source,
            selection.input_profile,
            selection.output_signals,
            selection.input_amplitude,
            selection.input_frequency_hz,
            selection.input_start_time,
            road.road_type,
            road.amplitude,
            road.roughness,
            road.cutoff_hz,
            road.seed,
            road.speed_mps,
            simulation.sample_time,
            simulation.duration,
            simulation.runtime_backend,
            simulation.model_template,
        )

    def _backend_option_summary(self) -> dict[str, RuntimeBackendOption]:
        profile = self._template_runtime_profile()
        numeric_capabilities = self._numeric_runtime_backend_for_template().capabilities() if profile.supports_numeric_runtime else BackendCapabilities(supports_live_runtime=False)
        symbolic_enabled = profile.supports_symbolic_runtime
        symbolic_reason = f"Available for {profile.label} runtime stepping." if profile.supports_symbolic_runtime else f"Live symbolic runtime is not enabled for {profile.label} yet."
        if profile.supports_symbolic_runtime:
            try:
                symbolic_capabilities = SymbolicStateSpaceRuntimeBackend(self.app_state.parameters).capabilities()
            except Exception as exc:
                symbolic_enabled = False
                symbolic_capabilities = self.runtime_backend.capabilities() if self.active_runtime_backend_mode == "symbolic" else BackendCapabilities()
                symbolic_reason = f"Unavailable for current configuration: {exc}"
        else:
            symbolic_capabilities = BackendCapabilities(supports_live_runtime=False)
        return {
            "numeric": RuntimeBackendOption(
                label="Numeric (default)",
                enabled=profile.supports_numeric_runtime and bool(numeric_capabilities.supports_live_runtime),
                experimental=False,
                reason="Stable reference runtime." if profile.supports_numeric_runtime else f"Live numeric runtime is not enabled for {profile.label} yet.",
            ),
            "symbolic": RuntimeBackendOption(
                label="Symbolic (experimental)",
                enabled=symbolic_enabled and bool(symbolic_capabilities.supports_live_runtime),
                experimental=True,
                reason=symbolic_reason,
            ),
        }

    def _capability_summary(self) -> str:
        capabilities = self.runtime_backend.capabilities()
        labels = []
        if capabilities.supports_live_runtime:
            labels.append("live")
        if capabilities.supports_state_space:
            labels.append("state-space")
        if capabilities.supports_transfer_function:
            labels.append("transfer-function")
        if capabilities.supports_traceability:
            labels.append("traceable")
        if capabilities.supports_fallback:
            labels.append("fallback-aware")
        return ", ".join(labels) if labels else "none"

    def _template_runtime_profile(self) -> TemplateRuntimeProfile:
        return TEMPLATE_RUNTIME_PROFILES.get(
            self.app_state.simulation.model_template,
            TEMPLATE_RUNTIME_PROFILES["quarter_car"],
        )

    def _numeric_runtime_backend_for_template(self) -> SimulationRuntimeBackend:
        template_id = self.app_state.simulation.model_template
        if template_id == "single_mass":
            return SingleMassNumericRuntimeBackend(self.app_state.parameters)
        if template_id == "two_mass":
            return TwoMassNumericRuntimeBackend(self.app_state.parameters)
        return QuarterCarNumericRuntimeBackend(self.app_state.parameters)
