# Palette Catalog Sync And Search

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

As the component catalog grew, the palette missed some valid components and became harder to navigate. Visible palette content was drifting away from the semantic component catalog.

## Decision

Generate the palette from catalog data plus explicit group mapping, and add a search bar that filters across all component names while preserving the hierarchical palette structure.

## Implementation Notes

- Palette generation uses component catalog as the source of truth.
- Group mapping remains explicit.
- Search is case-insensitive and works across groups.
- Default hierarchy remains the primary navigation model.

## Files Affected

- `app/ui/panels/model_panel.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Continue maintaining palette items manually.
- Replace the grouped palette with a flat search-only list.

These were rejected because they either miss components over time or weaken the editor’s hierarchical browsing model.

## Consequences

- New components are less likely to disappear from the visible palette.
- Larger catalogs remain usable without flattening the UI.

## Known Risks / Follow-up

- Group mapping still needs to be updated intentionally for brand-new categories.

## Test / Validation Notes

- Tests verify palette visibility for previously missing components and search behavior.

## Prompt / Iteration Summary

This decision kept the palette scalable while aligning it more tightly with the semantic component catalog.
