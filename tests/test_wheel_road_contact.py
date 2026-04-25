"""Faz 4d-1 — Wheel road-contact infrastructure tests.

Validates the additive changes to Wheel:
  * Backward compat: old API (mass, radius) unchanged.
  * New road_contact_port: correct domain, variable names, required=False.
  * New parameters: defaults, overrides, disable semantics, 0.0 accepted.
  * mass is required; mass=0.0 is accepted (deliberate choice).
  * Invalid mode strings raise ValueError at construction.
  * Mass matrix contribution preserved despite new port.
"""
import unittest

from app.core.models.mechanical.wheel import (
    Wheel,
    WHEEL_CONTACT_MODES,
    WHEEL_OUTPUT_MODES,
)
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN


class TestWheelBackwardCompatibility(unittest.TestCase):
    """The old 2-arg API (component_id, mass) must work without changes."""

    def test_old_api_constructs_without_error(self):
        """Wheel('w', mass=40.0) still works."""
        w = Wheel("w", mass=40.0)
        self.assertEqual(w.parameters["mass"], 40.0)

    def test_old_api_radius_preserved(self):
        """radius parameter accessible via old API."""
        w = Wheel("w", mass=40.0, radius=0.30)
        self.assertEqual(w.parameters["radius"], 0.30)

    def test_old_api_default_radius(self):
        """Default radius is 0.32 (unchanged from pre-4d-1)."""
        w = Wheel("w", mass=40.0)
        self.assertAlmostEqual(w.parameters["radius"], 0.32)

    def test_old_api_still_contributes_mass_state(self):
        """Wheel still contributes its DOF to the system graph just like before
        (port_a / reference_port still present, behavior matches Mass)."""
        w = Wheel("wheel_mass", mass=30.0)
        port_names = [p.name for p in w.ports]
        self.assertIn("port_a", port_names)
        self.assertIn("reference_port", port_names)

    def test_wheel_no_longer_inherits_from_mass(self):
        """Faz 4d-2a: Wheel was split off from Mass into its own first-class
        component. isinstance(wheel, Mass) must now be False even though the
        observable behavior is unchanged."""
        from app.core.models.mechanical import Mass
        from app.core.base.component import BaseComponent
        w = Wheel("w", mass=40.0)
        self.assertFalse(isinstance(w, Mass),
            "Wheel should be its own class after 4d-2a split")
        self.assertTrue(isinstance(w, BaseComponent),
            "Wheel must still be a BaseComponent")

    def test_wheel_behavior_matches_mass_for_same_mass(self):
        """Parity check: Wheel and Mass with the same component_id and mass
        must produce identical states, equations, and matrix contributions —
        the split into independent classes preserved behavior bit-for-bit."""
        from app.core.models.mechanical import Mass
        # Same id so symbolic names line up.
        m = Mass("x", mass=12.5)
        w = Wheel("x", mass=12.5)
        self.assertEqual(m.get_states(), w.get_states())
        self.assertEqual(m.constitutive_equations(), w.constitutive_equations())
        m_state = m.get_state_contribution()
        w_state = w.get_state_contribution()
        self.assertEqual(m_state.dof_count, w_state.dof_count)
        self.assertEqual(m_state.stores_inertial_energy, w_state.stores_inertial_energy)
        self.assertEqual(m_state.state_kind, w_state.state_kind)
        self.assertEqual(m_state.owning_port_name, w_state.owning_port_name)
        # Connect port_a on both and check matrix contribution structure.
        m.port("port_a").connect_to("nx")
        w.port("port_a").connect_to("nx")
        m_c = m.contribute_mass({"nx": 0})
        w_c = w.contribute_mass({"nx": 0})
        self.assertEqual(len(m_c), len(w_c))
        self.assertEqual(m_c[0].row, w_c[0].row)
        self.assertEqual(m_c[0].col, w_c[0].col)
        self.assertEqual(m_c[0].value, w_c[0].value)
        self.assertEqual(m_c[0].contribution_kind, w_c[0].contribution_kind)


class TestWheelRoadContactPort(unittest.TestCase):
    """road_contact_port shape and semantics."""

    def _get_road_port(self, w: Wheel):
        for p in w.ports:
            if p.name == "road_contact_port":
                return p
        self.fail("road_contact_port not found on Wheel")

    def test_road_contact_port_exists(self):
        """Wheel must have a port named road_contact_port."""
        w = Wheel("w", mass=40.0)
        names = [p.name for p in w.ports]
        self.assertIn("road_contact_port", names)

    def test_road_contact_port_domain(self):
        """road_contact_port domain must be mechanical_translational."""
        w = Wheel("w", mass=40.0)
        port = self._get_road_port(w)
        self.assertEqual(port.domain.name, MECHANICAL_TRANSLATIONAL_DOMAIN.name)

    def test_road_contact_port_variable_names(self):
        """Variable names follow the f_<id>_road / v_<id>_road convention."""
        w = Wheel("wheel_mass", mass=40.0)
        port = self._get_road_port(w)
        self.assertEqual(port.across_var.name, "v_wheel_mass_road")
        self.assertEqual(port.through_var.name, "f_wheel_mass_road")

    def test_road_contact_port_not_required(self):
        """road_contact_port must be required=False so it can sit unconnected."""
        w = Wheel("w", mass=40.0)
        port = self._get_road_port(w)
        self.assertFalse(port.required)


class TestWheelNewParameters(unittest.TestCase):
    """New parameter defaults, overrides, and disable semantics."""

    def test_contact_mode_default(self):
        w = Wheel("w", mass=40.0)
        self.assertEqual(w.parameters["contact_mode"], "kinematic_follow")

    def test_contact_stiffness_default(self):
        w = Wheel("w", mass=40.0)
        self.assertAlmostEqual(w.parameters["contact_stiffness"], 200000.0)

    def test_contact_damping_default(self):
        w = Wheel("w", mass=40.0)
        self.assertAlmostEqual(w.parameters["contact_damping"], 500.0)

    def test_disable_contact_force_default(self):
        w = Wheel("w", mass=40.0)
        self.assertFalse(w.parameters["disable_contact_force"])

    def test_rotational_inertia_default(self):
        w = Wheel("w", mass=40.0)
        self.assertAlmostEqual(w.parameters["rotational_inertia"], 1.0)

    def test_rolling_resistance_default(self):
        w = Wheel("w", mass=40.0)
        self.assertAlmostEqual(w.parameters["rolling_resistance"], 0.015)

    def test_output_mode_default(self):
        w = Wheel("w", mass=40.0)
        self.assertEqual(w.parameters["output_mode"], "displacement")

    def test_disable_contact_force_flag(self):
        """disable_contact_force=True must be stored; stiffness/damping preserved."""
        w = Wheel("w", mass=40.0, contact_stiffness=180000.0, disable_contact_force=True)
        self.assertTrue(w.parameters["disable_contact_force"])
        # The tuning must survive — only the flag changes, not the values.
        self.assertAlmostEqual(w.parameters["contact_stiffness"], 180000.0)

    def test_zero_rotational_inertia_accepted(self):
        """rotational_inertia=0.0 is a valid user choice (no rotational DOF)."""
        w = Wheel("w", mass=40.0, rotational_inertia=0.0)
        self.assertAlmostEqual(w.parameters["rotational_inertia"], 0.0)

    def test_zero_rolling_resistance_accepted(self):
        """rolling_resistance=0.0 is a valid user choice (frictionless)."""
        w = Wheel("w", mass=40.0, rolling_resistance=0.0)
        self.assertAlmostEqual(w.parameters["rolling_resistance"], 0.0)


class TestWheelMassRequired(unittest.TestCase):
    def test_mass_omitted_raises_typeerror(self):
        """Wheel() without mass must raise TypeError."""
        with self.assertRaises(TypeError):
            Wheel("w")  # type: ignore[call-arg]

    def test_mass_zero_accepted(self):
        """mass=0.0 is valid — user explicitly requests a massless wheel."""
        w = Wheel("w", mass=0.0)
        self.assertAlmostEqual(w.parameters["mass"], 0.0)


class TestWheelParameterValidation(unittest.TestCase):
    def test_invalid_contact_mode_raises(self):
        with self.assertRaises(ValueError):
            Wheel("w", mass=40.0, contact_mode="hover")

    def test_invalid_output_mode_raises(self):
        with self.assertRaises(ValueError):
            Wheel("w", mass=40.0, output_mode="acceleration")

    def test_module_constants_enumerate_valid_modes(self):
        """WHEEL_CONTACT_MODES and WHEEL_OUTPUT_MODES list the accepted values."""
        self.assertIn("kinematic_follow", WHEEL_CONTACT_MODES)
        self.assertIn("dynamic_contact", WHEEL_CONTACT_MODES)
        self.assertIn("displacement", WHEEL_OUTPUT_MODES)
        self.assertIn("force", WHEEL_OUTPUT_MODES)


class TestWheelMassContributionPreserved(unittest.TestCase):
    def test_mass_contribution_unchanged(self):
        """The new port must not alter the Wheel's mass contribution."""
        w_old_style = Wheel("w1", mass=50.0)
        w_new_style = Wheel("w2", mass=50.0,
                            contact_stiffness=180000.0,
                            contact_damping=0.0,
                            rotational_inertia=0.0,
                            rolling_resistance=0.0)
        # Both should have the same mass value in parameters
        self.assertAlmostEqual(w_old_style.parameters["mass"],
                                w_new_style.parameters["mass"])
        # And the same number of non-road ports (port_a + reference_port)
        legacy_ports = [p for p in w_old_style.ports if p.name != "road_contact_port"]
        new_ports = [p for p in w_new_style.ports if p.name != "road_contact_port"]
        self.assertEqual(len(legacy_ports), len(new_ports))


class TestWheelTransducerMode(unittest.TestCase):
    """Faz 4d-2b: mass=0.0 puts the wheel into transducer mode at the API level.

    The four polymorphic methods all agree on the criterion mass==0:
    - get_states() returns []
    - constitutive_equations() returns [] (4f Mode A populates it)
    - get_state_contribution() reports state_kind="transducer", dof_count=0
    - contribute_mass() returns []

    These tests only check the API surface. Pipeline integration
    (dae_reducer, equation_builder honoring the transducer state_kind)
    is intentionally out of scope here — Faz 4d-2c handles that.
    """

    def test_transducer_get_states_empty(self):
        """A mass=0 wheel owns no integration state."""
        w = Wheel("w", mass=0.0)
        self.assertEqual(w.get_states(), [])

    def test_transducer_constitutive_equations_empty(self):
        """4d-2b leaves the algebraic passthrough unimplemented; 4f Mode A
        will fill it. For now we assert the slot is empty so 4f can detect
        that it needs to populate it (rather than appending blindly)."""
        w = Wheel("w", mass=0.0)
        self.assertEqual(w.constitutive_equations(), [])

    def test_transducer_state_contribution(self):
        """state_kind=='transducer', dof_count=0, no inertial energy storage."""
        w = Wheel("w", mass=0.0)
        sc = w.get_state_contribution()
        self.assertEqual(sc.state_kind, "transducer")
        self.assertEqual(sc.dof_count, 0)
        self.assertFalse(sc.stores_inertial_energy)
        self.assertFalse(sc.stores_potential_energy)
        self.assertIsNone(sc.owning_port_name)

    def test_transducer_contribute_mass_empty_even_when_port_a_connected(self):
        """Even with port_a wired to a node, a mass=0 wheel produces no
        mass-matrix entry — that is precisely what 'transducer' means."""
        w = Wheel("w", mass=0.0)
        w.port("port_a").connect_to("nx")
        contributions = w.contribute_mass({"nx": 0})
        self.assertEqual(contributions, [])


class TestWheelMassPositiveBehaviorParity(unittest.TestCase):
    """Faz 4d-2b parity guard: mass>0 path must remain bit-for-bit identical
    to the pre-4d-2b implementation. We compare against Mass with the same
    component_id and mass — the same parity check that 4d-2a established —
    to ensure the new branching did not perturb the inertial path."""

    def test_states_match_mass_when_mass_positive(self):
        from app.core.models.mechanical import Mass
        w = Wheel("x", mass=12.5)
        m = Mass("x", mass=12.5)
        self.assertEqual(w.get_states(), m.get_states())

    def test_equations_match_mass_when_mass_positive(self):
        from app.core.models.mechanical import Mass
        w = Wheel("x", mass=12.5)
        m = Mass("x", mass=12.5)
        self.assertEqual(w.constitutive_equations(), m.constitutive_equations())

    def test_state_contribution_matches_mass_when_mass_positive(self):
        from app.core.models.mechanical import Mass
        w = Wheel("x", mass=12.5)
        m = Mass("x", mass=12.5)
        w_sc = w.get_state_contribution()
        m_sc = m.get_state_contribution()
        self.assertEqual(w_sc.state_kind, m_sc.state_kind)
        self.assertEqual(w_sc.dof_count, m_sc.dof_count)
        self.assertEqual(w_sc.stores_inertial_energy, m_sc.stores_inertial_energy)
        self.assertEqual(w_sc.owning_port_name, m_sc.owning_port_name)


if __name__ == "__main__":
    unittest.main()
