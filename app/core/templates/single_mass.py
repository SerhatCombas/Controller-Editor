from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring
from app.core.models.sources import StepForce
from app.core.probes import BaseProbe
from app.core.symbolic.output_kind import (
    OutputKind,
    QK_ACCELERATION,
    QK_DISPLACEMENT,
    QK_SPRING_FORCE,
)
from app.core.templates.template_definition import TemplateDefinition


def build_single_mass_template() -> TemplateDefinition:
    graph = SystemGraph()

    mass = graph.add_component(Mass("mass", mass=2.0))
    spring = graph.add_component(Spring("spring", stiffness=10.0))
    damper = graph.add_component(Damper("damper", damping=3.0))
    source = graph.add_component(StepForce("input_force", amplitude=1.0))
    ground = graph.add_component(MechanicalGround("ground"))

    graph.connect(mass.port("port_a").id, spring.port("port_a").id, label="mass_spring")
    graph.connect(mass.port("port_a").id, damper.port("port_a").id, label="mass_damper")
    graph.connect(mass.port("port_a").id, source.port("port").id, label="mass_force")
    graph.connect(spring.port("port_b").id, ground.port("port").id, label="spring_ground")
    graph.connect(damper.port("port_b").id, ground.port("port").id, label="damper_ground")
    graph.connect(mass.port("reference_port").id, ground.port("port").id, label="mass_reference")
    graph.connect(source.port("reference_port").id, ground.port("port").id, label="source_reference")

    displacement_probe = graph.attach_probe(BaseProbe(
        "mass_displacement", "Mass displacement", "displacement", mass.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "mass_acceleration", "Mass acceleration", "acceleration", mass.id,
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))
    graph.attach_probe(BaseProbe(
        "spring_force", "Spring force", "force", spring.id,
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_SPRING_FORCE,
    ))

    graph.selected_input_id = source.id
    graph.selected_output_id = displacement_probe.id

    return TemplateDefinition(
        id="single_mass",
        name="Single Mass-Spring-Damper",
        graph=graph,
        default_input_id=source.id,
        default_output_id=displacement_probe.id,
        suggested_plots=["time_response", "step_response", "bode", "pole_zero"],
        description="Single mass connected to ground with spring and damper, excited by a force input.",
        parameter_groups={"mass": [mass.id], "passive": [spring.id, damper.id], "input": [source.id]},
        schematic_layout={
            "mass": (220.0, 100.0),
            "spring": (160.0, 220.0),
            "damper": (280.0, 220.0),
            "input_force": (80.0, 160.0),
            "ground": (220.0, 340.0),
        },
    )
