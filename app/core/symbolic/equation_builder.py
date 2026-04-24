from __future__ import annotations

from app.core.graph.assembler import GraphAssembler
from app.core.graph.system_graph import SystemGraph
from app.core.symbolic.structured_equation import EquationRecord
from app.core.symbolic.symbolic_system import SymbolicSystem
from app.core.symbolic.sympy_adapter import SympyAdapter


class EquationBuilder:
    """Builds a unified symbolic system from graph + assembler outputs."""

    def __init__(self, assembler: GraphAssembler | None = None) -> None:
        self.assembler = assembler or GraphAssembler()
        self.sympy_adapter = SympyAdapter()

    def build(self, graph: SystemGraph) -> SymbolicSystem:
        assembly = self.assembler.assemble(graph)

        input_variables: list[str] = []
        for component in graph.components.values():
            if component.metadata.get("role") == "source":
                input_variables.append(f"u_{component.id}")

        output_definitions = {
            probe_id: probe.measurement_equation()
            for probe_id, probe in graph.probes.items()
            if hasattr(probe, "measurement_equation")
        }

        parameter_names = set(assembly.parameters.keys())
        component_records = self._build_component_records(graph)
        node_records = self._build_node_records(graph)
        output_records = self._build_output_records(graph)
        source_lookup = self._build_source_lookup(assembly)
        equation_records = self._build_records(
            assembly.component_equations + assembly.node_equations,
            "equation",
            parameter_names,
            component_records,
            source_lookup,
        )
        dae_records = self._build_records(
            assembly.dae_equations + assembly.node_equations,
            "dae",
            parameter_names,
            component_records,
            source_lookup,
        )
        differential_records = self._build_records(
            assembly.differential_equations,
            "differential",
            parameter_names,
            component_records,
            source_lookup,
        )
        algebraic_records = self._build_records(
            assembly.algebraic_constraints,
            "algebraic",
            parameter_names,
            component_records,
            source_lookup,
        )
        variable_registry = self._build_variable_registry(
            graph=graph,
            state_variables=assembly.states,
            input_variables=input_variables,
            parameters=assembly.parameters,
        )

        return SymbolicSystem(
            all_equations=assembly.component_equations + assembly.node_equations,
            dae_equations=assembly.dae_equations + assembly.node_equations,
            differential_equations=assembly.differential_equations,
            algebraic_constraints=assembly.algebraic_constraints,
            equation_records=equation_records,
            dae_equation_records=dae_records,
            differential_records=differential_records,
            algebraic_records=algebraic_records,
            state_variables=assembly.states,
            input_variables=input_variables,
            output_definitions=output_definitions,
            parameters=assembly.parameters,
            variable_registry=variable_registry,
            metadata={
                "component_count": len(graph.components),
                "node_count": len(graph.nodes),
                "probe_count": len(graph.probes),
                "component_records": component_records,
                "node_records": node_records,
                "output_records": output_records,
                "derivative_links": {
                    variable_id: record["derivative_id"]
                    for variable_id, record in variable_registry.items()
                    if record.get("kind") == "state" and record.get("derivative_id") is not None
                },
                "sympy_available": self.sympy_adapter.available,
            },
        )

    def _build_records(
        self,
        equations: list[str],
        equation_type: str,
        parameter_names: set[str],
        component_records: dict[str, dict[str, object]],
        source_lookup: dict[str, dict[str, object]],
    ) -> list[EquationRecord]:
        records: list[EquationRecord] = []
        for equation_text in equations:
            lhs_text, rhs_text, sympy_expression = self.sympy_adapter.parse_equation(equation_text)
            involved_variables = self.sympy_adapter.extract_tokens(f"{lhs_text} {rhs_text}")
            derivative_variables = self.sympy_adapter.extract_derivatives(equation_text)
            involved_parameters = [token for token in involved_variables if token in parameter_names]
            for component_id, record in component_records.items():
                if component_id in equation_text:
                    involved_parameters.extend(record["parameters"].keys())
            records.append(
                EquationRecord(
                    display_text=equation_text,
                    lhs_text=lhs_text,
                    rhs_text=rhs_text,
                    equation_type=equation_type,
                    sympy_expression=sympy_expression,
                    involved_variables=involved_variables,
                    involved_parameters=sorted(set(involved_parameters)),
                    derivative_variables=derivative_variables,
                    metadata=dict(source_lookup.get(equation_text, {})),
                )
            )
        return records

    def _build_variable_registry(
        self,
        *,
        graph: SystemGraph,
        state_variables: list[str],
        input_variables: list[str],
        parameters: dict[str, float],
    ) -> dict[str, object]:
        registry: dict[str, object] = {}
        for variable in state_variables:
            derivative_name = f"ddt_{variable}" if variable.startswith(("x_", "v_")) else None
            registry[variable] = {
                "id": variable,
                "kind": "state",
                "name": variable,
                "derivative_id": derivative_name,
            }
            if derivative_name is not None:
                registry[derivative_name] = {
                    "id": derivative_name,
                    "kind": "derivative",
                    "name": derivative_name,
                    "base_variable_id": variable,
                }
        for variable in input_variables:
            registry[variable] = {"id": variable, "kind": "input", "name": variable}
        for parameter_name, value in parameters.items():
            registry[parameter_name] = {
                "id": parameter_name,
                "kind": "parameter",
                "name": parameter_name,
                "value": value,
            }
        for component in graph.components.values():
            for port in component.ports:
                if port.across_var is not None:
                    registry[port.across_var.name] = {
                        "id": port.across_var.name,
                        "kind": port.across_var.kind,
                        "name": port.across_var.name,
                        "component_id": component.id,
                        "port_id": port.id,
                        "domain": port.domain.name,
                    }
                if port.through_var is not None:
                    registry[port.through_var.name] = {
                        "id": port.through_var.name,
                        "kind": port.through_var.kind,
                        "name": port.through_var.name,
                        "component_id": component.id,
                        "port_id": port.id,
                        "domain": port.domain.name,
                    }
        return registry

    def _build_component_records(self, graph: SystemGraph) -> dict[str, dict[str, object]]:
        records: dict[str, dict[str, object]] = {}
        for component_id, component in graph.components.items():
            records[component_id] = {
                "id": component_id,
                "type": component.__class__.__name__,
                "name": component.name,
                "parameters": dict(component.parameters),
                "metadata": dict(component.metadata),
                "port_nodes": {port.name: port.node_id for port in component.ports},
                "port_variables": {
                    port.name: {
                        "across": port.across_var.name if port.across_var is not None else None,
                        "through": port.through_var.name if port.through_var is not None else None,
                    }
                    for port in component.ports
                },
            }
        return records

    def _build_node_records(self, graph: SystemGraph) -> dict[str, dict[str, object]]:
        return {
            node_id: {"id": node_id, "domain": node.domain.name, "ports": list(node.port_ids)}
            for node_id, node in graph.nodes.items()
        }

    def _build_output_records(self, graph: SystemGraph) -> dict[str, dict[str, object]]:
        records: dict[str, dict[str, object]] = {}
        for probe_id, probe in graph.probes.items():
            records[probe_id] = {
                "id": probe_id,
                "name": getattr(probe, "name", probe_id),
                "quantity": getattr(probe, "quantity", None),
                "target_component_id": getattr(probe, "target_component_id", None),
                "reference_component_id": getattr(probe, "reference_component_id", None),
                "measurement_equation": probe.measurement_equation() if hasattr(probe, "measurement_equation") else "",
            }
        return records

    def _build_source_lookup(self, assembly) -> dict[str, dict[str, object]]:
        lookup: dict[str, dict[str, object]] = {}
        for source_record in assembly.component_equation_sources + assembly.node_equation_sources + assembly.dae_equation_sources:
            lookup[source_record["equation"]] = {
                "source_type": source_record["source_type"],
                "source_id": source_record["source_id"],
                "source_name": source_record["source_name"],
                "origin_layer": source_record.get("origin_layer", "assembler"),
                "domain": source_record["domain"],
                "owner_component_id": source_record.get("owner_component_id"),
                "owner_node_id": source_record.get("owner_node_id"),
                "tags": list(source_record["tags"]),
            }
        return lookup
