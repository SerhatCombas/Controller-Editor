from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import signal

from app.services.simulation_backend import (
    BackendStateSpace,
    QuarterCarNumericBackend,
    SimulationBackend,
    StepResponseResult,
    SymbolicStateSpaceBackend,
)


@dataclass(slots=True)
class MatrixDiff:
    max_abs_error: float
    shape_left: tuple[int, ...]
    shape_right: tuple[int, ...]


@dataclass(slots=True)
class StepResponseDiff:
    output_name: str
    peak_abs_error: float
    final_value_error: float
    rms_error: float


@dataclass(slots=True)
class ParityReport:
    input_channel: str
    common_outputs: list[str]
    numeric_only_outputs: list[str]
    symbolic_only_outputs: list[str]
    output_order_matches: bool
    state_order_matches: bool
    input_labels_match: bool
    output_labels_match: bool
    state_trace_matches: bool
    output_trace_matches: bool
    matrix_diffs: dict[str, MatrixDiff] = field(default_factory=dict)
    transfer_function_diffs: dict[str, MatrixDiff] = field(default_factory=dict)
    pole_zero_diffs: dict[str, MatrixDiff] = field(default_factory=dict)
    eigenvalue_diff: MatrixDiff | None = None
    step_response_diffs: list[StepResponseDiff] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class QuarterCarParityHarness:
    def __init__(
        self,
        numeric_backend: SimulationBackend | None = None,
        symbolic_backend: SimulationBackend | None = None,
    ) -> None:
        self.numeric_backend = numeric_backend or QuarterCarNumericBackend()
        self.symbolic_backend = symbolic_backend or SymbolicStateSpaceBackend()

    def compare(
        self,
        *,
        input_channel: str = "road_displacement",
        output_variables: list[str] | None = None,
        duration: float = 5.0,
        sample_count: int = 400,
    ) -> ParityReport:
        numeric_outputs = self.numeric_backend.get_outputs()
        symbolic_outputs = self.symbolic_backend.get_outputs()
        requested_outputs = output_variables or [
            output_name for output_name in numeric_outputs if output_name in symbolic_outputs
        ]
        common_outputs = [
            output_name
            for output_name in requested_outputs
            if output_name in numeric_outputs and output_name in symbolic_outputs
        ]

        numeric_state_space = self.numeric_backend.get_state_space(
            input_channel=input_channel,
            output_variables=common_outputs,
        )
        symbolic_state_space = self.symbolic_backend.get_state_space(
            input_channel=input_channel,
            output_variables=common_outputs,
        )
        aligned_symbolic = self._align_symbolic_state_space(
            symbolic_state_space=symbolic_state_space,
            reference_state_space=numeric_state_space,
        )

        numeric_step = self.numeric_backend.simulate_step_response(
            input_channel=input_channel,
            output_variables=common_outputs,
            duration=duration,
            sample_count=sample_count,
        )
        symbolic_step = self.symbolic_backend.simulate_step_response(
            input_channel=input_channel,
            output_variables=common_outputs,
            duration=duration,
            sample_count=sample_count,
        )

        numeric_input_labels = self.numeric_backend.get_input_labels()
        symbolic_input_labels = self.symbolic_backend.get_input_labels()
        numeric_output_labels = self.numeric_backend.get_output_labels()
        symbolic_output_labels = self.symbolic_backend.get_output_labels()
        transfer_function_diffs = self._transfer_function_diffs(
            numeric_state_space=numeric_state_space,
            symbolic_state_space=aligned_symbolic,
            common_outputs=common_outputs,
        )
        pole_zero_diffs = self._pole_zero_diffs(
            numeric_state_space=numeric_state_space,
            symbolic_state_space=aligned_symbolic,
            common_outputs=common_outputs,
        )
        eigenvalue_diff = self._matrix_diff(
            np.sort_complex(np.linalg.eigvals(numeric_state_space.a_matrix)),
            np.sort_complex(np.linalg.eigvals(aligned_symbolic.a_matrix)),
        )
        state_trace_matches = numeric_state_space.state_trace == aligned_symbolic.state_trace
        output_trace_matches = numeric_state_space.output_trace == aligned_symbolic.output_trace
        issues = self._collect_issues(
            common_outputs=common_outputs,
            numeric_outputs=numeric_outputs,
            symbolic_outputs=symbolic_outputs,
            numeric_state_space=numeric_state_space,
            symbolic_state_space=aligned_symbolic,
            state_trace_matches=state_trace_matches,
            output_trace_matches=output_trace_matches,
            transfer_function_diffs=transfer_function_diffs,
            pole_zero_diffs=pole_zero_diffs,
            eigenvalue_diff=eigenvalue_diff,
        )

        return ParityReport(
            input_channel=input_channel,
            common_outputs=common_outputs,
            numeric_only_outputs=[
                output_name for output_name in numeric_outputs if output_name not in symbolic_outputs
            ],
            symbolic_only_outputs=[
                output_name for output_name in symbolic_outputs if output_name not in numeric_outputs
            ],
            output_order_matches=common_outputs == aligned_symbolic.output_variables,
            state_order_matches=numeric_state_space.state_variables == aligned_symbolic.state_variables,
            input_labels_match=numeric_input_labels == symbolic_input_labels,
            output_labels_match={
                output_id: numeric_output_labels.get(output_id) for output_id in common_outputs
            }
            == {
                output_id: symbolic_output_labels.get(output_id) for output_id in common_outputs
            },
            state_trace_matches=state_trace_matches,
            output_trace_matches=output_trace_matches,
            matrix_diffs={
                "A": self._matrix_diff(numeric_state_space.a_matrix, aligned_symbolic.a_matrix),
                "B": self._matrix_diff(numeric_state_space.b_matrix, aligned_symbolic.b_matrix),
                "C": self._matrix_diff(numeric_state_space.c_matrix, aligned_symbolic.c_matrix),
                "D": self._matrix_diff(numeric_state_space.d_matrix, aligned_symbolic.d_matrix),
            },
            transfer_function_diffs=transfer_function_diffs,
            pole_zero_diffs=pole_zero_diffs,
            eigenvalue_diff=eigenvalue_diff,
            step_response_diffs=self._step_response_diffs(
                numeric_step=numeric_step,
                symbolic_step=symbolic_step,
                common_outputs=common_outputs,
            ),
            issues=issues,
            metadata={
                "numeric_states": numeric_state_space.state_variables,
                "symbolic_states": symbolic_state_space.state_variables,
                "aligned_symbolic_states": aligned_symbolic.state_variables,
                "numeric_state_trace": numeric_state_space.state_trace,
                "symbolic_state_trace": aligned_symbolic.state_trace,
                "numeric_output_trace": numeric_state_space.output_trace,
                "symbolic_output_trace": aligned_symbolic.output_trace,
            },
        )

    def _align_symbolic_state_space(
        self,
        *,
        symbolic_state_space: BackendStateSpace,
        reference_state_space: BackendStateSpace,
    ) -> BackendStateSpace:
        symbolic_order = {
            state_id: index for index, state_id in enumerate(symbolic_state_space.state_variables)
        }
        permutation = [symbolic_order[state_id] for state_id in reference_state_space.state_variables]

        aligned_a = symbolic_state_space.a_matrix[np.ix_(permutation, permutation)]
        aligned_b = symbolic_state_space.b_matrix[permutation, :]
        aligned_c = symbolic_state_space.c_matrix[:, permutation]

        return BackendStateSpace(
            a_matrix=aligned_a,
            b_matrix=aligned_b,
            c_matrix=aligned_c,
            d_matrix=symbolic_state_space.d_matrix,
            state_variables=list(reference_state_space.state_variables),
            input_channel=symbolic_state_space.input_channel,
            output_variables=list(symbolic_state_space.output_variables),
            state_trace=list(symbolic_state_space.state_trace),
            output_trace=list(symbolic_state_space.output_trace),
            metadata=dict(symbolic_state_space.metadata),
        )

    def _matrix_diff(self, left: np.ndarray, right: np.ndarray) -> MatrixDiff:
        left_array = np.atleast_1d(np.asarray(left))
        right_array = np.atleast_1d(np.asarray(right))
        if left_array.shape != right_array.shape:
            return MatrixDiff(
                max_abs_error=float("inf"),
                shape_left=left_array.shape,
                shape_right=right_array.shape,
            )
        return MatrixDiff(
            max_abs_error=float(np.max(np.abs(left_array - right_array))) if left_array.size else 0.0,
            shape_left=left_array.shape,
            shape_right=right_array.shape,
        )

    def _step_response_diffs(
        self,
        *,
        numeric_step: StepResponseResult,
        symbolic_step: StepResponseResult,
        common_outputs: list[str],
    ) -> list[StepResponseDiff]:
        diffs: list[StepResponseDiff] = []
        for output_name in common_outputs:
            numeric_response = numeric_step.responses[output_name]
            symbolic_response = symbolic_step.responses[output_name]
            difference = numeric_response - symbolic_response
            diffs.append(
                StepResponseDiff(
                    output_name=output_name,
                    peak_abs_error=float(
                        abs(np.max(np.abs(numeric_response)) - np.max(np.abs(symbolic_response)))
                    ),
                    final_value_error=float(abs(numeric_response[-1] - symbolic_response[-1])),
                    rms_error=float(np.sqrt(np.mean(np.square(difference)))),
                )
            )
        return diffs

    def _transfer_function_diffs(
        self,
        *,
        numeric_state_space: BackendStateSpace,
        symbolic_state_space: BackendStateSpace,
        common_outputs: list[str],
    ) -> dict[str, MatrixDiff]:
        diffs: dict[str, MatrixDiff] = {}
        for output_index, output_name in enumerate(common_outputs):
            numeric_num, numeric_den = signal.ss2tf(
                numeric_state_space.a_matrix,
                numeric_state_space.b_matrix,
                numeric_state_space.c_matrix[output_index : output_index + 1],
                numeric_state_space.d_matrix[output_index : output_index + 1],
                input=0,
            )
            symbolic_num, symbolic_den = signal.ss2tf(
                symbolic_state_space.a_matrix,
                symbolic_state_space.b_matrix,
                symbolic_state_space.c_matrix[output_index : output_index + 1],
                symbolic_state_space.d_matrix[output_index : output_index + 1],
                input=0,
            )
            diffs[f"{output_name}:numerator"] = self._matrix_diff(
                np.asarray(numeric_num),
                np.asarray(symbolic_num),
            )
            diffs[f"{output_name}:denominator"] = self._matrix_diff(
                np.asarray(numeric_den),
                np.asarray(symbolic_den),
            )
        return diffs

    def _pole_zero_diffs(
        self,
        *,
        numeric_state_space: BackendStateSpace,
        symbolic_state_space: BackendStateSpace,
        common_outputs: list[str],
    ) -> dict[str, MatrixDiff]:
        diffs: dict[str, MatrixDiff] = {}
        for output_index, output_name in enumerate(common_outputs):
            numeric_zeros, numeric_poles, _ = signal.ss2zpk(
                numeric_state_space.a_matrix,
                numeric_state_space.b_matrix,
                numeric_state_space.c_matrix[output_index : output_index + 1],
                numeric_state_space.d_matrix[output_index : output_index + 1],
            )
            symbolic_zeros, symbolic_poles, _ = signal.ss2zpk(
                symbolic_state_space.a_matrix,
                symbolic_state_space.b_matrix,
                symbolic_state_space.c_matrix[output_index : output_index + 1],
                symbolic_state_space.d_matrix[output_index : output_index + 1],
            )
            diffs[f"{output_name}:zeros"] = self._matrix_diff(
                np.sort_complex(np.asarray(numeric_zeros)),
                np.sort_complex(np.asarray(symbolic_zeros)),
            )
            diffs[f"{output_name}:poles"] = self._matrix_diff(
                np.sort_complex(np.asarray(numeric_poles)),
                np.sort_complex(np.asarray(symbolic_poles)),
            )
        return diffs

    def _collect_issues(
        self,
        *,
        common_outputs: list[str],
        numeric_outputs: list[str],
        symbolic_outputs: list[str],
        numeric_state_space: BackendStateSpace,
        symbolic_state_space: BackendStateSpace,
        state_trace_matches: bool,
        output_trace_matches: bool,
        transfer_function_diffs: dict[str, MatrixDiff],
        pole_zero_diffs: dict[str, MatrixDiff],
        eigenvalue_diff: MatrixDiff,
    ) -> list[str]:
        issues: list[str] = []
        missing_numeric = [
            output_name for output_name in symbolic_outputs if output_name not in numeric_outputs
        ]
        missing_symbolic = [
            output_name for output_name in numeric_outputs if output_name not in symbolic_outputs
        ]
        if missing_numeric:
            issues.append(f"Missing outputs in numeric backend: {missing_numeric}")
        if missing_symbolic:
            issues.append(f"Missing outputs in symbolic backend: {missing_symbolic}")
        if numeric_state_space.state_variables != symbolic_state_space.state_variables:
            issues.append("Mismatched state ordering between backends.")
        if common_outputs != symbolic_state_space.output_variables:
            issues.append("Mismatched output ordering between backends.")
        if not state_trace_matches:
            issues.append("State trace mismatch between backends.")
        if not output_trace_matches:
            issues.append("Output trace mismatch between backends.")
        if any(diff.max_abs_error > 1e-8 for diff in transfer_function_diffs.values()):
            issues.append("Transfer function mismatch exceeds tolerance.")
        if any(diff.max_abs_error > 1e-8 for diff in pole_zero_diffs.values()):
            issues.append("Pole-zero mismatch exceeds tolerance.")
        if eigenvalue_diff.max_abs_error > 1e-8:
            issues.append("Eigenvalue mismatch exceeds tolerance.")
        return issues
