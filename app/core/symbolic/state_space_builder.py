from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.symbolic.symbolic_system import ReducedODESystem, StateSpaceModel, SymbolicSystem


class StateSpaceBuilder:
    """Creates linear state-space matrices from reduced ODE form."""

    def build(
        self,
        graph: SystemGraph,
        reduced_system: ReducedODESystem,
        symbolic_system: SymbolicSystem | None = None,
    ) -> StateSpaceModel:
        output_variables: list[str] = []
        c_matrix: list[list[float]] = []
        d_matrix: list[list[float]] = []
        output_records = reduced_system.metadata.get("output_records", {})
        state_index_lookup = reduced_system.metadata.get("state_index_lookup", {})

        for probe_id in graph.probes:
            output_variables.append(probe_id)
            c_row, d_row = self._probe_row(
                reduced_system,
                output_record=output_records.get(probe_id, {}),
                symbolic_system=symbolic_system,
            )
            c_matrix.append(c_row)
            d_matrix.append(d_row)

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
                "output_trace": [
                    {
                        "output_id": output_id,
                        "origin_layer": "state_space_builder",
                        "source_type": output_records.get(output_id, {}).get("reference_component_id") and "relative_probe" or "probe",
                        "target_component_id": output_records.get(output_id, {}).get("target_component_id"),
                        "reference_component_id": output_records.get(output_id, {}).get("reference_component_id"),
                        "quantity": output_records.get(output_id, {}).get("quantity"),
                        "state_columns": [
                            state_id
                            for state_id, state_idx in state_index_lookup.items()
                            if state_idx < len(c_matrix[idx]) and c_matrix[idx][state_idx] != 0.0
                        ],
                    }
                    for idx, output_id in enumerate(output_variables)
                ],
            },
        )

    def _probe_row(
        self,
        reduced_system: ReducedODESystem,
        *,
        output_record: dict[str, object],
        symbolic_system: SymbolicSystem | None,
    ) -> tuple[list[float], list[float]]:
        state_count = len(reduced_system.state_variables)
        input_count = len(reduced_system.input_variables)
        c_row = [0.0] * state_count
        d_row = [0.0] * input_count
        dof = len(reduced_system.node_order)
        node_index = {node_id: idx for idx, node_id in enumerate(reduced_system.node_order)}
        component_records = reduced_system.metadata.get("component_records", {})

        target_component_id = output_record.get("target_component_id")
        reference_component_id = output_record.get("reference_component_id")
        quantity = output_record.get("quantity")

        if target_component_id is None:
            return c_row, d_row

        if reference_component_id is not None:
            target_record = component_records.get(target_component_id, {})
            reference_record = component_records.get(reference_component_id, {})
            target_node = target_record.get("port_nodes", {}).get("port_a")
            reference_node = reference_record.get("port_nodes", {}).get("port_a")
            if target_node in node_index:
                c_row[node_index[target_node]] = 1.0
            if reference_node in node_index:
                c_row[node_index[reference_node]] = -1.0
            elif reference_record.get("metadata", {}).get("role") == "source":
                if reference_record.get("metadata", {}).get("source_kind", "displacement") == "displacement":
                    for input_idx, input_name in enumerate(reduced_system.input_variables):
                        if input_name == f"u_{reference_component_id}":
                            d_row[input_idx] = -1.0
            return c_row, d_row

        target_record = component_records.get(target_component_id, {})
        target_node = target_record.get("port_nodes", {}).get("port_a")

        if quantity == "displacement" and target_record.get("type") in {"Mass", "Wheel"}:
            if target_node in node_index:
                c_row[node_index[target_node]] = 1.0
        elif quantity == "acceleration" and target_record.get("type") in {"Mass", "Wheel"}:
            if target_node in node_index:
                row_idx = node_index[target_node] + dof
                c_row = list(reduced_system.first_order_a[row_idx])
                d_row = list(reduced_system.first_order_b[row_idx])
        elif quantity == "force" and target_record.get("type") == "Spring":
            node_a = target_record.get("port_nodes", {}).get("port_a")
            node_b = target_record.get("port_nodes", {}).get("port_b")
            stiffness = target_record.get("parameters", {}).get("stiffness", 0.0)
            if node_a in node_index:
                c_row[node_index[node_a]] += stiffness
            if node_b in node_index:
                c_row[node_index[node_b]] -= stiffness

        return c_row, d_row
