from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm

from app.core.models.quarter_car_model import QuarterCarModel, QuarterCarParameters, QuarterCarState
from app.core.state.feature_flags import DEFAULT_FLAGS, FeatureFlags
from app.core.symbolic import DAEReducer, EquationBuilder, StateSpaceBuilder
from app.core.symbolic.linearization_warnings import (
    METADATA_KEY_LINEARIZED_MODE_B,
    detect_linearized_mode_b_wheels,
    emit_linearization_warning,
)

if TYPE_CHECKING:
    from app.core.graph.system_graph import SystemGraph


@dataclass(slots=True)
class RuntimeStepResult:
    state: QuarterCarState
    outputs: dict[str, float]


@dataclass(slots=True)
class BackendCapabilities:
    supports_live_runtime: bool = True
    supports_equations: bool = True
    supports_state_space: bool = True
    supports_transfer_function: bool = True
    supports_traceability: bool = True
    supports_fallback: bool = False


class SimulationRuntimeBackend(Protocol):
    mode_id: str
    display_name: str

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None: ...

    def set_state(self, state: QuarterCarState) -> None: ...

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult: ...

    def current_state(self) -> QuarterCarState: ...

    def capabilities(self) -> BackendCapabilities: ...


class UnavailableRuntimeBackend:
    mode_id = "unavailable"
    display_name = "Runtime not enabled"

    def __init__(self, template_label: str) -> None:
        self.template_label = template_label
        self.state = QuarterCarState()

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None:
        self.state = initial_state or QuarterCarState()

    def set_state(self, state: QuarterCarState) -> None:
        self.state = state

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult:
        raise RuntimeError(f"Live runtime is not enabled for template '{self.template_label}'.")

    def current_state(self) -> QuarterCarState:
        return self.state

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_live_runtime=False,
            supports_equations=True,
            supports_state_space=True,
            supports_transfer_function=True,
            supports_traceability=True,
            supports_fallback=False,
        )


class QuarterCarNumericRuntimeBackend:
    mode_id = "numeric"
    display_name = "Numeric (default)"

    def __init__(self, parameters: QuarterCarParameters) -> None:
        self.parameters = parameters
        self.model = QuarterCarModel(parameters)
        self.state = QuarterCarState()

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None:
        self.model = QuarterCarModel(self.parameters)
        self.state = initial_state or QuarterCarState()

    def set_state(self, state: QuarterCarState) -> None:
        self.state = state

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult:
        current_state = self.state.as_vector()
        result = solve_ivp(
            lambda t, y: self.model.derivatives(t, y, road_height=road_height, external_force=external_force),
            t_span=(0.0, dt),
            y0=current_state,
            t_eval=[dt],
            method="RK45",
        )
        self.state = QuarterCarState.from_vector(result.y[:, -1])
        return RuntimeStepResult(
            state=self.state,
            outputs=self.model.output_values(
                self.state,
                road_height=road_height,
                external_force=external_force,
            ),
        )

    def current_state(self) -> QuarterCarState:
        return self.state

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_live_runtime=True,
            supports_equations=False,
            supports_state_space=True,
            supports_transfer_function=True,
            supports_traceability=False,
            supports_fallback=False,
        )


class SingleMassNumericRuntimeBackend:
    mode_id = "numeric"
    display_name = "Numeric (default)"

    def __init__(self, parameters: QuarterCarParameters) -> None:
        self.parameters = parameters
        self.state = np.zeros((2,), dtype=float)

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None:
        initial = initial_state or QuarterCarState()
        self.state = np.array([initial.body_displacement, initial.body_velocity], dtype=float)

    def set_state(self, state: QuarterCarState) -> None:
        self.state = np.array([state.body_displacement, state.body_velocity], dtype=float)

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult:
        result = solve_ivp(
            lambda _t, y: self._derivatives(y, external_force=external_force),
            t_span=(0.0, dt),
            y0=self.state,
            t_eval=[dt],
            method="RK45",
        )
        self.state = np.asarray(result.y[:, -1], dtype=float)
        displacement = float(self.state[0])
        velocity = float(self.state[1])
        acceleration = float(self._derivatives(self.state, external_force=external_force)[1])
        quarter_state = QuarterCarState(
            body_displacement=displacement,
            body_velocity=velocity,
            wheel_displacement=0.0,
            wheel_velocity=0.0,
        )
        return RuntimeStepResult(
            state=quarter_state,
            outputs={
                "body_displacement": displacement,
                "wheel_displacement": 0.0,
                "suspension_deflection": displacement,
                "body_acceleration": acceleration,
                "tire_deflection": 0.0,
                "mass_displacement": displacement,
                "mass_velocity": velocity,
            },
        )

    def current_state(self) -> QuarterCarState:
        return QuarterCarState(
            body_displacement=float(self.state[0]),
            body_velocity=float(self.state[1]),
            wheel_displacement=0.0,
            wheel_velocity=0.0,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_live_runtime=True,
            supports_equations=False,
            supports_state_space=False,
            supports_transfer_function=False,
            supports_traceability=False,
            supports_fallback=False,
        )

    def _derivatives(self, state: np.ndarray, *, external_force: float) -> np.ndarray:
        displacement, velocity = state
        mass = max(self.parameters.body_mass, 1e-6)
        spring = self.parameters.suspension_spring
        damping = self.parameters.suspension_damper
        acceleration = (external_force - spring * displacement - damping * velocity) / mass
        return np.array([velocity, acceleration], dtype=float)


class TwoMassNumericRuntimeBackend:
    mode_id = "numeric"
    display_name = "Numeric (default)"

    def __init__(self, parameters: QuarterCarParameters) -> None:
        self.parameters = parameters
        self.state = np.zeros((4,), dtype=float)

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None:
        initial = initial_state or QuarterCarState()
        self.state = np.array(
            [
                initial.body_displacement,
                initial.body_velocity,
                initial.wheel_displacement,
                initial.wheel_velocity,
            ],
            dtype=float,
        )

    def set_state(self, state: QuarterCarState) -> None:
        self.reset(initial_state=state)

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult:
        result = solve_ivp(
            lambda _t, y: self._derivatives(y, external_force=external_force),
            t_span=(0.0, dt),
            y0=self.state,
            t_eval=[dt],
            method="RK45",
        )
        self.state = np.asarray(result.y[:, -1], dtype=float)
        x1, v1, x2, v2 = [float(value) for value in self.state]
        a1 = float(self._derivatives(self.state, external_force=external_force)[1])
        quarter_state = QuarterCarState(
            body_displacement=x1,
            body_velocity=v1,
            wheel_displacement=x2,
            wheel_velocity=v2,
        )
        return RuntimeStepResult(
            state=quarter_state,
            outputs={
                "body_displacement": x1,
                "wheel_displacement": x2,
                "suspension_deflection": x1 - x2,
                "body_acceleration": a1,
                "tire_deflection": 0.0,
                "mass_1_displacement": x1,
                "mass_2_displacement": x2,
                "relative_deflection": x1 - x2,
            },
        )

    def current_state(self) -> QuarterCarState:
        x1, v1, x2, v2 = [float(value) for value in self.state]
        return QuarterCarState(
            body_displacement=x1,
            body_velocity=v1,
            wheel_displacement=x2,
            wheel_velocity=v2,
        )

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_live_runtime=True,
            supports_equations=False,
            supports_state_space=False,
            supports_transfer_function=False,
            supports_traceability=False,
            supports_fallback=False,
        )

    def _derivatives(self, state: np.ndarray, *, external_force: float) -> np.ndarray:
        x1, v1, x2, v2 = state
        m1 = max(self.parameters.body_mass, 1e-6)
        m2 = max(self.parameters.wheel_mass, 1e-6)
        k_ground = self.parameters.tire_stiffness
        c_ground = self.parameters.suspension_damper * 0.6
        k_coupling = self.parameters.suspension_spring
        c_coupling = self.parameters.suspension_damper
        a1 = (
            external_force
            - k_ground * x1
            - c_ground * v1
            - k_coupling * (x1 - x2)
            - c_coupling * (v1 - v2)
        ) / m1
        a2 = (
            k_coupling * (x1 - x2)
            + c_coupling * (v1 - v2)
        ) / m2
        return np.array([v1, a1, v2, a2], dtype=float)


class SymbolicStateSpaceRuntimeBackend:
    mode_id = "symbolic"
    display_name = "Symbolic (experimental)"
    STATE_ORDER = [
        "x_body_mass",
        "v_body_mass",
        "x_wheel_mass",
        "v_wheel_mass",
    ]
    OUTPUT_ORDER = [
        "body_displacement",
        "wheel_displacement",
        "suspension_deflection",
        "body_acceleration",
        "tire_deflection",
        "suspension_force",
    ]

    def __init__(
        self,
        parameters: QuarterCarParameters,
        canvas_graph_provider: Callable[[], SystemGraph | None] | None = None,
        flags: FeatureFlags = DEFAULT_FLAGS,
    ) -> None:
        self.parameters = parameters
        self._canvas_graph_provider = canvas_graph_provider
        self._flags = flags
        self._build_runtime_model()
        self.state = QuarterCarState()

    def _build_runtime_model(self) -> None:
        from app.services.graph_resolver import resolve_graph
        graph, _ = resolve_graph(self._flags, self._canvas_graph_provider)
        graph.components["body_mass"].parameters["mass"] = self.parameters.body_mass
        graph.components["wheel_mass"].parameters["mass"] = self.parameters.wheel_mass
        graph.components["suspension_spring"].parameters["stiffness"] = self.parameters.suspension_spring
        graph.components["suspension_damper"].parameters["damping"] = self.parameters.suspension_damper
        # Faz 4j-1 -- tire_stiffness Spring removed from template;
        # parameters.tire_stiffness now drives wheel_mass.contact_stiffness.
        # The dae_reducer Wheel branch (4f-1) and the polymorphic
        # Wheel.contribute_stiffness (4f-1.5) accumulate this into K
        # exactly the way the deleted tire_stiffness Spring used to.
        graph.components["wheel_mass"].parameters["contact_stiffness"] = self.parameters.tire_stiffness
        # Faz 4h — Detect Wheel(s) that will be silently linearized in the
        # symbolic state-space (Mode B's max(0, ...) clamp is invisible to
        # the parameter-driven K/C accumulation). Warn here and stash the
        # trigger list on `self.metadata` so the simulation service / UI
        # panels can surface the situation. Note: no metadata dict existed
        # on the runtime-backend protocol before 4h — this attribute is
        # advisory only and consumers should `getattr(..., "metadata", {})`
        # when reading it across backend types.
        linearized_mode_b = detect_linearized_mode_b_wheels(graph)
        emit_linearization_warning(
            linearized_mode_b, backend_label="SymbolicStateSpaceRuntimeBackend"
        )
        self.metadata = {METADATA_KEY_LINEARIZED_MODE_B: linearized_mode_b}
        symbolic = EquationBuilder().build(graph)
        reduced = DAEReducer().reduce(graph, symbolic)
        state_space = StateSpaceBuilder().build(graph, reduced, symbolic)
        state_indices = [state_space.state_variables.index(state_id) for state_id in self.STATE_ORDER]
        self.a_matrix = np.asarray(state_space.a_matrix, dtype=float)[np.ix_(state_indices, state_indices)]
        self.b_matrix = np.asarray(state_space.b_matrix, dtype=float)[state_indices, :]
        self.output_map: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for output_index, output_name in enumerate(state_space.output_variables):
            c_row = np.asarray(state_space.c_matrix[output_index], dtype=float)[state_indices]
            d_row = np.asarray(state_space.d_matrix[output_index], dtype=float)
            self.output_map[output_name] = (
                c_row,
                d_row,
            )
        self.input_index = {
            input_name: index for index, input_name in enumerate(state_space.input_variables)
        }

    def reset(self, *, initial_state: QuarterCarState | None = None) -> None:
        self._build_runtime_model()
        self.state = initial_state or QuarterCarState()

    def set_state(self, state: QuarterCarState) -> None:
        self.state = state

    def step(self, dt: float, *, road_height: float, external_force: float) -> RuntimeStepResult:
        current_state = self.state.as_vector()
        input_vector = np.zeros((self.b_matrix.shape[1],), dtype=float)
        if "u_road_source" in self.input_index:
            input_vector[self.input_index["u_road_source"]] = road_height
        if "u_body_force" in self.input_index:
            input_vector[self.input_index["u_body_force"]] = external_force

        next_vector = self._discrete_step(current_state, input_vector, dt)
        self.state = QuarterCarState.from_vector(next_vector)

        outputs: dict[str, float] = {}
        for output_name in self.OUTPUT_ORDER:
            c_row, d_row = self.output_map[output_name]
            outputs[output_name] = float(c_row @ next_vector + d_row @ input_vector)

        return RuntimeStepResult(state=self.state, outputs=outputs)

    def current_state(self) -> QuarterCarState:
        return self.state

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            supports_live_runtime=True,
            supports_equations=True,
            supports_state_space=True,
            supports_transfer_function=True,
            supports_traceability=True,
            supports_fallback=True,
        )

    def _discrete_step(self, state_vector: np.ndarray, input_vector: np.ndarray, dt: float) -> np.ndarray:
        state_dim = self.a_matrix.shape[0]
        input_dim = self.b_matrix.shape[1]
        augmented = np.zeros((state_dim + input_dim, state_dim + input_dim), dtype=float)
        augmented[:state_dim, :state_dim] = self.a_matrix
        augmented[:state_dim, state_dim:] = self.b_matrix
        transition = expm(augmented * dt)
        ad = transition[:state_dim, :state_dim]
        bd = transition[:state_dim, state_dim:]
        return ad @ state_vector + bd @ input_vector
