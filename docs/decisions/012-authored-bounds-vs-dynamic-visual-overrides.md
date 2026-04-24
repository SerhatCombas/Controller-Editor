# Authored Bounds Vs Dynamic Visual Overrides

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

User-built components could become difficult or impossible to resize after wiring and animation-mapper refreshes. The root issue was that interactive resize handles were being derived from dynamic visual rectangles, while resize edits themselves mutate authored component bounds. When animation overrides deformed or translated the visual rect, the editable handles no longer matched the user-authored geometry.

## Decision

Keep authored bounds and dynamic visual overrides as separate concepts:

- authored bounds remain the persistent editable source of truth
- dynamic mapper rectangles remain transient visual overlays
- resize handles and resize hit-testing must use authored bounds, not dynamic override bounds

## Implementation Notes

- `ModelCanvas._component_rect(...)` remains the persistent authored rectangle.
- `ModelCanvas._dynamic_rect(...)` still returns simulation-time visual overrides when available.
- Resize handles now derive from the authored rectangle so connected/deformed components remain manually resizable after wiring and scene refreshes.
- Dynamic simulation visuals may continue to deform components during playback, but they no longer replace the user’s editable size state.

## Files Affected

- `app/ui/canvas/model_canvas.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep resize handles on top of dynamic override geometry.
- Disable resize for components once topology-driven deformation exists.
- Copy dynamic rectangles back into persistent component size/position.

These were rejected because they either broke editing ergonomics or corrupted authored layout state with transient simulation visuals.

## Consequences

- User-built components remain resizable after wiring and mapper refreshes.
- Scene animation can continue to use rest-pose-based dynamic geometry without locking component editing.
- The editor now has a clearer separation between authored scene data and runtime visualization.

## Known Risks / Follow-up

- Very advanced future workflows may want explicit UI to visualize both authored bounds and current dynamic extents simultaneously.
- Constraint-aware resizing for fully connected deformables may later need stronger topology feedback, but authored-bounds editing remains the baseline.

## Test / Validation Notes

- Added regression ensuring manually authored spring bounds remain resizable after mapper-driven deformation is active.

## Prompt / Iteration Summary

This decision formalizes that simulation-time visual overrides must never overwrite the user-authored editable bounds used for scene editing.
