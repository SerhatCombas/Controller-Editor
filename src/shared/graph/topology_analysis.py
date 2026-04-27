from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.graph.system_graph import SystemGraph


@dataclass(slots=True)
class TopologySummary:
    domain_types: set[str] = field(default_factory=set)
    component_count: int = 0
    node_count: int = 0
    input_components: list[str] = field(default_factory=list)
    output_probes: list[str] = field(default_factory=list)
    degrees_of_freedom_hint: int = 0
    notes: list[str] = field(default_factory=list)


def analyze_topology(graph: SystemGraph) -> TopologySummary:
    summary = TopologySummary()
    summary.component_count = len(graph.components)
    summary.node_count = len(graph.nodes)
    summary.domain_types = {component.domain.name for component in graph.components.values()}
    summary.input_components = [
        component.name
        for component in graph.components.values()
        if component.metadata.get("role") == "source"
    ]
    summary.output_probes = [
        getattr(probe, "name", probe_id)
        for probe_id, probe in graph.probes.items()
    ]
    summary.degrees_of_freedom_hint = sum(
        1 for component in graph.components.values() if "Mass" in component.__class__.__name__
    )
    if len(summary.domain_types) > 1:
        summary.notes.append("Mixed-domain graph detected.")
    return summary
