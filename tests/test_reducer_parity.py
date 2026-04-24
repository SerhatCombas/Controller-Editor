"""Parity tests: DAEReducer (legacy) vs PolymorphicDAEReducer (Wave 1).

These tests run both reducers on identical system graphs and assert that their
M / D / K matrices and A / B first-order forms agree within numerical tolerance.

Important notes:
  - EquationBuilder's sympy parsing fails in this sandbox (pre-existing issue in
    sympy_adapter.py).  The parity test therefore constructs a minimal but
    correct SymbolicSystem using EquationBuilder's *non-parsing* helpers
    (_build_component_records, _build_variable_registry).  This is a
    test-infrastructure workaround — it does NOT affect production code.
  - Input variable *names* differ by design: legacy uses ``u_{id}`` convention,
    polymorphic uses SourceDescriptor.input_variable_name.  Only matrix values
    are compared for parity.
  - State variable *names* must match, because downstream consumers (e.g.
    StateSpaceBuilder) index them by name.
"""
from __future__ import annotations

import math
import unittest


TOLERANCE = 1e-9  # absolute tolerance for float comparison


def _approx_equal_matrix(a: list[list[float]], b: list[list[float]], tol: float = TOLERANCE) -> bool:
    if len(a) != len(b):
        return False
    for row_a, row_b in zip(a, b):
        if len(row_a) != len(row_b):
            return False
        for va, vb in zip(row_a, row_b):
            if math.isnan(va) or math.isnan(vb):
                return False
            if abs(va - vb) > tol:
                return False
    return True


def _build_symbolic_system_for_legacy(graph, state_variables: list[str], input_variables: list[str]):
    """Build a minimal SymbolicSystem for the legacy DAEReducer.

    Bypasses EquationBuilder.build() (which has a sympy parsing issue) and
    calls only the non-parsing helpers that the legacy reducer actually needs.
    """
    from app.core.symbolic.equation_builder import EquationBuilder
    from app.core.symbolic.symbolic_system import SymbolicSystem

    eb = EquationBuilder()
    component_records = eb._build_component_records(graph)
    variable_registry = eb._build_variable_registry(
        graph=graph,
        state_variables=state_variables,
        input_variables=input_variables,
        parameters={},
    )
    derivative_links = {
        v: rec["derivative_id"]
        for v, rec in variable_registry.items()
        if rec.get("kind") == "state" and rec.get("derivative_id") is not None
    }

    return SymbolicSystem(
        state_variables=state_variables,
        input_variables=input_variables,
        output_definitions={},
        variable_registry=variable_registry,
        metadata={
            "component_records": component_records,
            "derivative_links": derivative_links,
            "output_records": {},
        },
    )


def _build_empty_symbolic():
    from app.core.symbolic.symbolic_system import SymbolicSystem
    return SymbolicSystem(
        output_definitions={},
        metadata={"component_records": {}, "derivative_links": {}, "output_records": {}},
    )


# ---------------------------------------------------------------------------
# Single-mass parity
# ---------------------------------------------------------------------------

class TestSingleMassParity(unittest.TestCase):

    def _build_graph(self):
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce

        graph = SystemGraph()
        mass = graph.add_component(Mass("mass", mass=2.0))
        spring = graph.add_component(Spring("spring", stiffness=10.0))
        damper = graph.add_component(Damper("damper", damping=3.0))
        source = graph.add_component(StepForce("input_force", amplitude=1.0))
        ground = graph.add_component(MechanicalGround("ground"))

        graph.connect(mass.port("port_a").id, spring.port("port_a").id)
        graph.connect(mass.port("port_a").id, damper.port("port_a").id)
        graph.connect(mass.port("port_a").id, source.port("port").id)
        graph.connect(spring.port("port_b").id, ground.port("port").id)
        graph.connect(damper.port("port_b").id, ground.port("port").id)
        graph.connect(mass.port("reference_port").id, ground.port("port").id)
        graph.connect(source.port("reference_port").id, ground.port("port").id)

        return graph

    def _run_both(self):
        from app.core.symbolic.dae_reducer import DAEReducer
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer

        graph = self._build_graph()
        sym_legacy = _build_symbolic_system_for_legacy(
            graph,
            state_variables=["x_mass", "v_mass"],
            input_variables=["u_input_force"],
        )
        legacy = DAEReducer().reduce(graph, sym_legacy)
        poly = PolymorphicDAEReducer().reduce(graph, _build_empty_symbolic())
        return legacy, poly

    def test_mass_matrix_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.mass_matrix, poly.mass_matrix),
            f"Mass matrix mismatch:\n  legacy: {legacy.mass_matrix}\n  poly:   {poly.mass_matrix}",
        )

    def test_damping_matrix_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.damping_matrix, poly.damping_matrix),
            f"Damping matrix mismatch:\n  legacy: {legacy.damping_matrix}\n  poly:   {poly.damping_matrix}",
        )

    def test_stiffness_matrix_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.stiffness_matrix, poly.stiffness_matrix),
            f"Stiffness matrix mismatch:\n  legacy: {legacy.stiffness_matrix}\n  poly:   {poly.stiffness_matrix}",
        )

    def test_input_matrix_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.input_matrix, poly.input_matrix),
            f"Input matrix mismatch:\n  legacy: {legacy.input_matrix}\n  poly:   {poly.input_matrix}",
        )

    def test_first_order_a_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.first_order_a, poly.first_order_a),
            f"A matrix mismatch:\n  legacy: {legacy.first_order_a}\n  poly:   {poly.first_order_a}",
        )

    def test_first_order_b_parity(self):
        legacy, poly = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.first_order_b, poly.first_order_b),
            f"B matrix mismatch:\n  legacy: {legacy.first_order_b}\n  poly:   {poly.first_order_b}",
        )

    def test_state_variable_names_match(self):
        legacy, poly = self._run_both()
        self.assertEqual(
            legacy.state_variables,
            poly.state_variables,
            f"State variable names differ:\n  legacy: {legacy.state_variables}\n  poly:   {poly.state_variables}",
        )

    def test_node_order_length_matches(self):
        legacy, poly = self._run_both()
        self.assertEqual(len(legacy.node_order), len(poly.node_order))

    def test_matrix_values_exact_single_mass(self):
        """Spot-check exact numeric values for the known single-mass system."""
        legacy, poly = self._run_both()
        self.assertAlmostEqual(poly.mass_matrix[0][0], 2.0)
        self.assertAlmostEqual(poly.damping_matrix[0][0], 3.0)
        self.assertAlmostEqual(poly.stiffness_matrix[0][0], 10.0)
        self.assertAlmostEqual(poly.input_matrix[0][0], 1.0)
        # A = [[0, 1], [-k/m, -d/m]] = [[0,1],[-5,-1.5]]
        self.assertAlmostEqual(poly.first_order_a[0][0], 0.0)
        self.assertAlmostEqual(poly.first_order_a[0][1], 1.0)
        self.assertAlmostEqual(poly.first_order_a[1][0], -5.0)   # -K/M
        self.assertAlmostEqual(poly.first_order_a[1][1], -1.5)   # -D/M


# ---------------------------------------------------------------------------
# Two-mass coupled system parity
# ---------------------------------------------------------------------------

class TestTwoMassParity(unittest.TestCase):

    def _build_graph(self):
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce

        graph = SystemGraph()
        m1 = graph.add_component(Mass("m1", mass=1.0))
        m2 = graph.add_component(Mass("m2", mass=2.0))
        k1 = graph.add_component(Spring("k1", stiffness=100.0))
        k2 = graph.add_component(Spring("k2", stiffness=200.0))
        d1 = graph.add_component(Damper("d1", damping=5.0))
        src = graph.add_component(StepForce("f_in", amplitude=1.0))
        gnd = graph.add_component(MechanicalGround("ground"))

        # m1 connects to k1 (to ground) and k2 (to m2)
        # m2 connects to k2, d1 (to ground), and force source
        graph.connect(m1.port("port_a").id, k1.port("port_a").id)
        graph.connect(m1.port("port_a").id, k2.port("port_a").id)
        graph.connect(m2.port("port_a").id, k2.port("port_b").id)
        graph.connect(m2.port("port_a").id, d1.port("port_a").id)
        graph.connect(m2.port("port_a").id, src.port("port").id)
        graph.connect(k1.port("port_b").id, gnd.port("port").id)
        graph.connect(d1.port("port_b").id, gnd.port("port").id)
        graph.connect(m1.port("reference_port").id, gnd.port("port").id)
        graph.connect(m2.port("reference_port").id, gnd.port("port").id)
        graph.connect(src.port("reference_port").id, gnd.port("port").id)

        return graph

    def _run_both(self):
        from app.core.symbolic.dae_reducer import DAEReducer
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer

        graph = self._build_graph()
        sym_legacy = _build_symbolic_system_for_legacy(
            graph,
            state_variables=["x_m1", "x_m2", "v_m1", "v_m2"],
            input_variables=["u_f_in"],
        )
        legacy = DAEReducer().reduce(graph, sym_legacy)
        poly = PolymorphicDAEReducer().reduce(graph, _build_empty_symbolic())
        return legacy, poly, graph

    def test_dof_count_matches(self):
        legacy, poly, _ = self._run_both()
        self.assertEqual(len(legacy.node_order), len(poly.node_order))
        self.assertEqual(len(legacy.node_order), 2)

    def test_mass_matrix_parity(self):
        legacy, poly, _ = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.mass_matrix, poly.mass_matrix),
            f"Two-mass M mismatch:\n  legacy: {legacy.mass_matrix}\n  poly:   {poly.mass_matrix}",
        )

    def test_stiffness_matrix_parity(self):
        legacy, poly, _ = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.stiffness_matrix, poly.stiffness_matrix),
            f"Two-mass K mismatch:\n  legacy: {legacy.stiffness_matrix}\n  poly:   {poly.stiffness_matrix}",
        )

    def test_damping_matrix_parity(self):
        legacy, poly, _ = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.damping_matrix, poly.damping_matrix),
            f"Two-mass D mismatch:\n  legacy: {legacy.damping_matrix}\n  poly:   {poly.damping_matrix}",
        )

    def test_first_order_a_parity(self):
        legacy, poly, _ = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.first_order_a, poly.first_order_a),
            f"Two-mass A mismatch:\n  legacy: {legacy.first_order_a}\n  poly:   {poly.first_order_a}",
        )

    def test_first_order_b_parity(self):
        legacy, poly, _ = self._run_both()
        self.assertTrue(
            _approx_equal_matrix(legacy.first_order_b, poly.first_order_b),
            f"Two-mass B mismatch:\n  legacy: {legacy.first_order_b}\n  poly:   {poly.first_order_b}",
        )

    def test_state_variables_match(self):
        legacy, poly, _ = self._run_both()
        self.assertEqual(
            sorted(legacy.state_variables),
            sorted(poly.state_variables),
            "Two-mass state variable names diverged",
        )

    def test_coupling_stiffness_symmetric(self):
        """K[i,j] == K[j,i] for the coupled spring — symmetric system."""
        _, poly, _ = self._run_both()
        K = poly.stiffness_matrix
        self.assertAlmostEqual(K[0][1], K[1][0], places=9)

    def test_k2_coupling_value(self):
        """k2=200 coupling: K[i,j] = K[j,i] = -200."""
        _, poly, _ = self._run_both()
        K = poly.stiffness_matrix
        self.assertAlmostEqual(K[0][1], -200.0, places=6)


# ---------------------------------------------------------------------------
# Parametric sweep parity: vary mass, stiffness, damping
# ---------------------------------------------------------------------------

class TestParametricParity(unittest.TestCase):
    """Run single-mass parity across several parameter combinations."""

    CASES = [
        {"mass": 1.0, "stiffness": 1.0, "damping": 0.1},
        {"mass": 5.0, "stiffness": 50.0, "damping": 10.0},
        {"mass": 0.5, "stiffness": 1000.0, "damping": 0.01},
        {"mass": 100.0, "stiffness": 100.0, "damping": 100.0},
    ]

    def _run_case(self, mass, stiffness, damping):
        from app.core.graph.system_graph import SystemGraph
        from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
        from app.core.models.sources import StepForce
        from app.core.symbolic.dae_reducer import DAEReducer
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer

        graph = SystemGraph()
        m = graph.add_component(Mass("mass", mass=mass))
        k = graph.add_component(Spring("spring", stiffness=stiffness))
        d = graph.add_component(Damper("damper", damping=damping))
        src = graph.add_component(StepForce("force", amplitude=1.0))
        gnd = graph.add_component(MechanicalGround("ground"))

        graph.connect(m.port("port_a").id, k.port("port_a").id)
        graph.connect(m.port("port_a").id, d.port("port_a").id)
        graph.connect(m.port("port_a").id, src.port("port").id)
        graph.connect(k.port("port_b").id, gnd.port("port").id)
        graph.connect(d.port("port_b").id, gnd.port("port").id)
        graph.connect(m.port("reference_port").id, gnd.port("port").id)
        graph.connect(src.port("reference_port").id, gnd.port("port").id)

        sym = _build_symbolic_system_for_legacy(
            graph, ["x_mass", "v_mass"], ["u_force"]
        )
        legacy = DAEReducer().reduce(graph, sym)
        poly = PolymorphicDAEReducer().reduce(graph, _build_empty_symbolic())
        return legacy, poly

    def test_all_cases_m_d_k_a_b_match(self):
        for params in self.CASES:
            with self.subTest(**params):
                legacy, poly = self._run_case(**params)
                for name, lm, pm in [
                    ("M", legacy.mass_matrix, poly.mass_matrix),
                    ("D", legacy.damping_matrix, poly.damping_matrix),
                    ("K", legacy.stiffness_matrix, poly.stiffness_matrix),
                    ("B", legacy.input_matrix, poly.input_matrix),
                    ("A", legacy.first_order_a, poly.first_order_a),
                    ("b", legacy.first_order_b, poly.first_order_b),
                ]:
                    self.assertTrue(
                        _approx_equal_matrix(lm, pm),
                        f"Params {params}: {name} matrix mismatch\n  legacy: {lm}\n  poly: {pm}",
                    )


if __name__ == "__main__":
    unittest.main()
