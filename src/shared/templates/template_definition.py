from __future__ import annotations

from dataclasses import dataclass, field

from src.shared.graph.system_graph import SystemGraph


@dataclass(slots=True)
class TemplateDefinition:
    id: str
    name: str
    graph: SystemGraph
    default_input_id: str | None = None
    default_output_id: str | None = None
    suggested_plots: list[str] = field(default_factory=list)
    description: str = ""
    parameter_groups: dict[str, list[str]] = field(default_factory=dict)
    schematic_layout: dict[str, tuple[float, float]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
