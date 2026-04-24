# Random Road Scene Ownership

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

The project originally treated road animation as a quarter-car-specific visual overlay. A manually placed `Mechanical Random Reference` in the scene did not actually own the animated road surface.

## Decision

Bind road animation ownership to the actual `Mechanical Random Reference` component present in the scene.

## Implementation Notes

- The mapper identifies the random-reference component as the road owner.
- Road rendering is positioned relative to that actual scene component.
- If no random-reference component exists, no scene-owned road animation is implied.

## Files Affected

- `app/ui/canvas/scene_animation_mapper.py`
- `app/ui/canvas/model_canvas.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep a hidden quarter-car road overlay independent of scene components.
- Animate road visuals even when the scene has no random-reference component.

These were rejected because they detached runtime visuals from the actual workspace topology.

## Consequences

- User-built quarter-car-like scenes can own their own road animation source.
- Built-in and user-built scenes follow the same ownership rule.

## Known Risks / Follow-up

- If multiple random-reference components are present, ownership policy is still simple.

## Test / Validation Notes

- Tests verify that user-built scenes expose the random-reference as the active road owner.

## Prompt / Iteration Summary

This decision moved road animation from a hidden template assumption into an explicit scene-owned component behavior.
