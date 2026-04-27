from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import TYPE_CHECKING
import warnings

if TYPE_CHECKING:
    from app.core.base.component import BaseComponent
    from app.ui.canvas.visual_contract import ComponentVisualContract

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer

from app.ui.canvas.electrical_contracts import (
    CAPACITOR_CONTRACT,
    GROUND_CONTRACT,
    INDUCTOR_CONTRACT,
    RESISTOR_CONTRACT,
)
from app.ui.canvas.translational_contracts import (
    DAMPER_CONTRACT,
    FIXED_CONTRACT,
    MASS_CONTRACT,
    SPRING_CONTRACT,
)


class ComponentDomain(str, Enum):
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"


class ComponentVisualCategory(str, Enum):
    RIGID = "rigid"
    DEFORMABLE = "deformable"


class ComponentIoRole(str, Enum):
    INPUT = "input"
    OUTPUT = "output"


class ComponentIoAxis(str, Enum):
    AUTO = "auto"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class Orientation(Enum):
    DEG_0 = 0
    DEG_90 = 90
    DEG_180 = 180
    DEG_270 = 270

    def rotate_clockwise(self) -> "Orientation":
        return Orientation((self.value + 90) % 360)

    def rotate_counterclockwise(self) -> "Orientation":
        return Orientation((self.value - 90) % 360)


@dataclass(frozen=True, slots=True)
class ConnectorPortDefinition:
    name: str
    anchor: tuple[float, float]
    terminal_label: str = ""
    label_offset: tuple[float, float] = (0.0, 0.0)
    connector_offset: float = 0.0


@dataclass(frozen=True, slots=True)
class SvgSymbolAsset:
    asset_path: str
    padding: tuple[float, float, float, float] = (12.0, 8.0, 12.0, 8.0)
    preserve_aspect_ratio: bool = True
    fill_ratio: float = 1.0
    normalization_group: str = "default"


_MISSING_SVG_WARNINGS: set[str] = set()
_SVG_NORMALIZATION_PRESETS: dict[str, dict[str, object]] = {
    "default": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 1.0},
    "mechanical_passive_vertical": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 0.98},
    "mechanical_boundary": {"padding": (12.0, 8.0, 12.0, 8.0), "fill_ratio": 0.96},
    "mechanical_source_sensor_vertical": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 0.97},
    "mechanical_rotary": {"padding": (12.0, 12.0, 12.0, 12.0), "fill_ratio": 0.95},
    "electrical_passive": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 0.95},
    "electrical_reference": {"padding": (10.0, 10.0, 10.0, 10.0), "fill_ratio": 0.95},
    "electrical_source": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 0.96},
    "electrical_sensor": {"padding": (10.0, 8.0, 10.0, 8.0), "fill_ratio": 0.96},
}


def resolve_component_svg(filename: str) -> str | None:
    candidate = Path("app") / "SVG" / filename
    resolved = Path(__file__).resolve().parents[3] / candidate
    if resolved.exists():
        return candidate.as_posix()
    if filename not in _MISSING_SVG_WARNINGS:
        warnings.warn(f"Missing component SVG asset: {candidate.as_posix()}", RuntimeWarning, stacklevel=2)
        _MISSING_SVG_WARNINGS.add(filename)
    return None


def component_svg_asset(
    filename: str,
    *,
    normalization_group: str = "default",
    padding: tuple[float, float, float, float] | None = None,
    preserve_aspect_ratio: bool = True,
    fill_ratio: float | None = None,
) -> SvgSymbolAsset | None:
    asset_path = resolve_component_svg(filename)
    if asset_path is None:
        return None
    preset = _SVG_NORMALIZATION_PRESETS.get(normalization_group, _SVG_NORMALIZATION_PRESETS["default"])
    return SvgSymbolAsset(
        asset_path=asset_path,
        padding=padding if padding is not None else preset["padding"],
        preserve_aspect_ratio=preserve_aspect_ratio,
        fill_ratio=float(fill_ratio if fill_ratio is not None else preset["fill_ratio"]),
        normalization_group=normalization_group,
    )


@dataclass(frozen=True, slots=True)
class SimulationVisualHooks:
    supports_translation: bool = False
    supports_deformation: bool = False
    endpoint_deformation: bool = False
    fixed_reference: bool = False
    free_end: bool = False
    electrical_reference: bool = False
    directional: bool = False
    polarity_visible: bool = False
    source_component: bool = False
    source_type: str = ""
    display_scale: float = 1.0
    rest_length: float | None = None
    deformation_scale: float = 1.0
    zigzag_segments: int = 0
    piston_ratio: float = 0.0
    cylinder_ratio: float = 0.0


@dataclass(frozen=True, slots=True)
class ComponentPresentationStyle:
    preferred_size: tuple[float, float] | None = None
    minimum_size: tuple[float, float] | None = None
    art_scale: float = 1.0
    port_inset: float = 0.0
    selection_padding: tuple[float, float, float, float] = (8.0, 8.0, 8.0, 8.0)
    terminal_anchor_mode: str = "bounds_edge"
    label_mode: str = "overlay_text"
    emphasis_fill_color: str = ""
    emphasis_fill_opacity: float = 0.0
    emphasis_shape: str = "none"
    emphasis_padding: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    def resolved_minimum_size(self, base_size: tuple[float, float], spec_minimum: tuple[float, float] | None) -> tuple[float, float] | None:
        candidate = self.minimum_size or spec_minimum
        if candidate is None:
            return None
        return (
            max(base_size[0], candidate[0]),
            max(base_size[1], candidate[1]),
        )


@dataclass(frozen=True, slots=True)
class ComponentVisualSpec:
    type_key: str
    display_name: str
    domain: ComponentDomain
    symbol_kind: str
    category: ComponentVisualCategory
    base_size: tuple[float, float]
    connector_ports: tuple[ConnectorPortDefinition, ...]
    simulation_hooks: SimulationVisualHooks = field(default_factory=SimulationVisualHooks)
    allowed_io_roles: tuple[ComponentIoRole, ...] = ()
    preferred_io_axis: ComponentIoAxis = ComponentIoAxis.AUTO
    preferred_symbol_aspect_ratio: float | None = None
    minimum_size: tuple[float, float] | None = None
    rotatable: bool = True
    selection_name_visible: bool = True
    presentation: ComponentPresentationStyle = field(default_factory=ComponentPresentationStyle)
    svg_symbol: SvgSymbolAsset | None = None
    core_factory: Callable[[str], BaseComponent | None] | None = None
    # ── Phase 6 integration fields (T6.1a) ──────────────────────────
    # registry_name: maps this visual spec to a ComponentRegistry entry.
    # None = legacy path (core_factory used directly), str = registry path.
    registry_name: str | None = None
    # port_mapping: canvas connector name → core port name.
    # Empty dict = legacy path (_CANVAS_TO_CORE_PORT used).
    port_mapping: dict[str, str] = field(default_factory=dict)
    # ── Phase 7 visual contract (T7.1) ────────────────────────────────
    # When set, the primitive contract renderer draws this component
    # instead of the legacy SVG / _draw_* methods.
    visual_contract: ComponentVisualContract | None = None
    # default_orientation: preferred placement rotation for this component.
    # Horizontal-canonical contracts that should display vertically use DEG_90.
    default_orientation: Orientation = Orientation.DEG_0


@dataclass(slots=True)
class CanvasVisualComponent:
    spec: ComponentVisualSpec
    component_id: str
    position: QPointF
    size: tuple[float, float]
    deletable: bool = True
    orientation: Orientation = Orientation.DEG_0
    assigned_io_roles: tuple[ComponentIoRole, ...] = ()
    instance_name: str | None = None
    input_role_order: int | None = None
    output_role_order: int | None = None

    @property
    def assigned_io_role(self) -> ComponentIoRole | None:
        return self.assigned_io_roles[0] if len(self.assigned_io_roles) == 1 else None

    @assigned_io_role.setter
    def assigned_io_role(self, role: ComponentIoRole | None) -> None:
        self.assigned_io_roles = () if role is None else (role,)

    def has_io_role(self, role: ComponentIoRole) -> bool:
        return role in self.assigned_io_roles

    def add_io_role(self, role: ComponentIoRole) -> None:
        if role not in self.assigned_io_roles:
            self.assigned_io_roles = (*self.assigned_io_roles, role)
        if role == ComponentIoRole.INPUT and self.input_role_order is None:
            self.input_role_order = 0
        if role == ComponentIoRole.OUTPUT and self.output_role_order is None:
            self.output_role_order = 0

    def remove_io_role(self, role: ComponentIoRole) -> None:
        if role in self.assigned_io_roles:
            self.assigned_io_roles = tuple(item for item in self.assigned_io_roles if item != role)
        if role == ComponentIoRole.INPUT:
            self.input_role_order = None
        if role == ComponentIoRole.OUTPUT:
            self.output_role_order = None

    def io_role_order(self, role: ComponentIoRole) -> int | None:
        if role == ComponentIoRole.INPUT:
            return self.input_role_order
        return self.output_role_order

    def set_io_role_order(self, role: ComponentIoRole, order: int | None) -> None:
        if role == ComponentIoRole.INPUT:
            self.input_role_order = order
            return
        self.output_role_order = order

    def base_rect(self) -> QRectF:
        return QRectF(self.position.x(), self.position.y(), self.size[0], self.size[1])

    def selection_overlay_rect(self, rect: QRectF) -> QRectF:
        visual_rect = self.visual_bounds(rect)
        left, top, right, bottom = self.spec.presentation.selection_padding
        return visual_rect.adjusted(-left, -top, right, bottom)

    def selection_label(self, *, selected: bool) -> str | None:
        if selected and self.spec.selection_name_visible:
            return self.instance_name or self.spec.display_name
        return None

    def visual_bounds(self, rect: QRectF) -> QRectF:
        scale = min(max(self.spec.presentation.art_scale, 0.2), 1.2)
        if abs(scale - 1.0) < 1e-6:
            return QRectF(rect)
        width = rect.width() * scale
        height = rect.height() * scale
        return QRectF(
            rect.center().x() - width / 2.0,
            rect.center().y() - height / 2.0,
            width,
            height,
        )

    def preferred_size(self) -> tuple[float, float]:
        return self.spec.presentation.preferred_size or self.spec.base_size

    def preferred_symbol_aspect_ratio(self) -> float | None:
        return self.spec.preferred_symbol_aspect_ratio

    def minimum_size(self) -> tuple[float, float] | None:
        return self.spec.presentation.resolved_minimum_size(self.preferred_size(), self.spec.minimum_size)

    def is_rotatable(self) -> bool:
        return self.spec.rotatable

    def connector_centers(self, rect: QRectF) -> list[QPointF]:
        return [point for _, point in self.transformed_connector_ports(rect)]

    def connector_hit_rects(self, rect: QRectF, *, size: float = 14.0) -> list[tuple[ConnectorPortDefinition, QRectF]]:
        half = size / 2.0
        return [
            (port, QRectF(point.x() - half, point.y() - half, size, size))
            for port, point in self.transformed_connector_ports(rect)
        ]

    def connector_hit_test(self, rect: QRectF, point: QPointF, *, size: float = 14.0) -> ConnectorPortDefinition | None:
        for port, hit_rect in self.connector_hit_rects(rect, size=size):
            if hit_rect.contains(point):
                return port
        return None

    def connector_debug_geometry(self, rect: QRectF, *, size: float = 14.0) -> list[dict[str, object]]:
        debug_items: list[dict[str, object]] = []
        for port, center in self.transformed_connector_ports(rect):
            hit_rect = QRectF(center.x() - size / 2.0, center.y() - size / 2.0, size, size)
            debug_items.append(
                {
                    "name": port.name,
                    "center": center,
                    "hit_rect": hit_rect,
                    "terminal_label": port.terminal_label,
                }
            )
        return debug_items

    def is_rigid(self) -> bool:
        return self.spec.category == ComponentVisualCategory.RIGID

    def is_deformable(self) -> bool:
        return self.spec.category == ComponentVisualCategory.DEFORMABLE

    def supports_translation(self) -> bool:
        return self.spec.simulation_hooks.supports_translation

    def supports_deformation(self) -> bool:
        return self.spec.simulation_hooks.supports_deformation

    def is_fixed_reference(self) -> bool:
        return self.spec.simulation_hooks.fixed_reference

    def is_free_end(self) -> bool:
        return self.spec.simulation_hooks.free_end

    def is_electrical_reference(self) -> bool:
        return self.spec.simulation_hooks.electrical_reference

    def is_directional(self) -> bool:
        return self.spec.simulation_hooks.directional

    def polarity_visible(self) -> bool:
        return self.spec.simulation_hooks.polarity_visible

    def is_source_component(self) -> bool:
        return self.spec.simulation_hooks.source_component

    def source_type(self) -> str:
        return self.spec.simulation_hooks.source_type

    def boundary_role(self) -> str:
        if self.is_fixed_reference():
            return "fixed_reference"
        if self.is_free_end():
            return "free_end"
        if self.is_electrical_reference():
            return "electrical_reference"
        return "internal"

    def motion_profile(self) -> str:
        if self.supports_translation():
            return "translating"
        if self.supports_deformation():
            return "deformable"
        if self.is_fixed_reference():
            return "fixed"
        return "static"

    def deformation_metadata(self) -> dict[str, object]:
        return {
            "supports_translation": self.spec.simulation_hooks.supports_translation,
            "supports_deformation": self.spec.simulation_hooks.supports_deformation,
            "endpoint_deformation": self.spec.simulation_hooks.endpoint_deformation,
            "fixed_reference": self.spec.simulation_hooks.fixed_reference,
            "free_end": self.spec.simulation_hooks.free_end,
            "electrical_reference": self.spec.simulation_hooks.electrical_reference,
            "directional": self.spec.simulation_hooks.directional,
            "polarity_visible": self.spec.simulation_hooks.polarity_visible,
            "source_component": self.spec.simulation_hooks.source_component,
            "source_type": self.spec.simulation_hooks.source_type,
            "rest_length": self.spec.simulation_hooks.rest_length,
            "deformation_scale": self.spec.simulation_hooks.deformation_scale,
            "zigzag_segments": self.spec.simulation_hooks.zigzag_segments,
            "piston_ratio": self.spec.simulation_hooks.piston_ratio,
            "cylinder_ratio": self.spec.simulation_hooks.cylinder_ratio,
        }

    def rotate_clockwise(self) -> None:
        self.orientation = self.orientation.rotate_clockwise()

    def rotate_counterclockwise(self) -> None:
        self.orientation = self.orientation.rotate_counterclockwise()

    def transformed_connector_ports(self, rect: QRectF) -> list[tuple[ConnectorPortDefinition, QPointF]]:
        # ── Phase 7: contract-aware port positions ────────────────────
        # When a visual_contract is present, port screen positions come
        # from the contract (with rotation), but the ConnectorPortDefinition
        # objects are preserved so wire matching by name (R/C/ref) still works.
        contract = self.spec.visual_contract
        if contract is not None:
            from app.ui.canvas.visual_contract import ContractRenderer
            rotation_deg = float(self.orientation.value)
            # Build ordered list of contract port names matching connector_ports order
            contract_port_names = list(contract.ports.keys())
            port_points: list[tuple[ConnectorPortDefinition, QPointF]] = []
            for i, port in enumerate(self.spec.connector_ports):
                if i < len(contract_port_names):
                    cp = contract.ports[contract_port_names[i]]
                    screen_pos = ContractRenderer.port_screen_position(cp, rect, rotation_deg)
                else:
                    # Fallback: legacy calculation for extra ports
                    screen_pos = QPointF(
                        rect.left() + rect.width() * port.anchor[0],
                        rect.top() + rect.height() * port.anchor[1],
                    )
                port_points.append((port, screen_pos))
            return port_points

        # ── Legacy path (no visual contract) ──────────────────────────
        center = rect.center()
        anchor_rect = self.visual_bounds(rect) if self.spec.presentation.terminal_anchor_mode == "visual_terminal" else rect
        port_points: list[tuple[ConnectorPortDefinition, QPointF]] = []
        for port in self.spec.connector_ports:
            local = QPointF(
                anchor_rect.left() + anchor_rect.width() * port.anchor[0],
                anchor_rect.top() + anchor_rect.height() * port.anchor[1],
            )
            outward = _anchor_outward_unit_vector(port.anchor)
            local = QPointF(
                local.x() + outward.x() * (port.connector_offset + self.spec.presentation.port_inset),
                local.y() + outward.y() * (port.connector_offset + self.spec.presentation.port_inset),
            )
            port_points.append((port, _rotate_point(local, center, self.orientation)))
        return port_points

    def transformed_label_position(self, rect: QRectF, port: ConnectorPortDefinition) -> QPointF:
        anchor_rect = self.visual_bounds(rect) if self.spec.presentation.terminal_anchor_mode == "visual_terminal" else rect
        base = QPointF(
            anchor_rect.left() + anchor_rect.width() * port.anchor[0] + port.label_offset[0],
            anchor_rect.top() + anchor_rect.height() * port.anchor[1] + port.label_offset[1],
        )
        return _rotate_point(base, rect.center(), self.orientation)

    def has_svg_symbol(self) -> bool:
        return self.spec.svg_symbol is not None

    def allowed_io_roles(self) -> tuple[ComponentIoRole, ...]:
        return self.spec.allowed_io_roles

    def can_assign_io_role(self, role: ComponentIoRole) -> bool:
        return role in self.spec.allowed_io_roles

    def preferred_io_axis(self) -> ComponentIoAxis:
        return self.spec.preferred_io_axis


@dataclass(frozen=True, slots=True)
class CanvasWireConnection:
    source_component_id: str
    source_connector_name: str
    target_component_id: str
    target_connector_name: str


def _rotate_point(point: QPointF, center: QPointF, orientation: Orientation) -> QPointF:
    if orientation == Orientation.DEG_0:
        return point
    radians = math.radians(orientation.value)
    dx = point.x() - center.x()
    dy = point.y() - center.y()
    rotated_x = dx * math.cos(radians) - dy * math.sin(radians)
    rotated_y = dx * math.sin(radians) + dy * math.cos(radians)
    return QPointF(center.x() + rotated_x, center.y() + rotated_y)


def _anchor_outward_unit_vector(anchor: tuple[float, float]) -> QPointF:
    dx = anchor[0] - 0.5
    dy = anchor[1] - 0.5
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return QPointF(0.0, 0.0)
    if abs(dx) > abs(dy):
        return QPointF(1.0 if dx > 0.0 else -1.0, 0.0)
    return QPointF(0.0, 1.0 if dy > 0.0 else -1.0)


class ComponentRenderer:
    def __init__(self) -> None:
        self._svg_renderers: dict[str, QSvgRenderer] = {}

    def draw(
        self,
        painter: QPainter,
        component: CanvasVisualComponent,
        rect: QRectF,
        *,
        selected: bool,
        wheel_display_scale: float = 1.0,
        wheel_rotation: float = 0.0,
        road_profile_phase: float = 0.0,
        road_profile_active: bool = False,
    ) -> None:
        accent = QColor("#f39c3d") if selected else QColor("#5f7d92")
        painter.save()
        painter.setPen(QPen(accent, 3.0 if selected else 2.0))
        painter.setBrush(QColor("#ffffff"))
        self._draw_symbol_emphasis(painter, component, rect)
        self._draw_symbol(
            painter,
            component,
            rect,
            wheel_display_scale=wheel_display_scale,
            wheel_rotation=wheel_rotation,
            road_profile_phase=road_profile_phase,
            road_profile_active=road_profile_active,
        )
        self._draw_connector_ports(painter, component, rect, selected=selected)
        self._draw_terminal_labels(painter, component, rect)
        if selected:
            self._draw_selection_overlay(painter, component, rect)
        painter.restore()

    def draw_connector_debug_overlay(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        self._draw_connector_debug_overlay(painter, component, rect)

    def _draw_symbol(
        self,
        painter: QPainter,
        component: CanvasVisualComponent,
        rect: QRectF,
        *,
        wheel_display_scale: float,
        wheel_rotation: float,
        road_profile_phase: float,
        road_profile_active: bool,
    ) -> None:
        # ── Phase 7: visual contract renderer (takes priority) ────────
        contract = component.spec.visual_contract
        if contract is not None:
            from app.ui.canvas.visual_contract import ContractRenderer
            rotation_deg = float(component.orientation.value)
            ContractRenderer.draw(painter, contract, rect, rotation_deg)
            return

        kind = component.spec.symbol_kind
        if self._should_draw_svg_symbol(component, rect):
            if self._draw_svg_symbol(painter, component, rect, component.orientation):
                return
        if kind == "mass":
            self._draw_mass(painter, component, rect)
        elif kind == "spring":
            self._draw_spring(painter, rect, component.orientation)
        elif kind == "damper":
            self._draw_damper(painter, rect, component.orientation)
        elif kind == "wheel":
            self._draw_wheel(painter, rect, wheel_display_scale, wheel_rotation)
        elif kind == "tire":
            self._draw_tire(painter, rect, component.orientation)
        elif kind == "mechanical_reference":
            self._draw_ground(painter, rect, component.orientation)
        elif kind == "free_end":
            self._draw_free_end(painter, rect, component.orientation)
        elif kind == "force_source":
            self._draw_road_input(
                painter,
                rect,
                component.orientation,
                road_profile_phase=road_profile_phase,
                animated=road_profile_active,
            )
        elif kind == "electrical_reference":
            self._draw_reference_triangle(painter, rect, component.orientation)
        elif kind == "resistor":
            self._draw_resistor(painter, rect, component.orientation)
        elif kind == "capacitor":
            self._draw_capacitor(painter, rect, component.orientation)
        elif kind == "inductor":
            self._draw_inductor(painter, rect, component.orientation)
        elif kind == "diode":
            self._draw_diode(painter, rect, component.orientation)
        elif kind == "dc_voltage_source":
            self._draw_dc_voltage_source(painter, rect, component.orientation)
        elif kind == "ac_voltage_source":
            self._draw_ac_voltage_source(painter, rect, component.orientation)
        else:
            self._draw_generic_symbol(painter, rect, component.spec.display_name)

    def _draw_symbol_emphasis(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        style = component.spec.presentation
        if style.emphasis_fill_opacity <= 1e-6 or not style.emphasis_fill_color or style.emphasis_shape == "none":
            return
        emphasis_rect = self.emphasis_rect(component, rect)
        if emphasis_rect.width() <= 2.0 or emphasis_rect.height() <= 2.0:
            return
        fill = QColor(style.emphasis_fill_color)
        fill.setAlphaF(min(max(style.emphasis_fill_opacity, 0.0), 1.0))
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        if style.emphasis_shape == "ellipse":
            painter.drawEllipse(emphasis_rect)
        else:
            radius = min(emphasis_rect.width(), emphasis_rect.height()) * 0.16
            painter.drawRoundedRect(emphasis_rect, radius, radius)
        painter.restore()

    def emphasis_rect(self, component: CanvasVisualComponent, rect: QRectF) -> QRectF:
        style = component.spec.presentation
        if style.emphasis_fill_opacity <= 1e-6 or not style.emphasis_fill_color or style.emphasis_shape == "none":
            return QRectF()
        emphasis_rect = self.symbol_render_rect(component, rect) if self._should_draw_svg_symbol(component, rect) else component.visual_bounds(rect)
        left, top, right, bottom = style.emphasis_padding
        return emphasis_rect.adjusted(left, top, -right, -bottom)

    def _should_draw_svg_symbol(self, component: CanvasVisualComponent, rect: QRectF) -> bool:
        if component.spec.svg_symbol is None:
            return False
        if component.spec.symbol_kind in {"wheel", "tire"}:
            return False
        if component.is_deformable():
            base_width, base_height = component.spec.base_size
            return abs(rect.width() - base_width) <= 0.5 and abs(rect.height() - base_height) <= 0.5
        return True

    def _draw_svg_symbol(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF, orientation: Orientation) -> bool:
        svg_symbol = component.spec.svg_symbol
        if svg_symbol is None:
            return False
        renderer = self._svg_renderer(svg_symbol.asset_path)
        if renderer is None or not renderer.isValid():
            return False

        def draw_local(local_painter: QPainter, local_rect: QRectF) -> None:
            render_rect = self.symbol_render_rect(component, local_rect)
            renderer.render(local_painter, render_rect)

        self._with_orientation(painter, rect, orientation, draw_local)
        return True

    def symbol_render_rect(self, component: CanvasVisualComponent, rect: QRectF) -> QRectF:
        visual_rect = component.visual_bounds(rect)
        svg_symbol = component.spec.svg_symbol
        if svg_symbol is None:
            return visual_rect
        renderer = self._svg_renderer(svg_symbol.asset_path)
        if renderer is None or not renderer.isValid():
            return visual_rect
        left_pad, top_pad, right_pad, bottom_pad = self._scaled_svg_padding(component, visual_rect, svg_symbol)
        render_rect = visual_rect.adjusted(left_pad, top_pad, -right_pad, -bottom_pad)
        if render_rect.width() <= 1.0 or render_rect.height() <= 1.0:
            render_rect = visual_rect
        if svg_symbol.preserve_aspect_ratio:
            render_rect = self._aspect_fit_rect(render_rect, self._svg_aspect_reference(component, renderer))
        render_rect = self._apply_svg_fill_ratio(render_rect, svg_symbol.fill_ratio)
        return render_rect

    def _draw_selection_overlay(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        painter.save()
        painter.setPen(QPen(QColor("#8fc6ff"), 3.0, Qt.SolidLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(component.selection_overlay_rect(rect), 12.0, 12.0)
        selection_label = component.selection_label(selected=True)
        if selection_label:
            title_rect, alignment = self.selection_label_rect(component, rect, selection_label)
            painter.setPen(QPen(QColor("#3b5970"), 1.0))
            painter.drawText(title_rect, alignment, selection_label)
        painter.restore()

    def selection_label_rect(
        self,
        component: CanvasVisualComponent,
        rect: QRectF,
        label: str,
    ) -> tuple[QRectF, Qt.AlignmentFlag]:
        overlay_rect = component.selection_overlay_rect(rect)
        symbol_rect = self.symbol_render_rect(component, rect)
        connector_rects = [hit_rect.adjusted(-3.0, -3.0, 3.0, 3.0) for _, hit_rect in component.connector_hit_rects(rect)]
        label_width = max(74.0, 16.0 + len(label) * 7.5)
        label_height = 22.0
        margin = 8.0
        candidates = [
            (
                QRectF(
                    overlay_rect.center().x() - label_width / 2.0,
                    overlay_rect.top() - label_height - margin,
                    label_width,
                    label_height,
                ),
                Qt.AlignCenter,
            ),
            (
                QRectF(
                    overlay_rect.center().x() - label_width / 2.0,
                    overlay_rect.bottom() + margin,
                    label_width,
                    label_height,
                ),
                Qt.AlignCenter,
            ),
            (
                QRectF(
                    overlay_rect.left() - label_width - margin,
                    overlay_rect.center().y() - label_height / 2.0,
                    label_width,
                    label_height,
                ),
                Qt.AlignRight | Qt.AlignVCenter,
            ),
            (
                QRectF(
                    overlay_rect.left() + margin,
                    overlay_rect.top() + margin,
                    label_width,
                    label_height,
                ),
                Qt.AlignLeft | Qt.AlignVCenter,
            ),
        ]
        protected_rects = [symbol_rect.adjusted(-4.0, -4.0, 4.0, 4.0), *connector_rects]
        for candidate_rect, alignment in candidates:
            if any(candidate_rect.intersects(protected) for protected in protected_rects):
                continue
            return candidate_rect, alignment
        return candidates[0]

    def _draw_connector_ports(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF, *, selected: bool = False) -> None:
        painter.save()
        if selected:
            # Selected: slightly larger, more visible ports
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#2c3e50"), 1.4))
            radius = 4.0
        else:
            # Normal: subtle small circles — present but not distracting
            painter.setBrush(QColor("#f0f4f8"))
            painter.setPen(QPen(QColor("#94a3b8"), 1.0))
            radius = 3.0
        for _, point in component.transformed_connector_ports(rect):
            painter.drawEllipse(point, radius, radius)
        painter.restore()

    def _draw_connector_debug_overlay(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        painter.save()
        for item in component.connector_debug_geometry(rect):
            hit_rect = item["hit_rect"]
            center = item["center"]
            name = str(item["name"])
            painter.setPen(QPen(QColor("#d81b60"), 1.2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(hit_rect)
            painter.setPen(QPen(QColor("#ff6f00"), 1.6))
            painter.setBrush(QColor("#ffca28"))
            painter.drawEllipse(center, 3.4, 3.4)
            label_rect = QRectF(center.x() + 8.0, center.y() - 12.0, 56.0, 20.0)
            painter.setPen(QPen(QColor("#5d1049"), 1.0))
            painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, name)
        painter.restore()

    def _draw_terminal_labels(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        painter.save()
        painter.setPen(QPen(QColor("#2f3e46"), 1.0))
        for port in component.spec.connector_ports:
            if not port.terminal_label:
                continue
            label_point = component.transformed_label_position(rect, port)
            label_rect = QRectF(label_point.x() - 14.0, label_point.y() - 10.0, 28.0, 20.0)
            painter.drawText(label_rect, Qt.AlignCenter, port.terminal_label)
        painter.restore()

    def _draw_mass(self, painter: QPainter, component: CanvasVisualComponent, rect: QRectF) -> None:
        if self._draw_svg_symbol(painter, component, rect, component.orientation):
            return
        self._with_orientation(painter, rect, component.orientation, self._draw_mass_local)

    def _draw_mass_local(self, painter: QPainter, rect: QRectF) -> None:
        painter.drawRect(rect)
        inner = rect.adjusted(24.0, 20.0, -24.0, -20.0)
        painter.drawRect(inner)
        painter.drawText(rect, Qt.AlignCenter, "Mass")

    def _svg_renderer(self, asset_path: str) -> QSvgRenderer | None:
        if asset_path not in self._svg_renderers:
            resolved = Path(__file__).resolve().parents[3] / asset_path
            self._svg_renderers[asset_path] = QSvgRenderer(str(resolved))
        return self._svg_renderers[asset_path]

    def _scaled_svg_padding(
        self,
        component: CanvasVisualComponent,
        rect: QRectF,
        svg_symbol: SvgSymbolAsset,
    ) -> tuple[float, float, float, float]:
        base_width = max(component.spec.base_size[0], 1e-6)
        base_height = max(component.spec.base_size[1], 1e-6)
        scale_x = rect.width() / base_width
        scale_y = rect.height() / base_height
        left_pad, top_pad, right_pad, bottom_pad = svg_symbol.padding
        return (
            left_pad * scale_x,
            top_pad * scale_y,
            right_pad * scale_x,
            bottom_pad * scale_y,
        )

    def _svg_aspect_reference(self, component: CanvasVisualComponent, renderer: QSvgRenderer) -> QRectF:
        preferred_aspect_ratio = component.preferred_symbol_aspect_ratio()
        if preferred_aspect_ratio is not None and preferred_aspect_ratio > 1e-6:
            return QRectF(0.0, 0.0, preferred_aspect_ratio, 1.0)
        base_width, base_height = component.spec.base_size
        if base_width > 1e-6 and base_height > 1e-6:
            return QRectF(0.0, 0.0, base_width, base_height)
        view_box = renderer.viewBoxF()
        if view_box.width() > 1e-6 and view_box.height() > 1e-6:
            return view_box
        return QRectF(0.0, 0.0, 1.0, 1.0)

    def _apply_svg_fill_ratio(self, rect: QRectF, fill_ratio: float) -> QRectF:
        ratio = min(max(fill_ratio, 0.2), 1.0)
        if ratio >= 0.999:
            return rect
        width = rect.width() * ratio
        height = rect.height() * ratio
        return QRectF(
            rect.center().x() - width / 2.0,
            rect.center().y() - height / 2.0,
            width,
            height,
        )

    def _aspect_fit_rect(self, bounds: QRectF, source: QRectF) -> QRectF:
        if source.width() <= 1e-6 or source.height() <= 1e-6:
            return bounds
        scale = min(bounds.width() / source.width(), bounds.height() / source.height())
        width = source.width() * scale
        height = source.height() * scale
        return QRectF(
            bounds.center().x() - width / 2.0,
            bounds.center().y() - height / 2.0,
            width,
            height,
        )

    def _draw_spring(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_spring_local)

    def _draw_spring_local(self, painter: QPainter, rect: QRectF) -> None:
        x = rect.center().x()
        lead = max(rect.height() * 0.1, 14.0)
        spring_top = rect.top() + lead
        spring_bottom = rect.bottom() - lead
        available_length = max(spring_bottom - spring_top, 24.0)
        segment_count = 8
        rest_length = 160.0
        deformation_ratio = min(max(available_length / max(rest_length, 1e-6), 0.55), 1.65)
        lateral_amplitude = max(10.0, min(rect.width() * 0.28, 28.0)) / max(deformation_ratio, 0.75)

        painter.drawLine(x, rect.top(), x, spring_top)
        path = QPainterPath(QPointF(x, spring_top))
        direction = -1.0
        step = available_length / segment_count
        for index in range(1, segment_count + 1):
            path.lineTo(x + direction * lateral_amplitude, spring_top + index * step)
            direction *= -1.0
        painter.drawPath(path)
        painter.drawLine(x, spring_bottom, x, rect.bottom())

    def _draw_damper(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_damper_local)

    def _draw_damper_local(self, painter: QPainter, rect: QRectF) -> None:
        x = rect.center().x()
        lead = max(rect.height() * 0.12, 16.0)
        body_top = rect.top() + lead
        body_bottom = rect.bottom() - lead
        available_length = max(body_bottom - body_top, 30.0)
        rest_length = 150.0
        deformation_ratio = min(max(available_length / max(rest_length, 1e-6), 0.55), 1.65)

        cylinder_height = min(max(available_length * 0.40, 52.0), available_length * 0.62)
        cylinder_width = min(max(rect.width() * 0.56, 28.0), rect.width() - 24.0)
        rod_extension = (available_length - cylinder_height) * deformation_ratio
        piston_y = body_top + cylinder_height * 0.55

        painter.drawLine(x, rect.top(), x, body_top)
        painter.drawRect(QRectF(x - cylinder_width / 2.0, body_top, cylinder_width, cylinder_height))
        painter.drawLine(x - cylinder_width / 2.2, piston_y, x + cylinder_width / 2.2, piston_y)
        painter.drawLine(x, piston_y, x, min(body_bottom, body_top + rod_extension))
        painter.drawLine(x, min(body_bottom, body_top + rod_extension), x, rect.bottom())

    def _draw_wheel(self, painter: QPainter, rect: QRectF, scale: float, rotation: float) -> None:
        scaled_rect = self._scaled_rect(rect, scale)
        painter.drawEllipse(scaled_rect)
        inner_margin = max(min(scaled_rect.width(), scaled_rect.height()) * 0.24, 20.0)
        inner = scaled_rect.adjusted(inner_margin, inner_margin, -inner_margin, -inner_margin)
        painter.drawEllipse(inner)
        center = scaled_rect.center()
        for spoke_index in range(4):
            spoke_angle = rotation + spoke_index * (math.pi / 2.0)
            end = QPointF(
                center.x() + math.cos(spoke_angle) * inner.width() * 0.45,
                center.y() + math.sin(spoke_angle) * inner.height() * 0.45,
            )
            painter.drawLine(center, end)
        painter.drawText(rect.adjusted(0, rect.height() - 28.0, 0, 0), Qt.AlignCenter, "Wheel")

    def _draw_tire(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_tire_local)

    def _draw_tire_local(self, painter: QPainter, rect: QRectF) -> None:
        path = QPainterPath(QPointF(rect.left() + 10.0, rect.center().y()))
        segment = (rect.width() - 20.0) / 6.0
        direction = -1.0
        for index in range(1, 7):
            path.lineTo(rect.left() + 10.0 + segment * index, rect.center().y() + direction * 18.0)
            direction *= -1.0
        painter.drawPath(path)

    def _draw_ground(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_ground_local)

    def _draw_ground_local(self, painter: QPainter, rect: QRectF) -> None:
        painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())
        for x in range(int(rect.left()), int(rect.right()), 26):
            painter.drawLine(x, rect.center().y(), x - 12.0, rect.bottom())
        painter.drawText(rect.adjusted(0, -30.0, 0, 0), Qt.AlignCenter, "Ground")

    def _draw_free_end(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_free_end_local)

    def _draw_free_end_local(self, painter: QPainter, rect: QRectF) -> None:
        x = rect.center().x()
        top = rect.top()
        stem_bottom = rect.bottom() - max(rect.height() * 0.22, 10.0)
        cap_half_width = min(max(rect.width() * 0.24, 10.0), 18.0)
        painter.drawLine(x, top, x, stem_bottom)
        painter.drawLine(x - cap_half_width, stem_bottom, x + cap_half_width, stem_bottom)
        painter.drawLine(x - cap_half_width * 0.72, stem_bottom + 7.0, x + cap_half_width * 0.72, stem_bottom + 7.0)

    def _draw_source_box(self, painter: QPainter, rect: QRectF, text: str) -> None:
        painter.drawRect(rect)
        painter.drawText(rect, Qt.AlignCenter, text)

    def road_profile_points(self, rect: QRectF, *, phase: float = 0.0) -> list[QPointF]:
        left = rect.left() + max(rect.width() * 0.08, 8.0)
        right = rect.right() - max(rect.width() * 0.18, 18.0)
        width = max(right - left, 24.0)
        base_y = rect.center().y() + rect.height() * 0.02
        amplitude = max(min(rect.height() * 0.16, 12.0), 5.0)
        points: list[QPointF] = []
        sample_count = 13
        for index in range(sample_count):
            t = index / (sample_count - 1)
            harmonic = (
                math.sin((t * math.tau * 1.08) + phase)
                + 0.52 * math.sin((t * math.tau * 2.31) + phase * 1.37 + 0.8)
                + 0.24 * math.cos((t * math.tau * 4.15) - phase * 0.63 + 0.35)
            )
            x = left + width * t
            y = base_y - harmonic * amplitude
            points.append(QPointF(x, y))
        return points

    def _draw_road_input(
        self,
        painter: QPainter,
        rect: QRectF,
        orientation: Orientation,
        *,
        road_profile_phase: float,
        animated: bool,
    ) -> None:
        def draw_local(local_painter: QPainter, local_rect: QRectF) -> None:
            profile_points = self.road_profile_points(local_rect, phase=road_profile_phase if animated else 0.0)
            if len(profile_points) < 2:
                return
            baseline_y = local_rect.center().y() + local_rect.height() * 0.28
            baseline_left = local_rect.left() + max(local_rect.width() * 0.08, 8.0)
            baseline_right = local_rect.right() - max(local_rect.width() * 0.12, 12.0)
            axis_pen = QPen(QColor("#9aa9b5"), 1.0)
            local_painter.save()
            local_painter.setPen(axis_pen)
            local_painter.drawLine(QPointF(baseline_left, baseline_y), QPointF(baseline_right, baseline_y))
            tick_x = baseline_left + local_rect.width() * 0.1
            local_painter.drawLine(QPointF(tick_x, baseline_y - 5.0), QPointF(tick_x, baseline_y + 5.0))
            local_painter.restore()

            path = QPainterPath(profile_points[0])
            for point in profile_points[1:]:
                path.lineTo(point)
            local_painter.drawPath(path)

            arrow_tip = QPointF(local_rect.right() - 10.0, local_rect.center().y())
            arrow_base = QPointF(arrow_tip.x() - 16.0, arrow_tip.y())
            local_painter.drawLine(profile_points[-1], arrow_base)
            local_painter.drawLine(arrow_base, arrow_tip)
            local_painter.drawLine(arrow_tip, QPointF(arrow_tip.x() - 6.0, arrow_tip.y() - 4.0))
            local_painter.drawLine(arrow_tip, QPointF(arrow_tip.x() - 6.0, arrow_tip.y() + 4.0))

            label_rect = QRectF(
                local_rect.left() + 8.0,
                local_rect.bottom() - 24.0,
                34.0,
                18.0,
            )
            local_painter.save()
            local_painter.setPen(QPen(QColor("#6b7280"), 1.0))
            local_painter.drawText(label_rect, Qt.AlignLeft | Qt.AlignVCenter, "h(t)")
            local_painter.restore()

        self._with_orientation(painter, rect, orientation, draw_local)

    def _draw_reference_triangle(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        def draw_local(local_painter: QPainter, local_rect: QRectF) -> None:
            center = local_rect.center()
            path = QPainterPath(QPointF(center.x(), local_rect.top() + 8.0))
            path.lineTo(local_rect.left() + 10.0, local_rect.bottom() - 8.0)
            path.lineTo(local_rect.right() - 10.0, local_rect.bottom() - 8.0)
            path.closeSubpath()
            local_painter.drawPath(path)
        self._with_orientation(painter, rect, orientation, draw_local)

    def _draw_resistor(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_resistor_local)

    def _draw_resistor_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        lead = max(rect.width() * 0.16, 14.0)
        body_left = left + lead
        body_right = right - lead
        available_length = max(body_right - body_left, 36.0)
        segment_count = 6
        amplitude = min(max(rect.height() * 0.22, 8.0), 16.0)
        step = available_length / segment_count
        painter.drawLine(left, y, body_left, y)
        path = QPainterPath(QPointF(body_left, y))
        direction = -1.0
        for index in range(1, segment_count):
            path.lineTo(body_left + step * index, y + direction * amplitude)
            direction *= -1.0
        path.lineTo(body_right, y)
        painter.drawPath(path)
        painter.drawLine(body_right, y, right, y)

    def _draw_capacitor(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_capacitor_local)

    def _draw_capacitor_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        plate_gap = min(max(rect.width() * 0.10, 8.0), 14.0)
        plate_height = min(max(rect.height() * 0.72, 22.0), rect.height() - 8.0)
        plate_top = y - plate_height / 2.0
        plate_bottom = y + plate_height / 2.0
        left_plate_x = rect.center().x() - plate_gap
        right_plate_x = rect.center().x() + plate_gap

        painter.drawLine(left, y, left_plate_x, y)
        painter.drawLine(left_plate_x, plate_top, left_plate_x, plate_bottom)
        painter.drawLine(right_plate_x, plate_top, right_plate_x, plate_bottom)
        painter.drawLine(right_plate_x, y, right, y)

    def _draw_inductor(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_inductor_local)

    def _draw_inductor_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        lead = max(rect.width() * 0.12, 12.0)
        coil_left = left + lead
        coil_right = right - lead
        coil_count = 4
        available_width = max(coil_right - coil_left, 40.0)
        coil_width = available_width / coil_count
        coil_height = min(max(rect.height() * 0.52, 18.0), 26.0)

        painter.drawLine(left, y, coil_left, y)
        for index in range(coil_count):
            arc_rect = QRectF(
                coil_left + index * coil_width,
                y - coil_height / 2.0,
                coil_width,
                coil_height,
            )
            painter.drawArc(arc_rect, 0, 180 * 16)
        painter.drawLine(coil_right, y, right, y)

    def _draw_diode(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_diode_local)

    def _draw_diode_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        lead = max(rect.width() * 0.12, 12.0)
        symbol_left = left + lead
        symbol_right = right - lead
        triangle_width = max((symbol_right - symbol_left) * 0.52, 24.0)
        bar_x = min(symbol_right - 8.0, symbol_left + triangle_width + 8.0)
        triangle_right = bar_x - 4.0
        triangle_left = symbol_left
        triangle_top = y - min(max(rect.height() * 0.34, 10.0), 18.0)
        triangle_bottom = y + min(max(rect.height() * 0.34, 10.0), 18.0)

        painter.drawLine(left, y, triangle_left, y)
        path = QPainterPath(QPointF(triangle_left, triangle_top))
        path.lineTo(triangle_right, y)
        path.lineTo(triangle_left, triangle_bottom)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(bar_x, triangle_top, bar_x, triangle_bottom)
        painter.drawLine(bar_x, y, right, y)

    def _draw_dc_voltage_source(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_dc_voltage_source_local)

    def _draw_dc_voltage_source_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        radius = min(rect.width(), rect.height()) * 0.28
        center = rect.center()
        circle_left = center.x() - radius
        circle_right = center.x() + radius

        painter.drawLine(left, y, circle_left, y)
        painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0))
        painter.drawLine(circle_right, y, right, y)

        painter.drawLine(center.x(), center.y() - radius * 0.44, center.x(), center.y() - radius * 0.10)
        painter.drawLine(center.x() - radius * 0.17, center.y() - radius * 0.27, center.x() + radius * 0.17, center.y() - radius * 0.27)
        painter.drawLine(center.x() - radius * 0.18, center.y() + radius * 0.28, center.x() + radius * 0.18, center.y() + radius * 0.28)

    def _draw_ac_voltage_source(self, painter: QPainter, rect: QRectF, orientation: Orientation) -> None:
        self._with_orientation(painter, rect, orientation, self._draw_ac_voltage_source_local)

    def _draw_ac_voltage_source_local(self, painter: QPainter, rect: QRectF) -> None:
        y = rect.center().y()
        left = rect.left()
        right = rect.right()
        radius = min(rect.width(), rect.height()) * 0.28
        center = rect.center()
        circle_left = center.x() - radius
        circle_right = center.x() + radius

        painter.drawLine(left, y, circle_left, y)
        painter.drawEllipse(QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0))
        painter.drawLine(circle_right, y, right, y)

        wave = QPainterPath(QPointF(center.x() - radius * 0.52, center.y()))
        wave.cubicTo(
            center.x() - radius * 0.28,
            center.y() - radius * 0.55,
            center.x() - radius * 0.05,
            center.y() - radius * 0.55,
            center.x() + radius * 0.08,
            center.y(),
        )
        wave.cubicTo(
            center.x() + radius * 0.22,
            center.y() + radius * 0.55,
            center.x() + radius * 0.42,
            center.y() + radius * 0.55,
            center.x() + radius * 0.56,
            center.y(),
        )
        painter.drawPath(wave)

    def _draw_generic_symbol(self, painter: QPainter, rect: QRectF, label: str) -> None:
        painter.drawRoundedRect(rect, 8.0, 8.0)
        painter.drawText(rect, Qt.AlignCenter, label)

    def _with_orientation(self, painter: QPainter, rect: QRectF, orientation: Orientation, draw_fn) -> None:
        painter.save()
        center = rect.center()
        painter.translate(center)
        painter.rotate(orientation.value)
        local_rect = QRectF(-rect.width() / 2.0, -rect.height() / 2.0, rect.width(), rect.height())
        draw_fn(painter, local_rect)
        painter.restore()

    def _scaled_rect(self, rect: QRectF, scale: float) -> QRectF:
        if scale >= 0.999:
            return rect
        width = rect.width() * scale
        height = rect.height() * scale
        return QRectF(rect.center().x() - width / 2.0, rect.center().y() - height / 2.0, width, height)


def build_component_catalog() -> dict[str, ComponentVisualSpec]:
    from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring, Wheel
    from app.core.models.sources import RandomRoad, StepForce
    return {
        "mechanical_random_reference": ComponentVisualSpec(
            type_key="mechanical_random_reference",
            display_name="Mechanical Random Reference",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="force_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(130.0, 80.0),
            connector_ports=(ConnectorPortDefinition("output", (1.0, 0.5)),),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            minimum_size=(96.0, 60.0),
            core_factory=lambda cid: RandomRoad(cid, amplitude=0.03, roughness=0.35, seed=7, vehicle_speed=6.0, dt=0.01, duration=15.0),
        ),
        "mass": ComponentVisualSpec(
            type_key="mass",
            display_name="Mass",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="mass",
            category=ComponentVisualCategory.RIGID,
            base_size=(180.0, 80.0),
            connector_ports=(
                ConnectorPortDefinition("top", (0.5, 0.0), connector_offset=10.0),
                ConnectorPortDefinition("bottom", (0.5, 1.0), connector_offset=10.0),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=True,
                supports_deformation=False,
                endpoint_deformation=False,
                display_scale=1.0,
            ),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=1.35,
            minimum_size=(120.0, 60.0),
            presentation=ComponentPresentationStyle(
                preferred_size=(172.0, 92.0),
                minimum_size=(140.0, 76.0),
                art_scale=1.12,
                port_inset=-4.0,
                selection_padding=(5.0, 6.0, 5.0, 6.0),
                terminal_anchor_mode="visual_terminal",
                label_mode="overlay_text",
                emphasis_fill_color="#b8d9c0",
                emphasis_fill_opacity=0.0,
                emphasis_shape="rounded_rect",
                emphasis_padding=(18.0, 12.0, 18.0, 12.0),
            ),
            core_factory=lambda cid: Mass(cid, mass=1.0),
            visual_contract=MASS_CONTRACT,
            default_orientation=Orientation.DEG_90,
        ),
        "translational_spring": ComponentVisualSpec(
            type_key="translational_spring",
            display_name="Translational Spring",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="spring",
            category=ComponentVisualCategory.DEFORMABLE,
            base_size=(90.0, 200.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0)),
                ConnectorPortDefinition("C", (0.5, 1.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=True,
                endpoint_deformation=True,
                display_scale=1.0,
                rest_length=160.0,
                deformation_scale=1.0,
                zigzag_segments=8,
            ),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            minimum_size=(72.0, 140.0),
            presentation=ComponentPresentationStyle(
                preferred_size=(78.0, 148.0),
                minimum_size=(78.0, 148.0),
                art_scale=1.04,
                port_inset=0.0,
                selection_padding=(6.0, 6.0, 6.0, 6.0),
                terminal_anchor_mode="visual_terminal",
                label_mode="embedded_svg",
                emphasis_fill_color="#d7eadc",
                emphasis_fill_opacity=0.0,
                emphasis_shape="rounded_rect",
                emphasis_padding=(24.0, 28.0, 24.0, 28.0),
            ),
            core_factory=lambda cid: Spring(cid, stiffness=1.0),
            visual_contract=SPRING_CONTRACT,
            default_orientation=Orientation.DEG_90,
        ),
        "translational_damper": ComponentVisualSpec(
            type_key="translational_damper",
            display_name="Translational Damper",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="damper",
            category=ComponentVisualCategory.DEFORMABLE,
            base_size=(90.0, 180.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0)),
                ConnectorPortDefinition("C", (0.5, 1.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=True,
                endpoint_deformation=True,
                display_scale=1.0,
                rest_length=150.0,
                deformation_scale=1.0,
                piston_ratio=0.42,
                cylinder_ratio=0.58,
            ),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            minimum_size=(72.0, 128.0),
            presentation=ComponentPresentationStyle(
                preferred_size=(80.0, 142.0),
                minimum_size=(80.0, 142.0),
                art_scale=1.04,
                port_inset=0.0,
                selection_padding=(6.0, 6.0, 6.0, 6.0),
                terminal_anchor_mode="visual_terminal",
                label_mode="embedded_svg",
                emphasis_fill_color="#d2e6d7",
                emphasis_fill_opacity=0.0,
                emphasis_shape="rounded_rect",
                emphasis_padding=(24.0, 26.0, 24.0, 26.0),
            ),
            core_factory=lambda cid: Damper(cid, damping=1.0),
            visual_contract=DAMPER_CONTRACT,
            default_orientation=Orientation.DEG_90,
        ),
        "wheel": ComponentVisualSpec(
            type_key="wheel",
            display_name="Wheel",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="wheel",
            category=ComponentVisualCategory.RIGID,
            base_size=(230.0, 230.0),
            connector_ports=(
                ConnectorPortDefinition("top", (0.5, 0.0)),
                ConnectorPortDefinition("bottom", (0.5, 1.0)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=True, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.INPUT, ComponentIoRole.OUTPUT),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(120.0, 120.0),
            svg_symbol=component_svg_asset("Wheel_black.svg", normalization_group="mechanical_rotary"),
            core_factory=lambda cid: Wheel(cid, mass=1.0),
        ),
        "tire_stiffness": ComponentVisualSpec(
            type_key="tire_stiffness",
            display_name="Tire Stiffness",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="tire",
            category=ComponentVisualCategory.DEFORMABLE,
            base_size=(130.0, 90.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0)),
                ConnectorPortDefinition("C", (0.5, 1.0)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_deformation=True, endpoint_deformation=True, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            core_factory=lambda cid: Spring(cid, stiffness=1.0),
        ),
        "mechanical_reference": ComponentVisualSpec(
            type_key="mechanical_reference",
            display_name="Mechanical Translational Reference",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="mechanical_reference",
            category=ComponentVisualCategory.RIGID,
            base_size=(260.0, 36.0),
            connector_ports=(ConnectorPortDefinition("ref", (0.5, 0.0)),),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            minimum_size=(160.0, 30.0),
            core_factory=lambda cid: MechanicalGround(cid),
            visual_contract=FIXED_CONTRACT,
        ),
        "translational_free_end": ComponentVisualSpec(
            type_key="translational_free_end",
            display_name="Translational Free End",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="free_end",
            category=ComponentVisualCategory.RIGID,
            base_size=(90.0, 60.0),
            connector_ports=(ConnectorPortDefinition("free", (0.5, 0.0)),),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            minimum_size=(72.0, 48.0),
            svg_symbol=component_svg_asset("FreeEnd_Icon_new.svg", normalization_group="mechanical_boundary"),
        ),
        "resistor": ComponentVisualSpec(
            type_key="resistor",
            display_name="Resistor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="resistor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 56.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=False,
                polarity_visible=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 56.0,
            minimum_size=(92.0, 44.0),
            presentation=ComponentPresentationStyle(
                preferred_size=(112.0, 52.0),
                minimum_size=(112.0, 52.0),
                art_scale=1.08,
                port_inset=-8.0,
                selection_padding=(5.0, 5.0, 5.0, 5.0),
                terminal_anchor_mode="visual_terminal",
                label_mode="embedded_svg",
            ),
            registry_name="electrical.resistor",
            port_mapping={"positive": "port_a", "negative": "port_b"},
            visual_contract=RESISTOR_CONTRACT,
        ),
        "capacitor": ComponentVisualSpec(
            type_key="capacitor",
            display_name="Capacitor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="capacitor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 56.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=False,
                polarity_visible=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 56.0,
            minimum_size=(92.0, 44.0),
            registry_name="electrical.capacitor",
            port_mapping={"positive": "port_a", "negative": "port_b"},
            visual_contract=CAPACITOR_CONTRACT,
        ),
        "inductor": ComponentVisualSpec(
            type_key="inductor",
            display_name="Inductor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="inductor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 56.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=False,
                polarity_visible=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 56.0,
            minimum_size=(92.0, 44.0),
            visual_contract=INDUCTOR_CONTRACT,
        ),
        "diode": ComponentVisualSpec(
            type_key="diode",
            display_name="Diode",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="diode",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 56.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=True,
                polarity_visible=True,
                source_component=False,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 56.0,
            minimum_size=(92.0, 44.0),
            svg_symbol=component_svg_asset("Diode_Icon_new.svg", normalization_group="electrical_passive"),
        ),
        "electrical_reference": ComponentVisualSpec(
            type_key="electrical_reference",
            display_name="Electrical Reference",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="electrical_reference",
            category=ComponentVisualCategory.RIGID,
            base_size=(72.0, 72.0),
            connector_ports=(ConnectorPortDefinition("ref", (0.5, 0.0)),),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=True,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(56.0, 56.0),
            registry_name="electrical.ground",
            port_mapping={"ref": "p"},
            visual_contract=GROUND_CONTRACT,
        ),
        "dc_voltage_source": ComponentVisualSpec(
            type_key="dc_voltage_source",
            display_name="DC Voltage Source",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="dc_voltage_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=True,
                polarity_visible=True,
                source_component=True,
                source_type="dc",
                display_scale=1.0,
            ),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("DC_Voltage_source.svg", normalization_group="electrical_source"),
            registry_name="electrical.voltage_source",
            port_mapping={"positive": "port_a", "negative": "port_b"},
        ),
        "ac_voltage_source": ComponentVisualSpec(
            type_key="ac_voltage_source",
            display_name="AC Voltage Source",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="ac_voltage_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("positive", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("negative", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                endpoint_deformation=False,
                fixed_reference=False,
                free_end=False,
                electrical_reference=False,
                directional=True,
                polarity_visible=True,
                source_component=True,
                source_type="ac",
                display_scale=1.0,
            ),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("AC_Voltage_source.svg", normalization_group="electrical_source"),
        ),
        "switch": ComponentVisualSpec(
            type_key="switch",
            display_name="Switch",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="switch",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 56.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                directional=False,
                display_scale=1.0,
            ),
            allowed_io_roles=(),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 56.0,
            minimum_size=(92.0, 44.0),
            svg_symbol=component_svg_asset("Switch_Icon_new.svg", normalization_group="electrical_passive"),
        ),
        "ideal_force_source": ComponentVisualSpec(
            type_key="ideal_force_source",
            display_name="Ideal Force Source",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="ideal_force_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(110.0, 150.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0), connector_offset=6.0),
                ConnectorPortDefinition("C", (0.5, 1.0), connector_offset=6.0),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=110.0 / 150.0,
            minimum_size=(76.0, 110.0),
            svg_symbol=component_svg_asset("Ideal_Force_source.svg", normalization_group="mechanical_source_sensor_vertical"),
            core_factory=lambda cid: StepForce(cid, amplitude=1.0),
        ),
        "ideal_torque_source": ComponentVisualSpec(
            type_key="ideal_torque_source",
            display_name="Ideal Torque Source",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="ideal_torque_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 90.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 90.0,
            minimum_size=(88.0, 60.0),
            svg_symbol=component_svg_asset("Ideal_Torque_source.svg", normalization_group="electrical_source"),
        ),
        "ideal_force_sensor": ComponentVisualSpec(
            type_key="ideal_force_sensor",
            display_name="Ideal Force Sensor",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="ideal_force_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(110.0, 150.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0), connector_offset=6.0),
                ConnectorPortDefinition("C", (0.5, 1.0), connector_offset=6.0),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=110.0 / 150.0,
            minimum_size=(76.0, 110.0),
            svg_symbol=component_svg_asset("Ideal_Force_sensor.svg", normalization_group="mechanical_source_sensor_vertical"),
        ),
        "ideal_torque_sensor": ComponentVisualSpec(
            type_key="ideal_torque_sensor",
            display_name="Ideal Torque Sensor",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="ideal_torque_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 90.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=120.0 / 90.0,
            minimum_size=(88.0, 60.0),
            svg_symbol=component_svg_asset("Ideal_torque_sensor.svg", normalization_group="electrical_sensor"),
        ),
        "ideal_translational_motion_sensor": ComponentVisualSpec(
            type_key="ideal_translational_motion_sensor",
            display_name="Ideal Translational Motion Sensor",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="ideal_translational_motion_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(110.0, 150.0),
            connector_ports=(
                ConnectorPortDefinition("R", (0.5, 0.0), connector_offset=6.0),
                ConnectorPortDefinition("C", (0.5, 1.0), connector_offset=6.0),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=110.0 / 150.0,
            minimum_size=(76.0, 110.0),
            svg_symbol=component_svg_asset("Ideal_Translational_Motion_sensor.svg", normalization_group="mechanical_source_sensor_vertical"),
        ),
        "ac_current_source": ComponentVisualSpec(
            type_key="ac_current_source",
            display_name="AC Current Source",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="ac_current_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("right", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                directional=True,
                polarity_visible=True,
                source_component=True,
                source_type="ac_current",
                display_scale=1.0,
            ),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("AC_Current_source.svg", normalization_group="electrical_source"),
        ),
        "dc_current_source": ComponentVisualSpec(
            type_key="dc_current_source",
            display_name="DC Current Source",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="dc_current_source",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5), "+", (-14.0, -14.0)),
                ConnectorPortDefinition("right", (1.0, 0.5), "-", (14.0, -14.0)),
            ),
            simulation_hooks=SimulationVisualHooks(
                supports_translation=False,
                supports_deformation=False,
                directional=True,
                polarity_visible=True,
                source_component=True,
                source_type="dc_current",
                display_scale=1.0,
            ),
            allowed_io_roles=(ComponentIoRole.INPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
        ),
        "voltage_sensor": ComponentVisualSpec(
            type_key="voltage_sensor",
            display_name="Voltage Sensor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="voltage_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("Voltage_sensor.svg", normalization_group="electrical_sensor"),
        ),
        "current_sensor": ComponentVisualSpec(
            type_key="current_sensor",
            display_name="Current Sensor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="current_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("Current_sensor.svg", normalization_group="electrical_sensor"),
        ),
        "dc_current_sensor": ComponentVisualSpec(
            type_key="dc_current_sensor",
            display_name="DC Current Sensor",
            domain=ComponentDomain.ELECTRICAL,
            symbol_kind="dc_current_sensor",
            category=ComponentVisualCategory.RIGID,
            base_size=(120.0, 72.0),
            connector_ports=(
                ConnectorPortDefinition("left", (0.0, 0.5)),
                ConnectorPortDefinition("right", (1.0, 0.5)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=False, supports_deformation=False, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.HORIZONTAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(84.0, 64.0),
            svg_symbol=component_svg_asset("DC_Current_sensor.svg", normalization_group="electrical_sensor"),
        ),
        "wheel_white_variant": ComponentVisualSpec(
            type_key="wheel_white_variant",
            display_name="Wheel White Variant",
            domain=ComponentDomain.MECHANICAL,
            symbol_kind="wheel_white_variant",
            category=ComponentVisualCategory.RIGID,
            base_size=(230.0, 230.0),
            connector_ports=(
                ConnectorPortDefinition("top", (0.5, 0.0)),
                ConnectorPortDefinition("bottom", (0.5, 1.0)),
            ),
            simulation_hooks=SimulationVisualHooks(supports_translation=True, display_scale=1.0),
            allowed_io_roles=(ComponentIoRole.OUTPUT,),
            preferred_io_axis=ComponentIoAxis.VERTICAL,
            preferred_symbol_aspect_ratio=1.0,
            minimum_size=(120.0, 120.0),
            svg_symbol=component_svg_asset("Wheel_white.svg", normalization_group="mechanical_rotary"),
        ),
    }


COMPONENT_CATALOG = build_component_catalog()


def component_catalog() -> dict[str, ComponentVisualSpec]:
    return dict(COMPONENT_CATALOG)


def component_spec_for_display_name(name: str) -> ComponentVisualSpec:
    mapping = {
        "Disturbance source": "mechanical_random_reference",
        "Disturbance Source": "mechanical_random_reference",
        "Mechanical Random Reference": "mechanical_random_reference",
        "Mass": "mass",
        "Body Mass": "mass",
        "Wheel": "wheel",
        "Spring": "translational_spring",
        "Translational Spring": "translational_spring",
        "Damper": "translational_damper",
        "Translational Damper": "translational_damper",
        "Tire stiffness": "tire_stiffness",
        "Tire Stiffness": "tire_stiffness",
        "Ground": "mechanical_reference",
        "Mechanical Ground": "mechanical_reference",
        "Mechanical Translational Reference": "mechanical_reference",
        "Free End": "translational_free_end",
        "Translational Free End": "translational_free_end",
        "Ideal Force Source": "ideal_force_source",
        "Ideal Torque Source": "ideal_torque_source",
        "Ideal Force Sensor": "ideal_force_sensor",
        "Ideal Torque Sensor": "ideal_torque_sensor",
        "Ideal Translational Motion Sensor": "ideal_translational_motion_sensor",
        "Switch": "switch",
        "Resistor": "resistor",
        "Capacitor": "capacitor",
        "Inductor": "inductor",
        "Diode": "diode",
        "Electrical Reference": "electrical_reference",
        "Voltage Sensor": "voltage_sensor",
        "Current Sensor": "current_sensor",
        "DC Current Sensor": "dc_current_sensor",
        "DC Voltage Source": "dc_voltage_source",
        "AC Voltage Source": "ac_voltage_source",
        "AC Current Source": "ac_current_source",
        "DC Current Source": "dc_current_source",
        "Wheel White Variant": "wheel_white_variant",
    }
    return COMPONENT_CATALOG[mapping.get(name, "mass")]
