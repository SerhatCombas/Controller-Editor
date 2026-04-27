"""ComponentVisualContract — MSL-inspired unified component visual system.

Defines a declarative visual contract for diagram components.  Each contract
specifies geometry primitives, port anchors, and label slots in a standard
coordinate system (Y-up, -100..+100).  The ``ContractRenderer`` transforms
these into QPainter calls on the canvas.

Coordinate convention
─────────────────────
Contract space uses **MSL-style Y-up** coordinates:

    y = +100 (top)
         │
  -100 ──┼── +100   (x axis, left → right)
         │
    y = -100 (bottom)

The renderer flips Y once so that QPainter (screen Y-down) draws correctly.
Contract authors always think in Y-up.

Canonical icon orientation
──────────────────────────
All two-terminal components are authored **horizontally** (flow left → right).
Vertical placement on the canvas is achieved via layout rotation, not by
redefining the contract geometry.

See ``docs/VISUAL_CONTRACT_SPEC.md`` for the full specification.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QColor, QPainter


# ═══════════════════════════════════════════════════════════════════════════
# Geometry primitives
# ═══════════════════════════════════════════════════════════════════════════
# All coordinates are in contract space (-100..+100, Y-up).
# ``stroke_width`` is in screen pixels (cosmetic).
# ``color_key`` is resolved by the renderer against the domain style.

@dataclass(frozen=True, slots=True)
class GLine:
    """Straight line segment."""
    start: tuple[float, float]
    end: tuple[float, float]
    stroke_width: float = 2.0
    color_key: str = "domain_stroke"


@dataclass(frozen=True, slots=True)
class GPolyline:
    """Open polyline (sequence of connected segments)."""
    points: tuple[tuple[float, float], ...]
    stroke_width: float = 2.0
    color_key: str = "domain_stroke"


@dataclass(frozen=True, slots=True)
class GRectangle:
    """Axis-aligned rectangle (x1,y1 = one corner, x2,y2 = opposite)."""
    x1: float
    y1: float
    x2: float
    y2: float
    fill_key: str = ""
    stroke_key: str = "domain_stroke"
    stroke_width: float = 2.0
    corner_radius: float = 0.0


@dataclass(frozen=True, slots=True)
class GEllipse:
    """Ellipse centered at (cx, cy) with radii (rx, ry)."""
    cx: float
    cy: float
    rx: float
    ry: float
    fill_key: str = ""
    stroke_key: str = "domain_stroke"
    stroke_width: float = 2.0


@dataclass(frozen=True, slots=True)
class GArc:
    """Elliptical arc.  Angles in degrees, counter-clockwise from 3-o'clock."""
    cx: float
    cy: float
    rx: float
    ry: float
    start_angle: float
    sweep_angle: float
    stroke_width: float = 2.0
    color_key: str = "domain_stroke"


@dataclass(frozen=True, slots=True)
class GPolygon:
    """Closed polygon (auto-closed from last point to first)."""
    points: tuple[tuple[float, float], ...]
    fill_key: str = ""
    stroke_key: str = "domain_stroke"
    stroke_width: float = 2.0


GeometryPrimitive = Union[GLine, GPolyline, GRectangle, GEllipse, GArc, GPolygon]


# ═══════════════════════════════════════════════════════════════════════════
# Port and label definitions
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ContractPort:
    """A connection port in contract coordinates.

    ``name`` is the canonical physical name (``flange_a``, ``p``, etc.).
    ``x``, ``y`` are in contract space (-100..+100, Y-up).
    ``side`` hints at the stub direction for future use.
    """
    name: str
    x: float
    y: float
    side: str = "left"  # "left", "right", "top", "bottom"


@dataclass(frozen=True, slots=True)
class LabelSlot:
    """Declares where a label can appear relative to the screen bounding box.

    ``side`` is "top" or "bottom".
    ``offset`` is pixels from the bounding box edge.
    """
    side: str = "top"
    offset: float = 12.0


# ═══════════════════════════════════════════════════════════════════════════
# Domain visual styles
# ═══════════════════════════════════════════════════════════════════════════

DOMAIN_STYLES: dict[str, dict[str, str]] = {
    "electrical":    {"stroke": "#0055FF", "fill": "#E8F0FE", "stub": "#6699FF"},
    "translational": {"stroke": "#007F00", "fill": "#E8F5E8", "stub": "#66AA66"},
    "rotational":    {"stroke": "#7F7FA0", "fill": "#F0F0F5", "stub": "#9595B0"},
    "thermal":       {"stroke": "#BF0000", "fill": "#FDE8E8", "stub": "#D06060"},
}

_FALLBACK_STYLE: dict[str, str] = {
    "stroke": "#555555", "fill": "#F0F0F0", "stub": "#999999",
}


def resolve_domain_colors(domain_key: str) -> dict[str, str]:
    """Resolve color keys to hex strings for a given domain."""
    base = DOMAIN_STYLES.get(domain_key, _FALLBACK_STYLE)
    return {
        "domain_stroke": base["stroke"],
        "domain_fill":   base["fill"],
        "stub":          base["stub"],
        "background":    "#FFFFFF",
        "none":          "",
    }


# ═══════════════════════════════════════════════════════════════════════════
# The visual contract
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ComponentVisualContract:
    """Single source of truth for a component's visual appearance.

    Combines icon geometry, port anchors, default sizing, and label slots
    in a standard coordinate system.  The renderer uses this to draw the
    component via QPainter primitives — no SVG file needed.
    """
    geometry: tuple[GeometryPrimitive, ...]
    ports: dict[str, ContractPort]
    default_extent: tuple[float, float]
    min_extent: tuple[float, float] = (60.0, 40.0)
    preserve_aspect_ratio: bool = False
    label_slots: dict[str, LabelSlot] = field(default_factory=lambda: {
        "name": LabelSlot(side="top", offset=12.0),
    })
    domain_key: str = ""

    # ------------------------------------------------------------------
    # Port ↔ legacy connector bridge
    # ------------------------------------------------------------------

    def to_normalized_anchor(self, port_name: str) -> tuple[float, float]:
        """Convert a contract port to normalized (0..1) anchor for legacy compat.

        The returned anchor is in screen convention (Y-down):
            (0, 0) = top-left, (1, 1) = bottom-right.
        """
        port = self.ports[port_name]
        nx = (port.x + 100.0) / 200.0
        ny = (-port.y + 100.0) / 200.0   # Y-flip
        return (nx, ny)


# ═══════════════════════════════════════════════════════════════════════════
# Contract renderer (QPainter)
# ═══════════════════════════════════════════════════════════════════════════

class ContractRenderer:
    """Renders a ``ComponentVisualContract`` onto a QPainter.

    The renderer applies a coordinate transform so that contract geometry
    (Y-up, -100..+100) maps correctly to the screen-space layout rect.

    Usage::

        ContractRenderer.draw(painter, contract, rect, rotation_deg=90)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def draw(
        painter: QPainter,
        contract: ComponentVisualContract,
        rect: QRectF,
        rotation_deg: float = 0.0,
    ) -> None:
        """Draw all geometry primitives of *contract* into *rect*."""
        from PySide6.QtCore import QPointF, QRectF as QR
        from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF

        colors = resolve_domain_colors(contract.domain_key)

        painter.save()

        # Transform pipeline:  translate → rotate → scale → Y-flip
        cx = rect.x() + rect.width() / 2.0
        cy = rect.y() + rect.height() / 2.0
        painter.translate(cx, cy)

        if rotation_deg:
            painter.rotate(rotation_deg)

        sx = rect.width() / 200.0
        sy = rect.height() / 200.0
        painter.scale(sx, sy)
        painter.scale(1.0, -1.0)  # Y-flip: contract Y-up → screen Y-down

        for prim in contract.geometry:
            _draw_primitive(painter, prim, colors, sx, sy)

        painter.restore()

    @staticmethod
    def port_screen_position(
        port: ContractPort,
        rect: QRectF,
        rotation_deg: float = 0.0,
    ) -> QPointF:
        """Map a contract port to its screen-space position."""
        from PySide6.QtCore import QPointF

        # Contract → normalized (0..1, Y-flipped)
        nx = (port.x + 100.0) / 200.0
        ny = (-port.y + 100.0) / 200.0

        # Apply rotation around (0.5, 0.5)
        if rotation_deg:
            dx, dy = nx - 0.5, ny - 0.5
            rad = math.radians(rotation_deg)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            nx = 0.5 + dx * cos_r - dy * sin_r
            ny = 0.5 + dx * sin_r + dy * cos_r

        return QPointF(
            rect.x() + nx * rect.width(),
            rect.y() + ny * rect.height(),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Internal: primitive drawing helpers
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_color(key: str, colors: dict[str, str]) -> QColor:
    """Resolve a color key to a QColor."""
    from PySide6.QtGui import QColor
    hex_str = colors.get(key, key)  # fall back to treating key as hex
    if not hex_str:
        return QColor(0, 0, 0, 0)  # transparent
    return QColor(hex_str)


def _make_pen(
    color_key: str,
    stroke_width: float,
    colors: dict[str, str],
    sx: float,
    sy: float,
) -> QPen:
    """Create a cosmetic QPen from a color key and stroke width."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPen

    if not color_key or color_key == "none":
        return QPen(Qt.PenStyle.NoPen)

    pen = QPen(_resolve_color(color_key, colors))
    # Cosmetic pen: stroke_width is in screen pixels, unaffected by transform.
    # Compensate for the painter scale so that the final screen width matches.
    avg_scale = (abs(sx) + abs(sy)) / 2.0
    pen.setWidthF(stroke_width / avg_scale if avg_scale > 0 else stroke_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _make_brush(fill_key: str, colors: dict[str, str]) -> QBrush:
    """Create a QBrush from a fill color key."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QBrush

    if not fill_key or fill_key == "none":
        return QBrush(Qt.BrushStyle.NoBrush)
    return QBrush(_resolve_color(fill_key, colors))


def _draw_primitive(
    painter: QPainter,
    prim: GeometryPrimitive,
    colors: dict[str, str],
    sx: float,
    sy: float,
) -> None:
    """Dispatch and draw a single geometry primitive."""
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPolygonF

    if isinstance(prim, GLine):
        painter.setPen(_make_pen(prim.color_key, prim.stroke_width, colors, sx, sy))
        painter.drawLine(
            QPointF(prim.start[0], prim.start[1]),
            QPointF(prim.end[0], prim.end[1]),
        )

    elif isinstance(prim, GPolyline):
        painter.setPen(_make_pen(prim.color_key, prim.stroke_width, colors, sx, sy))
        painter.setBrush(_make_brush("", colors))
        points = [QPointF(x, y) for x, y in prim.points]
        painter.drawPolyline(points)

    elif isinstance(prim, GRectangle):
        painter.setPen(_make_pen(prim.stroke_key, prim.stroke_width, colors, sx, sy))
        painter.setBrush(_make_brush(prim.fill_key, colors))
        x = min(prim.x1, prim.x2)
        y = min(prim.y1, prim.y2)
        w = abs(prim.x2 - prim.x1)
        h = abs(prim.y2 - prim.y1)
        if prim.corner_radius > 0:
            painter.drawRoundedRect(QRectF(x, y, w, h), prim.corner_radius, prim.corner_radius)
        else:
            painter.drawRect(QRectF(x, y, w, h))

    elif isinstance(prim, GEllipse):
        painter.setPen(_make_pen(prim.stroke_key, prim.stroke_width, colors, sx, sy))
        painter.setBrush(_make_brush(prim.fill_key, colors))
        painter.drawEllipse(
            QPointF(prim.cx, prim.cy),
            prim.rx, prim.ry,
        )

    elif isinstance(prim, GArc):
        painter.setPen(_make_pen(prim.color_key, prim.stroke_width, colors, sx, sy))
        painter.setBrush(_make_brush("", colors))
        arc_rect = QRectF(
            prim.cx - prim.rx, prim.cy - prim.ry,
            prim.rx * 2, prim.ry * 2,
        )
        # Qt drawArc uses 1/16th degree units
        painter.drawArc(arc_rect, int(prim.start_angle * 16), int(prim.sweep_angle * 16))

    elif isinstance(prim, GPolygon):
        painter.setPen(_make_pen(prim.stroke_key, prim.stroke_width, colors, sx, sy))
        painter.setBrush(_make_brush(prim.fill_key, colors))
        poly = QPolygonF([QPointF(x, y) for x, y in prim.points])
        painter.drawPolygon(poly)
