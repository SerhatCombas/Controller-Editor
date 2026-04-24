# Rest Pose And Visual Constraint Animation

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Early mapper-based animation still allowed components to collapse toward incorrect coordinates because geometry was being recomputed too absolutely. Large runtime values could also produce visually implausible overlap or interpenetration.

## Decision

Use the loaded workspace geometry as the animation rest pose and apply runtime motion as deltas relative to that rest pose. Add lightweight visual constraints in the mapper to preserve plausible rigid-body separation and minimum deformable extents.

## Implementation Notes

- Rigid components translate from their original placed rects.
- Deformables derive geometry from rest connector geometry plus moving-anchor deltas.
- Vertical/horizontal deformables preserve their rest cross-axis placement.
- Mapper applies non-overlap guards for rigid bodies and minimum extent rules for deformables.
- If motion cannot be supported safely, static visuals are preferred over collapsed visuals.

## Files Affected

- `app/ui/canvas/scene_animation_mapper.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Re-solve the whole scene layout each frame.
- Let runtime values pass through without visual safety checks.
- Patch specific screenshots with per-component nudges.

These were rejected because they either destroyed original layout placement or created brittle behavior.

## Consequences

- Simulation motion stays anchored to the original workspace layout.
- Quarter-car, single-mass, and two-mass scenes animate in place more plausibly.
- Extreme runtime values are visually clamped before rigid bodies overlap.

## Known Risks / Follow-up

- Current constraints are visual plausibility rules, not a full kinematic solver.
- More advanced arbitrary user-built topologies may eventually need node-level constraint solving.

## Test / Validation Notes

- Added tests for in-place animation, rigid-body separation, and large-displacement clamping.

## Prompt / Iteration Summary

This decision establishes “rest pose + delta” as the core rule for live animation and adds safety bounds for physically implausible visuals.
