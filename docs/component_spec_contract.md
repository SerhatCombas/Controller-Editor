# Component Spec Contract

This note freezes the current reusable component contract before the first
electrical primitive rollout.

## Core Contract

Every reusable canvas component should continue to use the same shared fields:

- `domain`
- `category`
- `orientation`
- `connector_ports`
- `supports_translation`
- `supports_deformation`
- `selection_label`
- `motion_profile`
- `boundary_role`

These are the current source-of-truth concepts for canvas identity, selection
payloads, and property metadata. New fields should be added only when they
represent a genuinely new semantic requirement.

## Connector And Rotation Rules

- Connector boxes are the only valid attachment points.
- Wiring attaches to connector centers reported by the framework API.
- Connector geometry must remain deterministic in selected and unselected states.
- Rotation changes geometry, not logical terminal identity.
- Terminal labels that are part of the component identity remain visible in both
  selected and unselected states.

Mechanical examples:

- Spring: `R` -> first terminal, `C` -> second terminal
- Damper: `R` -> first terminal, `C` -> second terminal

Planned electrical rule:

- Logical polarity order must remain stable across rotation.

## Selection Overlay Rule

- The base symbol stays unchanged.
- Selected state only adds overlay and selection label.
- Connector geometry must not change when a component becomes selected.

## Mechanical Family Status

Current mechanical primitives are considered stable and template-ready:

- Mass
- Translational Spring
- Translational Damper
- Mechanical Translational Reference
- Translational Free End

Current semantic mapping:

- Mass -> `internal` / `translating`
- Spring -> `internal` / `deformable`
- Damper -> `internal` / `deformable`
- Mechanical Translational Reference -> `fixed_reference` / `fixed`
- Translational Free End -> `free_end` / `static`

## Property Panel Field Split

Common fields:

- Selected
- Component ID
- Domain
- Category
- Rotation
- Ports
- Status

Mechanical fields:

- Boundary
- Motion

Planned electrical fields should stay domain-specific and must not overload
mechanical meanings:

- Polarity
- Directional / Non-directional
- Source type
- Electrical reference semantics

## Electrical Rollout Guardrails

Before and during the first electrical primitive rollout:

- Keep all electrical primitives `rigid`.
- Keep `supports_translation = False`.
- Keep `supports_deformation = False`.
- Do not reuse spring/damper deformation logic for electrical symbols.
- Keep polarity and direction semantics inside connector metadata and
  component-specific helpers, not ad hoc canvas logic.

Recommended rollout order:

1. Electrical Reference
2. Resistor
3. Capacitor
4. Inductor
5. Diode
6. DC Voltage Source
7. AC Voltage Source

## Test Standard

Each new primitive should get the same minimum regression contract:

- spec semantics
- selected vs unselected behavior
- connector placement
- rotation validity
- domain-specific semantic helpers
- property panel metadata
