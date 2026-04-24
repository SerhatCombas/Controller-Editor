"""Tests for Wave 1 foundation dataclasses.

Covers:
- LinearityProfile (linearity.py)
- StateContribution (state_contribution.py)
- MatrixContribution (contribution.py)
- SourceDescriptor (source_descriptor.py)
- FeatureFlags / ParityMode (feature_flags.py)
- BaseComponent default polymorphic interface

All tests are purely additive — no existing behaviour is modified.
"""
from __future__ import annotations

import unittest

import sympy


# ---------------------------------------------------------------------------
# LinearityProfile
# ---------------------------------------------------------------------------

class TestLinearityProfile(unittest.TestCase):

    def test_default_is_lti(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile()
        self.assertTrue(lp.is_linear)
        self.assertTrue(lp.is_time_invariant)
        self.assertTrue(lp.is_lti)

    def test_nonlinear_not_lti(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile(is_linear=False, nonlinearity_kind="smooth")
        self.assertFalse(lp.is_lti)
        self.assertEqual(lp.nonlinearity_kind, "smooth")

    def test_ltv_not_lti(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile(is_time_invariant=False)
        self.assertTrue(lp.is_linear)
        self.assertFalse(lp.is_lti)

    def test_frozen(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile()
        with self.assertRaises((AttributeError, TypeError)):
            lp.is_linear = False  # type: ignore[misc]

    def test_notes_default_empty_tuple(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile()
        self.assertEqual(lp.notes, ())

    def test_notes_stored(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile(notes=("geometric stiffening",))
        self.assertIn("geometric stiffening", lp.notes)

    def test_requires_operating_point_flag(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile(is_linear=False, requires_operating_point=True)
        self.assertTrue(lp.requires_operating_point)

    def test_equality(self):
        from app.core.base.linearity import LinearityProfile
        a = LinearityProfile()
        b = LinearityProfile()
        self.assertEqual(a, b)

    def test_hashable(self):
        from app.core.base.linearity import LinearityProfile
        lp = LinearityProfile()
        # frozen dataclass must be hashable
        self.assertIsInstance(hash(lp), int)


# ---------------------------------------------------------------------------
# StateContribution
# ---------------------------------------------------------------------------

class TestStateContribution(unittest.TestCase):

    def test_inertial_defaults(self):
        from app.core.base.state_contribution import StateContribution
        sc = StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )
        self.assertTrue(sc.stores_inertial_energy)
        self.assertFalse(sc.stores_potential_energy)
        self.assertEqual(sc.state_kind, "inertial")
        self.assertEqual(sc.dof_count, 1)
        self.assertEqual(sc.owning_port_name, "port_a")

    def test_potential_energy(self):
        from app.core.base.state_contribution import StateContribution
        sc = StateContribution(
            stores_inertial_energy=False,
            stores_potential_energy=True,
            state_kind="potential",
            dof_count=1,
            owning_port_name="port_a",
        )
        self.assertEqual(sc.state_kind, "potential")

    def test_frozen(self):
        from app.core.base.state_contribution import StateContribution
        sc = StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )
        with self.assertRaises((AttributeError, TypeError)):
            sc.dof_count = 99  # type: ignore[misc]

    def test_hashable(self):
        from app.core.base.state_contribution import StateContribution
        sc = StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )
        self.assertIsInstance(hash(sc), int)


# ---------------------------------------------------------------------------
# MatrixContribution
# ---------------------------------------------------------------------------

class TestMatrixContribution(unittest.TestCase):

    def _make(self, **kwargs):
        from app.core.base.contribution import MatrixContribution
        defaults = dict(
            row=0,
            col=0,
            value=sympy.Symbol("m"),
            component_id="mass_1",
            contribution_kind="mass",
            connected_node_ids=("node_a", "node_ref"),
            physical_meaning="inertial resistance of Mass at DOF 0",
            equation_reference="M[0,0] += m",
        )
        defaults.update(kwargs)
        return MatrixContribution(**defaults)

    def test_basic_construction(self):
        mc = self._make()
        self.assertEqual(mc.row, 0)
        self.assertEqual(mc.col, 0)
        self.assertEqual(mc.component_id, "mass_1")
        self.assertEqual(mc.contribution_kind, "mass")

    def test_connected_node_ids_tuple(self):
        mc = self._make(connected_node_ids=("n1", "n2"))
        self.assertIsInstance(mc.connected_node_ids, tuple)
        self.assertEqual(mc.connected_node_ids, ("n1", "n2"))

    def test_physical_meaning_stored(self):
        mc = self._make(physical_meaning="spring force between nodes 0 and 1")
        self.assertIn("spring", mc.physical_meaning)

    def test_equation_reference_stored(self):
        mc = self._make(equation_reference="K[0,1] -= k")
        self.assertEqual(mc.equation_reference, "K[0,1] -= k")

    def test_frozen(self):
        mc = self._make()
        with self.assertRaises((AttributeError, TypeError)):
            mc.row = 99  # type: ignore[misc]

    def test_contribution_kinds_accepted(self):
        from app.core.base.contribution import MatrixContribution
        for kind in ("mass", "damping", "stiffness", "input", "output"):
            mc = self._make(contribution_kind=kind)
            self.assertEqual(mc.contribution_kind, kind)

    def test_sympy_value_preserved(self):
        sym = sympy.Symbol("k") * 2
        mc = self._make(value=sym, contribution_kind="stiffness")
        self.assertEqual(mc.value, sym)


# ---------------------------------------------------------------------------
# SourceDescriptor
# ---------------------------------------------------------------------------

class TestSourceDescriptor(unittest.TestCase):

    def test_force_source(self):
        from app.core.base.source_descriptor import SourceDescriptor
        sd = SourceDescriptor(
            kind="force",
            driven_port_name="port_a",
            reference_port_name="reference_port",
            input_variable_name="F_ext",
            amplitude_parameter="F0",
        )
        self.assertEqual(sd.kind, "force")
        self.assertEqual(sd.driven_port_name, "port_a")
        self.assertEqual(sd.reference_port_name, "reference_port")
        self.assertEqual(sd.input_variable_name, "F_ext")
        self.assertEqual(sd.amplitude_parameter, "F0")

    def test_displacement_source(self):
        from app.core.base.source_descriptor import SourceDescriptor
        sd = SourceDescriptor(
            kind="displacement",
            driven_port_name="port_a",
            reference_port_name="reference_port",
            input_variable_name="x_road",
            amplitude_parameter="A_road",
        )
        self.assertEqual(sd.kind, "displacement")

    def test_frozen(self):
        from app.core.base.source_descriptor import SourceDescriptor
        sd = SourceDescriptor(
            kind="force",
            driven_port_name="port_a",
            reference_port_name="reference_port",
            input_variable_name="F_ext",
            amplitude_parameter="F0",
        )
        with self.assertRaises((AttributeError, TypeError)):
            sd.kind = "velocity"  # type: ignore[misc]

    def test_hashable(self):
        from app.core.base.source_descriptor import SourceDescriptor
        sd = SourceDescriptor(
            kind="force",
            driven_port_name="port_a",
            reference_port_name="reference_port",
            input_variable_name="F_ext",
            amplitude_parameter="F0",
        )
        self.assertIsInstance(hash(sd), int)


# ---------------------------------------------------------------------------
# FeatureFlags / ParityMode
# ---------------------------------------------------------------------------

class TestFeatureFlags(unittest.TestCase):

    def test_default_flags_parity_primary(self):
        """Wave 2 cutover: DEFAULT_FLAGS.parity_mode == PRIMARY (polymorphic authoritative)."""
        from app.core.state.feature_flags import DEFAULT_FLAGS, ParityMode
        self.assertEqual(DEFAULT_FLAGS.parity_mode, ParityMode.PRIMARY)

    def test_development_flags_parity_shadow(self):
        from app.core.state.feature_flags import DEVELOPMENT_FLAGS, ParityMode
        self.assertEqual(DEVELOPMENT_FLAGS.parity_mode, ParityMode.SHADOW)

    def test_parity_mode_enum_values(self):
        from app.core.state.feature_flags import ParityMode
        self.assertEqual(ParityMode.OFF.value, "off")
        self.assertEqual(ParityMode.SHADOW.value, "shadow")
        self.assertEqual(ParityMode.PRIMARY.value, "primary")

    def test_feature_flags_frozen(self):
        from app.core.state.feature_flags import DEFAULT_FLAGS
        with self.assertRaises((AttributeError, TypeError)):
            DEFAULT_FLAGS.parity_mode = None  # type: ignore[misc]

    def test_custom_flags_construction(self):
        from app.core.state.feature_flags import FeatureFlags, ParityMode
        flags = FeatureFlags(
            parity_mode=ParityMode.PRIMARY,
            enable_linearity_classifier=True,
            enable_input_router=True,
        )
        self.assertEqual(flags.parity_mode, ParityMode.PRIMARY)
        self.assertTrue(flags.enable_linearity_classifier)
        self.assertTrue(flags.enable_input_router)

    def test_default_flags_classifiers_enabled(self):
        from app.core.state.feature_flags import DEFAULT_FLAGS
        # Classifier and router are enabled in DEFAULT_FLAGS even with parity OFF,
        # allowing the classifier verdict to surface in the UI while the
        # legacy reducer remains authoritative throughout Wave 1.
        self.assertTrue(DEFAULT_FLAGS.enable_linearity_classifier)
        self.assertTrue(DEFAULT_FLAGS.enable_input_router)


# ---------------------------------------------------------------------------
# BaseComponent default polymorphic interface
# ---------------------------------------------------------------------------

class TestBaseComponentPolymorphicDefaults(unittest.TestCase):
    """Verify the new opt-in methods on BaseComponent return safe neutral defaults.

    We use a minimal concrete subclass because BaseComponent.constitutive_equations()
    raises NotImplementedError (by design — subclasses must override it).
    The new polymorphic methods must NOT raise.
    """

    def _make_component(self):
        from app.core.base.component import BaseComponent
        from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
        from app.core.base.port import Port

        class _Stub(BaseComponent):
            def constitutive_equations(self) -> list[str]:
                return []

        port = Port(
            id="port_stub_1_a",
            name="port_a",
            domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            component_id="stub_1",
            required=False,
        )
        return _Stub(
            id="stub_1",
            name="Stub",
            domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            ports=[port],
        )

    def test_linearity_profile_returns_lti(self):
        from app.core.base.linearity import LinearityProfile
        comp = self._make_component()
        lp = comp.linearity_profile()
        self.assertIsInstance(lp, LinearityProfile)
        self.assertTrue(lp.is_lti)

    def test_get_state_contribution_returns_none(self):
        comp = self._make_component()
        self.assertIsNone(comp.get_state_contribution())

    def test_get_source_descriptor_returns_none(self):
        comp = self._make_component()
        self.assertIsNone(comp.get_source_descriptor())

    def test_contribute_mass_returns_empty_list(self):
        comp = self._make_component()
        result = comp.contribute_mass({"node_a": 0, "node_ref": 1})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_contribute_damping_returns_empty_list(self):
        comp = self._make_component()
        result = comp.contribute_damping({"node_a": 0, "node_ref": 1})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_contribute_stiffness_returns_empty_list(self):
        comp = self._make_component()
        result = comp.contribute_stiffness({"node_a": 0, "node_ref": 1})
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_existing_interface_unchanged(self):
        """Regression: original BaseComponent interface still works correctly."""
        comp = self._make_component()
        self.assertEqual(comp.get_states(), [])
        self.assertEqual(comp.get_parameters(), {})
        self.assertEqual(comp.initial_condition_map(), {})
        self.assertEqual(comp.constitutive_equations(), [])
        errors = comp.validate()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
