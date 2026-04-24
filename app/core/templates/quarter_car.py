from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring, Wheel
from app.core.models.sources import RandomRoad, StepForce
from app.core.probes import BaseProbe, RelativeProbe
from app.core.symbolic.output_kind import (
    OutputKind,
    QK_ACCELERATION,
    QK_DISPLACEMENT,
    QK_RELATIVE_DISPLACEMENT,
    QK_SPRING_FORCE,
)
from app.core.templates.template_definition import TemplateDefinition


def build_quarter_car_template() -> TemplateDefinition:
    graph = SystemGraph()

    body_mass = graph.add_component(Mass("body_mass", mass=300.0, name="Body Mass"))
    wheel_mass = graph.add_component(Wheel("wheel_mass", mass=40.0, name="Wheel / Unsprung Mass"))
    suspension_spring = graph.add_component(Spring("suspension_spring", stiffness=15000.0))
    suspension_damper = graph.add_component(Damper("suspension_damper", damping=1200.0))
    tire_stiffness = graph.add_component(Spring("tire_stiffness", stiffness=180000.0, name="Tire Stiffness"))
    road = graph.add_component(
        RandomRoad(
            "road_source",
            amplitude=0.03,
            roughness=0.35,
            seed=7,
            vehicle_speed=6.0,
            dt=0.01,
            duration=15.0,
        )
    )
    body_force = graph.add_component(
        StepForce(
            "body_force",
            amplitude=0.0,
            start_time=0.0,
            name="Body Force Source",
        )
    )
    ground = graph.add_component(MechanicalGround("ground"))

    graph.connect(body_mass.port("port_a").id, suspension_spring.port("port_a").id, label="body_to_spring")
    graph.connect(body_mass.port("port_a").id, suspension_damper.port("port_a").id, label="body_to_damper")
    graph.connect(wheel_mass.port("port_a").id, suspension_spring.port("port_b").id, label="wheel_to_spring")
    graph.connect(wheel_mass.port("port_a").id, suspension_damper.port("port_b").id, label="wheel_to_damper")
    graph.connect(wheel_mass.port("port_a").id, tire_stiffness.port("port_a").id, label="wheel_to_tire")
    graph.connect(tire_stiffness.port("port_b").id, road.port("port").id, label="tire_to_road")
    graph.connect(body_mass.port("reference_port").id, ground.port("port").id, label="body_reference")
    graph.connect(wheel_mass.port("reference_port").id, ground.port("port").id, label="wheel_reference")
    graph.connect(road.port("reference_port").id, ground.port("port").id, label="road_reference")
    graph.connect(body_mass.port("port_a").id, body_force.port("port").id, label="body_force_input")
    graph.connect(body_force.port("reference_port").id, wheel_mass.port("port_a").id, label="body_force_reference")

    body_probe = graph.attach_probe(BaseProbe(
        "body_displacement", "Body displacement", "displacement", body_mass.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "wheel_displacement", "Wheel displacement", "displacement", wheel_mass.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "body_acceleration", "Body acceleration", "acceleration", body_mass.id,
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))
    graph.attach_probe(BaseProbe(
        "suspension_force", "Suspension force", "force", suspension_spring.id,
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_SPRING_FORCE,
    ))
    graph.attach_probe(RelativeProbe(
        id="suspension_deflection",
        name="Suspension deflection",
        quantity="displacement",
        target_component_id=body_mass.id,
        reference_component_id=wheel_mass.id,
        output_kind=OutputKind.STATE_RELATIVE,
        quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))
    graph.attach_probe(RelativeProbe(
        id="tire_deflection",
        name="Tire deflection",
        quantity="displacement",
        target_component_id=wheel_mass.id,
        reference_component_id=road.id,
        # Intent: STATE_RELATIVE, but unsupported until D-feedthrough is handled
        output_kind=OutputKind.STATE_RELATIVE,
        quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))

    graph.selected_input_id = road.id
    graph.selected_output_id = body_probe.id

    return TemplateDefinition(
        id="quarter_car",
        name="Quarter-Car Suspension",
        graph=graph,
        default_input_id=road.id,
        default_output_id=body_probe.id,
        suggested_plots=["time_response", "step_response", "bode", "pole_zero"],
        description="Ready-made quarter-car suspension template built from reusable graph components.",
        parameter_groups={
            "masses": [body_mass.id, wheel_mass.id],
            "suspension": [suspension_spring.id, suspension_damper.id],
            "road": [road.id],
            "inputs": [body_force.id],
        },
        schematic_layout={
            "body_mass": (250.0, 90.0),
            "suspension_spring": (180.0, 190.0),
            "suspension_damper": (320.0, 190.0),
            "body_force": (70.0, 120.0),
            "wheel_mass": (250.0, 330.0),
            "tire_stiffness": (250.0, 455.0),
            "road_source": (120.0, 455.0),
            "ground": (250.0, 545.0),
        },
        warnings=[
            "Phase 1.5 idea: allow limited topology edits on top of this template before full free-form editing."
        ],
    )
