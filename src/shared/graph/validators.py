from __future__ import annotations

from dataclasses import dataclass

from src.shared.graph.system_graph import SystemGraph


@dataclass(frozen=True, slots=True)
class ValidationMessage:
    level: str
    text: str


class GraphValidator:
    def validate(self, graph: SystemGraph) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []

        if not graph.components:
            messages.append(ValidationMessage(level="error", text="Graph contains no components."))
            return messages

        if not graph.connections:
            messages.append(ValidationMessage(level="error", text="Graph contains no physical connections."))

        for component in graph.components.values():
            for error in component.validate():
                messages.append(ValidationMessage(level="error", text=error))

        connected_component_ids = {
            graph.get_port(connection.port_a).component_id for connection in graph.connections
        } | {
            graph.get_port(connection.port_b).component_id for connection in graph.connections
        }
        for component_id, component in graph.components.items():
            if component_id not in connected_component_ids:
                messages.append(
                    ValidationMessage(level="warning", text=f"Component {component.name} is isolated.")
                )

        messages.extend(self._validate_source_conflicts(graph))
        messages.extend(self._validate_probe_targets(graph))

        return messages

    def _validate_source_conflicts(self, graph: SystemGraph) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []
        sources_by_node: dict[tuple[str, str], list[str]] = {}
        for component in graph.components.values():
            if component.metadata.get("role") != "source":
                continue
            source_kind = component.metadata.get("source_kind", "displacement")
            port = component.port("port")
            if port.node_id is None:
                continue
            key = (port.node_id, source_kind)
            sources_by_node.setdefault(key, []).append(component.name)

        for (node_id, source_kind), names in sources_by_node.items():
            if len(names) > 1:
                messages.append(
                    ValidationMessage(
                        level="error",
                        text=f"Multiple {source_kind} sources connected to node {node_id}: {', '.join(names)}",
                    )
                )
        return messages

    def _validate_probe_targets(self, graph: SystemGraph) -> list[ValidationMessage]:
        messages: list[ValidationMessage] = []
        component_ids = set(graph.components.keys())
        for probe in graph.probes.values():
            target_component_id = getattr(probe, "target_component_id", None)
            reference_component_id = getattr(probe, "reference_component_id", None)
            if target_component_id is not None and target_component_id not in component_ids:
                messages.append(
                    ValidationMessage(level="error", text=f"Probe {probe.id} targets missing component {target_component_id}.")
                )
            if reference_component_id is not None and reference_component_id not in component_ids:
                messages.append(
                    ValidationMessage(level="error", text=f"Probe {probe.id} references missing component {reference_component_id}.")
                )
        return messages
