from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.symbolic.output_mapper import OutputMapper
from app.core.symbolic.symbolic_system import ReducedODESystem, StateSpaceModel, SymbolicSystem


class StateSpaceBuilder:
    """Creates linear state-space matrices from reduced ODE form.

    Wave 3B update: delegates all C/D row construction to ``OutputMapper``,
    which is now the single authoritative source for probe → state-space
    mapping.  The graph is threaded through so that force probes (spring,
    damper) can resolve their connected DOFs without duplicating that logic
    here.

    Probes that ``OutputMapper`` cannot express (``supported_for_tf=False``)
    still appear in ``output_variables`` with all-zero C/D rows; callers
    should inspect ``output_trace[i]["supported_for_tf"]`` before using the
    row for frequency-domain analysis.
    """

    def build(
        self,
        graph: SystemGraph,
        reduced_system: ReducedODESystem,
        symbolic_system: SymbolicSystem | None = None,
    ) -> StateSpaceModel:
        mapper = OutputMapper()
        output_variables: list[str] = []
        c_matrix: list[list[float]] = []
        d_matrix: list[list[float]] = []
        output_trace: list[dict[str, object]] = []

        for probe_id, probe in graph.probes.items():
            expr = mapper.map(probe, reduced_system, graph)
            output_variables.append(probe_id)
            c_matrix.append(list(expr.c_row))
            d_matrix.append(list(expr.d_row))
            output_trace.append({
                "output_id": probe_id,
                "origin_layer": "state_space_builder",
                "source_type": (
                    "relative_probe"
                    if getattr(probe, "reference_component_id", None)
                    else "probe"
                ),
                "target_component_id": getattr(probe, "target_component_id", None),
                "reference_component_id": getattr(probe, "reference_component_id", None),
                "quantity": getattr(probe, "quantity", None),
                "state_columns": list(expr.contributing_state_names),
                "supported_for_tf": expr.supported_for_tf,
                "unsupported_reason": expr.unsupported_reason,
            })

        return StateSpaceModel(
            a_matrix=reduced_system.first_order_a,
            b_matrix=reduced_system.first_order_b,
            c_matrix=c_matrix,
            d_matrix=d_matrix,
            state_variables=reduced_system.state_variables,
            input_variables=reduced_system.input_variables,
            output_variables=output_variables,
            metadata={
                "builder": "StateSpaceBuilder",
                "linear": True,
                "output_trace": output_trace,
            },
        )
