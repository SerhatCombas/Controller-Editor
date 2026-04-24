# Architecture Notes

## Current Repository Context
This repository root contains multiple folders, but the actively developed application is centered around the `app/` package and related test/support folders.

Important top-level items:
- `app/` -> main application package
- `tests/` -> test coverage
- `control_ui_spec.md` -> UI behavior and structure reference
- `userinterface.py` -> legacy or alternate entry area, if still used
- other folders may contain models, plots, signals, controls, or experiments

## Intended Application Structure

### app/core
Purpose:
- application-independent core logic
- domain models
- computations
- reusable abstractions
- state/data transformation rules

Should contain:
- logic that should survive UI changes
- code that can be tested without the full UI

Should not contain:
- direct widget handling
- UI rendering concerns
- ad-hoc window orchestration

### app/services
Purpose:
- orchestration
- adapters
- external or cross-module coordination
- non-UI workflow helpers

Typical examples:
- loading, saving, parsing, transformation pipelines
- coordination between UI events and core operations

Should not become:
- a dumping ground for random utilities
- a second core layer with duplicated logic

### app/ui
Purpose:
- presentation layer
- main window
- panels
- widgets
- canvas-related visual composition

Expected substructure:
- `main_window.py` -> main shell / main composition root
- `panels/` -> larger UI regions
- `widgets/` -> reusable smaller UI elements
- `canvas/` -> drawing / visual interaction area

UI layer should:
- delegate logic downward where possible
- stay readable and compositional
- avoid embedding too much business logic directly in event handlers

## Intended Data Flow
Preferred flow:

UI interaction
-> UI event handler
-> service / coordinator / application action
-> core logic / model transformation
-> result mapping
-> UI update

Undesired flow:
- widget directly owns deep domain logic
- UI directly performs all transformations
- multiple panels implement the same business rule separately
- services and core have overlapping responsibilities

## Architecture Review Priorities
When reviewing the system, examine:

1. Entry points
   - where the app starts
   - how `main.py` and `ui/main_window.py` interact

2. Composition root
   - where panels, widgets, services, and state are wired together

3. State ownership
   - where the real application state lives
   - whether state is duplicated across UI components

4. Cross-layer calls
   - whether UI talks directly to core or always via services
   - whether services leak presentation concerns

5. Spec alignment
   - whether implementation matches `control_ui_spec.md`

## Desired Long-Term Qualities
- thin UI, stronger reusable core
- explicit module responsibilities
- minimal duplication
- testable non-UI logic
- incremental extensibility
- clear relationship between UI spec and implementation
