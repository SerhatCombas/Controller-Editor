# Component Visual Contract Specification

**Status:** Phase 7 — Pilot (mass, spring, damper, fixed)
**Date:** 2026-04-27

---

## 1. Purpose

Every component in the system must be produced from a single, unified
**ComponentVisualContract**.  The contract is the single source of truth for:

- Icon geometry (what to draw)
- Port anchors (where to connect)
- Default extent (how big on canvas)
- Label slots (where name/parameter text goes)
- Domain color (stroke/fill)

No separate SVG file, no separate `base_size`, no separate `port_mapping`
table should override what the contract declares.  The goal is:
**one contract → one component → predictable layout.**

---

## 2. Coordinate System

### 2.1 Contract Space: MSL-style, Y-up

All geometry and port coordinates in the contract use the Modelica convention:

```
            y = +100 (top)
               │
  x = -100 ────┼──── x = +100
               │
            y = -100 (bottom)
```

- Origin (0, 0) is the component center.
- X increases to the right.
- Y increases **upward** (mathematical convention).
- Full canvas: `{-100, -100}` to `{+100, +100}` — a 200×200 unit space.

### 2.2 Rendering: Qt Y-down

QPainter uses screen coordinates (Y increases downward).  The renderer
applies a single Y-flip transform when mapping contract → screen:

```python
screen_y = -contract_y
```

This transform is applied **once** in the renderer, never in individual
contracts.  Contract authors always think in Y-up.

### 2.3 Why This Matters

Without an explicit convention, port anchors at "top" and label slots at
"above the body" would flip unpredictably.  Y-up is declared, Y-flip is
the renderer's job.

---

## 3. Canonical Icon Orientation

### 3.1 Rule: All icons are defined horizontally

Every two-terminal component is authored with its signal/energy flow going
**left → right**:

```
  port_a (left)  ──── [ body ] ──── port_b (right)
```

This applies to **all** domains:

| Domain        | port_a (left)     | port_b (right)     |
|---------------|-------------------|--------------------|
| Electrical    | positive (p)      | negative (n)       |
| Translational | flange_a          | flange_b           |
| Rotational    | flange_a          | flange_b           |

### 3.2 Vertical placement = rotation

If the canvas layout needs a component to appear vertically (e.g., spring
hanging down), the **layout applies a 90° rotation** to the contract.
The contract itself never changes.

```
Contract:     [──spring──]     (horizontal)
Layout rot:   │                (vertical, 90° CW)
              spring
              │
```

### 3.3 Rotation and port mapping

When the renderer rotates a component by θ degrees clockwise:

| Rotation | port_a position | port_b position |
|----------|-----------------|-----------------|
| 0°       | left            | right           |
| 90° CW   | top             | bottom          |
| 180°     | right           | left            |
| 270° CW  | bottom          | top             |

Port identity never changes — only its screen position does.
The compiler always sees `flange_a` and `flange_b`, regardless of rotation.

---

## 4. Port Anchor Rule

### 4.1 Two-terminal components

Ports are at the **exact edges** of the contract canvas:

```
port_a:  x = -100,  y = 0    (left midpoint)
port_b:  x = +100,  y = 0    (right midpoint)
```

No exceptions for standard two-terminal components (resistor, spring,
damper, capacitor, inductor).

### 4.2 Single-port components (reference/ground)

Reference components have one port at one edge:

```
Ground/Fixed:  port at  x = 0,  y = +100   (top center, Y-up)
```

After rendering with Y-flip, this appears at the top of the drawn symbol —
the connection point faces upward toward the system.

### 4.3 Port stubs

The visual "wire lead-in" from the canvas edge to the component body is
called a **stub**.  Stubs are part of the icon geometry, not the wiring
system.  Typical stub length: 40 units (from ±100 to ±60).

### 4.4 Canonical port names

Contracts use **canonical physical names**, not visual names:

| Domain        | Port A name | Port B name |
|---------------|-------------|-------------|
| Electrical    | `p`         | `n`         |
| Translational | `flange_a`  | `flange_b`  |
| Rotational    | `flange_a`  | `flange_b`  |

Legacy canvas names (`R`, `C`, `top`, `bottom`, `positive`, `negative`)
are handled by a compatibility mapping layer, not stored in the contract.

---

## 5. Icon Body Proportions

### 5.1 Body zone

The icon body (the visible symbol shape) occupies the **inner portion**
of the contract canvas.  Standard proportions:

```
Body X range:  [-60, +60]    (60% of canvas width)
Body Y range:  [-40, +40]    (40% of canvas height)
Stub zone:     [-100, -60] and [+60, +100] on X axis
```

### 5.2 Component-specific body shapes

Individual contracts may use different body zones, but the port stubs
must always bridge from the body edge to the canvas edge at ±100.

Example:
- Mass: body fills `[-50, -30, +50, +30]`, stubs extend to ±100
- Spring: zigzag spans `[-60, -20, +60, +20]`, stubs extend to ±100
- Ground: hatched area below, port stub extends upward to y=+100

### 5.3 Extent scaling

By default, the renderer uses **non-uniform scaling**: the contract's
200×200 space stretches to fill the layout extent in both axes
independently.  This matches Modelica's extent behavior — a spring in
a 90×200 extent naturally appears tall and narrow.

```python
scale_x = layout_extent_width / 200.0
scale_y = layout_extent_height / 200.0
# Non-uniform: applied separately to X and Y
```

Components that require **uniform scaling** (e.g., wheel with circular
geometry) declare `preserve_aspect_ratio = True` in their contract.
For these, `scale = min(scale_x, scale_y)` is used, and the symbol is
centered within the extent.

---

## 6. Extent and Size

### 6.1 Three levels of size

```
contract_canvas:  Always 200×200 (fixed, never stored)
default_extent:   Suggested canvas size in pixels (from contract)
layout_extent:    Actual size on canvas (from layout/save file)
```

### 6.2 Relationship to current fields

| Current field      | New equivalent           | Source           |
|--------------------|--------------------------|------------------|
| base_size          | default_extent           | Contract         |
| preferred_size     | Removed (use default)    | —                |
| minimum_size       | min_extent               | Contract         |
| size (in layout)   | layout_extent            | Save file        |

### 6.3 Scale factor

```python
scale_x = layout_extent_width / 200.0
scale_y = layout_extent_height / 200.0
# Non-uniform by default (see §5.3)
```

---

## 7. Text / Label Slots

### 7.1 Label slots are NOT part of contract geometry

Label slots live in the **canvas annotation layer**, not in the contract
geometry primitive list.  The contract declares:

```python
label_slots = {
    "name": LabelSlot(side="top", offset=12),        # above bounding box
    "parameter": LabelSlot(side="bottom", offset=8),  # below bounding box
}
```

The `side` and `offset` are relative to the component's **screen-space
bounding box**, not to the contract coordinate system.

### 7.2 Labels do NOT rotate with the component

When a component is rotated, geometry and ports rotate.  Labels do NOT.
The name always appears above the component's screen bounding box, and
the parameter always appears below — regardless of rotation angle.

This ensures text remains readable in all orientations.

### 7.3 Parameter text template

The contract does NOT contain parameter display templates.  It only
declares that a parameter slot exists.

The actual template string (e.g., `"m={m} kg"`, `"c={c} N/m"`) comes
from **component registry / display metadata**, not from the visual
contract.  This prevents the contract from needing to know about
physics parameters.

### 7.4 Pilot scope

For Phase 7 pilot:
- `name` slot: rendered, shows instance name or display name
- `parameter` slot: optional, simple string from registry metadata
- No dynamic precision, units formatting, or hidden parameter logic yet

### 7.5 Text rendering rules

- Font: small, sans-serif
- Color: same as domain stroke color (or a muted variant)
- Alignment: centered on component center-x
- Text is always horizontal (never rotated)

---

## 8. Domain Color

### 8.1 Color source: domain registry, not component

Each physical domain defines its visual style:

```python
DOMAIN_STYLES = {
    "electrical":    {"stroke": "#0055FF", "fill": "#E8F0FE"},
    "translational": {"stroke": "#007F00", "fill": "#E8F5E8"},
    "rotational":    {"stroke": "#7F7FA0", "fill": "#F0F0F5"},
    "thermal":       {"stroke": "#BF0000", "fill": "#FDE8E8"},
}
```

### 8.2 UI state layering

Domain color is the **base layer**.  UI states are overlaid:

```
Layer 0 (base):     domain stroke + domain fill
Layer 1 (hover):    stroke brightens, fill lightens
Layer 2 (selected): selection outline (UI blue #3B82F6), domain fill preserved
Layer 3 (invalid):  red overlay or red stroke
Layer 4 (disabled): gray desaturation
```

Domain color and UI state color never mix.  The renderer computes the
final color by applying state modifiers to the domain base.

---

## 9. Legacy SVG Fallback

### 9.1 Gradual migration

Not all components will have visual contracts on day one.  The renderer
must support both paths:

```python
if component.has_visual_contract():
    render_from_contract(component.visual_contract, extent, rotation)
else:
    render_legacy_svg(component.svg_symbol, extent, rotation)
```

### 9.2 What triggers contract rendering

A component uses the contract path when its `ComponentVisualSpec` has a
`visual_contract` field set.  Otherwise, the existing `svg_symbol` +
`_draw_*` methods are used.

### 9.3 Shared canvas layers

Both render paths (contract primitive and legacy SVG) share the **same**
canvas overlay layers for:

- Selection box / outline
- Port markers (circles at connection points)
- Hover highlights
- Wire endpoints

Only the icon body drawing differs.  This prevents divergent
selection/port behavior between old and new components.

### 9.4 No big bang

Phase 7 pilot migrates 4 components.  All others remain on legacy SVG.
The two paths coexist indefinitely until full migration.

---

## 10. Geometry Primitives

### 10.1 Available primitives

The contract geometry is defined using these primitives:

```
Line(start, end, stroke_width, color_key)
Polyline(points, stroke_width, color_key)
Rectangle(x1, y1, x2, y2, fill_key, stroke_key, corner_radius)
Ellipse(cx, cy, rx, ry, fill_key, stroke_key)
Arc(cx, cy, rx, ry, start_angle, sweep_angle, stroke_width, color_key)
Polygon(points, fill_key, stroke_key)
```

Note: `Text` is NOT a geometry primitive.  Text labels (name, parameters)
are drawn by the canvas annotation layer using label slots (§7), not by
the contract geometry.  This separation prevents geometry text and UI
label text from mixing.

### 10.2 Color keys

Primitives use **color keys**, not literal colors:

```
"domain_stroke"   → resolved from domain registry
"domain_fill"     → resolved from domain registry
"background"      → canvas background (for white fills in dark theme)
"stub"            → lighter version of domain_stroke
```

This enables theme support without changing contracts.

### 10.3 Example: Spring contract geometry

```python
geometry = [
    # Left stub
    Line((-100, 0), (-60, 0), stroke_width=2, color_key="domain_stroke"),
    # Zigzag body
    Polyline([(-60, 0), (-45, 25), (-30, -25), (-15, 25),
              (0, -25), (15, 25), (30, -25), (45, 25), (60, 0)],
             stroke_width=2, color_key="domain_stroke"),
    # Right stub
    Line((60, 0), (100, 0), stroke_width=2, color_key="domain_stroke"),
]
```

---

## 11. Contract ↔ Physics Boundary

### 11.1 Contract does NOT touch physics

The visual contract knows:
- How to draw the component
- Where the ports are
- What the display name is

The visual contract does NOT know:
- Component equations
- Parameter values or defaults
- Reducer behavior
- Symbolic model structure

### 11.2 Port name invariant

```
visual_contract.ports.keys() == component_definition.ports.keys()
```

The canonical port names in the contract must exactly match the port
names in the physics component definition.  This is a testable invariant.

---

## 12. Rotation Behavior

### 12.1 Rotation affects geometry and ports, not labels

When a component is rotated by θ:

- All geometry primitives are rotated around (0, 0)
- Port anchor coordinates are rotated
- Text labels are NOT rotated (they remain horizontal/readable)

### 12.2 Rotation is a layout property

Rotation is stored in the layout/save file, not in the contract.
The contract defines the canonical horizontal form.

---

## 13. Success Criteria for Phase 7 Pilot

After the pilot is complete:

1. ✅ mass/spring/damper/fixed render from primitive contracts, not SVG
2. ✅ Port anchors come from contract (flange_a/flange_b)
3. ✅ Layout extent change scales the symbol correctly
4. ✅ 90° rotation makes spring/damper vertical with correct port positions
5. ✅ Canvas compiler sees same canonical ports as before
6. ✅ Domain color (green for translational) applied from registry
7. ✅ Name label appears above component
8. ✅ Legacy SVG components (wheel, road, electrical) still render correctly
9. ✅ Single Mass-Spring-Damper layout looks like a proper diagram editor
10. ✅ All existing tests pass (926+)
