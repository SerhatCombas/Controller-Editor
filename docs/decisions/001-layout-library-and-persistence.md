# Layout Library And Persistence

- Date: 2026-04-09
- Status: Accepted

## Problem / Context

The editor outgrew its early demo phase where a quarter-car layout auto-loaded on startup. Users needed a blank workspace, explicit default layouts, user-saved layouts, and workspace replacement instead of scene stacking.

## Decision

Introduce a layout library model with separate `Default Layouts` and `Saved Layouts`, startup on a blank workspace, explicit load on double-click, and JSON-backed persistence for user-saved layouts.

## Implementation Notes

- Workspace load is replace-based, not append-based.
- `Saved Layouts` are persistent user records.
- `Default Layouts` remain read-only examples.
- `New Workspace` resets the active scene without deleting saved records.
- Saved layout rename/delete apply only to user-owned records.

## Files Affected

- `app/ui/panels/model_panel.py`
- `app/ui/canvas/model_canvas.py`
- `app/ui/main_window.py`
- `tests/test_canvas_editing.py`

## Alternatives Considered

- Keep a single flat layout list.
- Keep auto-loaded demo content at startup.
- Store saved layouts only in memory.

These were rejected because they blurred product behavior, made workspace state ambiguous, and caused saved layouts to disappear across restarts.

## Consequences

- The editor now behaves like a workspace-based tool instead of a fixed demo.
- Saved layouts have a real lifecycle: create, load, rename, delete.
- Future unsaved-changes prompts and import/export can build on the same model.

## Known Risks / Follow-up

- Saved layout schema versioning is still lightweight.
- Import/export and migration policy are not formalized yet.

## Test / Validation Notes

- Startup blank workspace tests added.
- Default vs Saved Layouts separation covered.
- Save/load/rename/delete persistence tests added.

## Prompt / Iteration Summary

This decision consolidates the shift from a quarter-car demo UI to a reusable workspace editor with persistent layout management.
