"""Faz 5MVP-1 — GenericStaticBackend integration tests.

Verifies that GenericStaticBackend.analyze() produces correct results
for all four fixture topologies:
  1. Single mass-spring-damper (1-DOF, mechanical)
  2. Two-mass system (2-DOF, mechanical)
  3. RLC series circuit (2-state, electrical)
  4. Wheel-road suspension (2-DOF, mechanical with road source)

Each test class checks:
  - State-space dimensions (n_states, n_inputs, n_outputs)
  - A/B matrix golden values (bit-for-bit with test_symbolic_pipeline.py)
  - Transfer function structural properties (order, poles, stability)
  - Convenience properties on StaticAnalysisResult
  - SISO shorthand (analyze_siso)
  - Error paths (AnalysisError)
"""
from __future__ import annotations

import unittest

import sympy

from app.services.static_analysis_backend import (
    AnalysisError,
    GenericStaticBackend,
    StaticAnalysisResult,
)
from app.core.symbolic.tf_builder import (
    TransferFunctionResult,
    UnsupportedTFResult,
)
from tests.fixtures.graph_factories import (
    build_single_mass_graph,
    build_two_mass_graph,
    build_rlc_circuit_graph,
)
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph


def _assert_matrix_close(test, left, right, places=7):
    """Helper: assert two 2-D matrices are element-wise close."""
    test.assertEqual(len(left), len(right), "Row count mismatch")
    for i, (lr, rr) in enumerate(zip(left, right)):
        test.assertEqual(len(lr), len(rr), f"Col count mismatch in row {i}")
        for j, (lv, rv) in enumerate(zip(lr, rr)):
            test.assertAlmostEqual(
                float(lv), float(rv), places=places,
                msg=f"Matrix[{i}][{j}]: {lv} != {rv}",
            )


# ---------------------------------------------------------------------------
# Single-mass tests
# ---------------------------------------------------------------------------

class TestSingleMassBackend(unittest.TestCase):
    """1-DOF: m=2, k=10, d=3, force input. States: [x_mass, v_mass]."""

    @classmethod
    def setUpClass(cls):
        cls.backend = GenericStaticBackend()
        cls.graph = build_single_mass_graph()
        cls.result = cls.backend.analyze(cls.graph)

    # --- Dimensions ---

    def test_n_states_is_2(self):
        self.assertEqual(self.result.n_states, 2)

    def test_n_inputs_is_1(self):
        self.assertEqual(self.result.n_inputs, 1)

    def test_n_outputs_matches_probes(self):
        self.assertEqual(self.result.n_outputs, len(self.graph.probes))

    # --- State-space golden values ---

    def test_a_matrix(self):
        expected_a = [
            [0.0, 1.0],
            [-5.0, -1.5],
        ]
        _assert_matrix_close(self, self.result.state_space.a_matrix, expected_a)

    def test_b_matrix(self):
        expected_b = [
            [0.0],
            [0.5],
        ]
        _assert_matrix_close(self, self.result.state_space.b_matrix, expected_b)

    # --- Transfer functions ---

    def test_has_transfer_functions(self):
        # At least the displacement probe should produce a supported TF
        supported = [tf for tf in self.result.transfer_functions
                     if isinstance(tf, TransferFunctionResult)]
        self.assertGreater(len(supported), 0)

    def test_displacement_tf_order_2(self):
        disp_tfs = [tf for tf in self.result.transfer_functions
                    if tf.output_id == "mass_displacement"]
        self.assertEqual(len(disp_tfs), 1)
        self.assertEqual(disp_tfs[0].order, 2)

    def test_displacement_tf_strictly_proper(self):
        disp_tf = next(tf for tf in self.result.transfer_functions
                       if tf.output_id == "mass_displacement")
        self.assertTrue(disp_tf.is_strictly_proper)

    def test_all_poles_stable(self):
        self.assertTrue(self.result.is_stable)

    def test_poles_count(self):
        # Deduplicated poles across all TFs — at least 2 from the 1-DOF system
        self.assertGreaterEqual(len(self.result.poles), 2)

    # --- Convenience ---

    def test_result_type(self):
        self.assertIsInstance(self.result, StaticAnalysisResult)

    # --- SISO shorthand ---

    def test_analyze_siso_displacement(self):
        tf = self.backend.analyze_siso(
            self.graph, "f_input_force_out", "mass_displacement",
        )
        self.assertIsInstance(tf, TransferFunctionResult)
        self.assertEqual(tf.order, 2)

    # --- Selected input ---

    def test_selected_input_id_filters(self):
        result = self.backend.analyze(
            self.graph, selected_input_id="input_force",
        )
        # Should resolve to f_input_force_out via prefix matching
        self.assertGreater(len(result.transfer_functions), 0)

    # --- Selected output ---

    def test_selected_output_id_filters(self):
        result = self.backend.analyze(
            self.graph, selected_output_id="mass_displacement",
        )
        # Only mass_displacement TFs
        for tf in result.transfer_functions:
            self.assertEqual(tf.output_id, "mass_displacement")


# ---------------------------------------------------------------------------
# Two-mass tests
# ---------------------------------------------------------------------------

class TestTwoMassBackend(unittest.TestCase):
    """2-DOF: m1=2, m2=1; k_g=20, d_g=5, k_c=8, d_c=2."""

    @classmethod
    def setUpClass(cls):
        cls.backend = GenericStaticBackend()
        cls.graph = build_two_mass_graph()
        cls.result = cls.backend.analyze(cls.graph)

    def test_n_states_is_4(self):
        self.assertEqual(self.result.n_states, 4)

    def test_n_inputs_is_1(self):
        self.assertEqual(self.result.n_inputs, 1)

    def test_a_matrix_golden(self):
        """A matrix from reference: ground spring+damper on mass_1,
        coupling spring+damper between mass_1 and mass_2.
        States: [x_mass_1, x_mass_2, v_mass_1, v_mass_2]
        """
        expected_a = [
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [-14.0, 4.0, -3.5, 1.0],
            [8.0, -8.0, 2.0, -2.0],
        ]
        _assert_matrix_close(self, self.result.state_space.a_matrix, expected_a)

    def test_b_matrix_golden(self):
        expected_b = [
            [0.0],
            [0.0],
            [0.5],
            [0.0],
        ]
        _assert_matrix_close(self, self.result.state_space.b_matrix, expected_b)

    def test_displacement_tf_order_4(self):
        disp_tfs = [tf for tf in self.result.transfer_functions
                    if tf.output_id == "mass_1_displacement"]
        self.assertEqual(len(disp_tfs), 1)
        self.assertEqual(disp_tfs[0].order, 4)

    def test_all_poles_stable(self):
        self.assertTrue(self.result.is_stable)

    def test_is_stable_property(self):
        for tf in self.result.transfer_functions:
            for pole in tf.poles:
                self.assertLess(float(sympy.re(pole)), 0.0)


# ---------------------------------------------------------------------------
# RLC circuit tests
# ---------------------------------------------------------------------------

class TestRLCBackend(unittest.TestCase):
    """RLC series: V=10, R=10, L=0.5, C=1e-3.

    Known limitation: PolymorphicDAEReducer only handles mechanical
    components' contribute_mass/stiffness/damping interface. Electrical
    components (R, L, C, VoltageSource) do NOT implement this interface
    yet, so the reducer produces trivially-zero A/B matrices with
    input_variables=['u_undefined'].

    These tests verify the backend handles this gracefully:
      - State-space dimensions are correct (inductor is inertial → 2 states)
      - No TFs are produced (is_stable is False because TF list is empty)
      - Input resolution for electrical sources fails predictably

    TODO(5MVP-electrical): Once electrical contribute_* is implemented,
    replace these with full golden-value tests like TestSingleMassBackend.
    """

    @classmethod
    def setUpClass(cls):
        cls.backend = GenericStaticBackend()
        cls.graph = build_rlc_circuit_graph()
        cls.result = cls.backend.analyze(cls.graph)

    def test_n_states_is_2(self):
        """Inductor is recognized as inertial → 2 states (x_inductor, v_inductor)."""
        self.assertEqual(self.result.n_states, 2)

    def test_n_inputs_is_1(self):
        """Falls back to u_undefined when no routes are found."""
        self.assertEqual(self.result.n_inputs, 1)
        self.assertIn("u_undefined", self.result.state_space.input_variables)

    def test_a_matrix_shape(self):
        a = self.result.state_space.a_matrix
        self.assertEqual(len(a), 2)
        self.assertEqual(len(a[0]), 2)

    def test_b_matrix_shape(self):
        b = self.result.state_space.b_matrix
        self.assertEqual(len(b), 2)
        self.assertEqual(len(b[0]), 1)

    def test_no_tfs_from_trivial_system(self):
        """With zero A/B matrices, TF builder produces zero TFs or all-unsupported."""
        # is_stable returns False when transfer_functions list is empty
        # (no poles to check → vacuously False by design)
        self.assertFalse(self.result.is_stable)

    def test_analyze_siso_v_source_raises(self):
        """VoltageSource input ID can't be resolved → AnalysisError."""
        with self.assertRaises(AnalysisError):
            self.backend.analyze_siso(
                self.graph, "v_source", "loop_current",
            )


# ---------------------------------------------------------------------------
# Wheel-road (quarter-car) tests
# ---------------------------------------------------------------------------

class TestWheelRoadBackend(unittest.TestCase):
    """2-DOF wheel-road: mb=300, mw=40, ks=15000, ds=1200, kt=180000."""

    @classmethod
    def setUpClass(cls):
        cls.backend = GenericStaticBackend()
        cls.graph = build_wheel_road_graph()
        cls.result = cls.backend.analyze(cls.graph)

    def test_n_states_is_4(self):
        self.assertEqual(self.result.n_states, 4)

    def test_displacement_tf_order_4(self):
        body_tfs = [tf for tf in self.result.transfer_functions
                    if tf.output_id == "body_displacement"]
        self.assertGreater(len(body_tfs), 0)
        self.assertEqual(body_tfs[0].order, 4)

    def test_all_poles_stable(self):
        self.assertTrue(self.result.is_stable)

    def test_body_displacement_tf_strictly_proper(self):
        body_tf = next(
            (tf for tf in self.result.transfer_functions
             if tf.output_id == "body_displacement"),
            None,
        )
        self.assertIsNotNone(body_tf)
        self.assertTrue(body_tf.is_strictly_proper)

    def test_unsupported_outputs_reported(self):
        """Tire deflection references a source → unsupported."""
        unsup_ids = {u.output_id for u in self.result.unsupported_outputs}
        # tire_deflection should be unsupported (references road_source, not a DOF)
        self.assertIn("tire_deflection", unsup_ids)

    def test_result_has_output_expressions(self):
        self.assertGreater(len(self.result.output_expressions), 0)


# ---------------------------------------------------------------------------
# Error path tests
# ---------------------------------------------------------------------------

class TestBackendErrors(unittest.TestCase):
    """AnalysisError paths."""

    def test_empty_graph_raises(self):
        """Graph with no components → no state variables → AnalysisError."""
        from app.core.graph.system_graph import SystemGraph
        backend = GenericStaticBackend()
        with self.assertRaises(AnalysisError):
            backend.analyze(SystemGraph())

    def test_graph_without_inertial_raises(self):
        """Graph with only ground and spring (no mass) → no state vars."""
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import MechanicalGround, Spring
        g = SystemGraph()
        g.add_component(MechanicalGround("g"))
        g.add_component(Spring("s", stiffness=10.0))
        g.connect("s.port_a", "g.port")
        g.connect("s.port_b", "g.port")
        backend = GenericStaticBackend()
        with self.assertRaises(AnalysisError):
            backend.analyze(g)

    def test_invalid_input_id_raises(self):
        graph = build_single_mass_graph()
        backend = GenericStaticBackend()
        with self.assertRaises(AnalysisError):
            backend.analyze(graph, selected_input_id="nonexistent_input")

    def test_invalid_probe_id_raises(self):
        graph = build_single_mass_graph()
        backend = GenericStaticBackend()
        with self.assertRaises(AnalysisError):
            backend.analyze(graph, selected_output_id="nonexistent_probe")

    def test_analyze_siso_no_result_raises(self):
        """analyze_siso with unsupported probe → AnalysisError or UnsupportedTFResult."""
        graph = build_wheel_road_graph()
        backend = GenericStaticBackend()
        # tire_deflection is unsupported → should return UnsupportedTFResult
        result = backend.analyze_siso(graph, "r_road_source", "tire_deflection")
        self.assertIsInstance(result, UnsupportedTFResult)


# ---------------------------------------------------------------------------
# Skip TF tests
# ---------------------------------------------------------------------------

class TestSkipTransferFunctions(unittest.TestCase):
    """build_transfer_functions=False skips TF computation."""

    def test_no_tfs_when_skipped(self):
        graph = build_single_mass_graph()
        backend = GenericStaticBackend()
        result = backend.analyze(graph, build_transfer_functions=False)
        self.assertEqual(len(result.transfer_functions), 0)
        self.assertEqual(len(result.unsupported_outputs), 0)
        # State-space should still be valid
        self.assertEqual(result.n_states, 2)

    def test_no_tfs_when_no_probes(self):
        """Graph without probes → no TFs even when build_transfer_functions=True."""
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce
        g = SystemGraph()
        m = g.add_component(Mass("m", mass=1.0))
        s = g.add_component(Spring("s", stiffness=10.0))
        d = g.add_component(Damper("d", damping=1.0))
        gnd = g.add_component(MechanicalGround("gnd"))
        src = g.add_component(StepForce("f", amplitude=1.0))
        g.connect(m.port("port_a").id, s.port("port_a").id)
        g.connect(s.port("port_b").id, gnd.port("port").id)
        g.connect(m.port("port_a").id, d.port("port_a").id)
        g.connect(d.port("port_b").id, gnd.port("port").id)
        g.connect(m.port("port_a").id, src.port("port").id)
        g.connect(m.port("reference_port").id, gnd.port("port").id)
        g.connect(src.port("reference_port").id, gnd.port("port").id)

        backend = GenericStaticBackend()
        result = backend.analyze(g)
        self.assertEqual(len(result.transfer_functions), 0)
        self.assertEqual(result.n_states, 2)


if __name__ == "__main__":
    unittest.main()
