from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring
from app.core.models.sources import StepForce
from app.core.probes import BaseProbe, RelativeProbe
from app.core.symbolic.output_kind import (
    OutputKind,
    QK_ACCELERATION,
    QK_DISPLACEMENT,
    QK_RELATIVE_DISPLACEMENT,
)
from app.core.templates.template_definition import TemplateDefinition


def build_two_mass_template() -> TemplateDefinition:
    graph = SystemGraph()

    mass_1 = graph.add_component(Mass("mass_1", mass=2.0, name="Mass 1"))
    mass_2 = graph.add_component(Mass("mass_2", mass=1.0, name="Mass 2"))
    spring_ground = graph.add_component(Spring("spring_ground", stiffness=20.0, name="Ground Spring"))
    damper_ground = graph.add_component(Damper("damper_ground", damping=5.0, name="Ground Damper"))
    spring_coupling = graph.add_component(Spring("spring_coupling", stiffness=8.0, name="Coupling Spring"))
    damper_coupling = graph.add_component(Damper("damper_coupling", damping=2.0, name="Coupling Damper"))
    source = graph.add_component(StepForce("input_force", amplitude=1.0))
    ground = graph.add_component(MechanicalGround("ground"))

    graph.connect(mass_1.port("port_a").id, spring_ground.port("port_a").id, label="m1_spring_ground")
    graph.connect(mass_1.port("port_a").id, damper_ground.port("port_a").id, label="m1_damper_ground")
    graph.connect(mass_1.port("port_a").id, spring_coupling.port("port_a").id, label="m1_spring_coupling")
    graph.connect(mass_1.port("port_a").id, damper_coupling.port("port_a").id, label="m1_damper_coupling")
    graph.connect(mass_1.port("port_a").id, source.port("port").id, label="m1_force")
    graph.connect(spring_ground.port("port_b").id, ground.port("port").id, label="spring_ground_ref")
    graph.connect(damper_ground.port("port_b").id, ground.port("port").id, label="damper_ground_ref")
    graph.connect(spring_coupling.port("port_b").id, mass_2.port("port_a").id, label="coupling_to_m2")
    graph.connect(damper_coupling.port("port_b").id, mass_2.port("port_a").id, label="damper_to_m2")
    graph.connect(mass_1.port("reference_port").id, ground.port("port").id, label="m1_reference")
    graph.connect(mass_2.port("reference_port").id, ground.port("port").id, label="m2_reference")
    graph.connect(source.port("reference_port").id, ground.port("port").id, label="source_reference")

    displacement_probe = graph.attach_probe(BaseProbe(
        "mass_1_displacement", "Mass 1 displacement", "displacement", mass_1.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "mass_2_displacement", "Mass 2 displacement", "displacement", mass_2.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(RelativeProbe(
        "relative_deflection", "Relative deflection", "displacement",
        mass_1.id, reference_component_id=mass_2.id,
        output_kind=OutputKind.STATE_RELATIVE, quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "mass_1_acceleration", "Mass 1 acceleration", "acceleration", mass_1.id,
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))

    graph.selected_input_id = source.id
    graph.selected_output_id = displacement_probe.id

    return TemplateDefinition(
        id="two_mass",
        name="Two-Mass System",
        graph=graph,
        default_input_id=source.id,
        default_output_id=displacement_probe.id,
        suggested_plots=["time_response", "step_response", "bode", "pole_zero"],
        description="Two-mass translational template with grounded and coupling spring-damper branches.",
        parameter_groups={
            "masses": [mass_1.id, mass_2.id],
            "ground_branch": [spring_ground.id, damper_ground.id],
            "coupling_branch": [spring_coupling.id, damper_coupling.id],
            "input": [source.id],
        },
        schematic_layout={
            "mass_1": (180.0, 90.0),
            "mass_2": (380.0, 90.0),
            "spring_ground": (140.0, 220.0),
            "damper_ground": (240.0, 220.0),
            "spring_coupling": (320.0, 170.0),
            "damper_coupling": (320.0, 260.0),
            "input_force": (60.0, 120.0),
            "ground": (250.0, 360.0),
        },
    )
