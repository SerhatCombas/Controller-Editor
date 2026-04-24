# Multi-Input/Output Scene Selection And Analysis Binding

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Scene-level I/O selection originally covered only part of the workflow: outputs were easier to expose than inputs, the controller panel still looked close to a single-input model, and the equation/transfer-function layer was not yet clearly bound to scene-selected channels.

## Decision

Extend scene I/O selection into a reusable multi-I/O contract:

- scene components may expose input and output roles independently
- multiple inputs and multiple outputs may coexist
- the selected scene roles propagate into application state as component ids plus signal ids
- plotting continues to support multiple outputs
- equation/transfer-function extraction uses the selected bindings as the active analysis contract
- runtime execution remains stricter than analysis: at least one selected input must map to a backend-declared driving channel before simulation can run

## Implementation Notes

- `SignalSelection` now stores tuples of input signals/component ids and output signals/component ids.
- `CanvasVisualComponent` stores multiple assigned I/O roles so a component can participate in more than one role when the current template allows it.
- `signal_catalog.py` maps scene components to analysis/runtime bindings through `SceneSignalBinding`.
- `ControllerPanel` mirrors scene-selected inputs/outputs instead of acting as a separate source of truth.
- `EquationService` now uses selected I/O bindings directly and falls back honestly when the chosen input channel is not yet supported by the analysis backend.

## Files Affected

- `app/core/state/app_state.py`
- `app/services/signal_catalog.py`
- `app/ui/canvas/component_system.py`
- `app/ui/canvas/model_canvas.py`
- `app/ui/panels/controller_panel.py`
- `app/ui/main_window.py`
- `app/services/equation_service.py`
- `app/services/simulation_service.py`
- `tests/test_canvas_editing.py`
- `tests/test_component_system.py`

## Alternatives Considered

- Keep scene markers as visual-only metadata.
- Preserve a single-input mental model and delay multi-I/O until a future symbolic pass.
- Tie plotting and equation extraction to different I/O selection systems.

These were rejected because they would keep the simulation UI and the mathematical analysis contract divergent.

## Consequences

- Scene-selected I/O now acts as the explicit contract for plotting and equation analysis.
- Simulation run-readiness is honest about which selected inputs can actually drive the current runtime backend.
- Full MIMO symbolic extraction is still future work, but the data model is now prepared for it.

## Known Risks / Follow-up

- Some analysis-only candidate inputs, such as wheel displacement in the quarter-car scene, are selectable for future workflows but still fall back honestly in the current backend.
- Future work should lift primary-input limitations in static transfer-function extraction.

## Test / Validation Notes

- Added regression for multi-input coexistence, dual-role components, scene-to-app-state propagation, analysis fallback messaging, and template-safe clearing.

## Prompt / Iteration Summary

This decision upgrades scene I/O from a UI marker feature into the beginning of a real mathematical model-analysis interface.
