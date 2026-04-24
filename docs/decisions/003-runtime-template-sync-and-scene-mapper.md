# Runtime Template Sync And Scene Animation Mapper

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

The canvas could show `single_mass`, `two_mass`, or user-built quarter-car-like scenes while the live runtime still defaulted to quarter-car assumptions. Animation in the canvas was also driven by hard-coded component-id branches.

## Decision

Introduce:
- workspace-to-runtime template synchronization
- a structured `SceneAnimationMapper` layer

The mapper bridges runtime state to scene overrides using component list, wire topology, and workspace template context.

## Implementation Notes

- `ModelCanvas` emits `workspace_template_changed`.
- `MainWindow` synchronizes the active runtime template with the current workspace.
- `SceneAnimationMapper` returns structured per-component overrides and road ownership info.
- `ModelCanvas` consumes mapper output before falling back to legacy motion logic.

## Files Affected

- `app/ui/canvas/scene_animation_mapper.py`
- `app/ui/canvas/model_canvas.py`
- `app/ui/main_window.py`
- `app/services/simulation_service.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Add more hard-coded `component_id` branches inside canvas painting.
- Maintain separate animation paths for built-in scenes and user-built scenes.

These were rejected because they would extend the quarter-car-only hack layer and keep scene behavior inconsistent.

## Consequences

- Built-in and user-built mechanical scenes can start sharing one animation pipeline.
- Runtime/template mismatch is no longer silently ignored.

## Known Risks / Follow-up

- The mapper is intentionally conservative and still relies on template-aware runtime support.
- Unsupported templates should remain static safely rather than animate incorrectly.

## Test / Validation Notes

- Tests cover template sync, mapper structured overrides, and scene-owned road ownership.

## Prompt / Iteration Summary

This decision marks the transition from hard-coded quarter-car rect overrides to a reusable simulation-to-scene mapping layer.
