"""Tests for Wave 1 component-level polymorphic override methods.

Verifies that Mass, Spring, Damper, Wheel, StepForce, and RandomRoad correctly
implement the Wave 1 interface without altering existing behaviour.

All tests are purely additive — no legacy code paths are touched.
"""
from __future__ import annotations

import unittest
import sympy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node_index(*node_ids: str) -> dict[str, int]:
    """Build a simple {node_id: DOF_index} mapping from the given ids."""
    return {nid: idx for idx, nid in enumerate(node_ids)}


# ---------------------------------------------------------------------------
# Mass
# ---------------------------------------------------------------------------

class TestMassOverrides(unittest.TestCase):

    def _make(self, mass: float = 10.0) -> object:
        from app.core.models.mechanical.mass import Mass
        m = Mass("mass_1", mass=mass)
        # Wire port_a to a node so we can test contribute_mass
        m.port("port_a").connect_to("node_a")
        return m

    def test_get_state_contribution_inertial(self):
        from app.core.base.state_contribution import StateContribution
        m = self._make()
        sc = m.get_state_contribution()
        self.assertIsInstance(sc, StateContribution)
        self.assertTrue(sc.stores_inertial_energy)
        self.assertFalse(sc.stores_potential_energy)
        self.assertEqual(sc.state_kind, "inertial")
        self.assertEqual(sc.dof_count, 1)
        self.assertEqual(sc.owning_port_name, "port_a")

    def test_contribute_mass_single_entry(self):
        from app.core.base.contribution import MatrixContribution
        m = self._make()
        ni = _node_index("node_a")
        contribs = m.contribute_mass(ni)
        self.assertEqual(len(contribs), 1)
        c = contribs[0]
        self.assertIsInstance(c, MatrixContribution)
        self.assertEqual(c.row, 0)
        self.assertEqual(c.col, 0)
        self.assertEqual(c.contribution_kind, "mass")
        self.assertEqual(c.component_id, "mass_1")
        self.assertIn("node_a", c.connected_node_ids)
        self.assertEqual(c.value, sympy.Symbol("m_mass_1"))

    def test_contribute_mass_port_not_connected(self):
        from app.core.models.mechanical.mass import Mass
        m = Mass("mass_2", mass=5.0)  # port_a NOT connected
        contribs = m.contribute_mass({"node_a": 0})
        self.assertEqual(contribs, [])

    def test_contribute_mass_port_not_in_node_index(self):
        """Port connected to a ground node that's not in node_index → no entry."""
        from app.core.models.mechanical.mass import Mass
        m = Mass("mass_3", mass=5.0)
        m.port("port_a").connect_to("ground_node")
        contribs = m.contribute_mass({"node_a": 0})  # ground_node absent
        self.assertEqual(contribs, [])

    def test_contribute_damping_empty(self):
        """Mass does not contribute to damping matrix."""
        m = self._make()
        self.assertEqual(m.contribute_damping(_node_index("node_a")), [])

    def test_contribute_stiffness_empty(self):
        """Mass does not contribute to stiffness matrix."""
        m = self._make()
        self.assertEqual(m.contribute_stiffness(_node_index("node_a")), [])

    def test_linearity_profile_lti(self):
        from app.core.base.linearity import LinearityProfile
        m = self._make()
        lp = m.linearity_profile()
        self.assertIsInstance(lp, LinearityProfile)
        self.assertTrue(lp.is_lti)

    def test_existing_interface_unchanged(self):
        """Regression: existing Mass methods still work as before."""
        m = self._make(mass=5.0)
        self.assertIn("x_mass_1", m.get_states())
        self.assertIn("v_mass_1", m.get_states())
        eqs = m.constitutive_equations()
        self.assertTrue(any("5.0" in eq for eq in eqs))


# ---------------------------------------------------------------------------
# Wheel (inherits from Mass — override inherited automatically)
# ---------------------------------------------------------------------------

class TestWheelOverrides(unittest.TestCase):

    def _make(self) -> object:
        from app.core.models.mechanical.wheel import Wheel
        w = Wheel("wheel_1", mass=15.0, radius=0.32)
        w.port("port_a").connect_to("node_w")
        return w

    def test_get_state_contribution_inertial_inherited(self):
        """Wheel inherits Mass.get_state_contribution — must be inertial."""
        w = self._make()
        sc = w.get_state_contribution()
        self.assertTrue(sc.stores_inertial_energy)
        self.assertEqual(sc.state_kind, "inertial")

    def test_contribute_mass_inherited(self):
        """Wheel inherits Mass.contribute_mass."""
        from app.core.base.contribution import MatrixContribution
        w = self._make()
        contribs = w.contribute_mass(_node_index("node_w"))
        self.assertEqual(len(contribs), 1)
        c = contribs[0]
        self.assertEqual(c.contribution_kind, "mass")
        self.assertEqual(c.value, sympy.Symbol("m_wheel_1"))

    def test_radius_parameter_preserved(self):
        w = self._make()
        self.assertAlmostEqual(w.parameters["radius"], 0.32)


# ---------------------------------------------------------------------------
# Spring
# ---------------------------------------------------------------------------

class TestSpringOverrides(unittest.TestCase):

    def _make(self, k: float = 1000.0) -> object:
        from app.core.models.mechanical.spring import Spring
        s = Spring("spring_1", stiffness=k)
        s.port("port_a").connect_to("node_a")
        s.port("port_b").connect_to("node_b")
        return s

    def test_get_state_contribution_potential(self):
        from app.core.base.state_contribution import StateContribution
        s = self._make()
        sc = s.get_state_contribution()
        self.assertIsInstance(sc, StateContribution)
        self.assertFalse(sc.stores_inertial_energy)
        self.assertTrue(sc.stores_potential_energy)
        self.assertEqual(sc.state_kind, "potential")

    def test_contribute_stiffness_two_active_nodes_four_entries(self):
        """Between two active DOFs: 4 Laplacian entries."""
        from app.core.base.contribution import MatrixContribution
        s = self._make()
        ni = _node_index("node_a", "node_b")
        contribs = s.contribute_stiffness(ni)
        self.assertEqual(len(contribs), 4)

        kinds = {(c.row, c.col): c.value for c in contribs}
        k_sym = sympy.Symbol("k_spring_1")
        self.assertEqual(kinds[(0, 0)], k_sym)   # K[i,i] += k
        self.assertEqual(kinds[(1, 1)], k_sym)   # K[j,j] += k
        self.assertEqual(kinds[(0, 1)], -k_sym)  # K[i,j] -= k
        self.assertEqual(kinds[(1, 0)], -k_sym)  # K[j,i] -= k

    def test_contribute_stiffness_ground_port_b_two_entries(self):
        """When port_b is ground (not in node_index): only 1 diagonal entry."""
        from app.core.models.mechanical.spring import Spring
        s = Spring("spring_2", stiffness=500.0)
        s.port("port_a").connect_to("node_a")
        s.port("port_b").connect_to("ground")  # ground not in node_index
        ni = _node_index("node_a")
        contribs = s.contribute_stiffness(ni)
        self.assertEqual(len(contribs), 1)
        self.assertEqual(contribs[0].row, 0)
        self.assertEqual(contribs[0].col, 0)

    def test_contribute_stiffness_neither_connected(self):
        """Both ports unconnected → no entries."""
        from app.core.models.mechanical.spring import Spring
        s = Spring("spring_3", stiffness=200.0)
        contribs = s.contribute_stiffness({})
        self.assertEqual(contribs, [])

    def test_contribute_stiffness_all_have_provenance(self):
        s = self._make()
        ni = _node_index("node_a", "node_b")
        for c in s.contribute_stiffness(ni):
            self.assertEqual(c.component_id, "spring_1")
            self.assertEqual(c.contribution_kind, "stiffness")
            self.assertIn("spring_1", c.equation_reference)

    def test_contribute_mass_empty(self):
        s = self._make()
        self.assertEqual(s.contribute_mass(_node_index("node_a", "node_b")), [])

    def test_contribute_damping_empty(self):
        s = self._make()
        self.assertEqual(s.contribute_damping(_node_index("node_a", "node_b")), [])

    def test_existing_interface_unchanged(self):
        s = self._make(k=200.0)
        eqs = s.constitutive_equations()
        self.assertTrue(any("200.0" in eq for eq in eqs))


# ---------------------------------------------------------------------------
# Damper
# ---------------------------------------------------------------------------

class TestDamperOverrides(unittest.TestCase):

    def _make(self, d: float = 100.0) -> object:
        from app.core.models.mechanical.damper import Damper
        comp = Damper("damper_1", damping=d)
        comp.port("port_a").connect_to("node_a")
        comp.port("port_b").connect_to("node_b")
        return comp

    def test_get_state_contribution_none(self):
        """Damper is dissipative — no energy storage state."""
        comp = self._make()
        self.assertIsNone(comp.get_state_contribution())

    def test_contribute_damping_two_active_nodes_four_entries(self):
        from app.core.base.contribution import MatrixContribution
        comp = self._make()
        ni = _node_index("node_a", "node_b")
        contribs = comp.contribute_damping(ni)
        self.assertEqual(len(contribs), 4)

        kinds = {(c.row, c.col): c.value for c in contribs}
        d_sym = sympy.Symbol("d_damper_1")
        self.assertEqual(kinds[(0, 0)], d_sym)
        self.assertEqual(kinds[(1, 1)], d_sym)
        self.assertEqual(kinds[(0, 1)], -d_sym)
        self.assertEqual(kinds[(1, 0)], -d_sym)

    def test_contribute_damping_ground_port_b_one_entry(self):
        from app.core.models.mechanical.damper import Damper
        comp = Damper("damper_2", damping=50.0)
        comp.port("port_a").connect_to("node_a")
        comp.port("port_b").connect_to("ground")
        ni = _node_index("node_a")
        contribs = comp.contribute_damping(ni)
        self.assertEqual(len(contribs), 1)
        self.assertEqual(contribs[0].row, 0)
        self.assertEqual(contribs[0].col, 0)

    def test_contribute_damping_provenance(self):
        comp = self._make()
        ni = _node_index("node_a", "node_b")
        for c in comp.contribute_damping(ni):
            self.assertEqual(c.component_id, "damper_1")
            self.assertEqual(c.contribution_kind, "damping")

    def test_contribute_mass_empty(self):
        comp = self._make()
        self.assertEqual(comp.contribute_mass(_node_index("node_a", "node_b")), [])

    def test_contribute_stiffness_empty(self):
        comp = self._make()
        self.assertEqual(comp.contribute_stiffness(_node_index("node_a", "node_b")), [])

    def test_existing_interface_unchanged(self):
        comp = self._make(d=50.0)
        eqs = comp.constitutive_equations()
        self.assertTrue(any("50.0" in eq for eq in eqs))


# ---------------------------------------------------------------------------
# StepForce
# ---------------------------------------------------------------------------

class TestStepForceOverrides(unittest.TestCase):

    def _make(self) -> object:
        from app.core.models.sources.step_force import StepForce
        return StepForce("sf_1", amplitude=100.0, start_time=0.5)

    def test_get_source_descriptor_force_kind(self):
        from app.core.base.source_descriptor import SourceDescriptor
        sf = self._make()
        sd = sf.get_source_descriptor()
        self.assertIsInstance(sd, SourceDescriptor)
        self.assertEqual(sd.kind, "force")

    def test_get_source_descriptor_ports(self):
        sf = self._make()
        sd = sf.get_source_descriptor()
        self.assertEqual(sd.driven_port_name, "port")
        self.assertEqual(sd.reference_port_name, "reference_port")

    def test_get_source_descriptor_variables(self):
        sf = self._make()
        sd = sf.get_source_descriptor()
        self.assertEqual(sd.input_variable_name, "f_sf_1_out")
        self.assertEqual(sd.amplitude_parameter, "amplitude")

    def test_get_state_contribution_none(self):
        """Source component carries no inertial or potential state."""
        sf = self._make()
        self.assertIsNone(sf.get_state_contribution())

    def test_contribute_mass_empty(self):
        sf = self._make()
        self.assertEqual(sf.contribute_mass({}), [])

    def test_linearity_profile_lti(self):
        sf = self._make()
        self.assertTrue(sf.linearity_profile().is_lti)

    def test_existing_force_output_unchanged(self):
        sf = self._make()
        self.assertAlmostEqual(sf.force_output(0.0), 0.0)   # before start
        self.assertAlmostEqual(sf.force_output(1.0), 100.0) # after start


# ---------------------------------------------------------------------------
# RandomRoad
# ---------------------------------------------------------------------------

class TestRandomRoadOverrides(unittest.TestCase):

    def _make(self) -> object:
        from app.core.models.sources.random_road import RandomRoad
        return RandomRoad(
            "rr_1",
            amplitude=0.05,
            roughness=0.1,
            seed=42,
            vehicle_speed=20.0,
            dt=0.01,
            duration=1.0,
        )

    def test_get_source_descriptor_displacement_kind(self):
        from app.core.base.source_descriptor import SourceDescriptor
        rr = self._make()
        sd = rr.get_source_descriptor()
        self.assertIsInstance(sd, SourceDescriptor)
        self.assertEqual(sd.kind, "displacement")

    def test_get_source_descriptor_ports(self):
        rr = self._make()
        sd = rr.get_source_descriptor()
        self.assertEqual(sd.driven_port_name, "port")
        self.assertEqual(sd.reference_port_name, "reference_port")

    def test_get_source_descriptor_variables(self):
        rr = self._make()
        sd = rr.get_source_descriptor()
        self.assertEqual(sd.input_variable_name, "r_rr_1")
        self.assertEqual(sd.amplitude_parameter, "amplitude")

    def test_get_state_contribution_none(self):
        rr = self._make()
        self.assertIsNone(rr.get_state_contribution())

    def test_contribute_all_matrices_empty(self):
        """RandomRoad is a pure excitation source — zero matrix contributions."""
        rr = self._make()
        self.assertEqual(rr.contribute_mass({}), [])
        self.assertEqual(rr.contribute_damping({}), [])
        self.assertEqual(rr.contribute_stiffness({}), [])

    def test_existing_displacement_output_unchanged(self):
        """Regression: displacement_output still returns a float."""
        rr = self._make()
        result = rr.displacement_output(0.0)
        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
