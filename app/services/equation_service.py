from __future__ import annotations

import numpy as np
from scipy import signal

from app.core.state.app_state import AppState
from app.services.signal_catalog import input_definition
from app.services.simulation_backend import SimulationBackend


class EquationService:
    def build_summary(
        self,
        app_state: AppState,
        *,
        symbolic_backend: SimulationBackend,
        analysis_backend: SimulationBackend,
    ) -> dict[str, str]:
        if not app_state.selection.input_signals or not app_state.selection.output_signals:
            return {
                "input_label": "None",
                "output_label": "None",
                "equations": "No explicit simulation input/output selection yet.",
                "equation_trace": "Select at least one input and one output to inspect the active model.",
                "states": "No active selection.",
                "state_space": "No active selection.",
                "transfer_function": "No active selection.",
                "source_badge": "Awaiting explicit simulation I/O selection",
            }
        selected_input = self._selected_input_channel(app_state)
        input_label = ", ".join(
            (
                input_definition(app_state.simulation.model_template, signal_id).label
                if input_definition(app_state.simulation.model_template, signal_id) is not None
                else signal_id
            )
            for signal_id in app_state.selection.input_signals
        )
        output_label = ", ".join(
            analysis_backend.get_output_labels().get(output_signal, output_signal)
            for output_signal in app_state.selection.output_signals
        )
        equations_payload = symbolic_backend.get_equations()
        if selected_input is None:
            return {
                "input_label": input_label,
                "output_label": output_label,
                "equations": self._equation_text(equations_payload),
                "equation_trace": self._equation_trace_text(equations_payload),
                "states": self._state_text(equations_payload),
                "state_space": "Selected input channels are not yet supported by the analysis backend.",
                "transfer_function": "Transfer-function extraction currently supports only backend-declared driving inputs.",
                "source_badge": "Symbolic equations + constrained analysis fallback",
            }
        state_space = analysis_backend.get_state_space(
            input_channel=selected_input,
            output_variables=list(app_state.selection.output_signals),
        )
        tf_text = self._transfer_function_text(state_space, output_count=len(app_state.selection.output_signals))
        if len(app_state.selection.input_signals) > 1:
            tf_text = (
                f"Primary analysis input: {analysis_backend.get_input_labels().get(selected_input, selected_input)}\n"
                "Multi-input symbolic transfer extraction is not fully available yet.\n\n"
                f"{tf_text}"
            )
        return {
            "input_label": input_label,
            "output_label": output_label,
            "equations": self._equation_text(equations_payload),
            "equation_trace": self._equation_trace_text(equations_payload),
            "states": self._state_text(equations_payload),
            "state_space": self._state_space_text(state_space),
            "transfer_function": tf_text,
            "source_badge": "Symbolic equations + backend-neutral analysis",
        }

    def _selected_input_channel(self, app_state: AppState) -> str | None:
        backend_labels = {
            "road": "road_displacement",
            "body_force": "body_force",
        }
        for selected_input in app_state.selection.input_signals:
            if selected_input in backend_labels:
                return backend_labels[selected_input]
        return None

    def _equation_text(self, equations_payload: dict[str, object]) -> str:
        return "\n".join(equations_payload.get("equations", []))

    def _state_text(self, equations_payload: dict[str, object]) -> str:
        reduced_states = equations_payload.get("reduced_state_variables") or []
        symbolic_states = equations_payload.get("state_variables") or []
        state_lines = [
            f"Reduced states: {reduced_states}",
            f"Symbolic states: {symbolic_states}",
        ]
        return "\n".join(state_lines)

    def _equation_trace_text(self, equations_payload: dict[str, object]) -> str:
        records = equations_payload.get("equation_records", [])
        lines: list[str] = []
        for record in records[:12]:
            source_type = record.metadata.get("source_type", "unknown")
            source_name = record.metadata.get("source_name", "unknown")
            tags = ", ".join(record.metadata.get("tags", []))
            variables = ", ".join(record.involved_variables[:6])
            lines.append(f"[{source_type}] {source_name} | tags={tags} | vars={variables}")
        return "\n".join(lines)

    def _state_space_text(self, state_space) -> str:
        a_text = np.array2string(state_space.a_matrix, precision=3, suppress_small=True)
        b_text = np.array2string(state_space.b_matrix, precision=3, suppress_small=True)
        return f"A = {a_text}\n\nB = {b_text}"

    def _transfer_function_text(self, state_space, *, output_count: int) -> str:
        num, den = signal.ss2tf(
            state_space.a_matrix,
            state_space.b_matrix,
            state_space.c_matrix,
            state_space.d_matrix,
            input=0,
        )
        numerator_rows = []
        for row_index in range(min(output_count, len(num))):
            numerator = np.trim_zeros(num[row_index], "f")
            numerator_rows.append(f"Output {row_index + 1} numerator = {np.array2string(numerator, precision=5, suppress_small=True)}")
        denominator = np.trim_zeros(den, "f")
        denominator_text = np.array2string(denominator, precision=5, suppress_small=True)
        return f"{chr(10).join(numerator_rows)}\nG(s) denominator = {denominator_text}"
