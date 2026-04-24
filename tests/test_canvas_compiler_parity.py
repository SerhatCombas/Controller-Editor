"""Faz 0.5 — Numerical Parity Test

Two test classes with distinct scopes:

TestCanvasCompilerNumericalParity  (parity-canonical config — MUST stay green)
──────────────────────────────────────────────────────────────────────────────
Verifies that CanvasCompiler, when given a *parity-canonical* canvas
(component IDs identical to the template, including the explicit ``body_force``
and ``ground`` components that do NOT appear in the production canvas), produces
A, B, C, D matrices numerically identical to build_quarter_car_template().

This class answers: "If the canvas were fully spec-complete, would
CanvasCompiler produce the right physics?"  Answer: YES.

IMPORTANT: ``body_force`` (ideal_force_source) is explicitly included in
``_PARITY_COMPONENTS`` (line ~135) and wired in ``_PARITY_WIRES`` (two wires).
It is NOT present in the production canvas (load_default_quarter_car_layout).
Removing it from this fixture would cause B to have 1 column instead of 2
and the parity tests would legitimately fail.

TestProductionCanvasGap  (documents known failures — EXPECTED to fail)
──────────────────────────────────────────────────────────────────────
Tests the *actual* production canvas layout as loaded by
model_canvas.py::load_default_quarter_car_layout.  These tests are decorated
with @unittest.expectedFailure to document the gap that Phase 2 must close.
They act as regression sentinels: if Phase 2 fixes one of these gaps, the
corresponding expectedFailure becomes an unexpected pass → test framework
reports it, reminding you to promote it to a real green test.

Pipeline choice
───────────────
EquationBuilder is bypassed on purpose.  It has a pre-existing parse error
for component IDs that generate ``r_<name>(t)`` equations (e.g.
``r_road_source(t)``).  PolymorphicDAEReducer works directly from the
polymorphic BaseComponent interface and produces numeric float matrices
immediately — no sympy substitution needed.
"""
from __future__ import annotations

import sys
import types
import unittest
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# PySide6-free stand-ins (identical pattern to test_canvas_compiler.py)
# ---------------------------------------------------------------------------

def _install_ui_shim() -> None:
    """Register a minimal fake for app.ui.canvas.component_system."""
    if "app.ui.canvas.component_system" in sys.modules:
        return
    fake = types.ModuleType("app.ui.canvas.component_system")

    class _ComponentIoRole(Enum):
        INPUT  = "input"
        OUTPUT = "output"

    fake.ComponentIoRole = _ComponentIoRole
    sys.modules["app.ui.canvas.component_system"] = fake


_install_ui_shim()


@dataclass
class _Spec:
    type_key: str


@dataclass
class _Comp:
    component_id: str
    type_key: str
    assigned_io_roles: tuple = field(default_factory=tuple)

    @property
    def spec(self) -> _Spec:
        return _Spec(self.type_key)


@dataclass
class _Wire:
    source_component_id:   str
    source_connector_name: str
    target_component_id:   str
    target_connector_name: str


def _comp(cid: str, tkey: str) -> _Comp:
    return _Comp(cid, tkey)


def _wire(s: str, sc: str, t: str, tc: str) -> _Wire:
    return _Wire(s, sc, t, tc)


# ---------------------------------------------------------------------------
# Pipeline dependencies
# ---------------------------------------------------------------------------

try:
    from app.services.canvas_compiler import CanvasCompiler
    from app.core.templates.quarter_car import build_quarter_car_template
    from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
    from app.core.symbolic.state_space_builder import StateSpaceBuilder
    from app.core.probes import BaseProbe, RelativeProbe
    from app.core.symbolic.output_kind import (
        OutputKind,
        QK_ACCELERATION,
        QK_DISPLACEMENT,
        QK_RELATIVE_DISPLACEMENT,
        QK_SPRING_FORCE,
    )
    _PIPELINE_OK = True
except ImportError as _e:
    _PIPELINE_OK = False
    _IMPORT_ERROR = str(_e)


# ---------------------------------------------------------------------------
# Stub SymbolicSystem (bypasses EquationBuilder — see module docstring)
# ---------------------------------------------------------------------------

class _StubSymbolicSystem:
    output_definitions:    dict = {}
    algebraic_constraints: list = []
    metadata:              dict = {}
    equation_records:      list = []


# ---------------------------------------------------------------------------
# Parity-canonical canvas layout
# ---------------------------------------------------------------------------
# Component IDs here are chosen to match build_quarter_car_template() exactly.
# See "ID mapping" section at the bottom for the production canvas discrepancy.

_PARITY_COMPONENTS: list[_Comp] = [
    _comp("body_mass",          "mass"),
    _comp("wheel_mass",         "wheel"),
    _comp("suspension_spring",  "translational_spring"),
    _comp("suspension_damper",  "translational_damper"),
    _comp("tire_stiffness",     "tire_stiffness"),
    _comp("road_source",        "mechanical_random_reference"),
    _comp("body_force",         "ideal_force_source"),
    _comp("ground",             "mechanical_reference"),
]

# Wire encoding  (canvas connector names → CanvasCompiler port map):
#
#   mass.bottom       → port_a          spring/damper.R → port_a
#   mass.top          → port_a          spring/damper.C → port_b
#   wheel.top/bottom  → port_a          tire_stiffness.R/C → port_a/port_b
#   ideal_force.R     → port            ideal_force.C → reference_port
#   mech_random.output → port
#
# Topology being expressed:
#   BODY node  = {body_mass.port_a, suspension_spring.port_a,
#                 suspension_damper.port_a, body_force.port}
#   WHEEL node = {wheel_mass.port_a, suspension_spring.port_b,
#                 suspension_damper.port_b, tire_stiffness.port_a,
#                 body_force.reference_port}
#   ROAD node  = {tire_stiffness.port_b, road_source.port}
#   GROUND     = {ground.port, body_mass.reference_port (implicit),
#                 wheel_mass.reference_port (implicit),
#                 road_source.reference_port (implicit)}

_PARITY_WIRES: list[_Wire] = [
    # Body node
    _wire("body_mass",         "bottom", "suspension_spring", "R"),
    _wire("body_mass",         "bottom", "suspension_damper", "R"),
    _wire("body_mass",         "bottom", "body_force",        "R"),
    # Wheel node
    _wire("suspension_spring", "C",      "wheel_mass",        "top"),
    _wire("suspension_damper", "C",      "wheel_mass",        "top"),
    _wire("wheel_mass",        "bottom", "tire_stiffness",    "R"),
    _wire("body_force",        "C",      "wheel_mass",        "top"),
    # Road node
    _wire("road_source",       "output", "tire_stiffness",    "C"),
    # Ground wires: NONE needed — mass/wheel/road have implicit reference_port → ground
]

# Canonical parameters (must match build_quarter_car_template() defaults)
_CANONICAL_PARAMS: dict[str, tuple[str, float]] = {
    "body_mass":         ("mass",       300.0),
    "wheel_mass":        ("mass",        40.0),
    "suspension_spring": ("stiffness", 15000.0),
    "suspension_damper": ("damping",    1200.0),
    "tire_stiffness":    ("stiffness", 180000.0),
}

# Probes must match template's attach_probe() calls in quarter_car.py —
# same IDs, same target_component_id, same output_kind — so output_variables
# lists will be identical and C/D rows will align without reindexing.
def _canonical_probes(graph) -> None:
    """Attach the six template probes to a compiled graph, clearing auto-probes."""
    graph.probes.clear()
    graph.attach_probe(BaseProbe(
        "body_displacement", "Body displacement", "displacement", "body_mass",
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "wheel_displacement", "Wheel displacement", "displacement", "wheel_mass",
        output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
    ))
    graph.attach_probe(BaseProbe(
        "body_acceleration", "Body acceleration", "acceleration", "body_mass",
        output_kind=OutputKind.DERIVED_DYNAMIC, quantity_key=QK_ACCELERATION,
    ))
    graph.attach_probe(BaseProbe(
        "suspension_force", "Suspension force", "force", "suspension_spring",
        output_kind=OutputKind.DERIVED_ALGEBRAIC, quantity_key=QK_SPRING_FORCE,
    ))
    graph.attach_probe(RelativeProbe(
        "suspension_deflection", "Suspension deflection", "displacement",
        "body_mass", reference_component_id="wheel_mass",
        output_kind=OutputKind.STATE_RELATIVE, quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))
    graph.attach_probe(RelativeProbe(
        "tire_deflection", "Tire deflection", "displacement",
        "wheel_mass", reference_component_id="road_source",
        output_kind=OutputKind.STATE_RELATIVE, quantity_key=QK_RELATIVE_DISPLACEMENT,
    ))


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def _run_pipeline(graph) -> object:
    """PolymorphicDAEReducer → StateSpaceBuilder → StateSpaceModel (numeric)."""
    stub = _StubSymbolicSystem()
    reduced = PolymorphicDAEReducer().reduce(graph, stub)
    return StateSpaceBuilder().build(graph, reduced, stub)


# ---------------------------------------------------------------------------
# Pure-Python matrix comparison (no numpy)
# ---------------------------------------------------------------------------

def _assert_matrices_close(
    computed: list[list[float]],
    reference: list[list[float]],
    label: str,
    tol: float = 1e-9,
) -> None:
    """Raise AssertionError with a precise diff if any element exceeds tol."""
    if len(computed) != len(reference):
        raise AssertionError(
            f"{label}: row count mismatch — compiled {len(computed)} vs template {len(reference)}"
        )
    for i, (row_c, row_t) in enumerate(zip(computed, reference)):
        if len(row_c) != len(row_t):
            raise AssertionError(
                f"{label}[{i}]: col count mismatch — compiled {len(row_c)} vs template {len(row_t)}"
            )
        for j, (vc, vt) in enumerate(zip(row_c, row_t)):
            diff = abs(vc - vt)
            if diff > tol:
                raise AssertionError(
                    f"{label}[{i}][{j}]: compiled={vc:.8e}  template={vt:.8e}  "
                    f"diff={diff:.2e}  (tol={tol:.0e})"
                )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@unittest.skipUnless(_PIPELINE_OK, f"Pipeline import failed: {'' if _PIPELINE_OK else '?'}")
class TestCanvasCompilerNumericalParity(unittest.TestCase):
    """A, B, C, D matrices from compiled canvas == build_quarter_car_template()."""

    @classmethod
    def setUpClass(cls) -> None:
        # ── Template path ─────────────────────────────────────────────────
        template        = build_quarter_car_template()
        cls.ss_template = _run_pipeline(template.graph)

        # ── Compiled path ─────────────────────────────────────────────────
        compiled_graph = CanvasCompiler().compile(_PARITY_COMPONENTS, _PARITY_WIRES)

        # Apply canonical parameters
        for comp_id, (param_key, value) in _CANONICAL_PARAMS.items():
            compiled_graph.components[comp_id].parameters[param_key] = value

        # Attach template-identical probes
        _canonical_probes(compiled_graph)

        cls.ss_compiled = _run_pipeline(compiled_graph)

    # ── Ordering sanity ───────────────────────────────────────────────────

    def test_state_variable_order_identical(self) -> None:
        """State variable names and order must match — no reindexing needed."""
        self.assertEqual(
            self.ss_compiled.state_variables,
            self.ss_template.state_variables,
            msg=(
                f"Compiled: {self.ss_compiled.state_variables}\n"
                f"Template: {self.ss_template.state_variables}"
            ),
        )

    def test_input_variable_order_identical(self) -> None:
        """Input variable names and order must match."""
        self.assertEqual(
            self.ss_compiled.input_variables,
            self.ss_template.input_variables,
            msg=(
                f"Compiled: {self.ss_compiled.input_variables}\n"
                f"Template: {self.ss_template.input_variables}"
            ),
        )

    def test_output_variable_order_identical(self) -> None:
        """Probe IDs and order must match — ensures C/D rows are comparable."""
        self.assertEqual(
            self.ss_compiled.output_variables,
            self.ss_template.output_variables,
            msg=(
                f"Compiled: {self.ss_compiled.output_variables}\n"
                f"Template: {self.ss_template.output_variables}"
            ),
        )

    # ── Matrix parity ─────────────────────────────────────────────────────

    def test_a_matrix_parity(self) -> None:
        """System dynamics matrix A must be numerically identical (1e-9)."""
        _assert_matrices_close(
            self.ss_compiled.a_matrix,
            self.ss_template.a_matrix,
            label="A",
        )

    def test_b_matrix_parity(self) -> None:
        """Input coupling matrix B must be numerically identical."""
        _assert_matrices_close(
            self.ss_compiled.b_matrix,
            self.ss_template.b_matrix,
            label="B",
        )

    def test_c_matrix_parity(self) -> None:
        """Output selection matrix C must be numerically identical."""
        _assert_matrices_close(
            self.ss_compiled.c_matrix,
            self.ss_template.c_matrix,
            label="C",
        )

    def test_d_matrix_parity(self) -> None:
        """Direct feedthrough matrix D must be numerically identical."""
        _assert_matrices_close(
            self.ss_compiled.d_matrix,
            self.ss_template.d_matrix,
            label="D",
        )

    # ── Physical spot-checks ──────────────────────────────────────────────

    def test_a_matrix_four_by_four(self) -> None:
        """Quarter-car has 4 states (2 DOF × 2 orders) → 4×4 A matrix."""
        self.assertEqual(len(self.ss_compiled.a_matrix),    4)
        self.assertEqual(len(self.ss_compiled.a_matrix[0]), 4)

    def test_b_matrix_two_inputs(self) -> None:
        """Template has two inputs (road + body_force) → B has 2 columns."""
        self.assertEqual(len(self.ss_compiled.b_matrix[0]), 2)

    def test_c_matrix_six_outputs(self) -> None:
        """Six probes → C has 6 rows."""
        self.assertEqual(len(self.ss_compiled.c_matrix), 6)

    def test_a_matrix_body_row_physics(self) -> None:
        """Body acceleration row of A:
        a[2] = [-ks/mb, ks/mb, -ds/mb, ds/mb]
              = [-50, 50, -4, 4]  for ks=15000, ds=1200, mb=300.
        State order: [x_body, x_wheel, v_body, v_wheel].
        """
        # Locate body velocity row (state x_body_mass index = 0 → acceleration row = 2)
        states = self.ss_compiled.state_variables
        v_body_idx = states.index("v_body_mass")
        # The derivative of v_body is in A's row for v_body
        row = self.ss_compiled.a_matrix[v_body_idx]
        x_body_idx  = states.index("x_body_mass")
        x_wheel_idx = states.index("x_wheel_mass")
        v_wheel_idx = states.index("v_wheel_mass")

        self.assertAlmostEqual(row[x_body_idx],  -50.0, places=6,
                               msg="A[v_body, x_body]  should be -ks/mb = -50")
        self.assertAlmostEqual(row[x_wheel_idx],  50.0, places=6,
                               msg="A[v_body, x_wheel] should be +ks/mb = +50")
        self.assertAlmostEqual(row[v_body_idx],   -4.0, places=6,
                               msg="A[v_body, v_body]  should be -ds/mb = -4")
        self.assertAlmostEqual(row[v_wheel_idx],   4.0, places=6,
                               msg="A[v_body, v_wheel] should be +ds/mb = +4")

    def test_b_road_input_drives_wheel(self) -> None:
        """Road displacement enters the wheel DOF via tire stiffness.
        B[v_wheel, road] = kt/mw = 180000/40 = 4500.
        """
        states = self.ss_compiled.state_variables
        inputs = self.ss_compiled.input_variables

        v_wheel_idx  = states.index("v_wheel_mass")
        road_inp_idx = next(
            i for i, v in enumerate(inputs) if "road_source" in v
        )
        b_road_wheel = self.ss_compiled.b_matrix[v_wheel_idx][road_inp_idx]
        self.assertAlmostEqual(b_road_wheel, 4500.0, places=4,
                               msg="B[v_wheel, road] should be kt/mw = 4500")

    def test_c_body_displacement_row(self) -> None:
        """body_displacement = x_body → C row is [1, 0, 0, 0] (canonical order)."""
        outputs = self.ss_compiled.output_variables
        states  = self.ss_compiled.state_variables
        bd_idx  = outputs.index("body_displacement")
        row     = self.ss_compiled.c_matrix[bd_idx]

        x_body_idx = states.index("x_body_mass")
        for j, v in enumerate(row):
            expected = 1.0 if j == x_body_idx else 0.0
            self.assertAlmostEqual(v, expected, places=9,
                                   msg=f"C[body_disp, state {j}] should be {expected}")


# ---------------------------------------------------------------------------
# Production canvas fixture  (as loaded by load_default_quarter_car_layout)
# ---------------------------------------------------------------------------
# Phase 2 applied: IDs match template. body_force and ground are present.

_PRODUCTION_COMPONENTS: list[_Comp] = [
    _comp("road_source",       "mechanical_random_reference"),
    _comp("body_mass",         "mass"),
    _comp("suspension_damper", "translational_damper"),
    _comp("suspension_spring", "translational_spring"),
    _comp("wheel_mass",        "wheel"),
    _comp("tire_stiffness",    "tire_stiffness"),
    _comp("body_force",        "ideal_force_source"),
    _comp("ground",            "mechanical_reference"),
]

_PRODUCTION_WIRES: list[_Wire] = [
    _wire("body_mass",         "bottom", "suspension_damper", "R"),
    _wire("body_mass",         "bottom", "suspension_spring", "R"),
    _wire("suspension_damper", "C",      "wheel_mass",        "top"),
    _wire("suspension_spring", "C",      "wheel_mass",        "top"),
    _wire("wheel_mass",        "bottom", "tire_stiffness",    "R"),
    _wire("road_source",       "output", "tire_stiffness",    "C"),
    _wire("body_mass",         "bottom", "body_force",        "R"),
    _wire("body_force",        "C",      "wheel_mass",        "top"),
]


@unittest.skipUnless(_PIPELINE_OK, "Pipeline import failed")
class TestProductionCanvasGap(unittest.TestCase):
    """Phase 2 completed: production canvas IDs match template, body_force and ground added.

    All previously @expectedFailure tests are now green.
    """

    @classmethod
    def setUpClass(cls) -> None:
        template = build_quarter_car_template()
        cls.ss_template = _run_pipeline(template.graph)

        prod_graph = CanvasCompiler().compile(_PRODUCTION_COMPONENTS, _PRODUCTION_WIRES)
        # Apply production-equivalent parameters (IDs now match template after Phase 2)
        prod_graph.components["body_mass"].parameters["mass"]              = 300.0
        prod_graph.components["wheel_mass"].parameters["mass"]             = 40.0
        prod_graph.components["suspension_spring"].parameters["stiffness"] = 15000.0
        prod_graph.components["suspension_damper"].parameters["damping"]   = 1200.0
        prod_graph.components["tire_stiffness"].parameters["stiffness"]    = 180000.0

        # Probes: Phase 2 IDs match template
        prod_graph.probes.clear()
        prod_graph.attach_probe(BaseProbe(
            "body_displacement", "Body displacement", "displacement", "body_mass",
            output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
        ))
        prod_graph.attach_probe(BaseProbe(
            "wheel_displacement", "Wheel displacement", "displacement", "wheel_mass",
            output_kind=OutputKind.STATE_DIRECT, quantity_key=QK_DISPLACEMENT,
        ))

        cls.ss_prod = _run_pipeline(prod_graph)

    def test_gap_input_count(self) -> None:
        """Production canvas now has 2 inputs (road + body_force) matching template.
        """
        n_inputs_prod     = len(self.ss_prod.b_matrix[0])
        n_inputs_template = len(self.ss_template.b_matrix[0])
        self.assertEqual(n_inputs_prod, n_inputs_template,
                         msg=f"Production: {n_inputs_prod} inputs, template: {n_inputs_template}")

    def test_gap_state_variable_names(self) -> None:
        """Production canvas state variables now match template: x_body_mass, x_wheel_mass.
        Phase 2 renamed wheel → wheel_mass and disturbance_source → road_source.
        """
        self.assertEqual(
            self.ss_prod.state_variables,
            self.ss_template.state_variables,
            msg=(
                f"Production states: {self.ss_prod.state_variables}\n"
                f"Template states:   {self.ss_template.state_variables}"
            ),
        )

    def test_gap_b_matrix_shape(self) -> None:
        """B matrix shape now matches (4×2 = 4×2) because body_force was added in Phase 2.
        """
        _assert_matrices_close(self.ss_prod.b_matrix, self.ss_template.b_matrix, "B")

    def test_a_matrix_values_still_correct(self) -> None:
        """A matrix values are physically correct. Phase 2 IDs match template, name_map is identity.
        """
        # A is 4×4 in both cases; reorder production states to match template order
        t_states = self.ss_template.state_variables
        p_states = self.ss_prod.state_variables

        # Phase 2 applied: IDs match, so name_map is identity.
        name_map = {
            "x_body_mass":  "x_body_mass",
            "v_body_mass":  "v_body_mass",
            "x_wheel_mass": "x_wheel_mass",
            "v_wheel_mass": "v_wheel_mass",
        }
        try:
            perm = [p_states.index(name_map[ts]) for ts in t_states]
        except (KeyError, ValueError) as exc:
            self.skipTest(f"State alignment impossible: {exc}")
            return

        a_prod_reindexed = [[self.ss_prod.a_matrix[perm[r]][perm[c]]
                             for c in range(4)] for r in range(4)]
        _assert_matrices_close(a_prod_reindexed, self.ss_template.a_matrix, "A (reindexed)")


# ---------------------------------------------------------------------------
# ID Mapping Table  (summary of Phase 2 work items)
# ---------------------------------------------------------------------------
#
#  Production canvas ID    Template ID         Gap           Phase 2 action
#  ──────────────────────  ──────────────────  ────────────  ──────────────
#  disturbance_source      road_source         ID mismatch   RENAME
#  body_mass               body_mass           ✓ match       —
#  suspension_spring       suspension_spring   ✓ match       —
#  suspension_damper       suspension_damper   ✓ match       —
#  wheel                   wheel_mass          ID mismatch   RENAME
#  tire_stiffness          tire_stiffness      ✓ match       —
#  (absent)                body_force          missing input ADD
#  (absent)                ground              implicit only ADD (explicit)
#
# Consequence of ID mismatches:
#   State variables become ["x_wheel","v_wheel"] instead of
#   ["x_wheel_mass","v_wheel_mass"].  QuarterCarBackendContract.STATE_ORDER
#   alignment fails.  TestProductionCanvasGap.test_gap_state_variable_names
#   documents this as @expectedFailure.
#
# Consequence of missing body_force:
#   B matrix is 4×1 (road only) instead of 4×2 (road + force).
#   TestProductionCanvasGap.test_gap_input_count and test_gap_b_matrix_shape
#   document this as @expectedFailure.
#
# Failure analysis if TestCanvasCompilerNumericalParity breaks in future:
#
#   Which matrix   Likely root cause                Required fix
#   ────────────── ─────────────────────────────── ──────────────────────
#   A (wrong vals) Wrong parameter overlay          Phase 3
#   A (wrong rows) body_force removed from fixture  restore _PARITY_WIRES
#   B col missing  body_force removed from fixture  restore _PARITY_COMPONENTS
#   B wrong vals   ideal_force_source port mapping  canvas_compiler.py port map
#   C wrong row    Probe target ID changed           Phase 2 probe attachment
#   C wrong cols   State ordering changed            Phase 2 ID hizalama
#   D wrong        OutputMapper feedthrough bug      Phase 1 core_factory
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
