"""Tests for OutputMapper (Wave 3A update).

Covers:
- displacement / velocity absolute mapping (BaseProbe)
- relative_displacement / relative_velocity mapping (RelativeProbe)
- acceleration output: supported via DERIVED_DYNAMIC (c_row = A[vel_idx], d_row = B[vel_idx])
- spring_force / damper_force: supported via DERIVED_ALGEBRAIC (graph required)
- unsupported: force without graph, unknown quantity, non-DOF target
- unsupported: reference is non-DOF (source / ground)
- unsupported: no target_component_id
- OutputKind taxonomy: kind field on every OutputExpression
- c_row / d_row shapes and values
- contributing_state_indices / contributing_state_names
- provenance always populated
- supported_for_tf=False never produces a non-zero C row (honesty guarantee)
- single binding point: mapper is stateless, same instance reusable
- quarter-car probe set (all probes mapped, including new 3A types)
"""
from __future__ import annotations

import unittest

from app.core.symbolic.output_mapper import OutputExpression, OutputMapper
from app.core.symbolic.output_kind import OutputKind
from app.core.symbolic.symbolic_system import ReducedODESystem


# ---------------------------------------------------------------------------
# Minimal ReducedODESystem factory
# ---------------------------------------------------------------------------

def _ode(state_vars: list[str], input_vars: list[str] | None = None) -> ReducedODESystem:
    """Build a bare ReducedODESystem with zero A/B matrices (correct dimensions).

    Suitable for displacement / velocity tests where A/B are not accessed.
    """
    iv = input_vars or []
    n, m = len(state_vars), len(iv)
    return ReducedODESystem(
        state_variables=state_vars,
        input_variables=iv,
        first_order_a=[[0.0] * n for _ in range(n)],
        first_order_b=[[0.0] * m for _ in range(n)],
    )


def _ode_physical(m: float = 2.0, k: float = 10.0, d: float = 3.0) -> ReducedODESystem:
    """Single-mass system with real A/B matrices for acceleration tests.

    M·ẍ + D·ẋ + K·x = F  →  first-order:
        ẋ₁ = x₂
        ẋ₂ = -(k/m)·x₁ - (d/m)·x₂ + (1/m)·F

    A = [[0, 1], [-k/m, -d/m]],  B = [[0], [1/m]]
    """
    return ReducedODESystem(
        state_variables=["x_mass", "v_mass"],
        input_variables=["u_force"],
        first_order_a=[[0.0, 1.0], [-k / m, -d / m]],
        first_order_b=[[0.0], [1.0 / m]],
    )


# ---------------------------------------------------------------------------
# Probe stubs (duck-typed — no import of actual probe classes needed here)
# ---------------------------------------------------------------------------

class _BaseProbeStub:
    def __init__(self, pid, name, quantity, target_cid):
        self.id = pid
        self.name = name
        self.quantity = quantity
        self.target_component_id = target_cid
        self.reference_component_id = None


class _RelativeProbeStub(_BaseProbeStub):
    def __init__(self, pid, name, quantity, target_cid, ref_cid):
        super().__init__(pid, name, quantity, target_cid)
        self.reference_component_id = ref_cid


# ---------------------------------------------------------------------------
# Standard single-mass ODE fixture
# ---------------------------------------------------------------------------

SINGLE_MASS_STATES = ["x_mass", "v_mass"]
SINGLE_MASS_INPUTS = ["u_force"]


class TestOutputExpressionFrozen(unittest.TestCase):
    def test_frozen(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("d", "disp", "displacement", "mass")
        expr = OutputMapper().map(probe, ode)
        with self.assertRaises((AttributeError, TypeError)):
            expr.c_row = (9.0,)  # type: ignore[misc]

    def test_slots(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("d", "disp", "displacement", "mass")
        expr = OutputMapper().map(probe, ode)
        with self.assertRaises(AttributeError):
            expr.__dict__  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Absolute displacement
# ---------------------------------------------------------------------------

class TestAbsoluteDisplacement(unittest.TestCase):

    def setUp(self):
        self.ode = _ode(SINGLE_MASS_STATES, SINGLE_MASS_INPUTS)
        self.probe = _BaseProbeStub("body_disp", "Body displacement", "displacement", "mass")
        self.expr = OutputMapper().map(self.probe, self.ode)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_unsupported_reason_none(self):
        self.assertIsNone(self.expr.unsupported_reason)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "displacement")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.STATE_DIRECT)

    def test_c_row_length(self):
        self.assertEqual(len(self.expr.c_row), len(SINGLE_MASS_STATES))

    def test_c_row_values(self):
        # x_mass is at index 0 → C[0]=1, C[1]=0
        self.assertAlmostEqual(self.expr.c_row[0], 1.0)
        self.assertAlmostEqual(self.expr.c_row[1], 0.0)

    def test_d_row_all_zeros(self):
        self.assertTrue(all(v == 0.0 for v in self.expr.d_row))

    def test_d_row_length(self):
        self.assertEqual(len(self.expr.d_row), len(SINGLE_MASS_INPUTS))

    def test_contributing_state_indices(self):
        self.assertEqual(self.expr.contributing_state_indices, (0,))

    def test_contributing_state_names(self):
        self.assertEqual(self.expr.contributing_state_names, ("x_mass",))

    def test_provenance_non_empty(self):
        self.assertGreater(len(self.expr.provenance), 0)


# ---------------------------------------------------------------------------
# Absolute velocity
# ---------------------------------------------------------------------------

class TestAbsoluteVelocity(unittest.TestCase):

    def setUp(self):
        self.ode = _ode(SINGLE_MASS_STATES, SINGLE_MASS_INPUTS)
        self.probe = _BaseProbeStub("body_vel", "Body velocity", "velocity", "mass")
        self.expr = OutputMapper().map(self.probe, self.ode)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "velocity")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.STATE_DIRECT)

    def test_c_row_targets_v_state(self):
        # v_mass is at index 1 → C[0]=0, C[1]=1
        self.assertAlmostEqual(self.expr.c_row[0], 0.0)
        self.assertAlmostEqual(self.expr.c_row[1], 1.0)

    def test_contributing_state_names(self):
        self.assertEqual(self.expr.contributing_state_names, ("v_mass",))


# ---------------------------------------------------------------------------
# Relative displacement (two DOFs)
# ---------------------------------------------------------------------------

QUARTER_STATES = ["x_body_mass", "x_wheel_mass", "v_body_mass", "v_wheel_mass"]
QUARTER_INPUTS = ["u_road_source", "u_body_force"]


class TestRelativeDisplacement(unittest.TestCase):

    def setUp(self):
        self.ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        self.probe = _RelativeProbeStub(
            "susp_defl", "Suspension deflection", "displacement",
            "body_mass", "wheel_mass"
        )
        self.expr = OutputMapper().map(self.probe, self.ode)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "relative_displacement")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.STATE_RELATIVE)

    def test_c_row_length(self):
        self.assertEqual(len(self.expr.c_row), len(QUARTER_STATES))

    def test_c_row_target_plus_one(self):
        # x_body_mass at index 0 → C[0] = +1
        self.assertAlmostEqual(self.expr.c_row[0], 1.0)

    def test_c_row_reference_minus_one(self):
        # x_wheel_mass at index 1 → C[1] = -1
        self.assertAlmostEqual(self.expr.c_row[1], -1.0)

    def test_c_row_velocity_indices_zero(self):
        self.assertAlmostEqual(self.expr.c_row[2], 0.0)
        self.assertAlmostEqual(self.expr.c_row[3], 0.0)

    def test_d_row_all_zeros(self):
        self.assertEqual(len(self.expr.d_row), len(QUARTER_INPUTS))
        self.assertTrue(all(v == 0.0 for v in self.expr.d_row))

    def test_contributing_two_states(self):
        self.assertEqual(len(self.expr.contributing_state_indices), 2)
        self.assertIn("x_body_mass", self.expr.contributing_state_names)
        self.assertIn("x_wheel_mass", self.expr.contributing_state_names)


# ---------------------------------------------------------------------------
# Relative velocity
# ---------------------------------------------------------------------------

class TestRelativeVelocity(unittest.TestCase):

    def setUp(self):
        self.ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        self.probe = _RelativeProbeStub(
            "susp_vel", "Relative velocity", "velocity",
            "body_mass", "wheel_mass"
        )
        self.expr = OutputMapper().map(self.probe, self.ode)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "relative_velocity")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.STATE_RELATIVE)

    def test_c_row_body_velocity(self):
        # v_body_mass at index 2
        self.assertAlmostEqual(self.expr.c_row[2], 1.0)

    def test_c_row_wheel_velocity(self):
        # v_wheel_mass at index 3
        self.assertAlmostEqual(self.expr.c_row[3], -1.0)

    def test_displacement_indices_zero(self):
        self.assertAlmostEqual(self.expr.c_row[0], 0.0)
        self.assertAlmostEqual(self.expr.c_row[1], 0.0)


# ---------------------------------------------------------------------------
# Acceleration output (Wave 3A — DERIVED_DYNAMIC)
# ---------------------------------------------------------------------------

class TestAccelerationOutput(unittest.TestCase):
    """Acceleration: ÿ = A[vel_idx]·x + B[vel_idx]·u — now supported."""

    def setUp(self):
        # m=2, k=10, d=3  →  A=[[0,1],[-5,-1.5]],  B=[[0],[0.5]]
        self.ode = _ode_physical(m=2.0, k=10.0, d=3.0)
        self.probe = _BaseProbeStub("acc", "Acceleration", "acceleration", "mass")
        self.expr = OutputMapper().map(self.probe, self.ode)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_unsupported_reason_none(self):
        self.assertIsNone(self.expr.unsupported_reason)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "acceleration")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.DERIVED_DYNAMIC)

    def test_c_row_length(self):
        # c_row from A[vel_idx], length = n_states
        self.assertEqual(len(self.expr.c_row), 2)

    def test_c_row_from_a_row(self):
        # A[1] = [-k/m, -d/m] = [-5.0, -1.5]
        self.assertAlmostEqual(self.expr.c_row[0], -5.0, places=10)
        self.assertAlmostEqual(self.expr.c_row[1], -1.5, places=10)

    def test_d_row_from_b_row(self):
        # B[1] = [1/m] = [0.5]
        self.assertEqual(len(self.expr.d_row), 1)
        self.assertAlmostEqual(self.expr.d_row[0], 0.5, places=10)

    def test_contributing_state_names(self):
        # Both states contribute to acceleration (-5·x and -1.5·v)
        self.assertIn("x_mass", self.expr.contributing_state_names)
        self.assertIn("v_mass", self.expr.contributing_state_names)

    def test_provenance_non_empty(self):
        self.assertGreater(len(self.expr.provenance), 0)


class TestAccelerationUnsupportedNonDOF(unittest.TestCase):
    """Acceleration for a non-DOF target (e.g. road, ground) is unsupported."""

    def test_non_dof_target(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("acc", "Road acceleration", "acceleration", "road_source")
        expr = OutputMapper().map(probe, ode)
        self.assertFalse(expr.supported_for_tf)
        self.assertIsNotNone(expr.unsupported_reason)

    def test_c_row_all_zeros_for_non_dof(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("acc", "Road acceleration", "acceleration", "road_source")
        expr = OutputMapper().map(probe, ode)
        self.assertTrue(all(v == 0.0 for v in expr.c_row))

    def test_kind_unsupported(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("acc", "Road acceleration", "acceleration", "road_source")
        expr = OutputMapper().map(probe, ode)
        self.assertEqual(expr.kind, OutputKind.UNSUPPORTED)


# ---------------------------------------------------------------------------
# Force without graph — still unsupported
# ---------------------------------------------------------------------------

class TestForceWithoutGraph(unittest.TestCase):
    """Force output requires a graph; without one it is always unsupported."""

    def _map(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("frc", "Spring force", "force", "spring")
        return OutputMapper().map(probe, ode)  # no graph

    def test_not_supported(self):
        self.assertFalse(self._map().supported_for_tf)

    def test_c_row_all_zeros(self):
        expr = self._map()
        self.assertTrue(all(v == 0.0 for v in expr.c_row))

    def test_reason_mentions_graph(self):
        reason = self._map().unsupported_reason
        self.assertIsNotNone(reason)
        # Reason should mention that graph context is needed
        self.assertTrue(
            "graph" in reason.lower() or "Graph" in reason,
            f"Reason should mention graph: {reason!r}",
        )


# ---------------------------------------------------------------------------
# Spring force output (Wave 3A — DERIVED_ALGEBRAIC)
# ---------------------------------------------------------------------------

class TestSpringForceOutput(unittest.TestCase):
    """Spring force: F = k·x — supported when graph is provided."""

    @classmethod
    def setUpClass(cls):
        from tests.fixtures.graph_factories import build_single_mass_graph
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        from app.core.symbolic.symbolic_system import SymbolicSystem

        class _Stub(SymbolicSystem):
            pass

        cls.graph = build_single_mass_graph()
        cls.ode = PolymorphicDAEReducer().reduce(cls.graph, _Stub())
        cls.mapper = OutputMapper()

        probe = _BaseProbeStub("sp_force", "Spring force", "force", "spring")
        cls.expr = cls.mapper.map(probe, cls.ode, graph=cls.graph)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "spring_force")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.DERIVED_ALGEBRAIC)

    def test_c_row_length(self):
        self.assertEqual(len(self.expr.c_row), len(self.ode.state_variables))

    def test_c_row_x_mass_equals_k(self):
        # spring stiffness = 10.0; port_a → mass, port_b → ground
        # F = 10.0 · x_mass  →  C[x_mass] = +10.0
        x_idx = self.ode.state_variables.index("x_mass")
        self.assertAlmostEqual(self.expr.c_row[x_idx], 10.0, places=10)

    def test_c_row_velocity_zero(self):
        # Spring force depends only on displacement, not velocity
        v_idx = self.ode.state_variables.index("v_mass")
        self.assertAlmostEqual(self.expr.c_row[v_idx], 0.0, places=10)

    def test_d_row_all_zeros(self):
        # Spring is DERIVED_ALGEBRAIC — no direct feedthrough
        self.assertTrue(all(v == 0.0 for v in self.expr.d_row))

    def test_contributing_state_names(self):
        self.assertIn("x_mass", self.expr.contributing_state_names)

    def test_provenance_non_empty(self):
        self.assertGreater(len(self.expr.provenance), 0)


# ---------------------------------------------------------------------------
# Damper force output (Wave 3A — DERIVED_ALGEBRAIC)
# ---------------------------------------------------------------------------

class TestDamperForceOutput(unittest.TestCase):
    """Damper force: F = d·v — supported when graph is provided."""

    @classmethod
    def setUpClass(cls):
        from tests.fixtures.graph_factories import build_single_mass_graph
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        from app.core.symbolic.symbolic_system import SymbolicSystem

        class _Stub(SymbolicSystem):
            pass

        cls.graph = build_single_mass_graph()
        cls.ode = PolymorphicDAEReducer().reduce(cls.graph, _Stub())
        cls.mapper = OutputMapper()

        probe = _BaseProbeStub("dm_force", "Damper force", "damper_force", "damper")
        cls.expr = cls.mapper.map(probe, cls.ode, graph=cls.graph)

    def test_supported(self):
        self.assertTrue(self.expr.supported_for_tf)

    def test_quantity_type(self):
        self.assertEqual(self.expr.quantity_type, "damper_force")

    def test_kind(self):
        self.assertEqual(self.expr.kind, OutputKind.DERIVED_ALGEBRAIC)

    def test_c_row_v_mass_equals_d(self):
        # damper d = 3.0; port_a → mass, port_b → ground
        # F = 3.0 · v_mass  →  C[v_mass] = +3.0
        v_idx = self.ode.state_variables.index("v_mass")
        self.assertAlmostEqual(self.expr.c_row[v_idx], 3.0, places=10)

    def test_c_row_displacement_zero(self):
        # Damper force depends only on velocity
        x_idx = self.ode.state_variables.index("x_mass")
        self.assertAlmostEqual(self.expr.c_row[x_idx], 0.0, places=10)

    def test_d_row_all_zeros(self):
        self.assertTrue(all(v == 0.0 for v in self.expr.d_row))


# ---------------------------------------------------------------------------
# Force: target component not a spring/damper
# ---------------------------------------------------------------------------

class TestForceInvalidTarget(unittest.TestCase):
    """Force probe targeting a mass (no stiffness/damping) is unsupported."""

    def test_mass_target_unsupported(self):
        from tests.fixtures.graph_factories import build_single_mass_graph
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer
        from app.core.symbolic.symbolic_system import SymbolicSystem

        class _Stub(SymbolicSystem):
            pass

        graph = build_single_mass_graph()
        ode = PolymorphicDAEReducer().reduce(graph, _Stub())

        probe = _BaseProbeStub("frc", "Mass force", "force", "mass")
        expr = OutputMapper().map(probe, ode, graph=graph)
        self.assertFalse(expr.supported_for_tf)
        self.assertTrue(all(v == 0.0 for v in expr.c_row))


# ---------------------------------------------------------------------------
# Unsupported: unknown quantity
# ---------------------------------------------------------------------------

class TestUnsupportedUnknownQuantity(unittest.TestCase):

    def test_unknown_quantity_not_supported(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("q", "Q", "torque", "mass")
        expr = OutputMapper().map(probe, ode)
        self.assertFalse(expr.supported_for_tf)
        self.assertIn("torque", expr.unsupported_reason)

    def test_empty_quantity_not_supported(self):
        ode = _ode(SINGLE_MASS_STATES)
        probe = _BaseProbeStub("q", "Q", "", "mass")
        expr = OutputMapper().map(probe, ode)
        self.assertFalse(expr.supported_for_tf)


# ---------------------------------------------------------------------------
# Unsupported: target not in state_variables (e.g. ground, source)
# ---------------------------------------------------------------------------

class TestUnsupportedTargetNotDOF(unittest.TestCase):

    def test_non_dof_target(self):
        ode = _ode(["x_mass", "v_mass"])
        probe = _BaseProbeStub("rd", "Road displacement", "displacement", "road_source")
        expr = OutputMapper().map(probe, ode)
        self.assertFalse(expr.supported_for_tf)
        self.assertIn("road_source", expr.unsupported_reason)

    def test_c_row_zero_for_non_dof_target(self):
        ode = _ode(["x_mass", "v_mass"])
        probe = _BaseProbeStub("rd", "Road displacement", "displacement", "ground")
        expr = OutputMapper().map(probe, ode)
        self.assertTrue(all(v == 0.0 for v in expr.c_row))


# ---------------------------------------------------------------------------
# Unsupported: reference is non-DOF (displacement source → D feedthrough)
# ---------------------------------------------------------------------------

class TestUnsupportedReferenceNotDOF(unittest.TestCase):

    def test_tire_deflection_relative_to_road(self):
        """Relative to road_source requires D ≠ 0 — Wave 3 scope."""
        ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        probe = _RelativeProbeStub(
            "tire_defl", "Tire deflection", "displacement",
            "wheel_mass", "road_source"
        )
        expr = OutputMapper().map(probe, ode)
        self.assertFalse(expr.supported_for_tf)
        self.assertIn("road_source", expr.unsupported_reason)

    def test_c_row_zero_when_reference_is_non_dof(self):
        ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        probe = _RelativeProbeStub(
            "tire_defl", "Tire deflection", "displacement",
            "wheel_mass", "road_source"
        )
        expr = OutputMapper().map(probe, ode)
        self.assertTrue(all(v == 0.0 for v in expr.c_row))

    def test_reason_mentions_direct_feedthrough(self):
        ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        probe = _RelativeProbeStub(
            "td", "T", "displacement", "wheel_mass", "road_source"
        )
        expr = OutputMapper().map(probe, ode)
        reason = expr.unsupported_reason.lower()
        self.assertTrue(
            "feedthrough" in reason or "wave 3" in reason or "d row" in reason,
            f"Reason should mention feedthrough or wave 3: {reason!r}",
        )


# ---------------------------------------------------------------------------
# Unsupported: no target_component_id
# ---------------------------------------------------------------------------

class TestUnsupportedNoTarget(unittest.TestCase):

    def test_no_target(self):
        ode = _ode(SINGLE_MASS_STATES)

        class _NoTargetProbe:
            id = "nt"
            name = "No target"
            quantity = "displacement"
            target_component_id = None
            reference_component_id = None

        expr = OutputMapper().map(_NoTargetProbe(), ode)
        self.assertFalse(expr.supported_for_tf)


# ---------------------------------------------------------------------------
# Honesty guarantee: supported_for_tf=False always means C row is zero
# ---------------------------------------------------------------------------

class TestHonestyGuarantee(unittest.TestCase):
    """When supported_for_tf=False, c_row must be all zeros."""

    _UNSUPPORTED_PROBES = [
        # acceleration with wrong target (not a DOF in QUARTER_STATES → unsupported)
        _BaseProbeStub("a", "A", "acceleration", "mass"),
        # force without graph → unsupported
        _BaseProbeStub("f", "F", "force", "mass"),
        _BaseProbeStub("u", "U", "unknown_qty", "mass"),
        _BaseProbeStub("nd", "ND", "displacement", "road_source"),
        _RelativeProbeStub("rd", "RD", "displacement", "wheel_mass", "road_source"),
    ]

    def test_all_unsupported_have_zero_c_row(self):
        ode = _ode(QUARTER_STATES, QUARTER_INPUTS)
        mapper = OutputMapper()
        for probe in self._UNSUPPORTED_PROBES:
            with self.subTest(probe_id=probe.id):
                expr = mapper.map(probe, ode)
                if not expr.supported_for_tf:
                    self.assertTrue(
                        all(v == 0.0 for v in expr.c_row),
                        f"Probe {probe.id}: supported=False but c_row non-zero: {expr.c_row}",
                    )


# ---------------------------------------------------------------------------
# Stateless mapper: same instance, multiple probes / ODE systems
# ---------------------------------------------------------------------------

class TestMapperStateless(unittest.TestCase):

    def test_same_instance_multiple_calls(self):
        mapper = OutputMapper()
        ode = _ode(QUARTER_STATES, QUARTER_INPUTS)

        p1 = _BaseProbeStub("d1", "D1", "displacement", "body_mass")
        p2 = _BaseProbeStub("d2", "D2", "displacement", "wheel_mass")

        e1 = mapper.map(p1, ode)
        e2 = mapper.map(p2, ode)

        self.assertAlmostEqual(e1.c_row[0], 1.0)  # x_body_mass
        self.assertAlmostEqual(e2.c_row[1], 1.0)  # x_wheel_mass
        self.assertNotEqual(e1.c_row, e2.c_row)


# ---------------------------------------------------------------------------
# Quarter-car full probe set
# ---------------------------------------------------------------------------

class TestQuarterCarProbeSet(unittest.TestCase):
    """Map all probes from the quarter-car template against realistic ODE."""

    def setUp(self):
        from tests.fixtures.minimal_wheel_road import build_wheel_road_graph
        from app.core.symbolic.dae_reducer import DAEReducer
        from app.core.symbolic.equation_builder import EquationBuilder
        from app.core.symbolic.symbolic_system import SymbolicSystem

        self.graph = build_wheel_road_graph()

        # Build ReducedODESystem via workaround (sandbox EquationBuilder limitation)
        eb = EquationBuilder()
        comp_records = eb._build_component_records(self.graph)
        sv = ["x_body_mass", "v_body_mass", "x_wheel_mass", "v_wheel_mass"]
        iv = ["u_road_source", "u_body_force"]
        var_reg = eb._build_variable_registry(
            graph=self.graph, state_variables=sv, input_variables=iv, parameters={}
        )
        deriv_links = {
            v: rec["derivative_id"] for v, rec in var_reg.items()
            if rec.get("kind") == "state" and rec.get("derivative_id") is not None
        }
        sym = SymbolicSystem(
            state_variables=sv, input_variables=iv, output_definitions={},
            variable_registry=var_reg,
            metadata={"component_records": comp_records,
                      "derivative_links": deriv_links, "output_records": {}},
        )
        self.ode = DAEReducer().reduce(self.graph, sym)
        self.mapper = OutputMapper()
        self.probes = self.graph.probes

    def test_body_displacement_supported(self):
        expr = self.mapper.map(self.probes["body_displacement"], self.ode)
        self.assertTrue(expr.supported_for_tf)
        self.assertEqual(expr.quantity_type, "displacement")

    def test_wheel_displacement_supported(self):
        expr = self.mapper.map(self.probes["wheel_displacement"], self.ode)
        self.assertTrue(expr.supported_for_tf)
        self.assertEqual(expr.quantity_type, "displacement")

    def test_body_acceleration_supported(self):
        """Wave 3A: acceleration is now supported via c_row = A[vel_idx]."""
        expr = self.mapper.map(self.probes["body_acceleration"], self.ode)
        self.assertTrue(expr.supported_for_tf)
        self.assertEqual(expr.quantity_type, "acceleration")
        self.assertEqual(expr.kind, OutputKind.DERIVED_DYNAMIC)
        # d_row may be non-zero (acceleration has direct feedthrough from B)
        self.assertEqual(len(expr.c_row), len(self.ode.state_variables))

    def test_body_acceleration_c_row_from_a(self):
        """c_row for acceleration = row of first_order_a at vel_body_mass index."""
        expr = self.mapper.map(self.probes["body_acceleration"], self.ode)
        vel_idx = self.ode.state_variables.index("v_body_mass")
        for i, (cv, av) in enumerate(zip(expr.c_row, self.ode.first_order_a[vel_idx])):
            self.assertAlmostEqual(cv, float(av), places=10,
                msg=f"c_row[{i}] mismatch for body acceleration")

    def test_suspension_deflection_supported(self):
        expr = self.mapper.map(self.probes["suspension_deflection"], self.ode)
        self.assertTrue(expr.supported_for_tf)
        self.assertEqual(expr.quantity_type, "relative_displacement")
        self.assertEqual(len(expr.contributing_state_indices), 2)

    def test_suspension_force_without_graph_unsupported(self):
        """Without graph context, force probe is unsupported (graph=None default)."""
        expr = self.mapper.map(self.probes["suspension_force"], self.ode)
        self.assertFalse(expr.supported_for_tf)

    def test_suspension_force_with_graph_supported(self):
        """Wave 3A: force probe is supported when graph is passed.

        Suspension spring connects body_mass ↔ wheel_mass → two non-zero C entries.
        F = k·(x_body − x_wheel), k = 15000 N/m.
        """
        expr = self.mapper.map(
            self.probes["suspension_force"], self.ode, graph=self.graph
        )
        self.assertTrue(expr.supported_for_tf)
        self.assertEqual(expr.quantity_type, "spring_force")
        self.assertEqual(expr.kind, OutputKind.DERIVED_ALGEBRAIC)
        # Both ends have masses → two non-zero C entries (+k and -k)
        non_zero = [v for v in expr.c_row if v != 0.0]
        self.assertEqual(len(non_zero), 2)
        self.assertAlmostEqual(abs(non_zero[0]), 15000.0, places=5)  # k=15000 N/m
        self.assertAlmostEqual(abs(non_zero[1]), 15000.0, places=5)
        # Sum must be zero (symmetric Laplacian pattern)
        self.assertAlmostEqual(sum(expr.c_row), 0.0, places=10)

    def test_tire_deflection_not_supported(self):
        """Tire deflection ref = road_source (non-DOF) → D feedthrough → Wave 3+."""
        expr = self.mapper.map(self.probes["tire_deflection"], self.ode)
        self.assertFalse(expr.supported_for_tf)

    def test_body_displacement_c_row_shape(self):
        expr = self.mapper.map(self.probes["body_displacement"], self.ode)
        self.assertEqual(len(expr.c_row), len(self.ode.state_variables))

    def test_suspension_deflection_c_row_sums_to_zero(self):
        """C[body] = +1, C[wheel] = -1 → sum = 0."""
        expr = self.mapper.map(self.probes["suspension_deflection"], self.ode)
        self.assertAlmostEqual(sum(expr.c_row), 0.0)

    def test_provenance_always_present(self):
        for probe in self.probes.values():
            with self.subTest(probe_id=probe.id):
                expr = self.mapper.map(probe, self.ode)
                self.assertGreater(len(expr.provenance), 0)


if __name__ == "__main__":
    unittest.main()
