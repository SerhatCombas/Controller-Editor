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
        """Wheel contributes its DOF to the system graph (Mass inheritance intact)."""
        w = Wheel("wheel_mass", mass=30.0)
        # Mass subclass should expose port_a and reference_port
        port_names = [p.name for p in w.ports]
        self.assertIn("port_a", port_names)
        self.assertIn("reference_port", port_names)


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


if __name__ == "__main__":
    unittest.main()
