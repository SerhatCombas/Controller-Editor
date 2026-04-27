"""Visual contracts for mechanical translational pilot components.

Phase 7 pilot: mass, spring, damper, fixed (ground reference).

All contracts follow the MSL-inspired convention documented in
``docs/VISUAL_CONTRACT_SPEC.md``:
  - Contract space: -100..+100, Y-up
  - Domain: translational (green #007F00)
  - Canonical orientation: **horizontal** (flow left-to-right)

MSL geometry source
-------------------
Geometry proportions are extracted from the OMEdit SVG exports of
Modelica.Mechanics.Translational.Components (MSL 4.0).  The inner
Modelica coordinates live under ``matrix(0.505774,0,0,-0.505774,...)``
transform groups.  Key reference paths per component:

  Mass:   body rect (-55,-30) 111x60, axis line (-100,0)->(100,0)
  Spring: zigzag (-98,0)->(-60,0)->(-44,-30)->(-16,30)->(14,-30)->(44,30)->(60,0)->(100,0)
  Damper: axis (-90,0)->(100,0), U-shape (60,-30)->(-60,-30)->(-60,30)->(60,30),
          piston rect (-60,-30) 90x60 gray fill
  Fixed:  bar (-80,-40)->(80,-40), 4 hatch lines to y=-80, stub (0,-40)->(0,-10)

Canonical orientation
---------------------
All two-terminal contracts use **horizontal canonical** form (ports at
x=-100 and x=+100, flow left-to-right).  MSL SVG coordinates are used
AS-IS with no transposition.  Vertical placement on the canvas is
achieved through layout rotation (DEG_90 on ComponentVisualSpec /
CanvasVisualComponent), NOT by redefining contract geometry.

Port convention (horizontal canonical)
--------------------------------------
  flange_a:  x = -100, y = 0  (left)   -- MSL left port
  flange_b:  x = +100, y = 0  (right)  -- MSL right port

With DEG_90 layout rotation applied by the canvas:
  flange_a -> screen top    (0.5, 0.0)
  flange_b -> screen bottom (0.5, 1.0)

Index mapping bridge:
  connector_ports[0] ("top"/"R")    <-> contract_ports[0] (flange_a)
  connector_ports[1] ("bottom"/"C") <-> contract_ports[1] (flange_b)

Exception: Fixed is single-port, port at (0, +100) top, orientation DEG_0.
"""
from __future__ import annotations

from app.ui.canvas.visual_contract import (
    ComponentVisualContract,
    ContractPort,
    GLine,
    GPolyline,
    GRectangle,
    LabelSlot,
)

# ===================================================================
# Mass  (Modelica: Mechanics.Translational.Components.Mass)
# ===================================================================
# MSL horizontal: body rect (-55,-30)->(56,30) = 111x60, axis (-100,0)->(100,0)
# Used AS-IS: left stub (-100,0)->(-55,0), body rect, right stub (55,0)->(100,0).

MASS_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub
        GLine(start=(-100, 0), end=(-55, 0), stroke_width=2.0, color_key="domain_stroke"),
        # Body rectangle (filled) -- MSL proportions 110x60
        GRectangle(x1=-55, y1=-30, x2=55, y2=30,
                   fill_key="domain_fill", stroke_key="domain_stroke", stroke_width=2.0),
        # Right stub
        GLine(start=(55, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "flange_a": ContractPort("flange_a", x=-100, y=0, side="left"),
        "flange_b": ContractPort("flange_b", x=100, y=0, side="right"),
    },
    default_extent=(172.0, 92.0),
    min_extent=(120.0, 60.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="translational",
)


# ===================================================================
# Spring  (Modelica: Mechanics.Translational.Components.Spring)
# ===================================================================
# MSL horizontal zigzag: (-98,0)->(-60,0)->(-44,-30)->(-16,30)->(14,-30)->(44,30)->(60,0)->(100,0)
# Used AS-IS: left stub, zigzag body, right stub.
#   Body zone x:-60..+60 (120 units), amplitude +/-30, ~2.5 cycles.
#   Stubs x:-100..-60 and x:+60..+100 (40 units each).

SPRING_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub
        GLine(start=(-100, 0), end=(-60, 0), stroke_width=2.0, color_key="domain_stroke"),
        # Zigzag body -- MSL-faithful 2.5-cycle
        GPolyline(
            points=(
                (-60, 0), (-44, -30), (-16, 30), (14, -30),
                (44, 30), (60, 0),
            ),
            stroke_width=2.0,
            color_key="domain_stroke",
        ),
        # Right stub
        GLine(start=(60, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "flange_a": ContractPort("flange_a", x=-100, y=0, side="left"),
        "flange_b": ContractPort("flange_b", x=100, y=0, side="right"),
    },
    default_extent=(78.0, 148.0),
    min_extent=(60.0, 100.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="translational",
)


# ===================================================================
# Damper  (Modelica: Mechanics.Translational.Components.Damper)
# ===================================================================
# MSL horizontal:
#   Axis line (-90,0)->(100,0).
#   Cylinder U-shape opens right: (60,-30)->(-60,-30)->(-60,30)->(60,30).
#   Piston rect (gray #C0C0C0 fill): (-60,-30) w=90 h=60 -> (-60,-30)->(30,30).
#
# Used AS-IS: left stub, piston rect, U-shape walls, right rod.

DAMPER_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub -- rod from port into cylinder
        GLine(start=(-100, 0), end=(-60, 0), stroke_width=2.0, color_key="domain_stroke"),
        # Piston body (gray fill) -- drawn before walls so walls render on top
        GRectangle(x1=-60, y1=-30, x2=30, y2=30,
                   fill_key="#C0C0C0", stroke_key="domain_stroke", stroke_width=2.0),
        # Cylinder U walls (opens right)
        GLine(start=(60, -30), end=(-60, -30), stroke_width=2.0, color_key="domain_stroke"),
        GLine(start=(-60, -30), end=(-60, 30), stroke_width=2.0, color_key="domain_stroke"),
        GLine(start=(-60, 30), end=(60, 30), stroke_width=2.0, color_key="domain_stroke"),
        # Right rod -- from piston through open cylinder end to port
        GLine(start=(30, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "flange_a": ContractPort("flange_a", x=-100, y=0, side="left"),
        "flange_b": ContractPort("flange_b", x=100, y=0, side="right"),
    },
    default_extent=(80.0, 142.0),
    min_extent=(60.0, 100.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="translational",
)


# ===================================================================
# Fixed / Ground  (Modelica: Mechanics.Translational.Components.Fixed)
# ===================================================================
# Single-port component.  Port at (0, +100) top, orientation DEG_0.
# MSL horizontal:
#   Bar (-80,-40)->(80,-40) width=160, 4 hatch lines to y=-80,
#   stub (0,-40)->(0,-10).
#
# Kept with top port and horizontal bar (visual identity of ground/wall).
# No rotation needed -- always displayed as-is.

FIXED_CONTRACT = ComponentVisualContract(
    geometry=(
        # Stub: vertical line from port down to bar
        GLine(start=(0, 100), end=(0, 40), stroke_width=2.0, color_key="domain_stroke"),
        # Horizontal bar -- MSL width 160 units
        GLine(start=(-80, 40), end=(80, 40), stroke_width=2.5, color_key="domain_stroke"),
        # 4 hatch lines (diagonal, 45 deg left-and-down, matching MSL)
        GLine(start=(80, 40), end=(40, 0), stroke_width=1.5, color_key="domain_stroke"),
        GLine(start=(40, 40), end=(0, 0), stroke_width=1.5, color_key="domain_stroke"),
        GLine(start=(0, 40), end=(-40, 0), stroke_width=1.5, color_key="domain_stroke"),
        GLine(start=(-40, 40), end=(-80, 0), stroke_width=1.5, color_key="domain_stroke"),
    ),
    ports={
        "flange": ContractPort("flange", x=0, y=100, side="top"),
    },
    default_extent=(260.0, 36.0),
    min_extent=(160.0, 30.0),
    label_slots={
        "name": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="translational",
)
