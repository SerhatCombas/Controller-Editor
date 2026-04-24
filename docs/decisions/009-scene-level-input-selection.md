# Scene-Level Input Selection

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Explicit simulation I/O selection existed in the controller UI, but the scene itself only exposed output marking. Users could not declare the actual driving source component directly from the canvas, which kept the workflow half-explicit and allowed the UI selection state to drift from real scene intent.

## Decision

Promote scene component role assignment into the simulation I/O workflow:

- valid scene components can be marked as input or output from the canvas context menu
- only one input component is allowed at a time
- scene role selections map into template-aware signal-catalog entries
- the controller panel mirrors those mapped selections instead of inventing hidden defaults
- simulation requires a real scene-owned input component before it can run

## Implementation Notes

- Added template-aware component-to-signal helpers in `signal_catalog.py`.
- `ModelCanvas` now filters I/O context-menu actions through scene-signal compatibility, emits role-change snapshots, and enforces single active input.
- `MainWindow` synchronizes scene role assignments into controller selection state and runtime validation.
- `ControllerPanel` stores the scene-selected input component id so run readiness depends on a real canvas source, not only a theoretical signal id.

## Files Affected

- `app/services/signal_catalog.py`
- `app/core/state/app_state.py`
- `app/ui/canvas/model_canvas.py`
- `app/ui/panels/controller_panel.py`
- `app/ui/main_window.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep input selection only in the controller panel dropdown.
- Add more UI-level special cases without binding them to scene components.
- Let multiple inputs stay active and choose the latest one implicitly.

These were rejected because they preserved ambiguity about which actual source component drives the simulation.

## Consequences

- Scene I/O markers now participate in the explicit simulation workflow instead of being decorative only.
- The runtime selection state is more consistent with what the user marked in the workspace.
- Unsupported component/template combinations fail safely by hiding unsupported I/O actions.

## Known Risks / Follow-up

- Output selection is still represented in the controller panel as signal ids; future work may expand scene-to-signal bindings for richer sensor/output families.
- More advanced custom topologies may need richer binding heuristics than the current template-aware mappings.

## Test / Validation Notes

- Added tests for valid/invalid input actions, single active input enforcement, scene-to-controller selection sync, template-switch clearing, and scene-owned simulation readiness.

## Prompt / Iteration Summary

This decision completes the missing half of explicit simulation I/O selection by letting users choose the actual input source directly from scene components.
