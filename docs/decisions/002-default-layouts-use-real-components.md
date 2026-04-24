# Default Layouts Use Real Palette Components

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Built-in layouts originally used legacy hard-coded geometry that no longer matched the real palette components, SVGs, connector behavior, or inspector metadata.

## Decision

Rebuild default layouts using the same component specs and `CanvasWireConnection` pipeline as palette-created components.

## Implementation Notes

- Built-in layouts now instantiate real `CanvasVisualComponent` items.
- Topology is represented with real wires, not painter-only template connections.
- Built-in scenes and user-built scenes share the same canvas component model.

## Files Affected

- `app/ui/canvas/model_canvas.py`
- `app/ui/canvas/component_system.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep legacy visuals for built-in examples.
- Maintain a separate “template rendering” path beside real scene components.

These were rejected because they created two visual systems and broke consistency between palette behavior and built-in layouts.

## Consequences

- Selecting a spring in a default layout behaves like selecting the same spring dragged from the palette.
- Built-in scenes now act like genuine saved workspaces.

## Known Risks / Follow-up

- Visual animation must now respect real topology instead of relying on legacy template drawing shortcuts.

## Test / Validation Notes

- Tests verify that default layouts use real palette display names and load valid component/wire topology.

## Prompt / Iteration Summary

This decision removed the second visual system and made built-in examples first-class scenes.
