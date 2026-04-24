# Development Decisions

This folder keeps lightweight engineering memory for the project.

It is intentionally practical:
- small enough to maintain during active iteration
- specific enough to help future debugging and AI-assisted work
- focused on decisions that change architecture, runtime behavior, UI behavior, or development workflow

## When to add a record

Add a decision note when a change introduces or refines:
- architecture or ownership boundaries
- simulation/runtime behavior
- canvas or rendering policy
- persistence or data model structure
- interaction behavior with non-obvious tradeoffs
- fallback or safety policy

## What a record should contain

Each record should capture:
- Title
- Date
- Status
- Problem / Context
- Decision
- Implementation Notes
- Files Affected
- Alternatives Considered
- Consequences
- Known Risks / Follow-up
- Test / Validation Notes

Optional but useful:
- prompt summary
- phase / iteration summary
- screenshots or artifact references

## Naming

Use numeric prefixes so records stay stable over time:

- `001-...`
- `002-...`
- `003-...`

## Scope

These notes are not a full changelog.
They are a decision memory system:
- why a technical choice was made
- what code it touched
- what constraints and tradeoffs now exist

Use `docs/` for broader reference material.
Use `docs/decisions/` for durable engineering decisions and feature-behavior traces.
