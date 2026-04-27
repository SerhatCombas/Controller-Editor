"""Visual contracts for electrical passive pilot components.

Phase 7.7: resistor, capacitor, inductor, ground (electrical reference).

All contracts follow the MSL-inspired convention documented in
``docs/VISUAL_CONTRACT_SPEC.md``:
  - Contract space: -100..+100, Y-up
  - Domain: electrical (blue #0055FF)
  - Canonical orientation: **horizontal** (flow left-to-right)

MSL geometry source
-------------------
Geometry proportions are extracted from the OMEdit SVG exports of
Modelica.Electrical.Analog.Basic (MSL 4.0).  The inner Modelica
coordinates live under ``matrix(0.505774,0,0,-0.505774,...)`` transform
groups.  Key reference paths per component:

  Resistor:   body rect (-70,-30) 140x60, stubs (-90,0)->(-70,0) and (70,0)->(90,0)
  Capacitor:  two parallel plates at x=-6 and x=6, y:[-28,28],
              stubs (-90,0)->(-6,0) and (6,0)->(90,0)
  Inductor:   4 semicircular coils x:-60..60, peak y=14,
              stubs (-90,0)->(-60,0) and (60,0)->(90,0)
  Ground:     3 horizontal lines at y=50,30,10 (widths 120,80,40),
              stub (0,90)->(0,50), single port at (0,90)

Contract space scaling
----------------------
MSL port positions are at x=+/-90; contract space extends to +/-100.
Stubs are extended by 10 units to reach the contract edge ports.

Port convention (horizontal canonical)
--------------------------------------
  p (positive):  x = -100, y = 0  (left)   -- MSL pin p
  n (negative):  x = +100, y = 0  (right)  -- MSL pin n

With DEG_90 layout rotation applied by the canvas:
  p -> screen top    (0.5, 0.0)
  n -> screen bottom (0.5, 1.0)

Exception: Ground is single-port, port at (0, +100) top, orientation DEG_0.
"""
from __future__ import annotations

from app.ui.canvas.visual_contract import (
    ComponentVisualContract,
    ContractPort,
    GArc,
    GLine,
    GPolyline,
    GRectangle,
    LabelSlot,
)

# ===================================================================
# Resistor  (Modelica: Electrical.Analog.Basic.Resistor)
# ===================================================================
# MSL: body rect (-70,-30)->(70,30) = 140x60, white fill, blue stroke.
#       stubs (-90,0)->(-70,0) and (70,0)->(90,0).
# Extended stubs to x=+/-100 for contract edge ports.

RESISTOR_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub
        GLine(start=(-100, 0), end=(-70, 0), stroke_width=2.0, color_key="domain_stroke"),
        # Body rectangle (filled)
        GRectangle(x1=-70, y1=-30, x2=70, y2=30,
                   fill_key="domain_fill", stroke_key="domain_stroke", stroke_width=2.0),
        # Right stub
        GLine(start=(70, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "p": ContractPort("p", x=-100, y=0, side="left"),
        "n": ContractPort("n", x=100, y=0, side="right"),
    },
    default_extent=(120.0, 60.0),
    min_extent=(80.0, 40.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="electrical",
)


# ===================================================================
# Capacitor  (Modelica: Electrical.Analog.Basic.Capacitor)
# ===================================================================
# MSL: two parallel vertical plates at x=-6 and x=6, y:[-28,28].
#       stubs (-90,0)->(-6,0) and (6,0)->(90,0).
# Extended stubs to x=+/-100.

CAPACITOR_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub
        GLine(start=(-100, 0), end=(-6, 0), stroke_width=2.0, color_key="domain_stroke"),
        # Left plate
        GLine(start=(-6, -28), end=(-6, 28), stroke_width=2.5, color_key="domain_stroke"),
        # Right plate
        GLine(start=(6, -28), end=(6, 28), stroke_width=2.5, color_key="domain_stroke"),
        # Right stub
        GLine(start=(6, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "p": ContractPort("p", x=-100, y=0, side="left"),
        "n": ContractPort("n", x=100, y=0, side="right"),
    },
    default_extent=(120.0, 60.0),
    min_extent=(80.0, 40.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="electrical",
)


# ===================================================================
# Inductor  (Modelica: Electrical.Analog.Basic.Inductor)
# ===================================================================
# MSL: 4 semicircular coils from x=-60 to x=60, each 30 units wide,
#       peak at y=14.  Approximated as 4 arcs (half-ellipses).
#       stubs (-90,0)->(-60,0) and (60,0)->(90,0).
# Extended stubs to x=+/-100.
#
# Each coil is a semicircular arc centered on y=0 opening upward.
# Coil centers: x = -45, -15, 15, 45.  Radius rx=15, ry=14.

INDUCTOR_CONTRACT = ComponentVisualContract(
    geometry=(
        # Left stub
        GLine(start=(-100, 0), end=(-60, 0), stroke_width=2.0, color_key="domain_stroke"),
        # 4 semicircular coils (arcs from 0 to 180 deg, opening upward)
        GArc(cx=-45, cy=0, rx=15, ry=14, start_angle=0, sweep_angle=180,
             stroke_width=2.0, color_key="domain_stroke"),
        GArc(cx=-15, cy=0, rx=15, ry=14, start_angle=0, sweep_angle=180,
             stroke_width=2.0, color_key="domain_stroke"),
        GArc(cx=15, cy=0, rx=15, ry=14, start_angle=0, sweep_angle=180,
             stroke_width=2.0, color_key="domain_stroke"),
        GArc(cx=45, cy=0, rx=15, ry=14, start_angle=0, sweep_angle=180,
             stroke_width=2.0, color_key="domain_stroke"),
        # Right stub
        GLine(start=(60, 0), end=(100, 0), stroke_width=2.0, color_key="domain_stroke"),
    ),
    ports={
        "p": ContractPort("p", x=-100, y=0, side="left"),
        "n": ContractPort("n", x=100, y=0, side="right"),
    },
    default_extent=(120.0, 60.0),
    min_extent=(80.0, 40.0),
    label_slots={
        "name": LabelSlot(side="top", offset=12.0),
        "parameter": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="electrical",
)


# ===================================================================
# Ground  (Modelica: Electrical.Analog.Basic.Ground)
# ===================================================================
# MSL: 3 horizontal lines at y=50,30,10 with decreasing widths
#       (120, 80, 40 units).  Vertical stub (0,90)->(0,50).
#       Single port at (0,90).
# Extended stub to (0,100) for contract edge.
#
# Single-port component, always DEG_0 orientation.

GROUND_CONTRACT = ComponentVisualContract(
    geometry=(
        # Stub: vertical line from port down to top bar
        GLine(start=(0, 100), end=(0, 50), stroke_width=2.0, color_key="domain_stroke"),
        # Top bar (widest)
        GLine(start=(-60, 50), end=(60, 50), stroke_width=2.5, color_key="domain_stroke"),
        # Middle bar
        GLine(start=(-40, 30), end=(40, 30), stroke_width=2.5, color_key="domain_stroke"),
        # Bottom bar (narrowest)
        GLine(start=(-20, 10), end=(20, 10), stroke_width=2.5, color_key="domain_stroke"),
    ),
    ports={
        "p": ContractPort("p", x=0, y=100, side="top"),
    },
    default_extent=(160.0, 50.0),
    min_extent=(100.0, 30.0),
    label_slots={
        "name": LabelSlot(side="bottom", offset=8.0),
    },
    domain_key="electrical",
)
