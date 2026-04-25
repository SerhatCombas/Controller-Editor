# Faz 4 — Wheel-Centric Tire-Road Contact: Phase Summary

## TL;DR

Faz 4 migrated quarter-car tire-road coupling from a separate `tire_stiffness Spring` component to
an internal `road_contact_port` owned by `Wheel`. The migration: (a) enables non-linear lift-off
physics (Mode B) that a linear Spring cannot represent, (b) reduces template verbosity by one
component, and (c) preserves bit-for-bit numerical parity for Mode A. Twelve sub-phases were
implemented across multiple sessions; four items are deferred to Faz 5.

---

## Final Phase Map

| Commit tag     | Sub-phase  | Description                                              | Prod files changed |
|----------------|------------|----------------------------------------------------------|--------------------|
| `0414_4a`      | 4a         | `road_contact_port` added to Wheel (`required=False`)    | wheel.py           |
| `0414_4b`      | 4b         | Wheel `get_states()` conditional on `_has_road_contact`  | wheel.py           |
| `0414_4c`      | 4c         | Wheel `constitutive_equations()` Mode A path             | wheel.py           |
| `0415_4d`      | 4d / 4d-2a | `StateContribution` dataclass; `get_state_contribution`  | wheel.py, mass.py, state_contribution.py |
| `0415_4d2b`    | 4d-2b      | `_build_component_records` snapshots `state_contribution`| equation_builder.py |
| `0416_4d2c`    | 4d-2c      | DAEReducer polymorphic mass classification               | dae_reducer.py, test_dae_reducer_polymorphic.py |
| `0418_4f1`     | 4f-1       | Legacy DAEReducer Wheel branch (K/C accumulation)        | wheel.py, dae_reducer.py, test_wheel_road_contact_contribution.py |
| `0419_4g`      | 4g         | Wheel Mode B (`dynamic_contact`, lift-off `max(0,…)`)    | wheel.py, test_wheel_road_contact_contribution.py |
| `0420_4h`      | 4h         | Mode B linearization warnings module + backend metadata  | linearization_warnings.py, runtime_backend.py, simulation_backend.py, test_linearization_warnings.py |
| `0421_4f1p5`   | 4f-1.5     | Polymorphic `contribute_stiffness/damping` (gap fix)     | wheel.py, polymorphic_dae_reducer.py, test_wheel_road_contact_contribution.py |
| `0425_4j1`     | 4j-1       | Template migration: tire_stiffness Spring removed        | quarter_car.py, runtime_backend.py, simulation_backend.py, test_symbolic_pipeline.py |
| `0425_4j7`     | 4j-7       | Faz 4 documentation (phase closure)                     | docs/decisions/013-…md, docs/faz4_summary.md |

### Skipped / Deferred Sub-phases

| Sub-phase | Reason deferred                                                           |
|-----------|---------------------------------------------------------------------------|
| 4d-1      | Merged into 4a (port added at same time as initial Wheel changes)         |
| 4e        | Proposed canvas-side change; blocked on 4i ordering                       |
| 4f-2      | Symbolic SymPy solver integration; out of scope for this phase            |
| 4i        | Canvas UI: tire_stiffness component removal + Mode B visual               |
| 4j-2      | Transducer mode (mass=0 Wheel) full pipeline integration                  |
| 4j-3      | Canvas compiler fixture test updates for new topology                     |
| 4j-4/5    | Polymorphic refactor: remove legacy string `"Wheel"` check                |
| 4j-6      | 37 pre-existing failing tests (unrelated to Faz 4)                        |

---

## Phase-by-Phase Rationale

### 4a / 4b / 4c — Port, States, Mode A Equations

The foundational three commits established the `road_contact_port` as a `required=False` port on
`Wheel`, making it an inert no-op when unwired and an active contact interface when wired. The
`_has_road_contact()` helper (`port("road_contact_port").node_id is not None`) became the single
branch point throughout Wheel's polymorphic interface.

`get_states()` was extended to conditionally include `x_rel_<id>_road`, the road-relative
displacement that forms the third state. `constitutive_equations()` gained the Mode A contact-force
law: `f = k * x_rel + c * (v_road - v)`. The mass ODE was extended to include `f_road` when
road_contact_port is wired.

These three phases were deliberately non-breaking: no template changes, no reducer changes, no test
changes. The Wheel gained new capabilities without touching any integration point.

### 4d split — StateContribution

4d was originally conceived as a single commit. It split into three because the `StateContribution`
dataclass (4d / 4d-2a) required one PR, the `equation_builder.py` snapshot (4d-2b) required a
separate careful edit due to its complexity, and the `DAEReducer` classification change (4d-2c)
needed its own tests.

The key invariant across all three: the legacy string-based fallback (`record["type"] in {"Mass",
"Wheel"}`) was never deleted. It catches any component record that predates the `state_contribution`
snapshot, keeping the pipeline safe across partial upgrades.

The 4d-2c double-commit note: the first `0416_4d2c` attempt mislabeled as `0415_4d2b` due to a
git session artifact. The authoritative commit is `0416_4d2c`. This is tracked as a rebase
candidate for Faz 5 history cleanup.

### 4f-1 — Legacy DAEReducer Wheel Branch

This was the first phase to make Wheel's contact physics visible to the ODE assembler. The legacy
`DAEReducer` (used by test helpers and as a fallback) gained a new `elif record["type"] == "Wheel"`
branch in its Spring/Damper accumulation loop. When `road_contact_port` is wired, the branch calls
`_accumulate_branch` twice: once for `contact_stiffness` → K and once for `contact_damping` → C.

`_accumulate_branch` already existed for Spring/Damper; the only change was making `port_a_name`
and `port_b_name` keyword arguments with defaults, so the Wheel branch could pass
`port_b_name="road_contact_port"` without breaking the existing Spring/Damper calls.

The 14-test `test_wheel_road_contact_contribution.py` was created here. Its
`TestQuarterCarTopologyParity` class became the regression anchor for all subsequent phases.

### 4g — Mode B Lift-Off

Mode B wraps the contact-force RHS in `max(0, …)` inside `constitutive_equations()`. The guard is
`self.parameters["contact_mode"] == "dynamic_contact"`. Mode A is unchanged.

The silent-linearization consequence was documented from the start: the DAEReducer reads
`contact_stiffness` directly from parameters — it never parses the constitutive string. Mode B's
`max(0, …)` is therefore invisible to the ODE assembler. The K matrix for Mode A and Mode B is
identical. This is the correct behavior for the current use case (linear analysis around the
always-in-contact equilibrium) and is explicitly flagged by the warning system added in 4h.

Eight new tests were added: Mode A vs. Mode B equation content, K-matrix identity, and the
nonlinear-law string verification.

### 4h — Linearization Warnings

`linearization_warnings.py` is a thin utility module with two public functions:

- `detect_linearized_mode_b_wheels(graph)` → `list[str]` of component IDs
- `emit_linearization_warning(triggered, *, backend_label)` → logs at WARNING level

Both symbolic backends (`SymbolicStateSpaceRuntimeBackend` in `runtime_backend.py` and the
`get_state_space` method of the simulation backend) call both functions immediately after the graph
is assembled, before the symbolic pipeline runs. They stash the triggered list in
`self.metadata["linearized_contact_mode_b"]`.

The metadata key is a module-level constant (`METADATA_KEY_LINEARIZED_MODE_B`) to prevent typo
drift between producer and consumer.

Backends that use `getattr(backend, "metadata", {})` to read this field will gracefully receive an
empty dict for backend types that predate the metadata attribute (numeric backends).

### 4f-1.5 — Polymorphic Reducer Gap Fix

This was the most consequential bug fix in Faz 4. `DEFAULT_FLAGS` routes through
`PolymorphicDAEReducer` as the authoritative path (`ParityMode.PRIMARY`). But `PolymorphicDAEReducer`
had no Wheel-specific K/C accumulation — it relied on `contribute_stiffness()` / `contribute_damping()`
being called on each component. Wheel didn't implement those methods.

Without the fix, removing `tire_stiffness` Spring (Faz 4j-1) would have caused K[wheel,wheel]
to drop from 195000 to 15000, producing a ~13× wrong wheel-mode eigenvalue.

The fix: add `contribute_stiffness` / `contribute_damping` to `Wheel`, following the same
graph-Laplacian four-entry pattern used by `Spring`. Symbol names `k_contact_<id>` /
`c_contact_<id>` (not `k_<id>` / `d_<id>`) prevent collision. The polymorphic reducer maps these
in `_build_symbol_subs`.

Two correctness subtleties:

1. **Atomic-node guard**: `PolymorphicDAEReducer` may register a synthetic node for an unconnected
   `required=False` port. `contribute_stiffness` guards with `node_index.get(port_road.node_id)`
   and returns `[]` if `None`. Without this, a spurious K entry would appear whenever Wheel was
   present in any graph, even without road contact.

2. **Negative sentinel**: Displacement-source nodes (road) get a negative index. The method
   emits only `(i, i)` self-entry and `(i, j)` → B-matrix routing for the cross-entry, matching
   the convention already used by `Spring._negative_sentinel_contribution`.

Eleven new tests were added to `test_wheel_road_contact_contribution.py`.

### 4j-1 — Template Migration

With the polymorphic reducer gap closed, the `tire_stiffness` Spring could be safely removed from
`quarter_car.py`. The template change was mechanical:

- Remove: `Spring("tire_stiffness", stiffness=180000.0)` and its two connections.
- Add: `contact_stiffness=180000.0, contact_damping=0.0` to the Wheel constructor.
- Wire: `wheel_mass.road_contact_port → road_source.port`.
- Update `schematic_layout`: remove `tire_stiffness` coordinate, shift `road_source` to `(250.0, 455.0)`.

Both backends rerouted `parameters.tire_stiffness` → `graph.components["wheel_mass"].parameters["contact_stiffness"]`.
`QuarterCarParameters.tire_stiffness` was deliberately kept as the public API field.

`test_symbolic_pipeline.py` required two count updates:
- `all_equations`: 34 → 32 (two fewer equations from the removed Spring)
- `algebraic_constraints`: 15 → 14 (one fewer algebraic constraint)
- One parametric test: `graph.components["tire_stiffness"]` → `graph.components["wheel_mass"]`

`TestQuarterCarTopologyParity` (from 4f-1's test file) served as the regression proof that the
migration preserved numerical parity.

---

## Engineering Lessons

**Lesson 1: Authoritative path vs. legacy path diverge silently.**
`PolymorphicDAEReducer` and `DAEReducer` both claim to produce equivalent results. In Faz 4f-1 the
legacy reducer was updated; the polymorphic one was not. Tests passed because the test suite covered
the legacy path. The gap was only visible when checking which path `DEFAULT_FLAGS` actually routes
through. Lesson: when updating one reducer, immediately check the other. For Faz 5, the two paths
should be driven from a single `contribute_*` interface to make divergence structurally impossible.

**Lesson 2: `required=False` ports need an atomic-node guard.**
The polymorphic reducer eagerly registers nodes for all ports, including unconnected optional ones.
Any `contribute_*` method that reads a port's node_id must check whether that node_id is in the
active node index before contributing. This pattern now appears in both `Spring` and `Wheel`; it
should be documented as a required invariant in the `BaseComponent` interface for Faz 4j-4.

**Lesson 3: Symbol namespacing prevents silent parameter aliasing.**
Using `k_contact_<id>` / `c_contact_<id>` instead of the generic `k_<id>` / `d_<id>` made the
contact parameters impossible to alias with Spring/Damper symbols in the same graph. The
`_build_symbol_subs` mapping must stay in sync with the symbol names emitted by `contribute_*`.
For Faz 5, a unit test that enumerates all symbols emitted by all component types would catch
prefix collisions automatically.

---

## Test Growth

| Phase  | New tests | Cumulative total (faz4 files) |
|--------|-----------|-------------------------------|
| 4d-2c  | 8         | 8                             |
| 4f-1   | 14        | 22                            |
| 4g     | 8         | 30                            |
| 4h     | 9         | 39                            |
| 4f-1.5 | 11        | 50                            |
| 4j-1   | 0 new, 2 updated | 50                    |

Test files created:
- `tests/test_dae_reducer_polymorphic.py` (8 tests, 3 classes)
- `tests/test_wheel_road_contact_contribution.py` (33 tests, 7 classes)
- `tests/test_linearization_warnings.py` (9 tests, 4 classes)

---

## Open Items (Faz 5 Candidates)

Listed in suggested priority order:

1. **4j-6 — Pre-existing failing tests (37 tests)**: Baseline cleanup before any further feature
   work. These are unrelated to Faz 4 and likely accumulated across multiple earlier phases.

2. **4j-2 — Transducer mode pipeline integration**: Wheel with `mass=0.0` is currently excluded
   from state variables by `_is_transducer()` but the downstream pipeline (state-space builder,
   output builder) has not been tested with a zero-state Wheel in the graph. A dedicated test class
   and a minimal transducer template are needed.

3. **4j-4/5 — Polymorphic refactor**: Remove the legacy string-based `record["type"] in {"Mass",
   "Wheel"}` check from `dae_reducer.py`. Route all classification through `state_contribution`.
   Simultaneously define `BaseComponent.contribute_stiffness` / `contribute_damping` as the
   canonical interface and remove the Wheel-specific `elif` branch from `DAEReducer`.

4. **4i / 4j-3 — Canvas-side cleanup**: Update the canvas compiler and canvas fixture tests to
   reflect the new topology (no `tire_stiffness` component). Add a Mode B visual indicator (color
   or icon) on the Wheel node when `contact_mode == "dynamic_contact"`.

5. **History cleanup**: Rebase the mislabeled `0415_4d2b` commit to `0416_4d2c`. Low risk,
   cosmetic only.

---

## References

- `docs/decisions/013-wheel-centric-tire-road-contact.md` — ADR for this phase
- `app/core/models/mechanical/wheel.py` — primary implementation
- `app/core/symbolic/linearization_warnings.py` — Mode B detection
- `app/core/symbolic/polymorphic_dae_reducer.py` — authoritative reducer
- `app/core/symbolic/dae_reducer.py` — legacy reducer (retained for compatibility)
- `tests/test_wheel_road_contact_contribution.py` — integration and parity tests
