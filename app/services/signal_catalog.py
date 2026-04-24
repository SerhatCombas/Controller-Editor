from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SimulationSignalDefinition:
    signal_id: str
    label: str
    channel_id: str | None = None
    color: str | None = None
    unit: str = ""
    profiles: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class TemplateSignalCatalog:
    template_id: str
    label: str
    inputs: tuple[SimulationSignalDefinition, ...]
    outputs: tuple[SimulationSignalDefinition, ...]


@dataclass(frozen=True, slots=True)
class SceneSignalBinding:
    component_id: str
    signal_id: str
    label: str
    runtime_driving: bool = False
    analysis_supported: bool = False


TEMPLATE_SIGNAL_CATALOGS: dict[str, TemplateSignalCatalog] = {
    "quarter_car": TemplateSignalCatalog(
        template_id="quarter_car",
        label="Quarter-Car Suspension",
        inputs=(
            SimulationSignalDefinition(
                signal_id="road",
                label="Road disturbance h(t)",
                channel_id="road_displacement",
                profiles=(("random", "Random road input"), ("sine", "Sine road input"), ("step", "Step bump input")),
            ),
            SimulationSignalDefinition(
                signal_id="body_force",
                label="External force F(t)",
                channel_id="body_force",
                profiles=(("constant", "Constant external force"), ("step", "Step input"), ("sine", "Sinusoidal input")),
            ),
            SimulationSignalDefinition(
                signal_id="wheel_displacement",
                label="Wheel displacement x_w(t) (analysis candidate)",
            ),
        ),
        outputs=(
            SimulationSignalDefinition("body_displacement", "Body displacement", color="#0b84f3", unit="m"),
            SimulationSignalDefinition("wheel_displacement", "Wheel displacement", color="#ef6c00", unit="m"),
            SimulationSignalDefinition("suspension_deflection", "Suspension deflection", color="#2e7d32", unit="m"),
            SimulationSignalDefinition("body_acceleration", "Body acceleration", color="#7b1fa2", unit="m/s²"),
            SimulationSignalDefinition("tire_deflection", "Tire deflection", color="#c62828", unit="m"),
        ),
    ),
    "single_mass": TemplateSignalCatalog(
        template_id="single_mass",
        label="Single Mass-Spring-Damper",
        inputs=(
            SimulationSignalDefinition(
                signal_id="body_force",
                label="External force F(t)",
                channel_id="body_force",
                profiles=(("constant", "Constant external force"), ("step", "Step input"), ("sine", "Sinusoidal input")),
            ),
        ),
        outputs=(
            SimulationSignalDefinition("mass_displacement", "Mass displacement", color="#0b84f3", unit="m"),
            SimulationSignalDefinition("mass_velocity", "Mass velocity", color="#ef6c00", unit="m/s"),
            SimulationSignalDefinition("body_acceleration", "Mass acceleration", color="#2e7d32", unit="m/s²"),
        ),
    ),
    "two_mass": TemplateSignalCatalog(
        template_id="two_mass",
        label="Two-Mass System",
        inputs=(
            SimulationSignalDefinition(
                signal_id="body_force",
                label="External force F(t)",
                channel_id="body_force",
                profiles=(("constant", "Constant external force"), ("step", "Step input"), ("sine", "Sinusoidal input")),
            ),
        ),
        outputs=(
            SimulationSignalDefinition("mass_1_displacement", "Mass 1 displacement", color="#0b84f3", unit="m"),
            SimulationSignalDefinition("mass_2_displacement", "Mass 2 displacement", color="#ef6c00", unit="m"),
            SimulationSignalDefinition("relative_deflection", "Relative displacement", color="#2e7d32", unit="m"),
        ),
    ),
    "blank": TemplateSignalCatalog(
        template_id="blank",
        label="Blank Workspace",
        inputs=(),
        outputs=(),
    ),
}


def signal_catalog_for_template(template_id: str) -> TemplateSignalCatalog:
    return TEMPLATE_SIGNAL_CATALOGS.get(template_id, TEMPLATE_SIGNAL_CATALOGS["blank"])


def available_inputs(template_id: str) -> tuple[SimulationSignalDefinition, ...]:
    return signal_catalog_for_template(template_id).inputs


def available_outputs(template_id: str) -> tuple[SimulationSignalDefinition, ...]:
    return signal_catalog_for_template(template_id).outputs


def input_definition(template_id: str, signal_id: str | None) -> SimulationSignalDefinition | None:
    if signal_id is None:
        return None
    for definition in available_inputs(template_id):
        if definition.signal_id == signal_id:
            return definition
    return None


def output_definition(template_id: str, signal_id: str) -> SimulationSignalDefinition | None:
    for definition in available_outputs(template_id):
        if definition.signal_id == signal_id:
            return definition
    return None


def component_to_input_signal(
    template_id: str,
    *,
    component_id: str,
    component_type_key: str,
) -> SceneSignalBinding | None:
    binding: SceneSignalBinding | None = None
    if template_id == "quarter_car":
        if component_type_key == "mechanical_random_reference":
            definition = input_definition(template_id, "road")
            if definition is not None:
                binding = SceneSignalBinding(component_id=component_id, signal_id=definition.signal_id, label=definition.label, runtime_driving=True, analysis_supported=True)
        elif component_type_key == "ideal_force_source":
            definition = input_definition(template_id, "body_force")
            if definition is not None:
                binding = SceneSignalBinding(component_id=component_id, signal_id=definition.signal_id, label=definition.label, runtime_driving=True, analysis_supported=True)
        elif component_type_key == "wheel":
            definition = input_definition(template_id, "wheel_displacement")
            if definition is not None:
                binding = SceneSignalBinding(component_id=component_id, signal_id=definition.signal_id, label=definition.label, runtime_driving=False, analysis_supported=False)
    elif template_id in {"single_mass", "two_mass"}:
        if component_type_key == "ideal_force_source":
            definition = input_definition(template_id, "body_force")
            if definition is not None:
                binding = SceneSignalBinding(component_id=component_id, signal_id=definition.signal_id, label=definition.label, runtime_driving=True, analysis_supported=True)
    return binding


def component_to_output_signal(
    template_id: str,
    *,
    component_id: str,
    component_type_key: str,
    scene_components: tuple[tuple[str, str], ...],
) -> SceneSignalBinding | None:
    signal_id: str | None = None
    if template_id == "quarter_car":
        if component_type_key == "mass":
            signal_id = "body_displacement"
        elif component_type_key == "wheel":
            signal_id = "wheel_displacement"
        elif component_type_key == "translational_spring":
            signal_id = "suspension_deflection"
        elif component_type_key == "tire_stiffness":
            signal_id = "tire_deflection"
    elif template_id == "single_mass":
        if component_type_key == "mass":
            signal_id = "mass_displacement"
    elif template_id == "two_mass":
        if component_type_key == "mass":
            signal_id = _two_mass_signal_id(component_id, scene_components)
        elif component_type_key == "translational_spring" and "coupling" in component_id:
            signal_id = "relative_deflection"
    if signal_id is None:
        return None
    definition = output_definition(template_id, signal_id)
    if definition is None:
        return None
    return SceneSignalBinding(component_id=component_id, signal_id=definition.signal_id, label=definition.label)


def can_component_be_input(
    template_id: str,
    *,
    component_id: str,
    component_type_key: str,
) -> bool:
    return component_to_input_signal(
        template_id,
        component_id=component_id,
        component_type_key=component_type_key,
    ) is not None


def can_component_be_output(
    template_id: str,
    *,
    component_id: str,
    component_type_key: str,
    scene_components: tuple[tuple[str, str], ...],
) -> bool:
    return component_to_output_signal(
        template_id,
        component_id=component_id,
        component_type_key=component_type_key,
        scene_components=scene_components,
    ) is not None


def _two_mass_signal_id(component_id: str, scene_components: tuple[tuple[str, str], ...]) -> str | None:
    if component_id == "mass_1":
        return "mass_1_displacement"
    if component_id == "mass_2":
        return "mass_2_displacement"
    masses = [item_id for item_id, type_key in scene_components if type_key == "mass"]
    if component_id not in masses:
        return None
    rank = masses.index(component_id)
    if rank == 0:
        return "mass_1_displacement"
    if rank == 1:
        return "mass_2_displacement"
    return None
