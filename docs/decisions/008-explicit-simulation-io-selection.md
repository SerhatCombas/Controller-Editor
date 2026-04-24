# Explicit Simulation I/O Selection

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Simulation could start without an explicit user choice of driving input or observed outputs. That made runtime behavior ambiguous, encouraged stale plots, and allowed old curves to stay visible even when the active workspace or desired signals changed.

## Decision

Require explicit simulation I/O selection before running:

- the user must select at least one input
- the user must select at least one output
- `Run Simulation` stays disabled until the selection is valid
- analysis plots and live output values reflect only the selected outputs

Selections are now template-aware and come from a dedicated signal catalog rather than scattered hard-coded labels.

## Implementation Notes

- Added a template-aware signal catalog for inputs and outputs.
- Controller UI now uses an input selector plus a multi-select output checklist.
- Plotting and live-output display were updated to support multiple selected outputs with stable colors and legends.
- Invalid or missing selections keep the analysis area empty instead of showing implicit defaults or stale curves.
- Template changes clear incompatible selections rather than silently reusing them.

## Files Affected

- `app/services/signal_catalog.py`
- `app/core/state/app_state.py`
- `app/ui/panels/controller_panel.py`
- `app/ui/panels/analysis_panel.py`
- `app/ui/panels/equation_panel.py`
- `app/ui/widgets/status_widget.py`
- `app/ui/main_window.py`
- `app/services/plotting_service.py`
- `app/services/simulation_service.py`
- `app/services/equation_service.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep implicit default outputs behind the scenes.
- Auto-select the first valid input/output after a template switch.
- Continue using a single-output dropdown.

These were rejected because they hid user intent, made saved or switched workspaces ambiguous, and kept the results area vulnerable to stale curves.

## Consequences

- Simulation is now explicitly user-driven.
- Multi-output plotting is possible with stable legend labels and colors.
- Blank or incompatible selections fail safely to an empty state.

## Known Risks / Follow-up

- Static step/bode/pole-zero analysis is still strongest for templates already supported by the analysis backend.
- Future template-specific analysis backends should reuse the same signal catalog and multi-output contracts.

## Test / Validation Notes

- Added tests for disabled run state, empty results before valid selection, multi-output plotting, distinct colors, stale-curve removal, and template-aware signal list updates.

## Prompt / Iteration Summary

This decision removes implicit simulation assumptions and makes both simulation inputs and observed outputs explicit parts of the editor workflow.
