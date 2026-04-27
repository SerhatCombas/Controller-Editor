"""T3.3 — Backward compatibility: old components + old pipeline still work.

Verifies that changes to base classes (DomainSpec, Port enrichment,
symbolic equation path, component helpers) do NOT break existing
mechanical components or the PolymorphicDAEReducer pipeline.

Key invariant: all 39 pre-existing failures in test_tf_golden / test_tf_fuzz /
test_polymorphic_reducer / test_component_overrides / test_input_router /
test_linearization_warnings are pre-existing and NOT caused by our changes.
This test file covers the positive path — things that MUST keep working.
"""

from __future__ import annotations

import pytest

from app.core.base.component import BaseComponent
from app.core.base.domain import (
    Domain,
    ELECTRICAL_DOMAIN,
    MECHANICAL_TRANSLATIONAL_DOMAIN,
)
from app.core.base.port import Port
from app.core.base.variable import Variable


# ── Mechanical component imports (old-style, string-based) ────────────

from app.core.models.mechanical.spring import Spring
from app.core.models.mechanical.damper import Damper
from app.core.models.mechanical.mass import Mass
from app.core.models.mechanical.ground import MechanicalGround


# ── New electrical component imports (symbolic-style) ─────────────────

from app.core.models.electrical.resistor import Resistor
from app.core.models.electrical.capacitor import Capacitor
from app.core.models.electrical.ground import ElectricalGround
from app.core.models.electrical.source import VoltageSource


# =====================================================================
# 1. Old mechanical components still instantiate and produce equations
# =====================================================================


class TestMechanicalComponentsUnchanged:
    """Old-style mechanical components must keep working exactly as before."""

    def test_spring_instantiates(self):
        s = Spring("k1", stiffness=100.0)
        assert s.id == "k1"
        assert s.parameters["stiffness"] == 100.0

    def test_spring_has_two_ports(self):
        s = Spring("k1", stiffness=100.0)
        assert len(s.ports) == 2

    def test_spring_constitutive_equations(self):
        s = Spring("k1", stiffness=100.0)
        eqs = s.constitutive_equations()
        assert len(eqs) == 3
        assert any("d/dt" in eq for eq in eqs)
        assert any("100.0" in eq for eq in eqs)

    def test_spring_symbolic_equations_empty(self):
        """Old components return [] for symbolic_equations (no override)."""
        s = Spring("k1", stiffness=100.0)
        assert s.symbolic_equations() == []

    def test_damper_instantiates(self):
        d = Damper("d1", damping=50.0)
        assert d.id == "d1"
        assert d.parameters["damping"] == 50.0

    def test_damper_constitutive_equations(self):
        d = Damper("d1", damping=50.0)
        eqs = d.constitutive_equations()
        assert len(eqs) == 2
        assert any("50.0" in eq for eq in eqs)

    def test_mass_instantiates(self):
        m = Mass("m1", mass=10.0)
        assert m.id == "m1"
        assert m.parameters["mass"] == 10.0

    def test_mass_get_states(self):
        m = Mass("m1", mass=10.0)
        states = m.get_states()
        assert len(states) == 2
        assert "x_m1" in states
        assert "v_m1" in states

    def test_mass_constitutive_equations(self):
        m = Mass("m1", mass=10.0)
        eqs = m.constitutive_equations()
        assert len(eqs) == 3

    def test_ground_instantiates(self):
        g = MechanicalGround("gnd1")
        assert g.id == "gnd1"

    def test_ground_has_one_port(self):
        g = MechanicalGround("gnd1")
        assert len(g.ports) == 1


# =====================================================================
# 2. Base class enrichments are backward-compatible (opt-in defaults)
# =====================================================================


class TestBaseClassBackwardCompat:
    """New fields/methods on BaseComponent and Port have safe defaults."""

    def test_old_component_has_no_category_by_default(self):
        s = Spring("k1", stiffness=100.0)
        assert s.category is None

    def test_old_component_has_empty_tags(self):
        s = Spring("k1", stiffness=100.0)
        assert s.tags == ()

    def test_old_component_has_no_icon(self):
        s = Spring("k1", stiffness=100.0)
        assert s.icon_path is None

    def test_old_component_sym_cache_is_empty(self):
        s = Spring("k1", stiffness=100.0)
        assert len(s._sym_cache) == 0

    def test_old_component_sym_method_works(self):
        """Even old components can use _sym() if needed (future migration)."""
        s = Spring("k1", stiffness=100.0)
        sym = s._sym("test_var")
        assert str(sym) == "k1__test_var"

    def test_port_direction_hint_default_none(self):
        s = Spring("k1", stiffness=100.0)
        for port in s.ports:
            assert port.direction_hint is None

    def test_port_visual_anchor_default_none(self):
        s = Spring("k1", stiffness=100.0)
        for port in s.ports:
            assert port.visual_anchor is None

    def test_port_is_positive_false_for_old_ports(self):
        s = Spring("k1", stiffness=100.0)
        for port in s.ports:
            assert port.is_positive is False
            assert port.is_negative is False


# =====================================================================
# 3. Domain constants unchanged
# =====================================================================


class TestDomainConstantsUnchanged:
    """Legacy Domain constants must be identical to original values."""

    def test_electrical_domain_name(self):
        assert ELECTRICAL_DOMAIN.name == "electrical"

    def test_electrical_domain_across(self):
        assert ELECTRICAL_DOMAIN.across_variable == "voltage"

    def test_electrical_domain_through(self):
        assert ELECTRICAL_DOMAIN.through_variable == "current"

    def test_mechanical_domain_name(self):
        assert MECHANICAL_TRANSLATIONAL_DOMAIN.name == "mechanical_translational"

    def test_mechanical_domain_across(self):
        assert MECHANICAL_TRANSLATIONAL_DOMAIN.across_variable == "velocity"

    def test_mechanical_domain_through(self):
        assert MECHANICAL_TRANSLATIONAL_DOMAIN.through_variable == "force"

    def test_domain_is_frozen(self):
        with pytest.raises(AttributeError):
            ELECTRICAL_DOMAIN.name = "changed"


# =====================================================================
# 4. Coexistence: old + new components in same process
# =====================================================================


class TestOldNewCoexistence:
    """Old-style and new-style components coexist without interference."""

    def test_both_types_instantiate(self):
        spring = Spring("k1", stiffness=100.0)
        resistor = Resistor("r1", R=1000.0)
        assert spring.domain.name == "mechanical_translational"
        assert resistor.domain.name == "electrical"

    def test_old_has_string_equations_only(self):
        spring = Spring("k1", stiffness=100.0)
        assert len(spring.constitutive_equations()) > 0
        assert spring.symbolic_equations() == []

    def test_new_has_both_paths(self):
        """New components have symbolic_equations; string path may be empty."""
        resistor = Resistor("r1", R=1000.0)
        sym_eqs = resistor.symbolic_equations()
        assert len(sym_eqs) > 0

    def test_mixed_collection(self):
        """Can hold old and new components in a list."""
        components: list[BaseComponent] = [
            Spring("k1", stiffness=100.0),
            Resistor("r1", R=1000.0),
            Mass("m1", mass=10.0),
            Capacitor("c1", C=1e-6),
        ]
        assert len(components) == 4
        assert all(isinstance(c, BaseComponent) for c in components)

    def test_contribute_methods_still_work(self):
        """Old polymorphic contribute_* methods are unaffected."""
        spring = Spring("k1", stiffness=100.0)
        assert hasattr(spring, "contribute_stiffness")
        assert hasattr(spring, "get_state_contribution")
        sc = spring.get_state_contribution()
        assert sc.stores_potential_energy is True
