from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QContextMenuEvent, QDragEnterEvent, QDropEvent, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QWheelEvent
from PySide6.QtWidgets import QMenu, QWidget

from app.services.signal_catalog import (
    can_component_be_input,
    can_component_be_output,
    component_to_input_signal,
    component_to_output_signal,
)
from app.ui.canvas.component_system import (
    CanvasVisualComponent,
    CanvasWireConnection,
    ComponentIoAxis,
    ComponentIoRole,
    ComponentRenderer,
    ComponentVisualCategory,
    Orientation,
    component_spec_for_display_name,
)
from app.ui.canvas.scene_animation_mapper import SceneAnimationContext, SceneAnimationMapper, infer_workspace_template


@dataclass(slots=True)
class TemplateVisualProfile:
    template_id: str
    template_label: str
    support_visual_mode: str
    support_label: str
    wheel_display_scale: float = 1.0
    road_visual_smoothing: float = 0.0


@dataclass(slots=True)
class WirePreviewState:
    source_component_id: str
    source_connector_name: str
    current_scene_pos: QPointF


@dataclass(slots=True)
class HoveredConnectorState:
    component_id: str
    connector_name: str


@dataclass(frozen=True, slots=True)
class ResizeHandleState:
    component_id: str
    corner: str
    rect: QRectF


@dataclass(slots=True)
class ResizeInteractionState:
    component_index: int
    corner: str
    start_scene_pos: QPointF
    start_rect: QRectF


@dataclass(slots=True)
class PanInteractionState:
    start_widget_pos: QPointF
    start_pan_offset: QPointF


@dataclass(slots=True)
class GroupDragState:
    start_scene_pos: QPointF
    start_positions: dict[int, QPointF]


@dataclass(slots=True)
class MarqueeSelectionState:
    start_scene_pos: QPointF
    current_scene_pos: QPointF


@dataclass(frozen=True, slots=True)
class IoMarkerPlacement:
    component_id: str
    role: ComponentIoRole
    label: str
    side: str
    anchor: QPointF
    tip: QPointF
    label_rect: QRectF
    bounds: QRectF


class ModelCanvas(QWidget):
    component_selected = Signal(dict)
    workspace_template_changed = Signal(str)
    io_roles_changed = Signal(dict)

    MIME_TYPE = "application/x-quarter-car-component"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(780, 620)
        self._zoom = 1.0
        self._base_scale = 1.0
        self._view_offset = QPointF()
        self._pan_offset = QPointF()
        self._scene_width = 1200.0
        self._scene_height = 860.0
        self._renderer = ComponentRenderer()
        self._scene_animation_mapper = SceneAnimationMapper()
        self._scene_animation_result = None
        self._visual_profile = self._build_visual_profile("blank")
        self._connector_debug_visible = False
        self._components: list[CanvasVisualComponent] = []
        self._selected_index: int | None = None
        self._selected_indices: set[int] = set()
        self._selection_status_override: str | None = None
        self._drag_offset = QPointF()
        self._drag_enabled = False
        self._group_drag_state: GroupDragState | None = None
        self._resize_state: ResizeInteractionState | None = None
        self._pan_state: PanInteractionState | None = None
        self._marquee_state: MarqueeSelectionState | None = None
        self._component_counter = 0
        self._io_assignment_counters = {
            ComponentIoRole.INPUT: 0,
            ComponentIoRole.OUTPUT: 0,
        }
        self._wires: list[CanvasWireConnection] = []
        self._selected_wire_index: int | None = None
        self._wire_preview: WirePreviewState | None = None
        self._hovered_target_connector: HoveredConnectorState | None = None
        self._world_bounds = QRectF(-5000.0, -5000.0, 10000.0, 10000.0)
        self._animation = {
            "body_displacement": 0.0,
            "wheel_displacement": 0.0,
            "road_height": 0.0,
            "body_acceleration": 0.0,
            "road_x": [],
            "road_y": [],
            "wheel_rotation": 0.0,
        }

    def load_default_quarter_car_layout(self) -> None:
        self._visual_profile = self._build_visual_profile("quarter_car")
        components = [
            self._component("Mechanical Random Reference", "disturbance_source", QPointF(120.0, 610.0), (130.0, 80.0), deletable=False),
            self._component("Mass", "body_mass", QPointF(470.0, 110.0), (228.0, 108.0), deletable=False),
            self._component("Translational Damper", "suspension_damper", QPointF(410.0, 265.0), (80.0, 142.0), deletable=False),
            self._component("Translational Spring", "suspension_spring", QPointF(630.0, 260.0), (78.0, 148.0), deletable=False),
            self._component("Wheel", "wheel", QPointF(470.0, 470.0), (230.0, 230.0), deletable=False),
            self._component("Tire Stiffness", "tire_stiffness", QPointF(515.0, 705.0), (130.0, 90.0), deletable=False),
        ]
        wires = [
            CanvasWireConnection("body_mass", "bottom", "suspension_damper", "R"),
            CanvasWireConnection("body_mass", "bottom", "suspension_spring", "R"),
            CanvasWireConnection("suspension_damper", "C", "wheel", "top"),
            CanvasWireConnection("suspension_spring", "C", "wheel", "top"),
            CanvasWireConnection("wheel", "bottom", "tire_stiffness", "R"),
            CanvasWireConnection("disturbance_source", "output", "tire_stiffness", "C"),
        ]
        self._apply_loaded_layout(components, wires)

    def load_single_mass_layout(self) -> None:
        self._visual_profile = self._build_visual_profile("single_mass")
        components = [
            self._component("Mechanical Random Reference", "input_force", QPointF(120.0, 160.0), (130.0, 80.0), deletable=False),
            self._component("Mass", "mass", QPointF(430.0, 120.0), (228.0, 108.0), deletable=False),
            self._component("Translational Spring", "spring", QPointF(420.0, 300.0), (78.0, 148.0), deletable=False),
            self._component("Translational Damper", "damper", QPointF(590.0, 304.0), (80.0, 142.0), deletable=False),
            self._component("Mechanical Translational Reference", "ground", QPointF(320.0, 720.0), (440.0, 36.0), deletable=False, orientation=Orientation.DEG_0),
        ]
        wires = [
            CanvasWireConnection("input_force", "output", "mass", "top"),
            CanvasWireConnection("mass", "bottom", "spring", "R"),
            CanvasWireConnection("mass", "bottom", "damper", "R"),
            CanvasWireConnection("spring", "C", "ground", "ref"),
            CanvasWireConnection("damper", "C", "ground", "ref"),
        ]
        self._apply_loaded_layout(components, wires)

    def load_two_mass_layout(self) -> None:
        self._visual_profile = self._build_visual_profile("two_mass")
        components = [
            self._component("Mechanical Random Reference", "input_force", QPointF(80.0, 120.0), (130.0, 80.0), deletable=False),
            self._component("Mass", "mass_1", QPointF(430.0, 110.0), (228.0, 108.0), deletable=False),
            self._component("Mass", "mass_2", QPointF(430.0, 410.0), (228.0, 108.0), deletable=False),
            self._component("Translational Spring", "spring_coupling", QPointF(360.0, 245.0), (78.0, 148.0), deletable=False),
            self._component("Translational Damper", "damper_coupling", QPointF(650.0, 248.0), (80.0, 142.0), deletable=False),
            self._component("Translational Spring", "spring_ground", QPointF(360.0, 560.0), (78.0, 148.0), deletable=False),
            self._component("Translational Damper", "damper_ground", QPointF(650.0, 564.0), (80.0, 142.0), deletable=False),
            self._component("Mechanical Translational Reference", "ground", QPointF(250.0, 760.0), (560.0, 36.0), deletable=False),
        ]
        wires = [
            CanvasWireConnection("input_force", "output", "mass_1", "top"),
            CanvasWireConnection("mass_1", "bottom", "spring_coupling", "R"),
            CanvasWireConnection("mass_1", "bottom", "damper_coupling", "R"),
            CanvasWireConnection("spring_coupling", "C", "mass_2", "top"),
            CanvasWireConnection("damper_coupling", "C", "mass_2", "top"),
            CanvasWireConnection("mass_2", "bottom", "spring_ground", "R"),
            CanvasWireConnection("mass_2", "bottom", "damper_ground", "R"),
            CanvasWireConnection("spring_ground", "C", "ground", "ref"),
            CanvasWireConnection("damper_ground", "C", "ground", "ref"),
        ]
        self._apply_loaded_layout(components, wires)

    def load_template_layout(self, template_id: str) -> None:
        if template_id == "single_mass":
            self.load_single_mass_layout()
            return
        if template_id == "two_mass":
            self.load_two_mass_layout()
            return
        self.load_default_quarter_car_layout()

    def _apply_loaded_layout(
        self,
        components: list[CanvasVisualComponent],
        wires: list[CanvasWireConnection],
    ) -> None:
        self._components = components
        self._component_counter = len(self._components)
        self._wires = wires
        self._selected_indices = set()
        self._selected_wire_index = None
        self._wire_preview = None
        self._hovered_target_connector = None
        self._scene_animation_result = None
        self.select_component(None)
        self._emit_workspace_template_hint()
        self.update()

    def clear_workspace(self) -> None:
        self._visual_profile = self._build_visual_profile("blank")
        self._components = []
        self._wires = []
        self._selected_index = None
        self._selected_indices = set()
        self._selected_wire_index = None
        self._selection_status_override = None
        self._drag_enabled = False
        self._group_drag_state = None
        self._resize_state = None
        self._marquee_state = None
        self._wire_preview = None
        self._hovered_target_connector = None
        self._pan_offset = QPointF()
        self._pan_state = None
        self._zoom = 1.0
        self._animation = {
            "body_displacement": 0.0,
            "wheel_displacement": 0.0,
            "road_height": 0.0,
            "body_acceleration": 0.0,
            "road_x": [],
            "road_y": [],
            "wheel_rotation": 0.0,
        }
        self._scene_animation_result = None
        self._io_assignment_counters = {
            ComponentIoRole.INPUT: 0,
            ComponentIoRole.OUTPUT: 0,
        }
        self.unsetCursor()
        self.component_selected.emit(self.selected_component_details())
        self._emit_workspace_template_hint()
        self.update()

    def snapshot_workspace(self) -> dict[str, object]:
        return {
            "visual_profile": self._visual_profile.template_id,
            "components": [
                {
                    "display_name": component.spec.display_name,
                    "component_id": component.component_id,
                    "instance_name": component.instance_name,
                    "position": (component.position.x(), component.position.y()),
                    "size": component.size,
                    "deletable": component.deletable,
                    "orientation": component.orientation.value,
                    "assigned_io_role": component.assigned_io_role.value if component.assigned_io_role is not None else None,
                    "assigned_io_roles": [role.value for role in component.assigned_io_roles],
                    "input_role_order": component.input_role_order,
                    "output_role_order": component.output_role_order,
                }
                for component in self._components
            ],
            "wires": [
                {
                    "source_component_id": wire.source_component_id,
                    "source_connector_name": wire.source_connector_name,
                    "target_component_id": wire.target_component_id,
                    "target_connector_name": wire.target_connector_name,
                }
                for wire in self._wires
            ],
        }

    def load_workspace_snapshot(self, snapshot: dict[str, object]) -> None:
        self._visual_profile = self._build_visual_profile(str(snapshot.get("visual_profile", "blank")))
        self._components = []
        for component_data in snapshot.get("components", []):
            role_values = component_data.get("assigned_io_roles")
            if isinstance(role_values, list):
                assigned_roles = tuple(ComponentIoRole(value) for value in role_values)
            else:
                role_value = component_data.get("assigned_io_role")
                assigned_roles = () if role_value is None else (ComponentIoRole(role_value),)
            self._components.append(
                CanvasVisualComponent(
                    spec=component_spec_for_display_name(str(component_data["display_name"])),
                    component_id=str(component_data["component_id"]),
                    instance_name=component_data.get("instance_name"),
                    position=QPointF(float(component_data["position"][0]), float(component_data["position"][1])),
                    size=(float(component_data["size"][0]), float(component_data["size"][1])),
                    deletable=bool(component_data["deletable"]),
                    orientation=Orientation(int(component_data["orientation"])),
                    assigned_io_roles=assigned_roles,
                    input_role_order=component_data.get("input_role_order"),
                    output_role_order=component_data.get("output_role_order"),
                )
            )
        self._wires = [
            CanvasWireConnection(
                source_component_id=str(wire_data["source_component_id"]),
                source_connector_name=str(wire_data["source_connector_name"]),
                target_component_id=str(wire_data["target_component_id"]),
                target_connector_name=str(wire_data["target_connector_name"]),
            )
            for wire_data in snapshot.get("wires", [])
        ]
        self._selected_index = None
        self._selected_indices = set()
        self._selected_wire_index = None
        self._selection_status_override = None
        self._drag_enabled = False
        self._group_drag_state = None
        self._resize_state = None
        self._marquee_state = None
        self._wire_preview = None
        self._hovered_target_connector = None
        self._pan_offset = QPointF()
        self._pan_state = None
        self._zoom = 1.0
        self._animation = {
            "body_displacement": 0.0,
            "wheel_displacement": 0.0,
            "road_height": 0.0,
            "body_acceleration": 0.0,
            "road_x": [],
            "road_y": [],
            "wheel_rotation": 0.0,
        }
        self._scene_animation_result = None
        self.unsetCursor()
        self._component_counter = len(self._components)
        self._sync_io_assignment_counters()
        self.component_selected.emit(self.selected_component_details())
        self._emit_workspace_template_hint()
        self.update()

    def update_visualization(self, data: dict[str, object]) -> None:
        self._animation.update(data)
        runtime = data.get("runtime_outputs") or {}
        has_motion = any(
            abs(float(v)) > 1e-9
            for v in runtime.values()
            if isinstance(v, (int, float))
        )
        if not has_motion:
            self._scene_animation_result = None
            self.update()
            return
        template_id = str(self._animation.get("template_id") or self.workspace_template_hint())
        self._scene_animation_result = self._scene_animation_mapper.map(
            SceneAnimationContext(
                template_id=template_id,
                components=tuple(self._components),
                wires=tuple(self._wires),
                animation=dict(self._animation),
            )
        )
        self.update()

    def reset_animation(self) -> None:
        """Reset canvas to rest state after simulation stops.

        Clears animation overrides and zeroes all displacement channels so
        springs, dampers and masses return to their design-time positions.
        """
        self._scene_animation_result = None
        self._animation = {
            "body_displacement": 0.0,
            "wheel_displacement": 0.0,
            "road_height": 0.0,
            "body_acceleration": 0.0,
            "road_x": [],
            "road_y": [],
            "wheel_rotation": 0.0,
        }
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        self._zoom = min(2.5, max(0.55, self._zoom * factor))
        self.update()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasFormat(self.MIME_TYPE):
            payload = bytes(event.mimeData().data(self.MIME_TYPE)).decode("utf-8")
            name, ports = payload.split("|")
            scene_pos = self._to_scene(event.position().toPoint())
            self._components.append(self._instantiate_drop_component(name, int(ports), scene_pos))
            self._scene_animation_result = None
            self._emit_workspace_template_hint()
            self.select_component(len(self._components) - 1)
            self.update()
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus(Qt.MouseFocusReason)
        if event.button() == Qt.MiddleButton:
            self._drag_enabled = False
            self._group_drag_state = None
            self._resize_state = None
            self._marquee_state = None
            self._pan_state = PanInteractionState(
                start_widget_pos=QPointF(event.position()),
                start_pan_offset=QPointF(self._pan_offset),
            )
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        scene_pos = self._to_scene(event.position().toPoint())
        resize_hit = None if self._wire_preview is not None else self._resize_handle_hit_test(scene_pos)
        connector_hit = self._connector_hit_test(scene_pos)
        wire_hit = self._wire_hit_test(scene_pos)
        if event.button() == Qt.RightButton and self._wire_preview is not None:
            self.cancel_wire_preview()
            event.accept()
            return
        hit_index = self._hit_test(scene_pos)
        if event.button() == Qt.RightButton:
            self.select_component(hit_index)
            self.update()
            return
        if resize_hit is not None:
            self._drag_enabled = False
            self._resize_state = ResizeInteractionState(
                component_index=resize_hit["index"],
                corner=resize_hit["corner"],
                start_scene_pos=scene_pos,
                start_rect=self._dynamic_rect(self._components[resize_hit["index"]]),
            )
            self.update()
            event.accept()
            return
        if connector_hit is not None:
            self._drag_enabled = False
            if self._wire_preview is None:
                self._start_wire_preview(
                    connector_hit["component"].component_id,
                    connector_hit["port"].name,
                    connector_hit["center"],
                )
            else:
                self._finalize_wire(connector_hit["component"].component_id, connector_hit["port"].name)
            self.update()
            event.accept()
            return
        if self._wire_preview is not None:
            self.update()
            event.accept()
            return
        if wire_hit is not None:
            self.select_wire(wire_hit)
            self._drag_enabled = False
            self.update()
            event.accept()
            return
        hit_selected = hit_index is not None and hit_index in self._selected_indices
        if not (hit_selected and len(self._selected_indices) > 1):
            self.select_component(hit_index)
        if hit_index is not None and hit_index in self._selected_indices and len(self._selected_indices) > 1:
            self._drag_enabled = True
            self._group_drag_state = GroupDragState(
                start_scene_pos=QPointF(scene_pos),
                start_positions={index: QPointF(self._components[index].position) for index in self._selected_indices},
            )
        elif self._selected_index is not None and len(self._selected_indices) == 1:
            rect = self._dynamic_rect(self._components[self._selected_index])
            self._drag_offset = scene_pos - rect.topLeft()
            self._drag_enabled = True
            self._group_drag_state = None
        else:
            self._drag_enabled = False
            self._group_drag_state = None
            self._marquee_state = MarqueeSelectionState(start_scene_pos=QPointF(scene_pos), current_scene_pos=QPointF(scene_pos))
            self.clear_wire_selection()
        self.update()
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if self._wire_preview is not None:
            self.cancel_wire_preview()
            event.accept()
            return
        if self._marquee_state is not None:
            self._marquee_state = None
        scene_pos = self._to_scene(event.pos())
        hit_index = self._hit_test(scene_pos)
        if hit_index is None:
            self.select_component(None)
            return
        self.select_component(hit_index)
        menu = self.build_context_menu(hit_index)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape and self._wire_preview is not None:
            self.cancel_wire_preview()
            event.accept()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.delete_selected_wire():
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_R and self.rotate_selected_component(clockwise=True):
                event.accept()
                return
            if event.key() == Qt.Key_L and self.rotate_selected_component(clockwise=False):
                event.accept()
                return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.delete_selected_component():
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_state is not None and event.buttons() & Qt.MiddleButton:
            delta = QPointF(event.position()) - self._pan_state.start_widget_pos
            self._pan_offset = QPointF(
                self._pan_state.start_pan_offset.x() + delta.x(),
                self._pan_state.start_pan_offset.y() + delta.y(),
            )
            self.update()
            event.accept()
            return
        scene_pos = self._to_scene(event.position().toPoint())
        if self._wire_preview is not None:
            self._wire_preview.current_scene_pos = scene_pos
            self._update_hovered_target_connector(scene_pos)
            self.update()
        if self._marquee_state is not None and event.buttons() & Qt.LeftButton:
            self._marquee_state.current_scene_pos = QPointF(scene_pos)
            self.update()
            event.accept()
            return
        if self._resize_state is not None and event.buttons() & Qt.LeftButton:
            self._apply_resize(scene_pos)
            self.update()
            super().mouseMoveEvent(event)
            return
        if self._drag_enabled and self._group_drag_state is not None and event.buttons() & Qt.LeftButton:
            dx = scene_pos.x() - self._group_drag_state.start_scene_pos.x()
            dy = scene_pos.y() - self._group_drag_state.start_scene_pos.y()
            for index, start_pos in self._group_drag_state.start_positions.items():
                component = self._components[index]
                new_pos = QPointF(start_pos.x() + dx, start_pos.y() + dy)
                component.position = QPointF(
                    min(max(self._world_bounds.left() + 20.0, new_pos.x()), self._world_bounds.right() - component.size[0] - 20.0),
                    min(max(self._world_bounds.top() + 20.0, new_pos.y()), self._world_bounds.bottom() - component.size[1] - 20.0),
                )
            self.update()
            event.accept()
            return
        if self._drag_enabled and self._selected_index is not None and len(self._selected_indices) == 1 and event.buttons() & Qt.LeftButton:
            component = self._components[self._selected_index]
            new_pos = scene_pos - self._drag_offset
            component.position = QPointF(
                min(max(self._world_bounds.left() + 20.0, new_pos.x()), self._world_bounds.right() - component.size[0] - 20.0),
                min(max(self._world_bounds.top() + 20.0, new_pos.y()), self._world_bounds.bottom() - component.size[1] - 20.0),
            )
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton and self._pan_state is not None:
            self._pan_state = None
            self.unsetCursor()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._marquee_state is not None:
            self._apply_marquee_selection()
            self._marquee_state = None
            self._drag_enabled = False
            self._group_drag_state = None
            self.update()
            event.accept()
            return
        self._drag_enabled = False
        self._group_drag_state = None
        self._resize_state = None
        super().mouseReleaseEvent(event)

    def selected_component_details(self) -> dict[str, object]:
        if len(self._selected_indices) > 1:
            return {
                "name": "Multiple Components",
                "ports": sum(len(self._components[index].spec.connector_ports) for index in self._selected_indices),
                "component_id": ", ".join(self._components[index].component_id for index in sorted(self._selected_indices)),
                "deletable": all(self._components[index].deletable for index in self._selected_indices),
                "selection_state": "Multi-selected",
                "domain": "-",
                "rotation_degrees": 0,
                "visual_category": "multiple",
                "boundary_role": "-",
                "motion_profile": "-",
                "assigned_io_role": "-",
                "directional": "-",
                "source_component": "-",
                "source_type": "-",
                "status_text": f"{len(self._selected_indices)} components selected.",
            }
        if self._selected_index is None:
            return self._empty_selection_details()
        component = self._components[self._selected_index]
        return {
            "name": component.instance_name or component.spec.display_name,
            "ports": len(component.spec.connector_ports),
            "component_id": component.component_id,
            "deletable": component.deletable,
            "selection_state": "Selected",
            "domain": component.spec.domain.value,
            "rotation_degrees": component.orientation.value,
            "visual_category": component.spec.category.value,
            "boundary_role": component.boundary_role(),
            "motion_profile": component.motion_profile(),
            "assigned_io_role": ", ".join(role.value for role in component.assigned_io_roles) if component.assigned_io_roles else "-",
            "directional": component.is_directional(),
            "source_component": component.is_source_component(),
            "source_type": component.source_type() or "-",
            "status_text": self._selection_status_override or ("Editable" if component.deletable else "Locked template component"),
        }

    def select_component(self, index: int | None) -> None:
        self._selected_wire_index = None
        self._selected_index = index
        self._selected_indices = set() if index is None else {index}
        self._selection_status_override = None
        self.component_selected.emit(self.selected_component_details())

    def select_components(self, indices: list[int]) -> None:
        ordered = sorted(set(index for index in indices if 0 <= index < len(self._components)))
        self._selected_wire_index = None
        self._selected_indices = set(ordered)
        self._selected_index = ordered[0] if len(ordered) == 1 else (ordered[0] if ordered else None)
        self._selection_status_override = None
        self.component_selected.emit(self.selected_component_details())

    def clear_selection(self) -> None:
        self.select_component(None)
        self.clear_wire_selection()

    def select_wire(self, index: int | None) -> None:
        self._selected_index = None
        self._selected_indices = set()
        self._selection_status_override = None
        self._selected_wire_index = index
        self.component_selected.emit(self.selected_component_details())

    def clear_wire_selection(self) -> None:
        self._selected_wire_index = None

    def assign_selected_component_io_role(self, role: ComponentIoRole | None) -> bool:
        if self._selected_index is None:
            return False
        if len(self._selected_indices) != 1:
            return False
        component = self._components[self._selected_index]
        if role is None:
            component.assigned_io_roles = ()
            component.input_role_order = None
            component.output_role_order = None
            self._compact_io_role_orders()
            self.component_selected.emit(self.selected_component_details())
            self._emit_io_roles_changed()
            self.update()
            return True
        if not component.can_assign_io_role(role):
            return False
        if not self._component_supports_scene_signal_role(component, role):
            return False
        already_had_role = component.has_io_role(role)
        component.add_io_role(role)
        if not already_had_role:
            self._io_assignment_counters[role] += 1
            component.set_io_role_order(role, self._io_assignment_counters[role])
        self.component_selected.emit(self.selected_component_details())
        self._emit_io_roles_changed()
        self.update()
        return True

    def clear_selected_component_io_role(self, role: ComponentIoRole) -> bool:
        if self._selected_index is None:
            return False
        if len(self._selected_indices) != 1:
            return False
        component = self._components[self._selected_index]
        if not component.has_io_role(role):
            return False
        component.remove_io_role(role)
        self._compact_io_role_orders()
        self.component_selected.emit(self.selected_component_details())
        self._emit_io_roles_changed()
        self.update()
        return True

    def delete_selected_component(self) -> bool:
        if not self._selected_indices:
            return False
        selected_indices = sorted(self._selected_indices)
        if any(not self._components[index].deletable for index in selected_indices):
            self._selection_status_override = "Delete unavailable: predefined template components are locked."
            self.component_selected.emit(self.selected_component_details())
            self.update()
            return False
        removed_ids = {self._components[index].component_id for index in selected_indices}
        for index in reversed(selected_indices):
            del self._components[index]
        self._remove_wires_for_component_ids(removed_ids)
        self._scene_animation_result = None
        self._compact_io_role_orders()
        self._emit_workspace_template_hint()
        self.select_component(None)
        self.update()
        return True

    def delete_selected_wire(self) -> bool:
        if self._selected_wire_index is None:
            return False
        del self._wires[self._selected_wire_index]
        self._selected_wire_index = None
        self._scene_animation_result = None
        self._emit_workspace_template_hint()
        self.update()
        return True

    def rotate_selected_component(self, *, clockwise: bool) -> bool:
        if self._selected_index is None:
            return False
        if len(self._selected_indices) != 1:
            return False
        component = self._components[self._selected_index]
        if not component.is_rotatable():
            return False
        if clockwise:
            component.rotate_clockwise()
        else:
            component.rotate_counterclockwise()
        self.component_selected.emit(self.selected_component_details())
        self.update()
        return True

    def duplicate_selected_component(self) -> bool:
        if self._selected_index is None or len(self._selected_indices) != 1:
            return False
        source = self._components[self._selected_index]
        if not source.deletable:
            return False
        clone = CanvasVisualComponent(
            spec=source.spec,
            component_id=self._next_component_id(source.spec.display_name),
            instance_name=self._next_instance_name(source.spec.display_name),
            position=QPointF(source.position.x() + 36.0, source.position.y() + 36.0),
            size=source.size,
            deletable=True,
            orientation=source.orientation,
        )
        self._components.append(clone)
        self._scene_animation_result = None
        self._emit_workspace_template_hint()
        self.select_component(len(self._components) - 1)
        self.update()
        return True

    def build_context_menu(self, index: int | None = None) -> QMenu:
        if index is not None:
            self.select_component(index)
        menu = QMenu(self)
        delete_action = QAction("Delete", menu)
        selected = self._selected_index is not None
        deletable = selected and self._components[self._selected_index].deletable
        delete_action.setEnabled(bool(deletable))
        if not deletable:
            delete_action.setText("Delete (locked template item)")
        delete_action.triggered.connect(self.delete_selected_component)
        menu.addAction(delete_action)

        rotate_cw_action = QAction("Rotate Clockwise", menu)
        rotate_cw_action.setEnabled(selected and self._components[self._selected_index].is_rotatable())
        rotate_cw_action.triggered.connect(lambda: self.rotate_selected_component(clockwise=True))
        menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("Rotate Counterclockwise", menu)
        rotate_ccw_action.setEnabled(selected and self._components[self._selected_index].is_rotatable())
        rotate_ccw_action.triggered.connect(lambda: self.rotate_selected_component(clockwise=False))
        menu.addAction(rotate_ccw_action)

        if selected:
            component = self._components[self._selected_index]
            if self._component_supports_scene_signal_role(component, ComponentIoRole.INPUT):
                if component.has_io_role(ComponentIoRole.INPUT):
                    clear_input_action = QAction("Clear Input Role", menu)
                    clear_input_action.triggered.connect(lambda: self.clear_selected_component_io_role(ComponentIoRole.INPUT))
                    menu.addAction(clear_input_action)
                else:
                    input_action = QAction("Mark as Input", menu)
                    input_action.triggered.connect(lambda checked=False: self.assign_selected_component_io_role(ComponentIoRole.INPUT))
                    menu.addAction(input_action)
            if self._component_supports_scene_signal_role(component, ComponentIoRole.OUTPUT):
                if component.has_io_role(ComponentIoRole.OUTPUT):
                    clear_output_action = QAction("Clear Output Role", menu)
                    clear_output_action.triggered.connect(lambda: self.clear_selected_component_io_role(ComponentIoRole.OUTPUT))
                    menu.addAction(clear_output_action)
                else:
                    output_action = QAction("Mark as Output", menu)
                    output_action.triggered.connect(lambda checked=False: self.assign_selected_component_io_role(ComponentIoRole.OUTPUT))
                    menu.addAction(output_action)

        duplicate_action = QAction("Duplicate", menu)
        duplicate_action.setEnabled(selected and len(self._selected_indices) == 1 and bool(deletable))
        duplicate_action.triggered.connect(self.duplicate_selected_component)
        menu.addAction(duplicate_action)

        properties_action = QAction("Properties", menu)
        properties_action.setEnabled(False)
        menu.addAction(properties_action)
        return menu

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f6f9fc"))
        self._update_view_transform()
        painter.translate(self._view_offset)
        painter.scale(self._base_scale * self._zoom, self._base_scale * self._zoom)
        self._draw_grid(painter)
        self._draw_road(painter)
        self._draw_persistent_wires(painter, selected=False)
        self._draw_persistent_wires(painter, selected=True)
        for index, component in enumerate(self._components):
            if not self._component_visible_in_current_visual_mode(component):
                continue
            self._draw_component(painter, component, selected=index in self._selected_indices)
        self._draw_resize_handles(painter)
        self._draw_io_markers(painter)
        self._draw_wire_preview(painter)
        self._draw_marquee_selection(painter)
        self._draw_hovered_target_connector_highlight(painter)
        self._draw_connector_debug_overlays(painter)

    def _draw_grid(self, painter: QPainter) -> None:
        visible_rect = self._visible_scene_rect()
        minor_spacing = 40.0
        major_spacing = minor_spacing * 5.0
        start_x = math.floor(visible_rect.left() / minor_spacing) * minor_spacing
        end_x = math.ceil(visible_rect.right() / minor_spacing) * minor_spacing
        start_y = math.floor(visible_rect.top() / minor_spacing) * minor_spacing
        end_y = math.ceil(visible_rect.bottom() / minor_spacing) * minor_spacing
        painter.save()
        minor_pen = QPen(QColor("#dce8f1"), 1.0)
        major_pen = QPen(QColor("#c8d8e6"), 1.0)
        x = start_x
        while x <= end_x:
            painter.setPen(major_pen if abs(x / major_spacing - round(x / major_spacing)) < 1e-6 else minor_pen)
            painter.drawLine(QPointF(x, start_y), QPointF(x, end_y))
            x += minor_spacing
        y = start_y
        while y <= end_y:
            painter.setPen(major_pen if abs(y / major_spacing - round(y / major_spacing)) < 1e-6 else minor_pen)
            painter.drawLine(QPointF(start_x, y), QPointF(end_x, y))
            y += minor_spacing
        painter.restore()

    def _draw_road(self, painter: QPainter) -> None:
        if self._visual_profile.support_visual_mode != "road":
            return
        snapshot = self.road_render_snapshot()
        points = snapshot["points"]
        if not points:
            return
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter.setPen(QPen(QColor("#495c6b"), 3.0))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#8aa0b0"), 1.0))
        for point in points[::8]:
            painter.drawLine(point, QPointF(point.x() - 12.0, point.y() + 22.0))

    def _draw_template_connections(self, painter: QPainter) -> None:
        return

    def _draw_persistent_wires(self, painter: QPainter, *, selected: bool) -> None:
        if not self._wires:
            return
        painter.save()
        if selected:
            painter.setPen(QPen(QColor("#0f3d91"), 5.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            wire_indices = [self._selected_wire_index] if self._selected_wire_index is not None else []
        else:
            painter.setPen(QPen(QColor("#3b82f6"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            wire_indices = [index for index in range(len(self._wires)) if index != self._selected_wire_index]
        for index in wire_indices:
            wire = self._wires[index]
            if not self._wire_visible_in_current_visual_mode(wire):
                continue
            endpoints = self._wire_endpoints(wire)
            if endpoints is None:
                continue
            painter.drawLine(endpoints[0], endpoints[1])
        painter.restore()

    def _draw_component(self, painter: QPainter, component: CanvasVisualComponent, *, selected: bool) -> None:
        rect = self._dynamic_rect(component)
        self._renderer.draw(
            painter,
            component,
            rect,
            selected=selected,
            wheel_display_scale=self._visual_profile.wheel_display_scale,
            wheel_rotation=float(self._animation["wheel_rotation"]),
            road_profile_phase=self._road_profile_phase(),
            road_profile_active=self._road_profile_is_animated(),
        )

    def _road_profile_is_animated(self) -> bool:
        return bool(self._animation["road_x"] and self._animation["road_y"])

    def _road_profile_phase(self) -> float:
        if self._animation["road_x"]:
            return float(self._animation["road_x"][0]) * 0.9
        return float(self._animation["wheel_rotation"]) * 0.2 + float(self._animation["road_height"]) * 12.0

    def _simulation_road_surface_active(self) -> bool:
        return self._road_profile_is_animated() and self._road_owner_component() is not None

    def _component_visible_in_current_visual_mode(self, component: CanvasVisualComponent) -> bool:
        if self._simulation_road_surface_active() and component.spec.type_key == "tire_stiffness":
            return False
        return True

    def _wire_visible_in_current_visual_mode(self, wire: CanvasWireConnection) -> bool:
        if not self._simulation_road_surface_active():
            return True
        hidden_ids = {
            component.component_id
            for component in self._components
            if not self._component_visible_in_current_visual_mode(component)
        }
        return wire.source_component_id not in hidden_ids and wire.target_component_id not in hidden_ids

    def road_render_snapshot(self) -> dict[str, object]:
        road_x = self._animation["road_x"]
        road_y = self._animation["road_y"]
        if not road_x or not road_y:
            return {"points": [], "contact_gap": None, "active": False}
        road_owner = self._road_owner_component()
        smoothed_y = self._smoothed_road_profile([float(value) for value in road_y])
        points: list[QPointF] = []
        vertical_scale = 720.0 * (0.45 + 0.55 * (1.0 - min(self._visual_profile.wheel_display_scale, 1.0)))
        road_origin_x = 130.0
        road_baseline_y = 720.0
        if road_owner is not None:
            owner_rect = self._dynamic_rect(road_owner)
            road_origin_x = owner_rect.center().x() - 24.0
            road_baseline_y = owner_rect.center().y() + max(owner_rect.height() * 1.4, 110.0)
        for x, y in zip(road_x, smoothed_y):
            px = road_origin_x + ((x + 4.5) / 9.0) * 860.0
            py = road_baseline_y - (y * vertical_scale)
            points.append(QPointF(px, py))
        contact_gap: float | None = None
        wheel = next((component for component in self._components if component.spec.symbol_kind == "wheel"), None)
        if points and wheel is not None and self._simulation_road_surface_active():
            wheel_rect = self._dynamic_rect(wheel)
            contact_x = wheel_rect.center().x()
            nearest_point = min(points, key=lambda point: abs(point.x() - contact_x))
            contact_gap = abs(wheel_rect.bottom() - nearest_point.y())
        return {
            "points": points,
            "contact_gap": contact_gap,
            "active": self._simulation_road_surface_active(),
            "road_owner_component_id": road_owner.component_id if road_owner is not None else None,
        }

    def _road_owner_component(self) -> CanvasVisualComponent | None:
        road_owner_id = self._scene_animation_result.road_owner_component_id if self._scene_animation_result is not None else None
        if road_owner_id is None:
            return None
        return next((component for component in self._components if component.component_id == road_owner_id), None)

    def _draw_io_markers(self, painter: QPainter) -> None:
        for placement in self._compute_io_marker_layouts():
            self._draw_io_marker_placement(painter, placement)

    def _draw_resize_handles(self, painter: QPainter) -> None:
        if self._selected_index is None or len(self._selected_indices) != 1:
            return
        painter.save()
        painter.setPen(QPen(QColor("#1f6feb"), 1.6))
        painter.setBrush(QColor("#ffffff"))
        for handle in self._resize_handles_for_component(self._selected_index):
            painter.drawRect(handle.rect)
        painter.restore()

    def _draw_wire_preview(self, painter: QPainter) -> None:
        if self._wire_preview is None:
            return
        source = self._resolve_connector_center(
            self._wire_preview.source_component_id,
            self._wire_preview.source_connector_name,
        )
        if source is None:
            return
        painter.save()
        painter.setPen(QPen(QColor("#1d4ed8"), 3.0, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(source, self._wire_preview.current_scene_pos)
        painter.restore()

    def _draw_marquee_selection(self, painter: QPainter) -> None:
        if self._marquee_state is None:
            return
        rect = self._marquee_rect()
        if rect.isNull():
            return
        containment = self._marquee_mode() == "containment"
        painter.save()
        pen_color = QColor("#16a34a") if containment else QColor("#f97316")
        painter.setPen(QPen(pen_color, 2.0, Qt.DashLine))
        painter.setBrush(QColor(22, 163, 74, 38) if containment else Qt.NoBrush)
        painter.drawRect(rect)
        painter.restore()

    def _draw_hovered_target_connector_highlight(self, painter: QPainter) -> None:
        if self._hovered_target_connector is None:
            return
        component = next(
            (item for item in self._components if item.component_id == self._hovered_target_connector.component_id),
            None,
        )
        if component is None:
            return
        rect = self._dynamic_rect(component)
        hit_rect = next(
            (
                candidate_rect
                for port, candidate_rect in component.connector_hit_rects(rect, size=14.0)
                if port.name == self._hovered_target_connector.connector_name
            ),
            None,
        )
        if hit_rect is None:
            return
        highlight_rect = hit_rect.adjusted(-2.5, -2.5, 2.5, 2.5)
        painter.save()
        painter.setPen(QPen(QColor("#0f3d91"), 2.6))
        painter.setBrush(QColor("#93c5fd"))
        painter.drawRect(highlight_rect)
        painter.restore()

    def _draw_connector_debug_overlays(self, painter: QPainter) -> None:
        if not self._connector_debug_visible:
            return
        for component in self._components:
            if not self._component_visible_in_current_visual_mode(component):
                continue
            self._renderer.draw_connector_debug_overlay(painter, component, self._dynamic_rect(component))

    def _draw_io_marker_placement(self, painter: QPainter, placement: IoMarkerPlacement) -> None:
        painter.save()
        painter.setPen(QPen(self._io_marker_color(placement.role), 2.0))
        painter.drawLine(placement.anchor, placement.tip)
        self._draw_arrow_head(painter, placement.side, placement.tip)
        alignment = Qt.AlignLeft | Qt.AlignVCenter
        if placement.side == "left":
            alignment = Qt.AlignRight | Qt.AlignVCenter
        elif placement.side in {"top", "bottom"}:
            alignment = Qt.AlignCenter
        painter.drawText(placement.label_rect, alignment, placement.label)
        painter.restore()

    def _io_marker_color(self, role: ComponentIoRole) -> QColor:
        if role == ComponentIoRole.INPUT:
            return QColor("#0b84f3")
        return QColor("#d94841")

    def _draw_arrow_head(self, painter: QPainter, side: str, tip: QPointF) -> None:
        head = 8.0
        if side == "right":
            painter.drawLine(tip, QPointF(tip.x() - head, tip.y() - head * 0.75))
            painter.drawLine(tip, QPointF(tip.x() - head, tip.y() + head * 0.75))
        elif side == "left":
            painter.drawLine(tip, QPointF(tip.x() + head, tip.y() - head * 0.75))
            painter.drawLine(tip, QPointF(tip.x() + head, tip.y() + head * 0.75))
        elif side == "top":
            painter.drawLine(tip, QPointF(tip.x() - head * 0.75, tip.y() + head))
            painter.drawLine(tip, QPointF(tip.x() + head * 0.75, tip.y() + head))
        else:
            painter.drawLine(tip, QPointF(tip.x() - head * 0.75, tip.y() - head))
            painter.drawLine(tip, QPointF(tip.x() + head * 0.75, tip.y() - head))

    def _dynamic_rect(self, component: CanvasVisualComponent) -> QRectF:
        if self._scene_animation_result is not None:
            override = self._scene_animation_result.component_overrides.get(component.component_id)
            if override is not None:
                return QRectF(override.rect)
        rect = self._component_rect(component)
        if component.spec.symbol_kind == "mass":
            offset = float(self._animation["body_displacement"]) * 1500.0
            if component.component_id in {"body_mass", "mass_1", "mass"}:
                return rect.translated(0.0, offset)
            return rect
        if component.spec.symbol_kind == "wheel":
            offset = float(self._animation["wheel_displacement"]) * 1300.0
            return rect.translated(0.0, offset)
        if component.spec.symbol_kind in {"spring", "damper"} and component.component_id in {"suspension_spring", "suspension_damper"}:
            body_offset = float(self._animation["body_displacement"]) * 1500.0
            wheel_offset = float(self._animation["wheel_displacement"]) * 1300.0
            return rect.adjusted(0.0, body_offset, 0.0, wheel_offset)
        if component.spec.symbol_kind == "tire":
            wheel_offset = float(self._animation["wheel_displacement"]) * 1300.0
            road_offset = float(self._animation["road_height"]) * -250.0
            return rect.adjusted(0.0, wheel_offset, 0.0, road_offset)
        return rect

    def _component_rect(self, component: CanvasVisualComponent) -> QRectF:
        return QRectF(component.position.x(), component.position.y(), component.size[0], component.size[1])

    def _hit_test(self, scene_pos: QPointF) -> int | None:
        for index in range(len(self._components) - 1, -1, -1):
            if not self._component_visible_in_current_visual_mode(self._components[index]):
                continue
            if self._dynamic_rect(self._components[index]).contains(scene_pos):
                return index
        return None

    def _wire_hit_test(self, scene_pos: QPointF, *, tolerance: float = 8.0) -> int | None:
        best_index: int | None = None
        best_distance = float("inf")
        for index, wire in enumerate(self._wires):
            if not self._wire_visible_in_current_visual_mode(wire):
                continue
            endpoints = self._wire_endpoints(wire)
            if endpoints is None:
                continue
            distance = self._point_to_segment_distance(scene_pos, endpoints[0], endpoints[1])
            if distance <= tolerance and distance < best_distance:
                best_index = index
                best_distance = distance
        return best_index

    def _resize_handles_for_component(self, index: int) -> list[ResizeHandleState]:
        component = self._components[index]
        rect = component.selection_overlay_rect(self._dynamic_rect(component))
        size = 10.0
        half = size / 2.0
        centers = {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
        }
        return [
            ResizeHandleState(
                component_id=component.component_id,
                corner=corner,
                rect=QRectF(center.x() - half, center.y() - half, size, size),
            )
            for corner, center in centers.items()
        ]

    def _resize_handle_hit_test(self, scene_pos: QPointF) -> dict[str, object] | None:
        if self._selected_index is None or len(self._selected_indices) != 1:
            return None
        for handle in self._resize_handles_for_component(self._selected_index):
            if handle.rect.contains(scene_pos):
                return {"index": self._selected_index, "corner": handle.corner, "component_id": handle.component_id}
        return None

    def _minimum_component_size(self, component: CanvasVisualComponent) -> tuple[float, float]:
        if component.has_svg_symbol():
            base_width, base_height = component.preferred_size()
            spec_minimum = component.minimum_size()
            if spec_minimum is None:
                return (base_width, base_height)
            return (
                max(base_width, spec_minimum[0]),
                max(base_height, spec_minimum[1]),
            )
        if component.minimum_size() is not None:
            return component.minimum_size()
        return (
            max(72.0, component.spec.base_size[0] * 0.45),
            max(48.0, component.spec.base_size[1] * 0.45),
        )

    def _apply_resize(self, scene_pos: QPointF) -> None:
        if self._resize_state is None:
            return
        component = self._components[self._resize_state.component_index]
        start_rect = self._resize_state.start_rect
        min_width, min_height = self._minimum_component_size(component)
        dx = scene_pos.x() - self._resize_state.start_scene_pos.x()
        dy = scene_pos.y() - self._resize_state.start_scene_pos.y()

        left = start_rect.left()
        right = start_rect.right()
        top = start_rect.top()
        bottom = start_rect.bottom()

        if "left" in self._resize_state.corner:
            left = min(max(self._world_bounds.left() + 20.0, start_rect.left() + dx), right - min_width)
        if "right" in self._resize_state.corner:
            right = max(min(self._world_bounds.right() - 20.0, start_rect.right() + dx), left + min_width)
        if "top" in self._resize_state.corner:
            top = min(max(self._world_bounds.top() + 20.0, start_rect.top() + dy), bottom - min_height)
        if "bottom" in self._resize_state.corner:
            bottom = max(min(self._world_bounds.bottom() - 20.0, start_rect.bottom() + dy), top + min_height)

        component.position = QPointF(left, top)
        component.size = (right - left, bottom - top)

    def _connector_hit_test(self, scene_pos: QPointF) -> dict[str, object] | None:
        for index in range(len(self._components) - 1, -1, -1):
            component = self._components[index]
            if not self._component_visible_in_current_visual_mode(component):
                continue
            rect = self._dynamic_rect(component)
            port = component.connector_hit_test(rect, scene_pos)
            if port is not None:
                center = next(
                    point for candidate, point in component.transformed_connector_ports(rect) if candidate.name == port.name
                )
                return {"index": index, "component": component, "port": port, "center": center}
        return None

    def _update_hovered_target_connector(self, scene_pos: QPointF) -> None:
        if self._wire_preview is None:
            self._hovered_target_connector = None
            return
        connector_hit = self._connector_hit_test(scene_pos)
        if connector_hit is None or not self._is_valid_wire_target(
            connector_hit["component"].component_id,
            connector_hit["port"].name,
        ):
            self._hovered_target_connector = None
            return
        self._hovered_target_connector = HoveredConnectorState(
            component_id=connector_hit["component"].component_id,
            connector_name=connector_hit["port"].name,
        )

    def _to_scene(self, point: QPoint) -> QPointF:
        scale = max(self._base_scale * self._zoom, 1e-6)
        return QPointF((point.x() - self._view_offset.x()) / scale, (point.y() - self._view_offset.y()) / scale)

    def _visible_scene_rect(self) -> QRectF:
        top_left = self._to_scene(QPoint(0, 0))
        bottom_right = self._to_scene(QPoint(max(self.width(), 1), max(self.height(), 1)))
        return QRectF(top_left, bottom_right).normalized()

    def _update_view_transform(self) -> None:
        available_width = max(self.width() - 16.0, 100.0)
        available_height = max(self.height() - 16.0, 100.0)
        self._base_scale = min(available_width / self._scene_width, available_height / self._scene_height)
        total_scale = self._base_scale * self._zoom
        drawn_width = self._scene_width * total_scale
        drawn_height = self._scene_height * total_scale
        centered_offset = QPointF(max((self.width() - drawn_width) / 2.0, 8.0), max((self.height() - drawn_height) / 2.0, 8.0))
        self._view_offset = QPointF(centered_offset.x() + self._pan_offset.x(), centered_offset.y() + self._pan_offset.y())

    def _next_component_id(self, name: str) -> str:
        self._component_counter += 1
        return f"{name.lower().replace(' ', '_')}_{self._component_counter}"

    def _next_instance_name(self, spec_display_name: str) -> str:
        label = {
            "Translational Spring": "Spring",
            "Translational Damper": "Damper",
            "Mechanical Random Reference": "RandomReference",
            "Mechanical Translational Reference": "Reference",
            "Ideal Force Source": "ForceSource",
            "Tire Stiffness": "Tire",
        }.get(spec_display_name, spec_display_name.replace(" ", ""))
        existing = sum(1 for component in self._components if (component.instance_name or "").startswith(label))
        return f"{label}{existing + 1}"

    def _empty_selection_details(self) -> dict[str, object]:
        if self._selected_wire_index is not None:
            wire = self._wires[self._selected_wire_index]
            return {
                "name": "Wire",
                "ports": 2,
                "component_id": f"{wire.source_component_id}:{wire.source_connector_name}->{wire.target_component_id}:{wire.target_connector_name}",
                "deletable": True,
                "selection_state": "Selected",
                "domain": "-",
                "rotation_degrees": 0,
                "visual_category": "wire",
                "boundary_role": "connection",
                "motion_profile": "static",
                "assigned_io_role": "-",
                "directional": "-",
                "source_component": "-",
                "source_type": "-",
                "status_text": "Wire selected. Press Delete to remove it.",
            }
        return {
            "name": "No selection",
            "ports": 0,
            "component_id": "-",
            "deletable": False,
            "selection_state": "Idle",
            "domain": "-",
            "rotation_degrees": 0,
            "visual_category": "-",
            "boundary_role": "-",
            "motion_profile": "-",
            "assigned_io_role": "-",
            "directional": "-",
            "source_component": "-",
            "source_type": "-",
            "status_text": f"Click a component to select it. Support mode: {self._visual_profile.support_label}.",
        }

    def support_visual_mode(self) -> str:
        return self._visual_profile.support_visual_mode

    def support_visual_label(self) -> str:
        return self._visual_profile.support_label

    def set_connector_debug_visible(self, visible: bool) -> None:
        self._connector_debug_visible = visible
        self.update()

    def connector_debug_visible(self) -> bool:
        return self._connector_debug_visible

    def pan_mode_active(self) -> bool:
        return self._pan_state is not None

    def pan_offset_snapshot(self) -> QPointF:
        return QPointF(self._pan_offset)

    def view_offset_snapshot(self) -> QPointF:
        self._update_view_transform()
        return QPointF(self._view_offset)

    def visible_scene_rect_snapshot(self) -> QRectF:
        self._update_view_transform()
        return self._visible_scene_rect()

    def grid_render_snapshot(self) -> dict[str, object]:
        visible = self.visible_scene_rect_snapshot()
        minor_spacing = 40.0
        start_x = math.floor(visible.left() / minor_spacing) * minor_spacing
        end_x = math.ceil(visible.right() / minor_spacing) * minor_spacing
        start_y = math.floor(visible.top() / minor_spacing) * minor_spacing
        end_y = math.ceil(visible.bottom() / minor_spacing) * minor_spacing
        return {
            "visible_rect": visible,
            "start_x": start_x,
            "end_x": end_x,
            "start_y": start_y,
            "end_y": end_y,
            "covers_visible_rect": start_x <= visible.left() and end_x >= visible.right() and start_y <= visible.top() and end_y >= visible.bottom(),
        }

    def connector_debug_snapshot(self, index: int | None = None) -> list[dict[str, object]]:
        if index is None:
            indices = range(len(self._components))
        elif 0 <= index < len(self._components):
            indices = [index]
        else:
            return []
        snapshot: list[dict[str, object]] = []
        for item_index in indices:
            component = self._components[item_index]
            snapshot.append(
                {
                    "component_id": component.component_id,
                    "orientation": component.orientation.value,
                    "debug_ports": component.connector_debug_geometry(self._dynamic_rect(component)),
                }
            )
        return snapshot

    def persistent_wires(self) -> list[CanvasWireConnection]:
        return list(self._wires)

    def selected_wire_snapshot(self) -> dict[str, object] | None:
        if self._selected_wire_index is None:
            return None
        wire = self._wires[self._selected_wire_index]
        return {
            "index": self._selected_wire_index,
            "source_component_id": wire.source_component_id,
            "source_connector_name": wire.source_connector_name,
            "target_component_id": wire.target_component_id,
            "target_connector_name": wire.target_connector_name,
        }

    def selected_wire_style(self) -> dict[str, object]:
        return {
            "selected": self._selected_wire_index is not None,
            "line_width": 5.0 if self._selected_wire_index is not None else 3.0,
            "color": "#0f3d91" if self._selected_wire_index is not None else "#3b82f6",
        }

    def io_marker_layout_snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "component_id": placement.component_id,
                "label": placement.label,
                "side": placement.side,
                "bounds": placement.bounds,
                "role": placement.role.value,
                "color": self._io_marker_color(placement.role).name(),
            }
            for placement in self._compute_io_marker_layouts()
        ]

    def scene_signal_roles_snapshot(self) -> dict[str, object]:
        scene_components = self._scene_component_keys()
        input_bindings: list[dict[str, object]] = []
        output_bindings: list[dict[str, str]] = []
        template_id = self.workspace_template_hint()
        for component in self._components_with_role_in_assignment_order(ComponentIoRole.INPUT):
            binding = component_to_input_signal(
                template_id,
                component_id=component.component_id,
                component_type_key=component.spec.type_key,
            )
            if binding is not None:
                input_bindings.append(
                    {
                        "component_id": binding.component_id,
                        "component_name": component.instance_name or component.spec.display_name,
                        "signal_id": binding.signal_id,
                        "label": binding.label,
                        "runtime_driving": binding.runtime_driving,
                        "analysis_supported": binding.analysis_supported,
                    }
                )
        for component in self._components_with_role_in_assignment_order(ComponentIoRole.OUTPUT):
            binding = component_to_output_signal(
                template_id,
                component_id=component.component_id,
                component_type_key=component.spec.type_key,
                scene_components=scene_components,
            )
            if binding is not None:
                output_bindings.append(
                    {
                        "component_id": binding.component_id,
                        "component_name": component.instance_name or component.spec.display_name,
                        "signal_id": binding.signal_id,
                        "label": binding.label,
                    }
                )
        return {"template_id": template_id, "inputs": input_bindings, "outputs": output_bindings}

    def selected_resize_handles_snapshot(self) -> list[dict[str, object]]:
        if self._selected_index is None:
            return []
        return [
            {"component_id": handle.component_id, "corner": handle.corner, "rect": handle.rect}
            for handle in self._resize_handles_for_component(self._selected_index)
        ]

    def selected_component_ids_snapshot(self) -> list[str]:
        return [self._components[index].component_id for index in sorted(self._selected_indices)]

    def marquee_selection_snapshot(self) -> dict[str, object] | None:
        if self._marquee_state is None:
            return None
        mode = self._marquee_mode()
        rect = self._marquee_rect()
        return {
            "mode": mode,
            "rect": rect,
            "fill_enabled": mode == "containment",
            "color": "#16a34a" if mode == "containment" else "#f97316",
        }

    def wire_preview_active(self) -> bool:
        return self._wire_preview is not None

    def wire_preview_snapshot(self) -> dict[str, object] | None:
        if self._wire_preview is None:
            return None
        return {
            "source_component_id": self._wire_preview.source_component_id,
            "source_connector_name": self._wire_preview.source_connector_name,
            "current_scene_pos": self._wire_preview.current_scene_pos,
        }

    def hovered_target_connector_snapshot(self) -> dict[str, object] | None:
        if self._hovered_target_connector is None:
            return None
        return {
            "component_id": self._hovered_target_connector.component_id,
            "connector_name": self._hovered_target_connector.connector_name,
        }

    def _start_wire_preview(self, component_id: str, connector_name: str, start_pos: QPointF) -> None:
        self._selected_wire_index = None
        self._wire_preview = WirePreviewState(
            source_component_id=component_id,
            source_connector_name=connector_name,
            current_scene_pos=QPointF(start_pos),
        )
        self._hovered_target_connector = None

    def cancel_wire_preview(self) -> None:
        self._wire_preview = None
        self._hovered_target_connector = None
        self.update()

    def _finalize_wire(self, target_component_id: str, target_connector_name: str) -> None:
        if self._wire_preview is None:
            return
        if not self._is_valid_wire_target(target_component_id, target_connector_name):
            self._wire_preview = None
            self._hovered_target_connector = None
            return
        wire = CanvasWireConnection(
            source_component_id=self._wire_preview.source_component_id,
            source_connector_name=self._wire_preview.source_connector_name,
            target_component_id=target_component_id,
            target_connector_name=target_connector_name,
        )
        if wire not in self._wires:
            self._wires.append(wire)
            self._scene_animation_result = None
            self._emit_workspace_template_hint()
        self._wire_preview = None
        self._hovered_target_connector = None

    def _remove_wires_for_component_ids(self, component_ids: set[str]) -> None:
        if not component_ids:
            return
        self._selected_wire_index = None
        self._wires = [
            wire
            for wire in self._wires
            if wire.source_component_id not in component_ids and wire.target_component_id not in component_ids
        ]
        self._scene_animation_result = None

    def _resolve_connector_center(self, component_id: str, connector_name: str) -> QPointF | None:
        for component in self._components:
            if component.component_id != component_id:
                continue
            rect = self._dynamic_rect(component)
            for port, point in component.transformed_connector_ports(rect):
                if port.name == connector_name:
                    return point
        return None

    def _wire_endpoints(self, wire: CanvasWireConnection) -> tuple[QPointF, QPointF] | None:
        source = self._resolve_connector_center(wire.source_component_id, wire.source_connector_name)
        target = self._resolve_connector_center(wire.target_component_id, wire.target_connector_name)
        if source is None or target is None:
            return None
        return source, target

    def _is_valid_wire_target(self, component_id: str, connector_name: str) -> bool:
        if self._wire_preview is None:
            return False
        if component_id == self._wire_preview.source_component_id:
            return False
        return True

    def _point_to_segment_distance(self, point: QPointF, start: QPointF, end: QPointF) -> float:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return math.hypot(point.x() - start.x(), point.y() - start.y())
        t = ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        projection = QPointF(start.x() + t * dx, start.y() + t * dy)
        return math.hypot(point.x() - projection.x(), point.y() - projection.y())

    def _compute_io_marker_layouts(self) -> list[IoMarkerPlacement]:
        placements: list[IoMarkerPlacement] = []
        occupied: list[QRectF] = []
        component_rects = {component.component_id: self._dynamic_rect(component) for component in self._components}
        for component in self._components:
            if not component.assigned_io_roles:
                continue
            rect = component_rects[component.component_id]
            for role in component.assigned_io_roles:
                label = self._io_marker_label(component, role)
                candidates = self._io_marker_candidates(component, rect, label, role)
                scored = [
                    (
                        self._io_marker_collision_score(candidate, component, component.component_id, component_rects, occupied),
                        order,
                        candidate,
                    )
                    for order, candidate in enumerate(candidates)
                ]
                _, _, chosen = min(scored, key=lambda item: (item[0], item[1]))
                placements.append(chosen)
                occupied.append(chosen.bounds)
        return placements

    def _io_marker_candidates(self, component: CanvasVisualComponent, rect: QRectF, label: str, role: ComponentIoRole) -> list[IoMarkerPlacement]:
        label_width = max(28.0, 14.0 + len(label) * 9.0)
        label_height = 22.0
        gap = 10.0
        stem = 18.0
        label_gap = 6.0
        center = rect.center()
        specs = [
            ("right", QPointF(rect.right() + gap, center.y()), QPointF(rect.right() + gap + stem, center.y()),
             QRectF(rect.right() + gap + stem + label_gap, center.y() - label_height / 2.0, label_width, label_height)),
            ("left", QPointF(rect.left() - gap, center.y()), QPointF(rect.left() - gap - stem, center.y()),
             QRectF(rect.left() - gap - stem - label_gap - label_width, center.y() - label_height / 2.0, label_width, label_height)),
            ("top", QPointF(center.x(), rect.top() - gap), QPointF(center.x(), rect.top() - gap - stem),
             QRectF(center.x() - label_width / 2.0, rect.top() - gap - stem - label_gap - label_height, label_width, label_height)),
            ("bottom", QPointF(center.x(), rect.bottom() + gap), QPointF(center.x(), rect.bottom() + gap + stem),
             QRectF(center.x() - label_width / 2.0, rect.bottom() + gap + stem + label_gap, label_width, label_height)),
        ]
        candidates: list[IoMarkerPlacement] = []
        for side, anchor, tip, label_rect in specs:
            arrow_bounds = QRectF(
                min(anchor.x(), tip.x()) - 4.0,
                min(anchor.y(), tip.y()) - 4.0,
                abs(anchor.x() - tip.x()) + 8.0,
                abs(anchor.y() - tip.y()) + 8.0,
            )
            bounds = arrow_bounds.united(label_rect.adjusted(-4.0, -4.0, 4.0, 4.0))
            candidates.append(
                IoMarkerPlacement(
                    component_id=component.component_id,
                    role=role,
                    label=label,
                    side=side,
                    anchor=anchor,
                    tip=tip,
                    label_rect=label_rect,
                    bounds=bounds,
                )
            )
        return candidates

    def _io_marker_collision_score(
        self,
        candidate: IoMarkerPlacement,
        component: CanvasVisualComponent,
        component_id: str,
        component_rects: dict[str, QRectF],
        occupied: list[QRectF],
    ) -> float:
        score = 0.0
        preferred_sides = self._preferred_io_sides(component)
        if preferred_sides and candidate.side not in preferred_sides:
            score += 120.0
        own_rect = component_rects[component_id]
        if candidate.bounds.intersects(own_rect):
            score += 5000.0
        for other_id, other_rect in component_rects.items():
            if other_id == component_id:
                continue
            if candidate.bounds.intersects(other_rect):
                score += 1000.0 + self._intersection_area(candidate.bounds, other_rect) * 0.1
        for marker_rect in occupied:
            if candidate.bounds.intersects(marker_rect):
                score += 600.0 + self._intersection_area(candidate.bounds, marker_rect) * 0.1
        if not self._world_bounds.contains(candidate.bounds):
            score += 400.0 + self._rect_overflow(candidate.bounds, self._world_bounds)
        return score

    def _marquee_rect(self) -> QRectF:
        if self._marquee_state is None:
            return QRectF()
        return QRectF(self._marquee_state.start_scene_pos, self._marquee_state.current_scene_pos).normalized()

    def _marquee_mode(self) -> str:
        if self._marquee_state is None:
            return "containment"
        start = self._marquee_state.start_scene_pos
        current = self._marquee_state.current_scene_pos
        return "containment" if current.x() >= start.x() and current.y() >= start.y() else "crossing"

    def _apply_marquee_selection(self) -> None:
        rect = self._marquee_rect()
        if rect.width() < 1.0 or rect.height() < 1.0:
            return
        containment = self._marquee_mode() == "containment"
        matched: list[int] = []
        for index, component in enumerate(self._components):
            component_rect = component.selection_overlay_rect(self._dynamic_rect(component))
            if containment:
                if rect.contains(component_rect):
                    matched.append(index)
            elif rect.intersects(component_rect):
                matched.append(index)
        self.select_components(matched)

    def _preferred_io_sides(self, component: CanvasVisualComponent) -> tuple[str, ...]:
        axis = component.preferred_io_axis()
        if axis == ComponentIoAxis.AUTO:
            return ()
        vertical_sides = ("top", "bottom")
        horizontal_sides = ("left", "right")
        if axis == ComponentIoAxis.VERTICAL:
            return vertical_sides if component.orientation in {Orientation.DEG_0, Orientation.DEG_180} else horizontal_sides
        if axis == ComponentIoAxis.HORIZONTAL:
            return horizontal_sides if component.orientation in {Orientation.DEG_0, Orientation.DEG_180} else vertical_sides
        return ()

    def _intersection_area(self, first: QRectF, second: QRectF) -> float:
        overlap = first.intersected(second)
        if overlap.isNull():
            return 0.0
        return overlap.width() * overlap.height()

    def _rect_overflow(self, rect: QRectF, bounds: QRectF) -> float:
        overflow = 0.0
        overflow += max(bounds.left() - rect.left(), 0.0)
        overflow += max(rect.right() - bounds.right(), 0.0)
        overflow += max(bounds.top() - rect.top(), 0.0)
        overflow += max(rect.bottom() - bounds.bottom(), 0.0)
        return overflow

    def _io_marker_label(self, component: CanvasVisualComponent, role: ComponentIoRole) -> str:
        if role not in component.assigned_io_roles:
            return ""
        role_components = self._components_with_role_in_assignment_order(role)
        index = role_components.index(component) + 1
        prefix = "u" if role == ComponentIoRole.INPUT else "z"
        return f"{prefix}{index}"

    def _components_with_role_in_assignment_order(self, role: ComponentIoRole) -> list[CanvasVisualComponent]:
        return sorted(
            [item for item in self._components if role in item.assigned_io_roles],
            key=lambda item: (
                item.io_role_order(role) if item.io_role_order(role) is not None else 10_000_000,
                self._components.index(item),
            ),
        )

    def _compact_io_role_orders(self) -> None:
        for role in (ComponentIoRole.INPUT, ComponentIoRole.OUTPUT):
            ordered = self._components_with_role_in_assignment_order(role)
            for order, component in enumerate(ordered, start=1):
                component.set_io_role_order(role, order)
            self._io_assignment_counters[role] = len(ordered)

    def _sync_io_assignment_counters(self) -> None:
        for role in (ComponentIoRole.INPUT, ComponentIoRole.OUTPUT):
            self._io_assignment_counters[role] = max(
                (component.io_role_order(role) or 0 for component in self._components),
                default=0,
            )

    def _scene_component_keys(self) -> tuple[tuple[str, str], ...]:
        return tuple((component.component_id, component.spec.type_key) for component in self._components)

    def _component_supports_scene_signal_role(self, component: CanvasVisualComponent, role: ComponentIoRole) -> bool:
        if not component.can_assign_io_role(role):
            return False
        template_id = self.workspace_template_hint()
        if role == ComponentIoRole.INPUT:
            return can_component_be_input(
                template_id,
                component_id=component.component_id,
                component_type_key=component.spec.type_key,
            )
        return can_component_be_output(
            template_id,
            component_id=component.component_id,
            component_type_key=component.spec.type_key,
            scene_components=self._scene_component_keys(),
        )

    def visible_component_names(self) -> list[str]:
        return [component.spec.display_name for component in self._components]

    def workspace_template_hint(self) -> str:
        explicit = self._visual_profile.template_id
        if explicit in {"quarter_car", "single_mass", "two_mass"}:
            return explicit
        return infer_workspace_template(self._components, self._wires)

    def _emit_workspace_template_hint(self) -> None:
        self.workspace_template_changed.emit(self.workspace_template_hint())
        self._emit_io_roles_changed()

    def _emit_io_roles_changed(self) -> None:
        self.io_roles_changed.emit(self.scene_signal_roles_snapshot())

    def wheel_display_scale(self) -> float:
        return self._visual_profile.wheel_display_scale

    def road_visual_smoothing(self) -> float:
        return self._visual_profile.road_visual_smoothing

    def component_orientations(self) -> list[int]:
        return [component.orientation.value for component in self._components]

    def _smoothed_road_profile(self, values: list[float]) -> list[float]:
        if len(values) < 3 or self._visual_profile.road_visual_smoothing <= 0.0:
            return values
        smoothing = min(max(self._visual_profile.road_visual_smoothing, 0.0), 0.95)
        wheel_factor = min(max(self._visual_profile.wheel_display_scale, 0.35), 1.0)
        kernel_radius = max(2, int(round(7 * smoothing * wheel_factor)))
        smoothed: list[float] = []
        for index in range(len(values)):
            total = 0.0
            weight_sum = 0.0
            for offset in range(-kernel_radius, kernel_radius + 1):
                sample_index = min(max(index + offset, 0), len(values) - 1)
                distance = abs(offset) / max(kernel_radius, 1)
                weight = 1.0 - (distance * 0.75)
                total += values[sample_index] * weight
                weight_sum += weight
            smoothed.append(total / max(weight_sum, 1e-6))
        return smoothed

    def _component(
        self,
        display_name: str,
        component_id: str,
        position: QPointF,
        size: tuple[float, float],
        *,
        deletable: bool,
        orientation: Orientation = Orientation.DEG_0,
    ) -> CanvasVisualComponent:
        return CanvasVisualComponent(
            spec=component_spec_for_display_name(display_name),
            component_id=component_id,
            position=position,
            size=size,
            deletable=deletable,
            orientation=orientation,
        )

    def _drop_spec(self, display_name: str, ports: int):
        try:
            return component_spec_for_display_name(display_name)
        except KeyError:
            # Future components can still use the common framework before their dedicated symbol renderer lands.
            fallback = component_spec_for_display_name("Mass")
            return component_spec_for_display_name(display_name) if display_name in {"Mass"} else type(fallback)(
                type_key=display_name.lower().replace(" ", "_"),
                display_name=display_name,
                domain=fallback.domain,
                symbol_kind="mass",
                category=ComponentVisualCategory.RIGID,
                base_size=(120.0, 60.0),
                connector_ports=fallback.connector_ports[: min(max(ports, 1), 2)],
                simulation_hooks=fallback.simulation_hooks,
                selection_name_visible=True,
            )

    def _instantiate_drop_component(self, display_name: str, ports: int, scene_pos: QPointF) -> CanvasVisualComponent:
        spec = self._drop_spec(display_name, ports)
        width, height = spec.presentation.preferred_size or spec.base_size
        return CanvasVisualComponent(
            spec=spec,
            component_id=self._next_component_id(display_name),
            instance_name=self._next_instance_name(spec.display_name),
            position=QPointF(scene_pos.x() - width / 2.0, scene_pos.y() - height / 2.0),
            size=(width, height),
            deletable=True,
        )

    def _build_visual_profile(self, template_id: str) -> TemplateVisualProfile:
        profiles = {
            "quarter_car": TemplateVisualProfile(
                template_id="quarter_car",
                template_label="Quarter-Car Suspension",
                support_visual_mode="road",
                support_label="Road excitation",
                wheel_display_scale=0.56,
                road_visual_smoothing=0.82,
            ),
            "blank": TemplateVisualProfile(
                template_id="blank",
                template_label="Blank Workspace",
                support_visual_mode="blank",
                support_label="No predefined support",
            ),
            "single_mass": TemplateVisualProfile(
                template_id="single_mass",
                template_label="Single Mass-Spring-Damper",
                support_visual_mode="ground",
                support_label="Fixed ground",
            ),
            "two_mass": TemplateVisualProfile(
                template_id="two_mass",
                template_label="Two-Mass System",
                support_visual_mode="ground",
                support_label="Fixed ground",
            ),
        }
        return profiles.get(template_id, profiles["quarter_car"])
