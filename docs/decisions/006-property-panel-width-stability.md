# Property Panel Width Stability

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

Long property values, especially multi-selection `Component ID` text, were expanding the left inspector column and shrinking the workspace.

## Decision

Keep the left panel width-stable and render long property values inside scrollable value fields instead of allowing parent layout expansion.

## Implementation Notes

- Sidebar width is kept stable.
- Long values use internal horizontal scrolling rather than resizing the overall panel.
- Property semantics and selection data remain unchanged.

## Files Affected

- `app/ui/panels/model_panel.py`
- `app/ui/widgets/property_editor.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Truncate long values without a way to inspect them.
- Let the left column expand with content.

These were rejected because one hides information and the other damages workspace stability.

## Consequences

- Canvas width remains stable during single and multi-selection.
- Long values stay readable without disturbing the main layout.

## Known Risks / Follow-up

- Future metadata-heavy inspectors may need richer value presentation patterns.

## Test / Validation Notes

- Tests verify width stability and internal overflow handling.

## Prompt / Iteration Summary

This decision keeps the inspector panel professional and non-disruptive as metadata grows.
