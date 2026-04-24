from __future__ import annotations

from dataclasses import dataclass, field

from app.core.graph.system_graph import SystemGraph


@dataclass(slots=True)
class AssemblyContext:
    component_equations: list[str] = field(default_factory=list)
    component_equation_sources: list[dict[str, object]] = field(default_factory=list)
    node_equations: list[str] = field(default_factory=list)
    node_equation_sources: list[dict[str, object]] = field(default_factory=list)
    dae_equations: list[str] = field(default_factory=list)
    dae_equation_sources: list[dict[str, object]] = field(default_factory=list)
    algebraic_constraints: list[str] = field(default_factory=list)
    differential_equations: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    parameters: dict[str, float] = field(default_factory=dict)


class GraphAssembler:
    def assemble(self, graph: SystemGraph) -> AssemblyContext:
        context = AssemblyContext()

        for component in graph.components.values():
            constitutive = component.constitutive_equations()
            dae = component.dae_equations()
            context.component_equations.extend(constitutive)
            context.dae_equations.extend(dae)
            context.states.extend(component.get_states())
            context.parameters.update(component.get_parameters())
            context.component_equation_sources.extend(
                {
                    "source_type": "component",
                    "source_id": component.id,
                    "source_name": component.name,
                    "origin_layer": "assembler",
                    "domain": component.domain.name,
                    "owner_component_id": component.id,
                    "owner_node_id": None,
                    "tags": ["constitutive"],
                    "equation": equation,
                }
                for equation in constitutive
            )
            context.dae_equation_sources.extend(
                {
                    "source_type": "component",
                    "source_id": component.id,
                    "source_name": component.name,
                    "origin_layer": "assembler",
                    "domain": component.domain.name,
                    "owner_component_id": component.id,
                    "owner_node_id": None,
                    "tags": ["dae", "constitutive"],
                    "equation": equation,
                }
                for equation in dae
            )

        for node in graph.nodes.values():
            connected_ports = [graph.get_port(port_id) for port_id in node.port_ids]
            across_equations = node.explicit_across_equations(connected_ports)
            context.node_equations.extend(across_equations)
            context.node_equation_sources.extend(
                {
                    "source_type": "node",
                    "source_id": node.id,
                    "source_name": node.id,
                    "origin_layer": "assembler",
                    "domain": node.domain.name,
                    "owner_component_id": None,
                    "owner_node_id": node.id,
                    "tags": ["across_constraint"],
                    "equation": equation,
                }
                for equation in across_equations
            )
            through_equation = node.explicit_through_equation(connected_ports)
            if through_equation is not None:
                context.node_equations.append(through_equation)
                context.node_equation_sources.append(
                    {
                        "source_type": "node",
                        "source_id": node.id,
                        "source_name": node.id,
                        "origin_layer": "assembler",
                        "domain": node.domain.name,
                        "owner_component_id": None,
                        "owner_node_id": node.id,
                        "tags": ["through_constraint"],
                        "equation": through_equation,
                    }
                )

        context.algebraic_constraints = list(context.node_equations)
        context.differential_equations = [
            equation for equation in context.dae_equations if "d/dt" in equation
        ]

        return context
