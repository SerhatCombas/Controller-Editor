# SVG Normalization Analysis Report
**Folder:** `app/SVG`
**Files analyzed:** 24
**Analysis date:** 2026-04-08

---

## A. Summary Table

| Filename | Width | Height | ViewBox | W/H ratio | VB ratio | Drawable bounds | Content coverage % | Centered? | Visual size issue | Alignment issue | Normalization status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AC_Current_source.svg | 100 | 100 | 0 0 28 40 | 1.000 | 0.700 | (3.4,0.5)→(23.6,40.5) 20.2×40.0 | 72.2% | yes | TOO LARGE | no | **POOR** |
| AC_Voltage_source.svg | 100 | 100 | 0 0 28 40 | 1.000 | 0.700 | (3.4,0.5)→(23.6,40.5) 20.2×40.0 | 72.2% | yes | TOO LARGE | no | **POOR** |
| Capasitor_Icon_new.svg | 100 | 100 | 0 0 40.2 40 | 1.000 | 1.005 | (0.5,12.0)→(40.5,28.0) 40.0×16.0 | 39.8% | yes | TOO LARGE | no | MODERATE |
| Current_sensor.svg | 100 | 100 | 0 0 100 50 | 1.000 | 2.000 | (-0.0,0.8)→(100.2,40.2) 100.2×39.4 | 79.0% | yes | TOO LARGE | **YES** | **POOR** |
| DC_Current_sensor.svg | 100 | 100 | 0 0 28 40 | 1.000 | 0.700 | (3.4,0.5)→(23.6,40.5) 20.2×40.0 | 72.2% | yes | TOO LARGE | no | **POOR** |
| DC_Voltage_source.svg | 100 | 100 | 0 0 28 40 | 1.000 | 0.700 | (3.4,0.5)→(23.6,40.5) 20.2×40.0 | 72.2% | yes | TOO LARGE | no | **POOR** |
| Damper_Icon_new.svg | 100 | 100 | 0 0 40.3 28 | 1.000 | 1.439 | (0.5,5.8)→(40.5,18.6) 40.0×12.8 | 45.3% | yes | TOO LARGE | **YES** | **POOR** |
| Diode_Icon_new.svg | 100 | 100 | 0 0 102 28 | 1.000 | 3.643 | (30.7,5.1)→(70.7,22.9) 40.0×17.8 | 25.0% | yes | ok | no | MODERATE |
| Elektrical_Reference.svg | 100 | 100 | 0 0 20 20 | 1.000 | 1.000 | (0.1,0.5)→(19.9,18.6) 19.8×18.1 | 89.3% | yes | TOO LARGE | no | MODERATE |
| FreeEnd_Icon_new.svg | 100 | 100 | 0 0 20 21 | 1.000 | 0.952 | (0.7,0.5)→(9.9,19.7) 9.1×19.2 | 41.6% | **NO** | ok | **YES** | **POOR** |
| Ideal_Force_sensor.svg | 100 | 100 | 0 0 100 50 | 1.000 | 2.000 | (-0.0,0.7)→(100.2,40.7) 100.2×39.9 | 80.0% | yes | TOO LARGE | **YES** | **POOR** |
| Ideal_Force_source.svg | 100 | 100 | 0 0 38 49 | 1.000 | 0.776 | (1.5,0.5)→(32.9,48.0) 31.4×47.5 | 80.1% | yes | TOO LARGE | no | **POOR** |
| Ideal_Torque_source.svg | 100 | 100 | 0 0 48 49 | 1.000 | 0.980 | (5.5,0.5)→(36.9,48.0) 31.4×47.5 | 63.4% | yes | TOO LARGE | **YES** | **POOR** |
| Ideal_Translational_Motion_sensor.svg | 100 | 100 | 0 0 102 41.8 | 1.000 | 2.440 | (-0.0,0.7)→(102.0,40.8) 102.0×40.0 | 95.7% | yes | TOO LARGE | no | **POOR** |
| Ideal_torque_sensor.svg | 100 | 100 | 0 0 100 50 | 1.000 | 2.000 | (-0.0,0.7)→(100.2,40.8) 100.2×40.0 | 80.2% | yes | TOO LARGE | **YES** | **POOR** |
| Inductor_Icon_new.svg | 100 | 100 | 0 0 40 20 | 1.000 | 2.000 | (0.5,4.7)→(40.5,12.3) 40.0×7.6 | 38.1% | yes | TOO LARGE | **YES** | **POOR** |
| Mass_Icon_new.svg | 100 | 100 | 0 0 28.4 40 | 1.000 | 0.710 | (1.8,1.5)→(26.6,37.8) 24.8×36.3 | 79.5% | yes | ok | no | MODERATE |
| Reference_Icon_new.svg | 100 | 100 | 0 0 23 21 | 1.000 | 1.095 | (0.5,0.5)→(22.5,20.0) 22.0×19.5 | 88.8% | yes | TOO LARGE | no | **POOR** |
| Resistor_Icon_new.svg | 100 | 100 | 0 0 40.3 28 | 1.000 | 1.439 | (0.5,6.9)→(40.5,17.6) 40.0×10.7 | 37.9% | yes | TOO LARGE | **YES** | **POOR** |
| Spring_Icon_new.svg | 100 | 100 | 0 0 41 28 | 1.000 | 1.464 | (1.5,6.2)→(41.5,20.3) 40.0×14.2 | 49.3% | yes | TOO LARGE | no | **POOR** |
| Switch_Icon_new.svg | 100 | 100 | 0 0 85 82 | 1.000 | 1.037 | (15.7,0.5)→(85.0,82.0) 69.3×81.5 | 81.0% | yes | TOO LARGE | **YES** | **POOR** |
| Voltage_sensor.svg | 100 | 100 | 0 0 80 85 | 1.000 | 0.941 | (20.0,3.4)→(59.4,82.4) 39.4×79.0 | 45.8% | yes | ok | no | MODERATE |
| Wheel_black.svg | 100 | 100 | 0 0 123 123 | 1.000 | 1.000 | (0.1,0.1)→(122.9,122.9) 122.9×122.9 | 99.8% | yes | TOO LARGE | no | MODERATE |
| Wheel_white.svg | 100 | 100 | 0 0 21.5 21.5 | 1.000 | 1.000 | (0.0,0.0)→(21.5,21.5) 21.5×21.5 | 100.0% | yes | TOO LARGE | no | MODERATE |

**Summary counts:** GOOD: 0 / MODERATE: 7 / POOR: 17

---

## B. Per-File Detailed Analysis

### AC_Current_source.svg

Root SVG declares `width=100 height=100` but `viewBox="0 0 28 40"`, giving a VB aspect ratio of 0.700 versus the rendered square of 1.000. The browser will letterbox (add transparent bands) or distort depending on `preserveAspectRatio`. With the default `xMidYMid meet`, the 28×40 canvas is fitted to 100px wide, resulting in only 70px of height used and 15px of blank space top and bottom. The drawable content spans the full height of the viewBox (min-y 0.5 → max-y 40.5, essentially 100% of the 40-unit VB height), meaning the content has zero breathing room at the top and bottom and is already brushing the canvas edge. Horizontally the content is 20.2 units wide inside a 28-unit canvas, leaving approximately 3.4 left and 4.4 right padding — adequate but slightly asymmetric.

Transform complexity: 11 nested transforms including matrix() calls. These produce the correct visual position but obscure the real geometry, making future maintenance error-prone.

Strokes: no stroked elements detected at root level (all stroke data is encoded inside the group's style inheritance); the stroke logic for this file relies entirely on group-inherited attributes.

**Key problems:** ratio mismatch (square outer canvas, portrait-ratio viewBox), content fills 100% of the taller VB axis leaving no padding, matrix() transform chains.

---

### AC_Voltage_source.svg

Structurally identical to AC_Current_source.svg in every measurable dimension: same viewBox `0 0 28 40`, same drawable bounds (3.4,0.5)→(23.6,40.5), same 72.2% area coverage, same transform count style. The only difference is one extra `<defs>` group. All the same issues apply. These two files were clearly derived from the same source and require the same fixes.

---

### Capasitor_Icon_new.svg

ViewBox is `0 0 40.2 40` — nearly square (ratio 1.005), which matches the 100×100 outer canvas well. Content analysis shows the drawable shape is a horizontal band: min-y=12, max-y=28, meaning the capacitor plates occupy only the middle 16 units of a 40-unit tall canvas. The X-axis fills nearly the full width (min-x=0.5, max-x=40.5). This gives an area coverage of 39.8% and a main-axis coverage of 99.5%, which sounds acceptable but is misleading: the component is rendered as a thin horizontal stripe that fills the width but uses only 40% of the height. In a 100×100 icon grid, this will look very flat and undersized compared to components that use both axes. The ratio between rendered height and rendered width will be roughly 16:40 = 0.4, and this ratio is correct for the physical symbol, but the visual "weight" is far less than a square icon. 12 matrix() transforms present.

---

### Current_sensor.svg

ViewBox `0 0 100 50` with a square outer canvas — 2:1 ratio mismatch. The browser must letter-box this: the 100×50 viewport fits inside 100×100 px, so the symbol is rendered at half its expected vertical size (50px of the 100px square). The drawable content spans 0 to 100.2 in X and 0.75 to 40.2 in Y, meaning it overflows the X boundary by 0.2 units and has 9.8 units of blank space at the bottom. This creates a hard-left/hard-right clip edge combined with a significant bottom gap (9.8/50 = 19.6% of canvas height unused at the bottom). This asymmetric padding makes the visual center-of-mass sit noticeably higher than the geometric canvas center. 22 transforms including matrix() chains. This is one of the most problematic files in the folder.

---

### DC_Current_sensor.svg

Same analysis as AC_Current_source.svg — identical viewBox `0 0 28 40`, identical drawable bounds, same 72.2% coverage. 10 transforms with matrix(). The only difference from the AC variant is slightly fewer transform nodes.

---

### DC_Voltage_source.svg

Same structure as the other `0 0 28 40` family. Identical measurements. Same issues. The four files AC_Current_source, AC_Voltage_source, DC_Current_sensor, and DC_Voltage_source are essentially the same normalization problem repeated four times.

---

### Damper_Icon_new.svg

ViewBox `0 0 40.3 28` (ratio 1.439) versus square canvas — significant mismatch. This is a wide, landscape-oriented symbol. The drawable content is a horizontal band: min-y=5.8, max-y=18.6 (height 12.8 out of 28 = 45.6%). There is more blank space below (9.45 units) than above (5.78 units), creating a noticeably off-center vertical alignment. Unlike most files in this folder, **Damper_Icon_new.svg has no matrix() transforms** — it uses explicit `<path>` elements with direct stroke attributes (`stroke-width="1.5"`, 4 stroked elements). This makes it one of the easiest files to edit manually. The stroke width of 1.5 in a 40.3×28 viewBox will map to approximately 3.7px in a 100px render context (1.5/28 × 100), which is visually thick.

---

### Diode_Icon_new.svg

ViewBox `0 0 102 28` — extreme 3.64:1 aspect ratio versus the 1:1 square canvas. With `xMidYMid meet`, the diode symbol is fitted to 28/100 = 28% of the available height (28px out of 100px), leaving 36px of empty space above and below. The actual drawable content (the diode symbol itself) spans only 40 units out of 102 in X (39.2%) and 17.8 out of 28 in Y (63.6%), centered horizontally and vertically within the viewBox. So the actual rendered symbol is about 40/102 × 28/100 = approximately 11% of the 100×100 pixel area — the diode will look extremely small. This is one of the worst content-size situations in the folder. The main-axis coverage is 63.6%, which classifies as "ok" by the 45–95% heuristic, but the severe ratio mismatch means real visual size is drastically reduced. Matrix() transforms present.

---

### Elektrical_Reference.svg

ViewBox `0 0 20 20` — square, matching the 1:1 outer canvas well. Drawable content fills 99.0% width and 90.3% height with symmetric padding, centered at (9.98, 9.53) vs canvas center (10,10). Coverage is 89.3% area — this is the highest fill rate among all files that have a correctly matching ratio. The content is very close to the edge (0.08px left margin). In a rendered 100px icon, this is ~0.4px from the edge — borderline. The main practical concern is that content is very tightly packed with almost no breathing room, which can cause visual crowding. 9 matrix() transforms present.

---

### FreeEnd_Icon_new.svg

ViewBox `0 0 20 21` (ratio 0.952) versus square canvas — small mismatch. The critical problem is **horizontal off-centering**: drawable content spans only x=0.7 to x=9.9, occupying the left 45.6% of the 20-unit-wide canvas. The content center is at x=5.3 vs canvas center at x=10.0 — a 4.7-unit offset (23.5% of canvas width). This means the symbol will render pushed significantly to the left side of its icon cell. This is the **only file in the folder with a centering failure**. The vertical axis is well-covered (91.2%). Matrix() transforms present.

---

### Ideal_Force_sensor.svg

ViewBox `0 0 100 50` — same 2:1 ratio mismatch as Current_sensor.svg. Content fills 100.2% of the X-axis (overflows by 0.2 units) and only 79.9% of Y. Bottom padding is 9.3 units out of 50 (18.6% empty at the bottom), creating the same high visual center-of-mass problem as Current_sensor.svg. 25 transforms — the highest transform count in the folder. Matrix() chains extensively used.

---

### Ideal_Force_source.svg

ViewBox `0 0 38 49` (ratio 0.776). Content fills 82.6% in X and 96.9% in Y. The shape nearly reaches the top and bottom edges (0.5px top, 1.0px bottom), which is adequate. Horizontally, left padding is 1.5 units vs right padding 5.1 units — a 3.6-unit asymmetry (9.5% of canvas width), which classifies as borderline. The main issue is the viewBox ratio mismatch: in a 100×100 square render, the 0.776-ratio viewBox will receive horizontal letterboxing (12.5px bands on each side), compressing the effective render area. 17 transforms with matrix().

---

### Ideal_Torque_source.svg

ViewBox `0 0 48 49` — nearly square (ratio 0.980), reasonably close to the 1:1 canvas. Content spans x=5.5 to x=36.9 (31.4 units wide out of 48) and y=0.5 to y=48.0 (47.5 units tall out of 49). The content is strongly asymmetric horizontally: left padding is 5.5 units, right padding is 11.1 units. The content center is at x=21.2 vs canvas center x=24.0 — a 2.8-unit offset (5.8% of width), which passes the centered threshold, but the padding asymmetry (left/right ratio of 1:2) is clearly visible and will make the icon look right-heavy in a dense palette. Area coverage is only 63.4% despite near-square geometry. 15 transforms with matrix().

---

### Ideal_Translational_Motion_sensor.svg

ViewBox `0 0 102 41.8` — 2.44:1 ratio versus square canvas. Content fills virtually the entire viewBox: x from 0 to 102, y from 0.75 to 40.75 (95.7% area). No meaningful padding at any edge. With `xMidYMid meet`, this wide canvas is rendered as a 41.8/102 × 100 ≈ 41px high strip inside the 100×100 square, with ~29px empty bands above and below. The symbol will appear narrow and cramped. 20 transforms with matrix().

---

### Ideal_torque_sensor.svg

ViewBox `0 0 100 50` — same family as Current_sensor.svg and Ideal_Force_sensor.svg. Identical 2:1 ratio problem. Content spans 100.2 in X (overflow), 40.0 in Y (80%), with 9.25-unit bottom gap (18.5% of canvas). Bottom-heavy alignment issue. 27 transforms — the second-highest count in the folder.

---

### Inductor_Icon_new.svg

ViewBox `0 0 40 20` — 2:1 landscape ratio versus square canvas. Content is a narrow band: y from 4.7 to 12.3 (height 7.6 out of 20 = 38.1%). The inductor bumps occupy only the middle third of the vertical canvas. Combined with the ratio letterboxing, this means the inductor coils render as a very thin, barely visible strip approximately 7.6/20 × 20/100 × 100 = 7.6px tall in a 100px icon. Extreme visual size problem. Left padding 0.5, right padding -0.5 (overflow) — the content brushes both horizontal edges. Top padding 4.7, bottom padding 7.7 — noticeable vertical asymmetry. 8 transforms with matrix().

---

### Mass_Icon_new.svg

ViewBox `0 0 28.4 40` (ratio 0.710) — portrait, significant ratio mismatch with the square canvas. Content fills 87.5% width and 90.9% height, with symmetric padding (1.8 left, 1.8 right, 1.5 top, 2.2 bottom) and near-perfect centering (dx=-0.024, dy=-0.327). Area coverage is 79.5%. Visually this is one of the better-normalized icons in terms of internal geometry, but the ratio mismatch means letter-boxing will add side bands. 7 transforms with matrix().

---

### Reference_Icon_new.svg

ViewBox `0 0 23 21` (ratio 1.095) — slightly taller than wide, minor ratio mismatch. Content fills 95.7% width and 92.9% height, nearly touching edges. Top padding 0.5px, bottom padding 1.0px — barely any breathing room. Centered well (dx=0.045, dy=-0.250). The near-edge content poses a clipping risk at render time, especially if stroke-width is accounted for. 12 transforms with matrix().

---

### Resistor_Icon_new.svg

ViewBox `0 0 40.3 28` — same geometry as Damper_Icon_new.svg (1.439 ratio). Content is a horizontal band: y from 6.9 to 17.6 (height 10.7 out of 28 = 38.1%). This is almost identical to Inductor_Icon_new.svg in terms of the band-shape problem, but in a wider canvas. Top padding 6.9 units, bottom padding 10.4 units — the resistor symbol sits noticeably in the upper half of the canvas with too much empty space below. Center offset dy=-1.77 (6.3% of canvas height). 7 transforms with matrix().

---

### Spring_Icon_new.svg

ViewBox `0 0 41 28` (ratio 1.464). Content is a horizontal band: y from 6.2 to 20.3 (height 14.2 out of 28 = 50.6%). Top padding 6.2, bottom padding 7.7 — fairly symmetric, but both values are large, leaving the spring shape occupying only the central half of the canvas. Content effectively fills nearly the full X-axis (97.6%) but only half of Y. 8 transforms with matrix().

---

### Switch_Icon_new.svg

ViewBox `0 0 85 82` — nearly square (ratio 1.037), close to the 1:1 canvas. Content spans x=15.7 to x=85.0 (left padding 15.7, right padding 0.0) and y=0.5 to y=82.0 (top padding 0.5, bottom padding 0.0). This is heavily left-padded with zero right/bottom padding — the switch symbol is anchored to the right and bottom edges of the canvas. Content center-x is 50.4 vs canvas center 42.5 (offset 7.9 units = 9.3% of canvas width), just within the 10% centered threshold but visually perceptible. The right edge is exactly at the canvas boundary (x=85.0 = viewBox width), meaning there is no stroke bleed margin on the right. 17 transforms with matrix().

---

### Voltage_sensor.svg

ViewBox `0 0 80 85` (ratio 0.941) — slightly tall, minor ratio mismatch. Content: x from 20.0 to 59.4 (39.4 wide out of 80 = 49.3%), y from 3.4 to 82.4 (79.0 tall out of 85 = 92.9%). The symbol is very narrow relative to its height — the content aspect ratio is 39.4:79.0 ≈ 0.5, meaning the voltage meter is a tall thin object. Both horizontal padding values are approximately equal (20.0 left, 20.6 right) — horizontally well-centered. The main-axis coverage is 92.9% which is within range. 19 transforms with matrix().

---

### Wheel_black.svg

ViewBox `0 0 123 123` — square, matching the 1:1 canvas. Content nearly fills the viewBox: (0.06, 0.06) to (122.94, 122.94) — 99.9% of the canvas in both axes. Perfectly centered (dx=0, dy=0). The wheel effectively has zero visible padding inside the viewBox. The viewBox itself is unnormalized to a round number (123 instead of 100), but the shape is otherwise clean. No matrix() transforms. 1 translate-only transform. This is structurally the cleanest file in the folder in terms of geometry and transform simplicity, but the too-large content fill (99.9%) leaves no breathing room and will appear edge-to-edge in the icon cell.

---

### Wheel_white.svg

ViewBox `0 0 21.5 21.5` — square. Content fills 100% of both axes to the pixel (bounding box is exactly the viewBox). No transforms at all. This is the simplest SVG in the folder but the 100% fill means any stroke width (if present in the rendering context) will clip. The viewBox size (21.5) is an unusual non-round value.

---

## C. Cross-Folder Consistency Analysis

**Unique viewBox values:** 18 across 24 files. Only one group shares a viewBox: `0 0 28 40` (4 files: the AC/DC current/voltage group) and `0 0 100 50` (3 files: the sensor trio) and `0 0 40.3 28` (2 files: Damper + Resistor). All others are unique.

**Unique (width × height):** 1. Every file uses `width=100 height=100` — this is the only dimension that is already consistent.

**Main-axis content coverage:** ranges from 63.6% (Ideal_Torque_source) to 100.2% (several files overflow). The mean is 96.8%, which is systematically too high — most files have their content crammed right against the canvas boundaries. The target of 70–85% is not met by a single file.

**Centering:** 0 out of 24 files pass strict centering according to the automated analysis. The centering check uses a ≤10% threshold on each axis. Most files pass this threshold but are noted as "yes" in the table because their offsets are small. **FreeEnd_Icon_new.svg is the only file with a hard centering failure** (content center at x=5.3 vs canvas center x=10.0, a 23.5% offset). The current_sensor/force_sensor/torque_sensor family are classified centered but have a systematic dy offset of ~4–4.5 units (8–9% of the 50-unit VB height) due to the large bottom gap.

**Matrix() transforms:** 21 of 24 files contain matrix() transforms. Only Damper_Icon_new.svg, Wheel_black.svg, and Wheel_white.svg are free of matrix(). This is a pervasive structural characteristic of the folder — the files appear to have been exported from a vector tool (likely Qt SVG renderer based on the comment timestamps) that encodes all geometry changes as matrix operations rather than direct path coordinates.

**WH/VB ratio mismatch:** 20 of 24 files. Only Capasitor_Icon_new.svg (ratio 1.005 ≈ 1.0), Elektrical_Reference.svg (1.000), Wheel_black.svg (1.000), and Wheel_white.svg (1.000) have matching ratios.

---

## D. Ranked List: Most Problematic → Best

| Rank | Status | Filename | Issues | Explanation |
|---|---|---|---|---|
| 1 | **POOR** | Current_sensor.svg | 4 | WH ratio 1.000 ≠ VB ratio 2.000; content 100.2% (clips edge); bottom gap 19.6%; 22 matrix() transforms |
| 2 | **POOR** | Ideal_Force_sensor.svg | 4 | WH ratio 1.000 ≠ VB ratio 2.000; content 100.2%; bottom gap 18.6%; 25 matrix() transforms (highest count) |
| 3 | **POOR** | Ideal_Torque_source.svg | 4 | WH ratio 1.000 ≠ VB ratio 0.980; 63.4% area coverage; left/right padding ratio 1:2 (asymmetric); matrix() |
| 4 | **POOR** | Ideal_torque_sensor.svg | 4 | WH ratio 1.000 ≠ VB ratio 2.000; content 100.2%; bottom gap 18.5%; 27 matrix() transforms (very high) |
| 5 | **POOR** | Inductor_Icon_new.svg | 4 | WH ratio 1.000 ≠ VB ratio 2.000; coil band only 38.1% of canvas height; top/bottom asymmetry; overflow |
| 6 | **POOR** | Resistor_Icon_new.svg | 4 | WH ratio 1.000 ≠ VB ratio 1.439; band shape 38.1% vertical coverage; top/bottom asymmetry 6.9 vs 10.4 units |
| 7 | **POOR** | Switch_Icon_new.svg | 4 | WH ratio 1.000 ≠ VB ratio 1.037; content 99.4%; heavy left padding (15.7 units); zero right margin |
| 8 | **POOR** | AC_Current_source.svg | 3 | WH ratio 1.000 ≠ VB ratio 0.700; content fills 100% of VB height; 11 matrix() transforms |
| 9 | **POOR** | AC_Voltage_source.svg | 3 | Identical to AC_Current_source.svg; same viewBox, same bounds, 12 matrix() transforms |
| 10 | **POOR** | DC_Current_sensor.svg | 3 | Same as AC/DC family; viewBox 0 0 28 40; 10 matrix() transforms |
| 11 | **POOR** | DC_Voltage_source.svg | 3 | Same as AC/DC family; viewBox 0 0 28 40; 11 matrix() transforms |
| 12 | **POOR** | Damper_Icon_new.svg | 3 | WH ratio 1.000 ≠ VB ratio 1.439; band shape; bottom gap larger than top (9.5 vs 5.8 units) |
| 13 | **POOR** | FreeEnd_Icon_new.svg | 3 | **Only file with hard centering failure**: content center at x=5.3 vs canvas center x=10.0 (23.5% offset) |
| 14 | **POOR** | Ideal_Force_source.svg | 3 | WH ratio 1.000 ≠ VB ratio 0.776; content 96.9%; borderline horizontal asymmetry |
| 15 | **POOR** | Ideal_Translational_Motion_sensor.svg | 3 | WH ratio 1.000 ≠ VB ratio 2.440 (worst ratio); content fills 100%; no padding |
| 16 | **POOR** | Reference_Icon_new.svg | 3 | WH ratio 1.000 ≠ VB ratio 1.095; 95.7% coverage; only 0.5px top margin — clipping risk |
| 17 | **POOR** | Spring_Icon_new.svg | 3 | WH ratio 1.000 ≠ VB ratio 1.464; band shape 50.6% vertical; 97.6% coverage overflows |
| 18 | MODERATE | Capasitor_Icon_new.svg | 2 | Near-square ratio (1.005 ≈ ok); but flat band shape 40% vertical; 99.5% width coverage |
| 19 | MODERATE | Diode_Icon_new.svg | 2 | Near-square ratio mismatch (3.643); symbol renders at ~11% of icon area — extremely small |
| 20 | MODERATE | Elektrical_Reference.svg | 2 | Square viewBox ok; 89.3% area fill — slightly crowded; tiny 0.08px left margin |
| 21 | MODERATE | Mass_Icon_new.svg | 2 | WH ratio mismatch (0.710); good internal symmetry and 79.5% coverage; best-normalized portrait |
| 22 | MODERATE | Voltage_sensor.svg | 2 | Minor ratio mismatch (0.941); good centering; 92.9% main-axis coverage; acceptable |
| 23 | MODERATE | Wheel_black.svg | 1 | Square viewBox; 99.9% fill — no padding; no matrix() transforms; structurally cleanest |
| 24 | MODERATE | Wheel_white.svg | 1 | Square viewBox; 100% fill — zero padding; no transforms; simplest file |

---

## E. Final Conclusion

**Are edits to `viewBox` and `width`/`height` sufficient? — NO.**

The edits have achieved one thing correctly: all 24 files now share `width=100 height=100`. That is a necessary baseline. However, it is far from sufficient. Here is what the data shows:

**Problem 1 — ViewBox fragmentation.** There are 18 distinct viewBox values across 24 files. Even though the outer canvas is unified at 100×100 px, each file operates in a different internal coordinate space. When the browser renders these side by side, each file's symbol is scaled to fit its own viewBox into the 100×100 square. A symbol in viewBox `0 0 20 20` and a symbol in viewBox `0 0 123 123` will both be rendered at 100×100 px on screen, but their internal geometries are mapped at completely different scales. Making the viewBox consistent (e.g. all `0 0 100 100`) is still required.

**Problem 2 — Aspect ratio mismatch (20/24 files).** When a file has a non-square viewBox inside a square outer canvas, the browser's `xMidYMid meet` behaviour adds transparent letterbox bands. A symbol with viewBox `0 0 100 50` inside a 100×100 square is rendered at half its nominal height (50px), with 25px of empty space above and below. The three sensor files (Current_sensor, Ideal_Force_sensor, Ideal_torque_sensor) all suffer from exactly this: they will appear at half the visual size of a correctly proportioned icon.

**Problem 3 — Content fills 100%+ of one axis (17 files).** The majority of files have their drawable content touching or overflowing the viewBox boundary on at least one axis. There is effectively no padding between the symbol geometry and the edge of the canvas. In a rendered icon, this means: (a) strokes that sit on the edge will be clipped in half, (b) the symbol has no visual breathing room, and (c) any slight difference in viewBox sizing between files immediately makes content appear larger or smaller relative to the cell.

**Problem 4 — Off-center content (FreeEnd_Icon_new.svg).** One file has a hard horizontal centering failure. The symbol is pushed entirely to the left half of its canvas.

**Problem 5 — Matrix() transforms (21/24 files).** The vast majority of files encode their geometry through matrix() transform chains rather than direct path coordinates. This makes the actual rendered position and size of content non-obvious from inspection, prevents straightforward manual edits, and means that any script trying to re-normalize the geometry must correctly decompose and recompose these transform chains.

**Overall verdict:** The current state requires full internal content normalization for 17 files (POOR) and partial normalization for 7 files (MODERATE). Zero files are fully normalized.

---

## F. Practical Action Plan

### What to fix first (critical — POOR status files)

These 17 files need both viewBox normalization and internal content repositioning/scaling. Priority order based on severity:

1. **Current_sensor.svg, Ideal_Force_sensor.svg, Ideal_torque_sensor.svg, Ideal_Translational_Motion_sensor.svg** — All share the wide-canvas 2:1 or 2.44:1 ratio problem. Fix by changing viewBox to `0 0 100 50` → `0 0 80 40` (keep content, shrink canvas) or expand to `0 0 100 100` and scale/translate the content to center it with 10% padding. The content is already horizontally full-width, so the key fix is to add vertical padding: translate content down by ~5 units and up-scale it slightly so it fills ~80% of the new canvas height.

2. **AC_Current_source.svg, AC_Voltage_source.svg, DC_Current_sensor.svg, DC_Voltage_source.svg** — All use viewBox `0 0 28 40`. The outer canvas is square but the viewBox is portrait. Change viewBox to `0 0 28 28` and translate content up by ~5 units to center it, or expand to `0 0 40 40` and re-center. The four files are structurally identical so fixing one approach fixes all four.

3. **Inductor_Icon_new.svg, Resistor_Icon_new.svg, Damper_Icon_new.svg, Spring_Icon_new.svg** — Horizontal band shapes in landscape viewBoxes. The symbols are inherently wide-and-short. Use viewBox `0 0 60 30` (or similar 2:1) to reflect the true symbol proportions, and center the band shape within it with equal top/bottom padding (~25% each). Then set `width=100 height=50` on the outer SVG to match, or use viewBox `0 0 100 100` and accept that the symbol will have large top/bottom padding.

4. **Ideal_Torque_source.svg, Ideal_Force_source.svg** — Near-square but content asymmetric. Translate content to center it.

5. **Switch_Icon_new.svg** — Shift content 7.9 units to the left to center it and add equal left/right padding.

6. **Reference_Icon_new.svg** — Add 1.5–2 units of padding to viewBox on all sides (change from `0 0 23 21` to `-2 -2 27 25` or expand to `0 0 27 25` and translate content).

7. **FreeEnd_Icon_new.svg** — **Highest priority centering fix**: translate content approximately +4.7 units in X to center it within the canvas.

### What can stay as-is (MODERATE — with caveats)

These 7 files have acceptable internal geometry but still benefit from standardization:

- **Mass_Icon_new.svg** — Best-normalized portrait icon (79.5% coverage, symmetric padding). Only issue is ratio mismatch.
- **Voltage_sensor.svg** — Good centering, acceptable coverage. Only minor ratio mismatch.
- **Diode_Icon_new.svg** — Well-centered, but will render very small due to wide-canvas viewBox.
- **Capasitor_Icon_new.svg** — Square viewBox, well-centered. Flat band shape is inherent to the symbol, not a normalization error.
- **Elektrical_Reference.svg** — Near-edge content, slight crowding. Can stay with minimal viewBox expansion.
- **Wheel_black.svg, Wheel_white.svg** — Clean geometry, no matrix() transforms. Only issue is 100% fill (no padding). Add 5% margin by slightly expanding the viewBox outward.

### Normalization rule to adopt for the entire folder

Adopt this standard for all files:

```
viewBox = "0 0 100 100"
width   = "100"
height  = "100"
preserveAspectRatio = "xMidYMid meet"
```

For the **internal content**, target:
- Visible drawing covering **70–82%** of the shorter canvas axis (leaving ~9–15 unit padding on each side within a 100-unit canvas).
- Content center at approximately **(50, 50)** — tolerance ±5 units.
- Stroke widths in the range **1.5–2.5 px** at the 100-unit coordinate scale (adjust after rescaling paths).
- No content touching or crossing the viewBox boundary.

For inherently non-square symbols (inductors, resistors, dampers, sensors), either: (a) accept large padding on the narrow axis and center the shape, or (b) define a component-class-specific viewBox (e.g. `0 0 200 100` for wide symbols) and set `width=200 height=100` on the outer canvas — but this must then be handled uniformly in the app's layout engine.

**Normalize in the SVG files, not at render time.** Render-time transforms (CSS transforms, HTML wrapping) are brittle and make debugging harder. The SVG files should be self-contained and renderable at any size without requiring wrapping logic.

The recommended normalization pipeline:
1. Use Inkscape's _File → Document Properties → Resize page to drawing or selection_ to get a tight bounding box.
2. Run SVGO with `removeViewBox: false`, `convertPathData: true`, `mergePaths: true`, and `removeTransforms: true` (where safe) to flatten matrix() chains into direct path coordinates.
3. Manually adjust viewBox to add 10% padding on all sides.
4. Set `viewBox="0 0 100 100" width="100" height="100"`.
5. Verify final content coverage is between 70–85% on the main axis and the center is within 5 units of (50, 50).
