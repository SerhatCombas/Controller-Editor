# Wheel-Centric Tire-Road Contact (Faz 4)

- Date: 2026-04-26
- Status: Accepted

## Problem / Context

The original quarter-car model represented tire-road coupling as a separate `Spring` component
(`tire_stiffness`) wired between `wheel_mass.port_a` and `road_source.port`. This created three
problems:

1. **Topology leak**: The tire spring was a user-visible graph component, making it possible to
   accidentally delete or disconnect it and silently produce a physically wrong model.
2. **Mode B (lift-off) incompatibility**: A linear `Spring` cannot represent `max(0, …)` contact
   physics. Implementing lift-off required the wheel to own the contact law.
3. **Component proliferation**: Every Wheel-based template needed an explicit tire spring, making
   templates more verbose and harder to maintain.

The fix was to move all tire-road contact dynamics inside `Wheel` itself, activated by wiring
`Wheel.road_contact_port`.

## Decision

`Wheel` is now the single owner of tire-road coupling. When `road_contact_port` is wired:

- `get_states()` returns a third state: `x_rel_<id>_road` (road-relative displacement).
- `constitutive_equations()` emits the full contact-force law plus its ODE.
- `contribute_stiffness()` / `contribute_damping()` inject the contact stiffness/damping into the
  assembler's K/C matrices using the same graph-Laplacian four-entry pattern as `Spring`/`Damper`.
- The template (`quarter_car.py`) contains no separate tire-spring component; `wheel_mass` carries
  `contact_stiffness=180000.0` and `contact_damping=0.0` directly.
- `QuarterCarParameters.tire_stiffness` is preserved as the public API knob and is routed to
  `wheel_mass.contact_stiffness` in all backends.

Mode B (dynamic contact, lift-off) wraps the contact-force RHS in `max(0, …)` inside
`constitutive_equations()`. The symbolic pipeline silently linearizes this; the linearization is
detected and surfaced via `linearization_warnings.py`.

## Implementation Notes

**Symbol convention.** Wheel uses `k_contact_<id>` / `c_contact_<id>` as sympy symbol names to
avoid collision with `k_<id>` / `d_<id>` emitted by `Spring` / `Damper`. The polymorphic reducer
maps these in `_build_symbol_subs`.

**Cross-reducer parity.** Both the legacy `DAEReducer` (Faz 4f-1 Wheel branch) and the
authoritative `PolymorphicDAEReducer` (Faz 4f-1.5 `contribute_stiffness`/`contribute_damping`)
accumulate `contact_stiffness` → K and `contact_damping` → C. They produce identical matrices;
the legacy reducer is retained so test helpers that instantiate it directly continue to work.

**Silent linearization.** Both reducers read `contact_stiffness` directly from parameters — they
never see the `max(0, …)` in Mode B's constitutive equation. The K matrix is therefore identical
for Mode A and Mode B. This is intentional for the current linear-analysis use case and is flagged
by `detect_linearized_mode_b_wheels()`.

**Atomic-node guard in `contribute_stiffness`.** `PolymorphicDAEReducer` may register an atomic
node for `road_contact_port` when it is not wired. `contribute_stiffness` checks
`node_index.get(port_road.node_id)` and returns `[]` if the result is `None`, preventing spurious
K entries from unconnected optional ports.

**Negative sentinel (j < 0).** Displacement-source nodes receive a negative index in the extended
node index. `contribute_stiffness` emits only the `(i, i)` self-entry and routes the `(i, j)`
cross-entry to the input matrix B (via the negative-index convention already established by
`Spring`).

**Bit-for-bit parity.** With `contact_stiffness=180000.0` (matching the removed `tire_stiffness`
Spring's `stiffness=180000.0`) the A, B, C, D matrices produced by the new topology are
numerically identical to the old topology to floating-point precision.

## Files Affected

- `app/core/models/mechanical/wheel.py` — `get_states`, `constitutive_equations`,
  `contribute_stiffness`, `contribute_damping`, Mode B branch, docstrings
- `app/core/symbolic/dae_reducer.py` — Wheel branch in Spring/Damper loop (4f-1);
  polymorphic classification via `state_contribution` (4d-2c)
- `app/core/symbolic/equation_builder.py` — snapshots `state_contribution` into component records
- `app/core/symbolic/polymorphic_dae_reducer.py` — `k_contact_<id>` / `c_contact_<id>` symbol
  subs (4f-1.5)
- `app/core/symbolic/linearization_warnings.py` — new; Mode B detection + warning emission (4h)
- `app/core/templates/quarter_car.py` — `tire_stiffness` Spring removed; Wheel carries contact
  params; `road_contact_port` wired (4j-1)
- `app/services/runtime_backend.py` — `SymbolicStateSpaceRuntimeBackend`: tire_stiffness → 
  contact_stiffness; Mode B detection + metadata (4h, 4j-1)
- `app/services/simulation_backend.py` — same rerouting + metadata in `get_state_space()` (4h,
  4j-1)
- `tests/test_symbolic_pipeline.py` — equation/constraint counts updated; tire_stiffness →
  contact_stiffness in parametric test (4j-1)
- `tests/test_dae_reducer_polymorphic.py` — new; 8 tests for polymorphic classification (4d-2c)
- `tests/test_wheel_road_contact_contribution.py` — new; 33 tests for all Wheel contact branches
  (4f-1, 4g, 4f-1.5)
- `tests/test_linearization_warnings.py` — new; 9 tests for Mode B warning pipeline (4h)

## Alternatives Considered

**Keep tire_stiffness as a standalone Spring, add lift-off via override.** Would have required
subclassing `Spring` or adding a flag to the existing Spring to support `max(0, …)`, and still
wouldn't eliminate the template proliferation problem. Rejected: contact physics belong to the
Wheel.

**Make road_contact_port a required port.** Would have broken all existing Wheel-based templates
that don't model road contact (two-mass, single-mass). Rejected: `required=False` with conditional
activation is the correct encapsulation.

**Add a dedicated `TireSpring` component type.** Would have made templates even more verbose and
created a new first-class component for something that is logically internal to the Wheel model.
Rejected: violates the principle that physical subsystems own their own dynamics.

## Consequences

- Quarter-car templates are simpler by one component and one connection.
- `QuarterCarParameters.tire_stiffness` continues to work without API changes.
- Mode B lift-off physics are representable in constitutive equations (future symbolic backends can
  use the nonlinear form).
- The symbolic pipeline silently linearizes Mode B; callers must check
  `metadata["linearized_contact_mode_b"]` to detect this.
- Canvas-side UI still references `tire_stiffness` by name in some places (tracked as Faz 4i
  follow-up).

## Known Risks / Follow-up

- **Canvas fixture tests** referencing `tire_stiffness` as a component ID will fail when the
  canvas compiler is updated. Tracked as Faz 4i / 4j-3.
- **37 pre-existing failing tests** (unrelated to Faz 4) remain in the test suite. Tracked as Faz
  4j-6.
- **Transducer mode** (Wheel with mass=0 used as a kinematic passthrough) is not yet integrated
  into the full symbolic pipeline. Tracked as Faz 4j-2.
- **Polymorphic refactor** (removing the legacy string-based `"Wheel"` check from DAEReducer
  entirely) is deferred to Faz 4j-4/5.
- **Mode B visual indicator** in the canvas UI is deferred to Faz 4i.

## Test / Validation Notes

- All 10 `test_symbolic_pipeline.py` tests pass with the new topology.
- `test_wheel_road_contact_contribution.py::TestQuarterCarTopologyParity` confirms bit-for-bit
  parity between old (Spring) and new (Wheel) topologies across all 4×4 A-matrix entries.
- `test_linearization_warnings.py` verifies that Mode B wheels are detected, that warnings are
  emitted, and that both symbolic backends populate `metadata["linearized_contact_mode_b"]`.
- Parametric tests (damping, stiffness, tire stiffness) in `test_symbolic_pipeline.py` confirm
  that changing `wheel_mass.contact_stiffness` produces the expected A-matrix sensitivity.

## Prompt / Iteration Summary

Faz 4 spanned phases 4a–4j across multiple sessions. The core sequence: 4a/4b/4c established the
`road_contact_port` port infrastructure; 4d split state classification into polymorphic (4d-2c)
and legacy paths; 4f-1 added the contact-force accumulation to the legacy reducer; 4g added Mode B
constitutive law; 4h added linearization detection; 4f-1.5 closed the hidden gap in the
authoritative polymorphic reducer; 4j-1 completed the template migration and removed the
tire_stiffness Spring. See `docs/faz4_summary.md` for the full phase-by-phase narrative.
