from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from src.shared.types.component import BaseComponent
from src.shared.types.connection import Connection
from src.shared.types.node import Node
from src.shared.types.port import Port


@dataclass(slots=True)
class SystemGraph:
    components: dict[str, BaseComponent] = field(default_factory=dict)
    connections: list[Connection] = field(default_factory=list)
    nodes: dict[str, Node] = field(default_factory=dict)
    probes: dict[str, object] = field(default_factory=dict)
    selected_input_id: str | None = None
    selected_output_id: str | None = None

    def add_component(self, component: BaseComponent) -> BaseComponent:
        self.components[component.id] = component
        return component

    def add_node(self, node: Node) -> Node:
        self.nodes[node.id] = node
        return node

    def get_port(self, port_id: str) -> Port:
        for component in self.components.values():
            for port in component.ports:
                if port.id == port_id:
                    return port
        raise KeyError(f"Unknown port id: {port_id}")

    def connect(self, port_a_id: str, port_b_id: str, *, label: str | None = None) -> Connection:
        port_a = self.get_port(port_a_id)
        port_b = self.get_port(port_b_id)
        port_a.validate_compatibility(port_b)

        node_id = port_a.node_id or port_b.node_id or f"node_{uuid.uuid4().hex[:8]}"
        node = self.nodes.get(node_id)
        if node is None:
            node = self.add_node(Node(id=node_id, domain=port_a.domain))

        for port in (port_a, port_b):
            port.connect_to(node.id)
            node.attach_port(port.id)

        connection = Connection(
            id=f"conn_{uuid.uuid4().hex[:8]}",
            port_a=port_a_id,
            port_b=port_b_id,
            label=label,
        )
        self.connections.append(connection)
        return connection

    def attach_probe(self, probe: object) -> object:
        probe_id = getattr(probe, "id", f"probe_{uuid.uuid4().hex[:8]}")
        self.probes[probe_id] = probe
        return probe
