"""Minimal wheel-road fixture — replaces build_quarter_car_template() in tests.

Strategy A (Faz 5MVP-0): a lightweight 2-DOF system with Wheel + RandomRoad
that exercises the same physics pipeline the quarter-car template used to,
without coupling tests to a hardcoded template.

Topology:
    Body Mass (300 kg)
      ├─ Suspension Spring (15000 N/m) ─┐
      ├─ Suspension Damper (1200 N·s/m) ─┤
      └─ Body Force Source ──────────────│
    Wheel (40 kg, contact_stiffness=180000 N/m)
      └─ road_contact_port → RandomRoad
    Ground (reference)

Parameters match the old quarter_car template exactly so golden-value tests
stay bit-for-bit identical without any template dependency.
"""
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


def build_wheel_road_graph(
    *,
    body_mass: float = 300.0,
    wheel_mass: float = 40.0,
    suspension_stiffness: float = 15000.0,
    suspension_damping: float = 1200.0,
    contact_stiffness: float = 180000.0,
    contact_damping: float = 0.0,
    road_amplitude: float = 0.03,
    road_roughness: float = 0.35,
    road_seed: int = 7,
    road_speed: float = 6.0,
    road_dt: float = 0.01,
    road_duration: float = 15.0,
    body_force_amplitude: float = 0.0,
) -> SystemGraph:
    """Build a 2-DOF wheel-road system graph.

    Returns a fully-connected SystemGraph with probes attached.
    Parameters default to the old quarter-car values for backward
    compatibility with golden tests.
    """
    graph = SystemGraph()

    body = graph.add_component(Mass("body_mass", mass=body_mass, name="Body Mass"))
    wheel = graph.add_component(Wheel(
        "wheel_mass", mass=wheel_mass, name="Wheel / Unsprung Mass",
        contact_stiffness=contact_stiffness, contact_damping=contact_damping,
    ))
    susp_spring = graph.add_component(
        Spring("suspension_spring", stiffness=suspension_stiffness)
    )
    susp_damper = graph.add_component(
        Damper("suspension_damper", damping=suspension_damping)
    )
    road = graph.add_component(RandomRoad(
        "road_source",
        amplitude=road_amplitude,
        roughness=road_roughness,
        seed=road_seed,
        vehicle_speed=road_speed,
        dt=road_dt,
        duration=road_duration,
    ))
    force = graph.add_component(StepForce(
        "body_force",
        amplitude=body_force_amplitude,
        start_time=0.0,
        name="Body Force Source",
    ))
    ground = graph.add_component(MechanicalGround("ground"))

    # Connections — identical topology to old quarter_car.py
    graph.connect(body.port("port_a").id, susp_spring.port("port_a").id, label="body_to_spring")
    graph.connect(body.port("port_a").id, susp_damper.port("port_a").id, label="body_to_damper")
    graph.connect(wheel.port("port_a").id, susp_spring.port("port_b").id, label="wheel_to_spring")
    graph.connect(wheel.port("port_a").id, susp_damper.port("port_b").id, label="wheel_to_damper")
    graph.connect(wheel.port("road_contact_port").id, road.port("port").id, label="wheel_to_road")
    graph.connect(body.port("reference_port").id, ground.port("port").id, label="body_reference")
    graph.connect(wheel.port("reference_port").id, ground.port("port").id, label="wheel_reference")
    graph.connect(road.port("reference_port").id, ground.port("port").id, label="road_reference")
    graph.connect(body.port("port_a").id, force.port("port").id, label="body_force_input")
    graph.connect(force.port("reference_port").id, wheel.port("port_a").id, label="body_force_reference")

    # Probes — same IDs as old quarter_car template
    body_probe = graph.attach_probe(BaseProbe(
        "body_displacement", "Body displacement", "displacement", body.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "wheel_displacement", "Wheel displacement", "displacement", wheel.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "body_acceleration", "Body acceleration", "acceleration", body.id,
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))
    graph.attach_probe(BaseProbe(
        "suspension_force", "Suspension force", "force", susp_spring.id,
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_SPRING_FORCE,
    ))
    graph.attach_probe(RelativeProbe(
        id="suspension_deflection",
        name="Suspension deflection",
        quantity="displacement",
        target_component_id=body.id,
        reference_component_id=wheel.id,
        output_kind=OutputKind.STATE_RELATIVE,
        quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))
    graph.attach_probe(RelativeProbe(
        id="tire_deflection",
        name="Tire deflection",
        quantity="displacement",
        target_component_id=wheel.id,
        reference_component_id=road.id,
        output_kind=OutputKind.STATE_RELATIVE,
        quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))

    graph.selected_input_id = road.id
    graph.selected_output_id = body_probe.id

    return graph


def build_wheel_road_2dof() -> SystemGraph:
    """Convenience: default-parameter 2-DOF wheel-road system.

    Drop-in replacement for tests that called build_quarter_car_template().graph.
    """
    return build_wheel_road_graph()
