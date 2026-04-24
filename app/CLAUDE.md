# CLAUDE.md

## Project Purpose
This project is a Python application for control engineering / visualization workflows.
The actively developed application lives inside the `app/` package in this repository root.

The goal is to keep the codebase modular, understandable, and easy to extend without introducing duplicate logic or UI-core coupling.

## Primary Source of UI Intent
`control_ui_spec.md` is an active UI specification document used during development.
Treat it as the main UX / UI intent reference when reviewing or proposing UI-related changes.

If implementation and UI spec differ:
1. identify the mismatch clearly
2. explain whether the code or the spec seems outdated
3. do not silently rewrite architecture based on assumptions

## Required Reading Order
Before doing architecture review or code suggestions, read these files first:
1. `CLAUDE.md`
2. `docs/architecture.md`
3. `docs/progress.md`
4. `docs/review_rules.md`
5. `control_ui_spec.md` (especially for UI / workflow analysis)

## Architecture Intent
The intended structure is:
- `app/core` -> domain logic, computation, shared abstractions
- `app/services` -> external services, orchestration helpers, integration logic
- `app/ui` -> windows, panels, widgets, canvas, presentation logic
- `tests` -> regression and behavioral checks
- `docs` -> architecture notes and project memory

Keep business logic out of UI files where possible.
Avoid hiding important logic inside widget classes.

## Working Rules
- Do not rescan the whole repository for every small follow-up.
- Reuse already established findings unless code contradicts them.
- Prefer minimal, local, reversible changes.
- Do not duplicate existing functions under new names.
- Do not suggest broad rewrites unless clearly justified.
- Distinguish confirmed findings from assumptions.
- Reference concrete files when making architectural claims.

## What To Focus On During Review
When reviewing the current app, focus on:
- module boundaries
- data flow between UI, services, and core
- duplication
- tight coupling
- maintainability risks
- missing abstractions
- mismatch between implementation and `control_ui_spec.md`

## Output Style
For architecture analysis, use this structure:
1. High-level overview
2. Module map
3. Actual data flow
4. Strengths
5. Weaknesses
6. Risks / bottlenecks
7. Suggested improvements in priority order
8. Open questions / uncertainties

## Change Safety
Before proposing a new abstraction:
- check whether something similar already exists
- prefer extension over duplication
- preserve public behavior unless a change is intentional

## Definition of Done
A recommendation is only good if it:
- fits the existing architecture direction
- reduces confusion instead of increasing it
- avoids duplicate logic
- respects `control_ui_spec.md`
- is realistic to implement incrementally
