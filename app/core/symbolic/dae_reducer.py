from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.symbolic.symbolic_system import ReducedODESystem, SymbolicSystem


class DAEReducer:
    """Initial DAE-to-ODE reduction for linear translational mechanical templates."""

    def reduce(self, graph: SystemGraph, symbolic_system: SymbolicSystem) -> ReducedODESystem:
        component_records = symbolic_system.metadata.get("component_records", {})
        # Faz 4d-2c — Polymorphic state-bearing classification.
        # Old behavior: pick masses by class name (record["type"] in {"Mass",
        # "Wheel"}). That conflates "is a Mass/Wheel" with "owns an inertial
        # DoF", which breaks down once Wheel can be a transducer (mass=0,
        # dof_count=0). The new path consults state_contribution.dof_count
        # — only components that genuinely contribute a DoF are promoted to
        # state nodes.
        # The legacy string check is kept as a fallback for records that
        # predate Faz 4d-2c (e.g. external callers that build their own
        # component_records dict without the new state_contribution field).
        # Faz 4j cleanup will remove the fallback once all callers migrate.
        mass_records = []
        for record in component_records.values():
            sc = record.get("state_contribution")
            if sc is not None:
                # Polymorphic path: only inertial DoF owners count.
                if sc.get("dof_count", 0) > 0 and sc.get("stores_inertial_energy", False):
                    mass_records.append(record)
            else:
                # Legacy fallback: string-based class-name check.
                if record["type"] in {"Mass", "Wheel"}:
                    mass_records.append(record)
        state_nodes = [record["port_nodes"].get("port_a") for record in mass_records]
        state_nodes = [node_id for node_id in state_nodes if node_id is not None]
        node_order = list(dict.fromkeys(state_nodes))
        node_index = {node_id: idx for idx, node_id in enumerate(node_order)}

        source_records = [
            record for record in component_records.values()
            if record["metadata"].get("role") == "source"
        ]
        input_variables = [f"u_{record['id']}" for record in source_records]
        source_node_to_input = {
            record["port_nodes"].get("port"): input_idx
            for input_idx, record in enumerate(source_records)
            if record["port_nodes"].get("port") is not None
            and record["metadata"].get("source_kind", "displacement") == "displacement"
        }
        force_source_records = [
            (input_idx, record)
            for input_idx, record in enumerate(source_records)
            if record["metadata"].get("source_kind") == "force"
        ]

        dimension = len(node_order)
        input_count = max(len(input_variables), 1)
        mass_matrix = self._zero_matrix(dimension, dimension)
        damping_matrix = self._zero_matrix(dimension, dimension)
        stiffness_matrix = self._zero_matrix(dimension, dimension)
        input_matrix = self._zero_matrix(dimension, input_count)

        for record in mass_records:
            node_id = record["port_nodes"].get("port_a")
            if node_id is None:
                continue
            idx = node_index[node_id]
            mass_matrix[idx][idx] += record["parameters"]["mass"]

        for record in component_records.values():
            if record["type"] == "Spring":
                self._accumulate_branch(
                    component_record=record,
                    coefficient=record["parameters"]["stiffness"],
                    matrix=stiffness_matrix,
                    input_matrix=input_matrix,
                    node_index=node_index,
                    source_node_to_input=source_node_to_input,
                )
            elif record["type"] == "Damper":
                self._accumulate_branch(
                    component_record=record,
                    coefficient=record["parameters"]["damping"],
                    matrix=damping_matrix,
                    input_matrix=input_matrix,
                    node_index=node_index,
                    source_node_to_input=source_node_to_input,
                )
            elif record["type"] == "Wheel":
                # Faz 4f-1 — Wheel with an active road_contact_port carries
                # tire-like contact dynamics analogous to a Spring (and a
                # Damper) bridging port_a to road_contact_port. We emit a
                # K-matrix branch with coefficient=contact_stiffness and a
                # C-matrix branch with coefficient=contact_damping, treating
                # road_contact_port as the "second port" of the branch.
                # When road_contact_port is unconnected we skip both — the
                # wheel is then just a Mass and contributes nothing here
                # (the mass entry is handled in the mass_records loop above).
                # When the wheel is in transducer mode (mass=0.0) Faz 4d-2c
                # already excluded it from mass_records via dof_count=0;
                # the branch contribution is unaffected by that — a
                # transducer wheel can still bridge port_a ↔ road_contact_port
                # if anyone wires it up. Faz 4f-2 will handle that case.
                # Note: this is deliberately a string-based class-name check
                # paralleling Spring/Damper. A polymorphic
                # contribute_stiffness / contribute_damping API is a Wave 2
                # refactor target (see Faz 4j roadmap).
                if record["port_nodes"].get("road_contact_port") is not None:
                    self._accumulate_branch(
                        component_record=record,
                        coefficient=record["parameters"]["contact_stiffness"],
                        matrix=stiffness_matrix,
                        input_matrix=input_matrix,
                        node_index=node_index,
                        source_node_to_input=source_node_to_input,
                        port_a_name="port_a",
                        port_b_name="road_contact_port",
                    )
                    self._accumulate_branch(
                        component_record=record,
                        coefficient=record["parameters"]["contact_damping"],
                        matrix=damping_matrix,
                        input_matrix=input_matrix,
                        node_index=node_index,
                        source_node_to_input=source_node_to_input,
                        port_a_name="port_a",
                        port_b_name="road_contact_port",
                    )
        for input_idx, record in force_source_records:
            drive_node = record["port_nodes"].get("port")
            reference_node = record["port_nodes"].get("reference_port")
            if drive_node in node_index:
                input_matrix[node_index[drive_node]][input_idx] += 1.0
            if reference_node in node_index:
                input_matrix[node_index[reference_node]][input_idx] -= 1.0

        state_variables = self._build_canonical_state_variables(
            mass_records=mass_records,
            node_order=node_order,
            symbolic_system=symbolic_system,
            variable_registry=symbolic_system.variable_registry,
        )
        first_order_a, first_order_b = self._to_first_order(
            node_order=node_order,
            mass_matrix=mass_matrix,
            damping_matrix=damping_matrix,
            stiffness_matrix=stiffness_matrix,
            input_matrix=input_matrix,
            state_variables=state_variables,
        )
        state_index_lookup = {
            state_id: state_idx for state_idx, state_id in enumerate(state_variables)
        }
        derivative_links = symbolic_system.metadata.get("derivative_links", {})
        sympy_equation_count = sum(
            1 for record in symbolic_system.equation_records if record.sympy_expression is not None
        )

        return ReducedODESystem(
            state_variables=state_variables,
            input_variables=input_variables,
            output_definitions=dict(symbolic_system.output_definitions),
            mass_matrix=mass_matrix,
            damping_matrix=damping_matrix,
            stiffness_matrix=stiffness_matrix,
            input_matrix=input_matrix,
            first_order_a=first_order_a,
            first_order_b=first_order_b,
            node_order=node_order,
            metadata={
                "reduction_type": "linear_mechanical_template",
                "algebraic_constraint_count": len(symbolic_system.algebraic_constraints),
                "component_records": component_records,
                "output_records": symbolic_system.metadata.get("output_records", {}),
                "state_index_lookup": state_index_lookup,
                "derivative_links": derivative_links,
                "sympy_equation_count": sympy_equation_count,
                "canonical_state_source": "symbolic_records",
                "state_trace": [
                    {
                        "state_id": state_id,
                        "node_id": node_order[idx] if idx < len(node_order) else None,
                        "origin_layer": "dae_reducer",
                        "variable_kind": symbolic_system.variable_registry.get(state_id, {}).get("kind", "state"),
                        "derivative_id": derivative_links.get(state_id),
                    }
                    for idx, state_id in enumerate(state_variables[: len(node_order)])
                ] + [
                    {
                        "state_id": state_id,
                        "node_id": node_order[idx - len(node_order)] if idx - len(node_order) < len(node_order) else None,
                        "origin_layer": "dae_reducer",
                        "variable_kind": symbolic_system.variable_registry.get(state_id, {}).get("kind", "state"),
                        "derivative_id": derivative_links.get(state_id),
                    }
                    for idx, state_id in enumerate(state_variables[len(node_order):], start=len(node_order))
                ],
            },
        )

    def _build_canonical_state_variables(
        self,
        *,
        mass_records: list[dict[str, object]],
        node_order: list[str],
        symbolic_system: SymbolicSystem,
        variable_registry: dict[str, object],
    ) -> list[str]:
        differential_index = self._build_component_differential_index(symbolic_system)
        state_variable_set = set(symbolic_system.state_variables)
        derivative_links = symbolic_system.metadata.get("derivative_links", {})
        node_to_component = {
            record["port_nodes"].get("port_a"): record["id"]
            for record in mass_records
            if record["port_nodes"].get("port_a") is not None
        }
        displacement_states: list[str] = []
        velocity_states: list[str] = []

        for node_id in node_order:
            component_id = node_to_component.get(node_id)
            position_state, velocity_state = self._resolve_component_state_pair(
                component_id=component_id,
                differential_index=differential_index,
                state_variable_set=state_variable_set,
                derivative_links=derivative_links,
            )

            if position_state is None:
                position_state = f"x_{component_id}" if component_id is not None else f"x_{len(displacement_states)}"
            if velocity_state is None:
                velocity_state = f"v_{component_id}" if component_id is not None else f"v_{len(velocity_states)}"

            displacement_states.append(
                position_state if position_state in variable_registry else f"x_{len(displacement_states)}"
            )
            velocity_states.append(
                velocity_state if velocity_state in variable_registry else f"v_{len(velocity_states)}"
            )

        return displacement_states + velocity_states

    def _build_component_differential_index(
        self,
        symbolic_system: SymbolicSystem,
    ) -> dict[str, list[object]]:
        differential_index: dict[str, list[object]] = {}
        for record in symbolic_system.differential_records:
            component_id = record.metadata.get("owner_component_id") or record.metadata.get("source_id")
            if component_id is None:
                continue
            differential_index.setdefault(str(component_id), []).append(record)
        return differential_index

    def _resolve_component_state_pair(
        self,
        *,
        component_id: str | None,
        differential_index: dict[str, list[object]],
        state_variable_set: set[str],
        derivative_links: dict[str, str],
    ) -> tuple[str | None, str | None]:
        if component_id is None:
            return None, None

        candidate_records = differential_index.get(component_id, [])
        preferred_position: str | None = None
        preferred_velocity: str | None = None

        for record in candidate_records:
            for derivative_variable in record.derivative_variables:
                if derivative_variable not in state_variable_set:
                    continue
                if derivative_variable.startswith("x_") and preferred_position is None:
                    preferred_position = derivative_variable
                    linked_velocity = self._find_state_by_derivative(
                        derivative_id=f"ddt_{derivative_variable}",
                        derivative_links=derivative_links,
                    )
                    if linked_velocity is not None:
                        preferred_velocity = linked_velocity
                elif derivative_variable.startswith("v_") and preferred_velocity is None:
                    preferred_velocity = derivative_variable

            if preferred_position is None:
                for variable_name in record.involved_variables:
                    if variable_name in state_variable_set and variable_name.startswith("x_"):
                        preferred_position = variable_name
                        break
            if preferred_velocity is None:
                for variable_name in record.involved_variables:
                    if variable_name in state_variable_set and variable_name.startswith("v_"):
                        preferred_velocity = variable_name
                        break

        if preferred_position is None:
            fallback_position = f"x_{component_id}"
            if fallback_position in state_variable_set:
                preferred_position = fallback_position
        if preferred_velocity is None:
            fallback_velocity = f"v_{component_id}"
            if fallback_velocity in state_variable_set:
                preferred_velocity = fallback_velocity

        if preferred_velocity is None and preferred_position is not None:
            preferred_velocity = self._find_state_by_derivative(
                derivative_id=f"ddt_{preferred_position}",
                derivative_links=derivative_links,
            )

        return preferred_position, preferred_velocity

    def _find_state_by_derivative(
        self,
        *,
        derivative_id: str,
        derivative_links: dict[str, str],
    ) -> str | None:
        for state_id, linked_derivative_id in derivative_links.items():
            if linked_derivative_id == derivative_id:
                sibling_velocity = state_id.replace("x_", "v_", 1)
                return sibling_velocity if sibling_velocity in derivative_links or sibling_velocity.startswith("v_") else state_id
        return None

    def _accumulate_branch(
        self,
        *,
        component_record: dict[str, object],
        coefficient: float,
        matrix: list[list[float]],
        input_matrix: list[list[float]],
        node_index: dict[str, int],
        source_node_to_input: dict[str, int],
        port_a_name: str = "port_a",
        port_b_name: str = "port_b",
    ) -> None:
        # Faz 4f-1 — port_a_name / port_b_name parameters allow non-Spring
        # branch elements (Wheel's port_a ↔ road_contact_port pairing) to
        # reuse the same matrix-accumulation logic. Default values match
        # the historical Spring/Damper two-port convention so existing
        # callers stay bit-for-bit identical.
        port_nodes = component_record["port_nodes"]
        node_a = port_nodes.get(port_a_name)
        node_b = port_nodes.get(port_b_name)
        idx_a = node_index.get(node_a) if node_a is not None else None
        idx_b = node_index.get(node_b) if node_b is not None else None
        input_a = source_node_to_input.get(node_a) if node_a is not None else None
        input_b = source_node_to_input.get(node_b) if node_b is not None else None

        if idx_a is not None:
            matrix[idx_a][idx_a] += coefficient
        if idx_b is not None:
            matrix[idx_b][idx_b] += coefficient
        if idx_a is not None and idx_b is not None:
            matrix[idx_a][idx_b] -= coefficient
            matrix[idx_b][idx_a] -= coefficient
        if idx_a is not None and input_b is not None:
            input_matrix[idx_a][input_b] += coefficient
        if idx_b is not None and input_a is not None:
            input_matrix[idx_b][input_a] += coefficient

    def _to_first_order(
        self,
        *,
        node_order: list[str],
        mass_matrix: list[list[float]],
        damping_matrix: list[list[float]],
        stiffness_matrix: list[list[float]],
        input_matrix: list[list[float]],
        state_variables: list[str],
    ) -> tuple[list[list[float]], list[list[float]]]:
        dof = len(node_order)
        if dof == 0:
            return [], []

        mass_inverse = self._invert_diagonal(mass_matrix)
        top_left = self._zero_matrix(dof, dof)
        top_right = self._identity_matrix(dof)
        bottom_left = self._negate(self._multiply(mass_inverse, stiffness_matrix))
        bottom_right = self._negate(self._multiply(mass_inverse, damping_matrix))

        a_matrix = [left + right for left, right in zip(top_left, top_right)]
        a_matrix.extend([left + right for left, right in zip(bottom_left, bottom_right)])

        top_b = self._zero_matrix(dof, len(input_matrix[0]) if input_matrix else 0)
        bottom_b = self._multiply(mass_inverse, input_matrix)
        b_matrix = top_b + bottom_b

        return a_matrix, b_matrix

    def _zero_matrix(self, rows: int, cols: int) -> list[list[float]]:
        return [[0.0 for _ in range(cols)] for _ in range(rows)]

    def _identity_matrix(self, size: int) -> list[list[float]]:
        matrix = self._zero_matrix(size, size)
        for idx in range(size):
            matrix[idx][idx] = 1.0
        return matrix

    def _invert_diagonal(self, matrix: list[list[float]]) -> list[list[float]]:
        inverse = self._zero_matrix(len(matrix), len(matrix))
        for idx, row in enumerate(matrix):
            value = row[idx]
            inverse[idx][idx] = 0.0 if value == 0.0 else 1.0 / value
        return inverse

    def _multiply(self, left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
        if not left or not right:
            return []
        rows = len(left)
        cols = len(right[0])
        shared = len(right)
        result = self._zero_matrix(rows, cols)
        for i in range(rows):
            for j in range(cols):
                result[i][j] = sum(left[i][k] * right[k][j] for k in range(shared))
        return result

    def _negate(self, matrix: list[list[float]]) -> list[list[float]]:
        return [[-value for value in row] for row in matrix]
