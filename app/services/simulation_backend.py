from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
from scipy import signal

from app.core.models.quarter_car_model import QuarterCarModel, QuarterCarParameters
from app.core.state.feature_flags import DEFAULT_FLAGS, FeatureFlags
from app.core.symbolic import DAEReducer, EquationBuilder, StateSpaceBuilder
from app.core.symbolic.reducer_parity_harness import ReducerParityHarness
from app.core.templates import build_quarter_car_template


@dataclass(slots=True)
class BackendStateSpace:
    a_matrix: np.ndarray
    b_matrix: np.ndarray
    c_matrix: np.ndarray
    d_matrix: np.ndarray
    state_variables: list[str]
    input_channel: str
    output_variables: list[str]
    state_trace: list[dict[str, object]] = field(default_factory=list)
    output_trace: list[dict[str, object]] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StepResponseResult:
    time: np.ndarray
    responses: dict[str, np.ndarray]


class SimulationBackend(Protocol):
    def get_state_space(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
    ) -> BackendStateSpace: ...

    def get_equations(self) -> dict[str, object]: ...

    def get_outputs(self) -> list[str]: ...

    def get_output_labels(self) -> dict[str, str]: ...

    def get_input_labels(self) -> dict[str, str]: ...

    def get_state_labels(self) -> dict[str, str]: ...

    def simulate_step_response(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
        duration: float = 5.0,
        sample_count: int = 400,
    ) -> StepResponseResult: ...


class QuarterCarBackendContract:
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
    OUTPUT_LABELS = {
        "body_displacement": "Body displacement",
        "wheel_displacement": "Wheel displacement",
        "suspension_deflection": "Suspension deflection",
        "body_acceleration": "Body acceleration",
        "tire_deflection": "Tire deflection",
        "suspension_force": "Suspension force",
    }
    INPUT_LABELS = {
        "road_displacement": "Road displacement r(t)",
        "body_force": "External body force F(t)",
    }
    STATE_LABELS = {
        "x_body_mass": "Body displacement x_b",
        "v_body_mass": "Body velocity x_b'",
        "x_wheel_mass": "Wheel displacement x_w",
        "v_wheel_mass": "Wheel velocity x_w'",
    }


class QuarterCarNumericBackend:
    def __init__(self, parameters: QuarterCarParameters | None = None) -> None:
        self.model = QuarterCarModel(parameters)

    def get_state_space(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
    ) -> BackendStateSpace:
        a_matrix, b_matrix = self.model.state_space_matrices()
        selected_outputs = output_variables or self.get_outputs()
        c_rows: list[np.ndarray] = []
        d_rows: list[np.ndarray] = []
        input_index = self.model.input_index(input_channel)
        output_trace: list[dict[str, object]] = []

        for output_name in selected_outputs:
            c_full, d_full = self.model.output_matrices(output_name)
            c_rows.append(c_full[0])
            d_rows.append(d_full[0, input_index : input_index + 1])
            output_trace.append(self._output_trace(output_name, c_full[0].tolist()))

        return BackendStateSpace(
            a_matrix=np.asarray(a_matrix, dtype=float),
            b_matrix=np.asarray(b_matrix[:, input_index : input_index + 1], dtype=float),
            c_matrix=np.asarray(c_rows, dtype=float),
            d_matrix=np.asarray(d_rows, dtype=float),
            state_variables=list(QuarterCarBackendContract.STATE_ORDER),
            input_channel=input_channel,
            output_variables=selected_outputs,
            state_trace=self._state_trace(),
            output_trace=output_trace,
            metadata={"backend_type": "numeric", "source_model": "QuarterCarModel"},
        )

    def get_equations(self) -> dict[str, object]:
        return {
            "equations": [
                "m_b x_b'' + c_s(x_b' - x_w') + k_s(x_b - x_w) = F(t)",
                "m_w x_w'' + c_s(x_w' - x_b') + k_s(x_w - x_b) + k_t(x_w - r) = -F(t)",
            ],
            "state_variables": list(QuarterCarBackendContract.STATE_ORDER),
            "output_variables": self.get_outputs(),
        }

    def get_outputs(self) -> list[str]:
        return list(QuarterCarBackendContract.OUTPUT_ORDER)

    def get_output_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.OUTPUT_LABELS)

    def get_input_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.INPUT_LABELS)

    def get_state_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.STATE_LABELS)

    def simulate_step_response(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
        duration: float = 5.0,
        sample_count: int = 400,
    ) -> StepResponseResult:
        state_space = self.get_state_space(input_channel=input_channel, output_variables=output_variables)
        time = np.linspace(0.0, duration, sample_count)
        responses: dict[str, np.ndarray] = {}
        for output_index, output_name in enumerate(state_space.output_variables):
            system = signal.StateSpace(
                state_space.a_matrix,
                state_space.b_matrix,
                state_space.c_matrix[output_index : output_index + 1],
                state_space.d_matrix[output_index : output_index + 1],
            )
            _, response = signal.step(system, T=time)
            responses[output_name] = np.asarray(response, dtype=float)
        return StepResponseResult(time=time, responses=responses)

    def _state_trace(self) -> list[dict[str, object]]:
        return [
            {
                "state_id": state_id,
                "state_column": index,
                "node_id": "body_mass" if "body" in state_id else "wheel_mass",
                "origin_layer": "backend_contract",
                "variable_kind": "state",
                "derivative_id": f"ddt_{state_id}" if state_id.startswith("x_") else None,
            }
            for index, state_id in enumerate(QuarterCarBackendContract.STATE_ORDER)
        ]

    def _output_trace(self, output_name: str, c_row: list[float]) -> dict[str, object]:
        reference_map = {
            "body_displacement": None,
            "wheel_displacement": None,
            "suspension_deflection": "wheel_mass",
            "body_acceleration": None,
            "tire_deflection": "road_source",
            "suspension_force": None,
        }
        target_map = {
            "body_displacement": "body_mass",
            "wheel_displacement": "wheel_mass",
            "suspension_deflection": "body_mass",
            "body_acceleration": "body_mass",
            "tire_deflection": "wheel_mass",
            "suspension_force": "suspension_spring",
        }
        quantity_map = {
            "body_displacement": "displacement",
            "wheel_displacement": "displacement",
            "suspension_deflection": "displacement",
            "body_acceleration": "acceleration",
            "tire_deflection": "displacement",
            "suspension_force": "force",
        }
        return {
            "output_id": output_name,
            "origin_layer": "backend_contract",
            "source_type": "relative_probe" if output_name in {"suspension_deflection", "tire_deflection"} else "probe",
            "target_component_id": target_map[output_name],
            "reference_component_id": reference_map[output_name],
            "quantity": quantity_map[output_name],
            "state_columns": [
                state_id
                for state_id, coefficient in zip(QuarterCarBackendContract.STATE_ORDER, c_row)
                if coefficient != 0.0
            ],
        }


class SymbolicStateSpaceBackend:
    def __init__(
        self,
        parameters: QuarterCarParameters | None = None,
        flags: FeatureFlags = DEFAULT_FLAGS,
    ) -> None:
        self.parameters = parameters or QuarterCarParameters()
        self._harness = ReducerParityHarness(flags=flags)

    def get_state_space(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
    ) -> BackendStateSpace:
        template = self._build_template()
        symbolic = EquationBuilder().build(template.graph)
        reduced, _parity_report = self._harness.reduce(
            template.graph, symbolic, graph_id=template.id
        )
        state_space = StateSpaceBuilder().build(template.graph, reduced, symbolic)
        input_index = self._input_index(reduced.input_variables, input_channel)
        selected_outputs = output_variables or self.get_outputs()
        output_indices = [state_space.output_variables.index(output_name) for output_name in selected_outputs]
        canonical_state_indices = [
            state_space.state_variables.index(state_id)
            for state_id in QuarterCarBackendContract.STATE_ORDER
        ]

        return BackendStateSpace(
            a_matrix=np.asarray(state_space.a_matrix, dtype=float)[np.ix_(canonical_state_indices, canonical_state_indices)],
            b_matrix=np.asarray([[row[input_index]] for row in state_space.b_matrix], dtype=float)[canonical_state_indices, :],
            c_matrix=np.asarray([state_space.c_matrix[index] for index in output_indices], dtype=float)[:, canonical_state_indices],
            d_matrix=np.asarray([[state_space.d_matrix[index][input_index]] for index in output_indices], dtype=float),
            state_variables=list(QuarterCarBackendContract.STATE_ORDER),
            input_channel=input_channel,
            output_variables=selected_outputs,
            state_trace=self._state_trace(),
            output_trace=self._output_trace(selected_outputs, state_space),
            metadata={
                "backend_type": "symbolic",
                "source_template": template.id,
                "sympy_equation_count": reduced.metadata.get("sympy_equation_count", 0),
            },
        )

    def get_equations(self) -> dict[str, object]:
        template = self._build_template()
        symbolic = EquationBuilder().build(template.graph)
        reduced, _parity_report = self._harness.reduce(
            template.graph, symbolic, graph_id=template.id
        )
        return {
            "equations": [record.display_text for record in symbolic.equation_records],
            "equation_records": symbolic.equation_records,
            "state_variables": list(symbolic.state_variables),
            "reduced_state_variables": list(reduced.state_variables),
            "state_trace": reduced.metadata.get("state_trace", []),
            "output_variables": self.get_outputs(),
        }

    def get_outputs(self) -> list[str]:
        return list(QuarterCarBackendContract.OUTPUT_ORDER)

    def get_output_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.OUTPUT_LABELS)

    def get_input_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.INPUT_LABELS)

    def get_state_labels(self) -> dict[str, str]:
        return dict(QuarterCarBackendContract.STATE_LABELS)

    def simulate_step_response(
        self,
        *,
        input_channel: str,
        output_variables: list[str] | None = None,
        duration: float = 5.0,
        sample_count: int = 400,
    ) -> StepResponseResult:
        state_space = self.get_state_space(input_channel=input_channel, output_variables=output_variables)
        time = np.linspace(0.0, duration, sample_count)
        responses: dict[str, np.ndarray] = {}
        for output_index, output_name in enumerate(state_space.output_variables):
            system = signal.StateSpace(
                state_space.a_matrix,
                state_space.b_matrix,
                state_space.c_matrix[output_index : output_index + 1],
                state_space.d_matrix[output_index : output_index + 1],
            )
            _, response = signal.step(system, T=time)
            responses[output_name] = np.asarray(response, dtype=float)
        return StepResponseResult(time=time, responses=responses)

    def _state_trace(self) -> list[dict[str, object]]:
        return [
            {
                "state_id": state_id,
                "state_column": index,
                "node_id": "body_mass" if "body" in state_id else "wheel_mass",
                "origin_layer": "backend_contract",
                "variable_kind": "state",
                "derivative_id": f"ddt_{state_id}" if state_id.startswith("x_") else None,
            }
            for index, state_id in enumerate(QuarterCarBackendContract.STATE_ORDER)
        ]

    def _output_trace(self, selected_outputs: list[str], state_space) -> list[dict[str, object]]:
        trace_by_output = {
            trace["output_id"]: trace for trace in state_space.metadata.get("output_trace", [])
        }
        normalized: list[dict[str, object]] = []
        for output_id in selected_outputs:
            trace = dict(trace_by_output.get(output_id, {}))
            trace["origin_layer"] = "backend_contract"
            state_columns = trace.get("state_columns", [])
            trace["state_columns"] = [
                state_id
                for state_id in QuarterCarBackendContract.STATE_ORDER
                if state_id in state_columns
            ]
            normalized.append(trace)
        return normalized

    def _build_template(self):
        template = build_quarter_car_template()
        template.graph.components["body_mass"].parameters["mass"] = self.parameters.body_mass
        template.graph.components["wheel_mass"].parameters["mass"] = self.parameters.wheel_mass
        template.graph.components["suspension_spring"].parameters["stiffness"] = self.parameters.suspension_spring
        template.graph.components["suspension_damper"].parameters["damping"] = self.parameters.suspension_damper
        template.graph.components["tire_stiffness"].parameters["stiffness"] = self.parameters.tire_stiffness
        return template

    def _input_index(self, input_variables: list[str], input_channel: str) -> int:
        channel_to_prefix = {
            "road_displacement": "u_road_source",
            "body_force": "u_body_force",
        }
        expected = channel_to_prefix.get(input_channel)
        if expected is None:
            raise KeyError(f"Unknown symbolic input channel: {input_channel}")
        if expected not in input_variables:
            raise KeyError(f"Input channel {input_channel} not available in symbolic backend")
        return input_variables.index(expected)
