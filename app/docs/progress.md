# Progress and Current Development Notes

## Current Focus
The application inside `app/` is under active development.

The current review goal is not only to inspect code quality, but to determine whether the architecture is already coherent and whether the implementation matches the intended UI behavior described in `control_ui_spec.md`.

## Known Project Reality
- `control_ui_spec.md` is used as an active reference during development.
- The repository may contain older, experimental, or parallel structures outside the main `app/` package.
- Reviewers should not assume every top-level folder belongs to the same architectural layer.
- The most important task is to understand the currently active application structure, not to overfit to legacy files.

## Review Expectations
A useful review should answer:
- What is the real architecture today?
- Which modules are central vs. peripheral?
- Where is state managed?
- Where are responsibilities blurred?
- Which parts already look scalable?
- Which parts are fragile or likely to become hard to maintain?

## Important Rule
When uncertainty exists, explicitly say:
- confirmed from code
- likely inferred
- unknown without deeper inspection

Do not present assumptions as facts.

## Change Strategy
Suggestions should prefer:
- small architectural clarifications
- local refactors
- extraction of reusable logic
- reducing UI/service/core confusion

Avoid:
- recommending a total rewrite by default
- replacing working structure without evidence
- introducing new layers unless they solve a clear problem
