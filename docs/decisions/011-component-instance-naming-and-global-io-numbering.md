# Component Instance Naming And Global I/O Numbering

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Repeated user-created components were still identified mainly through internal `component_id` values, which are suitable for wiring/runtime logic but poor as user-facing names. I/O markers also needed a clearer numbering rule that was independent of component type and easier to predict during multi-I/O selection.

## Decision

Introduce two separate but related UX rules:

- user-created components receive stable default instance names based on component family and insertion order
- I/O markers use global per-role numbering based on assignment order

The numbering policy is compact renumbering:

- outputs are displayed as `z1`, `z2`, `z3`, ...
- inputs are displayed as `u1`, `u2`, `u3`, ...
- after a role is cleared, remaining labels are compacted back to the lowest available sequence

## Implementation Notes

- `CanvasVisualComponent` now carries an optional `instance_name`.
- Default layouts keep their authored template naming semantics; user-dropped and duplicated components receive generated names such as `Mass1`, `Mass2`, `Spring1`, `Damper1`.
- Scene-level I/O assignment stores an assignment-order value per role on the component.
- Marker labels are derived from global assignment order per role, not from component type or internal id.
- Controller-side scene summaries use user-facing component names instead of raw `component_id` strings where available.

## Files Affected

- `app/ui/canvas/component_system.py`
- `app/ui/canvas/model_canvas.py`
- `app/ui/main_window.py`
- `app/ui/panels/controller_panel.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Reuse raw `component_id` values as visible instance labels.
- Number inputs/outputs by component type instead of global assignment order.
- Keep numbering stable forever even after intermediate deletions.

These were rejected because they either exposed implementation details to users or made I/O numbering harder to scan during iterative selection changes.

## Consequences

- User-built scenes read more like authored models instead of internal object registries.
- I/O markers are easier to interpret in multi-selection workflows.
- Compact renumbering makes the active set of inputs/outputs visually dense and predictable after role removal.

## Known Risks / Follow-up

- Explicit user renaming of individual scene components is still future work.
- Future analysis views may want to show both instance name and mapped signal label together.

## Test / Validation Notes

- Added tests for sequential instance naming, duplicate naming, assignment-order-based `uN` / `zN` labels, and compact renumbering after clear.

## Prompt / Iteration Summary

This decision separates user-facing component naming from internal ids and formalizes global I/O numbering as an assignment-order UX contract.
