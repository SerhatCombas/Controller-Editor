"""Graph factory functions — replace deleted template build_*() in tests.

Each function builds a SystemGraph with the same topology, parameters,
and probes as the old template, so golden-value tests stay bit-for-bit
identical. The only difference: there is no TemplateDefinition wrapper.

Faz 5MVP-0: These exist solely for test backward-compat. They are NOT
templates and are NOT accessible from the UI.
"""
from __future__ import annotations

from app.core.graph.system_graph import SystemGraph
from app.core.models.electrical import (
    Capacitor,
    ElectricalGround,
    Inductor,
    Resistor,
    VoltageSource,
)
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring
from app.core.models.sources import StepForce
from app.core.probes import BaseProbe, RelativeProbe
from app.core.symbolic.output_kind import (
    OutputKind,
    QK_ACCELERATION,
    QK_CAPACITOR_VOLTAGE,
    QK_CURRENT,
    QK_DISPLACEMENT,
    QK_RELATIVE_DISPLACEMENT,
    QK_SPRING_FORCE,
    QK_VOLTAGE,
)
from app.core.templates.template_definition import TemplateDefinition


def build_single_mass_graph(
    *,
    mass: float = 2.0,
    stiffness: float = 10.0,
    damping: float = 3.0,
    force_amplitude: float = 1.0,
) -> SystemGraph:
    """1-DOF mass-spring-damper with force input.

    Matches old build_single_mass_template() topology exactly.
    """
    graph = SystemGraph()

    m = graph.add_component(Mass("mass", mass=mass))
    s = graph.add_component(Spring("spring", stiffness=stiffness))
    d = graph.add_component(Damper("damper", damping=damping))
    src = graph.add_component(StepForce("input_force", amplitude=force_amplitude))
    gnd = graph.add_component(MechanicalGround("ground"))

    graph.connect(m.port("port_a").id, s.port("port_a").id, label="mass_spring")
    graph.connect(m.port("port_a").id, d.port("port_a").id, label="mass_damper")
    graph.connect(m.port("port_a").id, src.port("port").id, label="mass_force")
    graph.connect(s.port("port_b").id, gnd.port("port").id, label="spring_ground")
    graph.connect(d.port("port_b").id, gnd.port("port").id, label="damper_ground")
    graph.connect(m.port("reference_port").id, gnd.port("port").id, label="mass_reference")
    graph.connect(src.port("reference_port").id, gnd.port("port").id, label="source_reference")

    disp_probe = graph.attach_probe(BaseProbe(
        "mass_displacement", "Mass displacement", "displacement", m.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "mass_acceleration", "Mass acceleration", "acceleration", m.id,
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))
    graph.attach_probe(BaseProbe(
        "spring_force", "Spring force", "force", s.id,
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_SPRING_FORCE,
    ))

    graph.selected_input_id = src.id
    graph.selected_output_id = disp_probe.id
    return graph


def build_single_mass_template_def(
    **kwargs,
) -> TemplateDefinition:
    """TemplateDefinition wrapper for single mass — used by tests that need it."""
    graph = build_single_mass_graph(**kwargs)
    return TemplateDefinition(
        id="single_mass",
        name="Single Mass-Spring-Damper",
        graph=graph,
        default_input_id="input_force",
        default_output_id="mass_displacement",
        suggested_plots=["time_response", "step_response", "bode", "pole_zero"],
        description="Single mass connected to ground with spring and damper.",
        schematic_layout={
            "mass": (220.0, 100.0),
            "spring": (160.0, 220.0),
            "damper": (280.0, 220.0),
            "input_force": (80.0, 160.0),
            "ground": (220.0, 340.0),
        },
    )


def build_two_mass_graph(
    *,
    m1: float = 2.0,
    m2: float = 1.0,
    k_ground: float = 20.0,
    d_ground: float = 5.0,
    k_coupling: float = 8.0,
    d_coupling: float = 2.0,
    force_amplitude: float = 1.0,
) -> SystemGraph:
    """2-DOF two-mass system with force input on mass_1.

    Topology (matches old build_two_mass_template() exactly):
      mass_1 ─┬─ spring_ground ─── ground
              ├─ damper_ground ─── ground
              ├─ spring_coupling ─ mass_2
              ├─ damper_coupling ─ mass_2
              └─ force_source

    Note: ground spring/damper attach to mass_1, NOT mass_2.
    """
    graph = SystemGraph()

    mass_1 = graph.add_component(Mass("mass_1", mass=m1, name="Mass 1"))
    mass_2 = graph.add_component(Mass("mass_2", mass=m2, name="Mass 2"))
    spring_ground = graph.add_component(Spring("spring_ground", stiffness=k_ground, name="Ground Spring"))
    damper_ground = graph.add_component(Damper("damper_ground", damping=d_ground, name="Ground Damper"))
    spring_coupling = graph.add_component(Spring("spring_coupling", stiffness=k_coupling, name="Coupling Spring"))
    damper_coupling = graph.add_component(Damper("damper_coupling", damping=d_coupling, name="Coupling Damper"))
    src = graph.add_component(StepForce("input_force", amplitude=force_amplitude))
    gnd = graph.add_component(MechanicalGround("ground"))

    # mass_1 connects to ground branch AND coupling branch
    graph.connect(mass_1.port("port_a").id, spring_ground.port("port_a").id, label="m1_spring_ground")
    graph.connect(mass_1.port("port_a").id, damper_ground.port("port_a").id, label="m1_damper_ground")
    graph.connect(mass_1.port("port_a").id, spring_coupling.port("port_a").id, label="m1_spring_coupling")
    graph.connect(mass_1.port("port_a").id, damper_coupling.port("port_a").id, label="m1_damper_coupling")
    graph.connect(mass_1.port("port_a").id, src.port("port").id, label="m1_force")
    # ground branch to ground reference
    graph.connect(spring_ground.port("port_b").id, gnd.port("port").id, label="spring_ground_ref")
    graph.connect(damper_ground.port("port_b").id, gnd.port("port").id, label="damper_ground_ref")
    # coupling branch to mass_2
    graph.connect(spring_coupling.port("port_b").id, mass_2.port("port_a").id, label="coupling_to_m2")
    graph.connect(damper_coupling.port("port_b").id, mass_2.port("port_a").id, label="damper_to_m2")
    # reference ports
    graph.connect(mass_1.port("reference_port").id, gnd.port("port").id, label="m1_ref")
    graph.connect(mass_2.port("reference_port").id, gnd.port("port").id, label="m2_ref")
    graph.connect(src.port("reference_port").id, gnd.port("port").id, label="src_ref")

    disp_probe = graph.attach_probe(BaseProbe(
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

    graph.selected_input_id = src.id
    graph.selected_output_id = disp_probe.id
    return graph


def build_two_mass_template_def(**kwargs) -> TemplateDefinition:
    """TemplateDefinition wrapper for two mass — used by tests that need it."""
    graph = build_two_mass_graph(**kwargs)
    return TemplateDefinition(
        id="two_mass",
        name="Two-Mass System",
        graph=graph,
        default_input_id="input_force",
        default_output_id="mass_1_displacement",
        suggested_plots=["time_response", "step_response", "bode", "pole_zero"],
        description="Two-mass system with coupling and grounding.",
        schematic_layout={
            "mass_1": (214.0, 100.0),
            "mass_2": (214.0, 400.0),
            "spring_coupling": (200.0, 222.0),
            "damper_coupling": (320.0, 222.0),
            "spring_ground": (200.0, 522.0),
            "damper_ground": (320.0, 522.0),
            "input_force": (60.0, 100.0),
            "ground": (170.0, 700.0),
        },
    )


def build_rlc_circuit_graph(
    *,
    voltage: float = 10.0,
    resistance: float = 10.0,
    inductance: float = 0.5,
    capacitance: float = 1e-3,
) -> SystemGraph:
    """RLC series circuit graph."""
    graph = SystemGraph()

    source = graph.add_component(VoltageSource("v_source", V=voltage, name="Step Voltage"))
    resistor = graph.add_component(Resistor("resistor", R=resistance, name="Resistor"))
    inductor = graph.add_component(Inductor("inductor", L=inductance, name="Inductor"))
    capacitor = graph.add_component(Capacitor("capacitor", C=capacitance, name="Capacitor"))
    ground = graph.add_component(ElectricalGround("ground"))

    graph.connect(source.port("port_a").id, resistor.port("port_a").id, label="source_to_resistor")
    graph.connect(resistor.port("port_b").id, inductor.port("port_a").id, label="resistor_to_inductor")
    graph.connect(inductor.port("port_b").id, capacitor.port("port_a").id, label="inductor_to_capacitor")
    graph.connect(capacitor.port("port_b").id, ground.port("p").id, label="capacitor_to_ground")
    graph.connect(source.port("port_b").id, ground.port("p").id, label="source_to_ground")

    current_probe = graph.attach_probe(BaseProbe(
        "loop_current", "Loop current", "current", inductor.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_CURRENT,
    ))
    graph.attach_probe(BaseProbe(
        "capacitor_voltage", "Capacitor voltage", "voltage", capacitor.id,
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_CAPACITOR_VOLTAGE,
    ))
    graph.attach_probe(BaseProbe(
        "resistor_voltage", "Resistor voltage", "voltage", resistor.id,
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_VOLTAGE,
    ))

    graph.selected_input_id = source.id
    graph.selected_output_id = current_probe.id
    return graph


def build_rlc_circuit_template_def(**kwargs) -> TemplateDefinition:
    """TemplateDefinition wrapper for RLC — used by tests that need it."""
    graph = build_rlc_circuit_graph(**kwargs)
    return TemplateDefinition(
        id="rlc_circuit",
        name="RLC Series Circuit",
        graph=graph,
        default_input_id="v_source",
        default_output_id="loop_current",
        suggested_plots=["time_response", "step_response", "bode"],
        description="RLC series circuit built from basic components.",
        schematic_layout={
            "v_source": (60.0, 200.0),
            "resistor": (220.0, 80.0),
            "inductor": (390.0, 80.0),
            "capacitor": (520.0, 200.0),
            "ground": (250.0, 380.0),
        },
    )
