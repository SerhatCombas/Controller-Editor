from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.templates.template_definition import TemplateDefinition


def build_rlc_circuit_template() -> TemplateDefinition:
    return TemplateDefinition(
        id="rlc_circuit",
        name="RLC Circuit",
        graph=SystemGraph(),
        description="Placeholder for the future predefined RLC template.",
    )
