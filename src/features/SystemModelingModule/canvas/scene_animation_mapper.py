from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from PySide6.QtCore import QPointF, QRectF

from src.features.SystemModelingModule.canvas.component_system import CanvasVisualComponent, CanvasWireConnection, Orientation


@dataclass(frozen=True, slots=True)
class SceneAnimationContext:
    template_id: str
    components: tuple[CanvasVisualComponent, ...]
    wires: tuple[CanvasWireConnection, ...]
    animation: dict[str, object]


@dataclass(frozen=True, slots=True)
class ComponentVisualOverride:
    rect: QRectF


@dataclass(frozen=True, slots=True)
class SceneAnimationResult:
    component_overrides: dict[str, ComponentVisualOverride] = field(default_factory=dict)
    road_owner_component_id: str | None = None


def infer_workspace_template(
    components: Iterable[CanvasVisualComponent],
    wires: Iterable[CanvasWireConnection],
) -> str:
    component_list = list(components)
    wire_list = list(wires)
    if not component_list:
        return "blank"

    by_type: dict[str, list[CanvasVisualComponent]] = {}
    for component in component_list:
        by_type.setdefault(component.spec.type_key, []).append(component)

    masses = by_type.get("mass", [])
    springs = by_type.get("translational_spring", [])
    dampers = by_type.get("translational_damper", [])
    wheels = by_type.get("wheel", [])
    tires = by_type.get("tire_stiffness", [])
    random_refs = by_type.get("mechanical_random_reference", [])
    grounds = by_type.get("mechanical_reference", [])

    if random_refs and wheels and tires and masses and (springs or dampers):
        return "quarter_car"
    if len(masses) >= 2 and grounds and (len(springs) + len(dampers) >= 2):
        return "two_mass"
    if len(masses) == 1 and grounds and (springs or dampers) and not wheels:
        return "single_mass"
    if wire_list and random_refs and wheels:
        return "quarter_car"
    return "blank"


class SceneAnimationMapper:
    def map(self, context: SceneAnimationContext) -> SceneAnimationResult:
        template_id = context.template_id
        inferred_template = infer_workspace_template(context.components, context.wires)
        if template_id == "blank":
            template_id = inferred_template

        outputs = self._runtime_outputs(context.animation)
        if template_id == "quarter_car":
            return self._map_quarter_car_like(context, outputs)
        if template_id == "single_mass":
            return self._map_single_mass(context, outputs)
        if template_id == "two_mass":
            return self._map_two_mass(context, outputs)
        return SceneAnimationResult()

    def _runtime_outputs(self, animation: dict[str, object]) -> dict[str, float]:
        raw = animation.get("runtime_outputs")
        if not isinstance(raw, dict):
            return {}
        normalized: dict[str, float] = {}
        for key, value in raw.items():
            try:
                normalized[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return normalized

    def _map_quarter_car_like(
        self,
        context: SceneAnimationContext,
        outputs: dict[str, float],
    ) -> SceneAnimationResult:
        body_disp = outputs.get("body_displacement", self._float(context.animation, "body_displacement"))
        wheel_disp = outputs.get("wheel_displacement", self._float(context.animation, "wheel_displacement"))
        overrides: dict[str, ComponentVisualOverride] = {}

        road_owner = next(
            (component.component_id for component in context.components if component.spec.type_key == "mechanical_random_reference"),
            None,
        )
        wheel = next((component for component in context.components if component.spec.type_key == "wheel"), None)
        masses = [component for component in context.components if component.spec.type_key == "mass"]
        springs = [component for component in context.components if component.spec.type_key == "translational_spring"]
        dampers = [component for component in context.components if component.spec.type_key == "translational_damper"]
        tires = [component for component in context.components if component.spec.type_key == "tire_stiffness"]

        for mass in self._sort_components_along_primary_axis(masses):
            overrides[mass.component_id] = ComponentVisualOverride(
                rect=self._translated_rest_rect(mass, body_disp * 1500.0)
            )
        if wheel is not None:
            overrides[wheel.component_id] = ComponentVisualOverride(
                rect=self._translated_rest_rect(wheel, wheel_disp * 1300.0)
            )
        overrides = self._enforce_rigid_non_overlap(context.components, overrides)

        anchor_overrides = self._deformable_overrides(context.components, context.wires, overrides)
        overrides.update(anchor_overrides)

        for tire in tires:
            if road_owner is None:
                continue
            tire_override = self._deformable_override_for_component(tire, context.components, context.wires, overrides)
            if tire_override is not None:
                overrides[tire.component_id] = tire_override

        return SceneAnimationResult(component_overrides=overrides, road_owner_component_id=road_owner)

    def _map_single_mass(
        self,
        context: SceneAnimationContext,
        outputs: dict[str, float],
    ) -> SceneAnimationResult:
        displacement = outputs.get("mass_displacement", outputs.get("body_displacement", 0.0))
        overrides: dict[str, ComponentVisualOverride] = {}
        mass = next((component for component in context.components if component.spec.type_key == "mass"), None)
        if mass is not None:
            overrides[mass.component_id] = ComponentVisualOverride(
                rect=self._translated_rest_rect(mass, displacement * 1500.0)
            )
        overrides = self._enforce_rigid_non_overlap(context.components, overrides)
        overrides.update(self._deformable_overrides(context.components, context.wires, overrides))
        return SceneAnimationResult(component_overrides=overrides)

    def _map_two_mass(
        self,
        context: SceneAnimationContext,
        outputs: dict[str, float],
    ) -> SceneAnimationResult:
        overrides: dict[str, ComponentVisualOverride] = {}
        masses = self._sort_components_along_primary_axis(
            [component for component in context.components if component.spec.type_key == "mass"]
        )
        displacements = [
            outputs.get("mass_1_displacement", outputs.get("body_displacement", 0.0)),
            outputs.get("mass_2_displacement", outputs.get("wheel_displacement", 0.0)),
        ]
        for component, displacement in zip(masses[:2], displacements):
            overrides[component.component_id] = ComponentVisualOverride(
                rect=self._translated_rest_rect(component, displacement * 1500.0)
            )
        overrides = self._enforce_rigid_non_overlap(context.components, overrides)
        overrides.update(self._deformable_overrides(context.components, context.wires, overrides))
        return SceneAnimationResult(component_overrides=overrides)

    def _deformable_overrides(
        self,
        components: tuple[CanvasVisualComponent, ...],
        wires: tuple[CanvasWireConnection, ...],
        rigid_overrides: dict[str, ComponentVisualOverride],
    ) -> dict[str, ComponentVisualOverride]:
        overrides: dict[str, ComponentVisualOverride] = {}
        for component in components:
            if not component.supports_deformation():
                continue
            override = self._deformable_override_for_component(component, components, wires, {**rigid_overrides, **overrides})
            if override is not None:
                overrides[component.component_id] = override
        return overrides

    def _deformable_override_for_component(
        self,
        component: CanvasVisualComponent,
        components: tuple[CanvasVisualComponent, ...],
        wires: tuple[CanvasWireConnection, ...],
        overrides: dict[str, ComponentVisualOverride],
    ) -> ComponentVisualOverride | None:
        if len(component.spec.connector_ports) < 2:
            return None
        ports = list(component.spec.connector_ports[:2])
        rest_rect = self._base_rect(component)
        rest_connectors = {port.name: point for port, point in component.transformed_connector_ports(rest_rect)}
        moved_anchors: dict[str, QPointF] = {}
        for port in ports:
            port_name = port.name
            anchor = self._connected_anchor_for(component, port_name, components, wires, overrides)
            if anchor is None:
                return None
            moved_anchors[port_name] = anchor
        return ComponentVisualOverride(rect=self._rect_from_rest_pose(component, ports, rest_rect, rest_connectors, moved_anchors))

    def _connected_anchor_for(
        self,
        component: CanvasVisualComponent,
        port_name: str,
        components: tuple[CanvasVisualComponent, ...],
        wires: tuple[CanvasWireConnection, ...],
        overrides: dict[str, ComponentVisualOverride],
    ) -> QPointF | None:
        for wire in wires:
            if wire.source_component_id == component.component_id and wire.source_connector_name == port_name:
                return self._connector_center_for(wire.target_component_id, wire.target_connector_name, components, overrides)
            if wire.target_component_id == component.component_id and wire.target_connector_name == port_name:
                return self._connector_center_for(wire.source_component_id, wire.source_connector_name, components, overrides)
        return None

    def _connector_center_for(
        self,
        component_id: str,
        connector_name: str,
        components: tuple[CanvasVisualComponent, ...],
        overrides: dict[str, ComponentVisualOverride],
    ) -> QPointF | None:
        component = next((item for item in components if item.component_id == component_id), None)
        if component is None:
            return None
        rect = overrides.get(component_id, ComponentVisualOverride(self._base_rect(component))).rect
        for port, point in component.transformed_connector_ports(rect):
            if port.name == connector_name:
                return point
        return None

    def _rect_from_rest_pose(
        self,
        component: CanvasVisualComponent,
        ports: list,
        rest_rect: QRectF,
        rest_connectors: dict[str, QPointF],
        moved_anchors: dict[str, QPointF],
    ) -> QRectF:
        first_port, second_port = ports[0], ports[1]
        first_rest = rest_connectors[first_port.name]
        second_rest = rest_connectors[second_port.name]
        first_moved = moved_anchors[first_port.name]
        second_moved = moved_anchors[second_port.name]

        if component.orientation in {Orientation.DEG_90, Orientation.DEG_270}:
            first_delta_x = first_moved.x() - first_rest.x()
            second_delta_x = second_moved.x() - second_rest.x()
            left = rest_rect.left() + first_delta_x
            right = rest_rect.right() + second_delta_x
            if right < left:
                left, right = right, left
            minimum_length = self._minimum_deformable_extent(rest_rect.width())
            if right - left < minimum_length:
                right = left + minimum_length
            return QRectF(
                left,
                rest_rect.top(),
                max(right - left, 1.0),
                rest_rect.height(),
            )

        first_delta_y = first_moved.y() - first_rest.y()
        second_delta_y = second_moved.y() - second_rest.y()
        top = rest_rect.top() + first_delta_y
        bottom = rest_rect.bottom() + second_delta_y
        if bottom < top:
            top, bottom = bottom, top
        minimum_length = self._minimum_deformable_extent(rest_rect.height())
        if bottom - top < minimum_length:
            bottom = top + minimum_length
        return QRectF(
            rest_rect.left(),
            top,
            rest_rect.width(),
            max(bottom - top, 1.0),
        )

    def _translated_rest_rect(self, component: CanvasVisualComponent, delta_primary: float) -> QRectF:
        base = self._base_rect(component)
        if component.orientation in {Orientation.DEG_90, Orientation.DEG_270}:
            return base.translated(delta_primary, 0.0)
        return base.translated(0.0, delta_primary)

    def _base_rect(self, component: CanvasVisualComponent) -> QRectF:
        return QRectF(component.position.x(), component.position.y(), component.size[0], component.size[1])

    def _enforce_rigid_non_overlap(
        self,
        components: tuple[CanvasVisualComponent, ...],
        overrides: dict[str, ComponentVisualOverride],
    ) -> dict[str, ComponentVisualOverride]:
        constrained = dict(overrides)
        rigid_components = self._sort_components_along_primary_axis(
            [
                component
                for component in components
                if component.spec.type_key in {"mass", "wheel", "mechanical_reference"}
            ]
        )
        if len(rigid_components) < 2:
            return constrained

        for _ in range(3):
            changed = False
            for upper, lower in zip(rigid_components, rigid_components[1:]):
                upper_rect = constrained.get(upper.component_id, ComponentVisualOverride(self._base_rect(upper))).rect
                lower_rect = constrained.get(lower.component_id, ComponentVisualOverride(self._base_rect(lower))).rect
                minimum_gap = self._minimum_gap_between(upper, lower)
                overlap = upper_rect.bottom() + minimum_gap - lower_rect.top()
                if overlap <= 0.0:
                    continue
                upper_dynamic = upper.component_id in constrained
                lower_dynamic = lower.component_id in constrained
                if lower_dynamic and not upper_dynamic:
                    shifted = QRectF(lower_rect)
                    shifted.moveTop(lower_rect.top() + overlap)
                    constrained[lower.component_id] = ComponentVisualOverride(shifted)
                    changed = True
                    continue
                if upper_dynamic and not lower_dynamic:
                    shifted = QRectF(upper_rect)
                    shifted.moveTop(upper_rect.top() - overlap)
                    constrained[upper.component_id] = ComponentVisualOverride(shifted)
                    changed = True
                    continue
                if upper_dynamic and lower_dynamic:
                    upper_shift = overlap * 0.5
                    lower_shift = overlap - upper_shift
                    shifted_upper = QRectF(upper_rect)
                    shifted_lower = QRectF(lower_rect)
                    shifted_upper.moveTop(upper_rect.top() - upper_shift)
                    shifted_lower.moveTop(lower_rect.top() + lower_shift)
                    constrained[upper.component_id] = ComponentVisualOverride(shifted_upper)
                    constrained[lower.component_id] = ComponentVisualOverride(shifted_lower)
                    changed = True
            if not changed:
                break
        return constrained

    def _minimum_gap_between(self, upper: CanvasVisualComponent, lower: CanvasVisualComponent) -> float:
        upper_rect = self._base_rect(upper)
        lower_rect = self._base_rect(lower)
        rest_gap = lower_rect.top() - upper_rect.bottom()
        if rest_gap <= 0.0:
            return 24.0
        return max(24.0, min(80.0, rest_gap * 0.3))

    def _minimum_deformable_extent(self, rest_extent: float) -> float:
        return max(24.0, min(64.0, rest_extent * 0.35))

    def _sort_components_along_primary_axis(
        self,
        components: list[CanvasVisualComponent],
    ) -> list[CanvasVisualComponent]:
        return sorted(
            components,
            key=lambda component: (
                self._base_rect(component).center().x()
                if component.orientation in {Orientation.DEG_90, Orientation.DEG_270}
                else self._base_rect(component).center().y()
            ),
        )

    def _float(self, animation: dict[str, object], key: str) -> float:
        try:
            return float(animation.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0
