from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.templates.template_definition import TemplateDefinition


def build_rc_circuit_template() -> TemplateDefinition:
    return TemplateDefinition(
        id="rc_circuit",
        name="RC Circuit",
        graph=SystemGraph(),
        description="Placeholder for the future predefined RC template.",
    )
