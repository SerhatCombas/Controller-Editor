"""T3.4 — Cross-domain tests: domain isolation + multi-domain readiness.

Since mechanical components don't yet have symbolic_equations() (that's T4),
this test file verifies:
  1. Domain isolation — connecting incompatible domains raises errors.
  2. DomainSpec registry covers all planned domains.
  3. New electrical symbolic pipeline + old mechanical string pipeline
     operate independently without cross-contamination.
  4. SystemGraph can hold components from multiple domains.
"""

from __future__ import annotations

import pytest

from app.core.base.domain import (
    Domain,
    DomainSpec,
    DOMAIN_SPECS,
    ELECTRICAL_DOMAIN,
    MECHANICAL_TRANSLATIONAL_DOMAIN,
    get_domain_spec,
)
from app.core.base.port import Port
from app.core.base.variable import Variable
from app.core.graph.system_graph import SystemGraph

from app.core.models.electrical.resistor import Resistor
from app.core.models.electrical.capacitor import Capacitor
from app.core.models.electrical.ground import ElectricalGround
from app.core.models.electrical.source import VoltageSource
from app.core.models.mechanical.spring import Spring
from app.core.models.mechanical.damper import Damper
from app.core.models.mechanical.mass import Mass
from app.core.models.mechanical.ground import MechanicalGround


# =====================================================================
# 1. Domain isolation — incompatible ports must not connect
# =====================================================================


class TestDomainIsolation:
    """Ports from different domains cannot connect."""

    def test_electrical_to_mechanical_raises(self):
        """Connecting an electrical port to a mechanical port should fail."""
        ep = Port(
            id="ep1", name="p", domain=ELECTRICAL_DOMAIN,
            component_id="r1",
        )
        mp = Port(
            id="mp1", name="port_a", domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            component_id="k1",
        )
        with pytest.raises(ValueError, match="Incompatible"):
            ep.validate_compatibility(mp)

    def test_same_domain_ok(self):
        """Same-domain ports pass validation."""
        p1 = Port(
            id="p1", name="p", domain=ELECTRICAL_DOMAIN,
            component_id="r1",
        )
        p2 = Port(
            id="p2", name="n", domain=ELECTRICAL_DOMAIN,
            component_id="r2",
        )
        # Should not raise
        p1.validate_compatibility(p2)


# =====================================================================
# 2. DomainSpec registry completeness
# =====================================================================


class TestDomainSpecRegistry:
    """All planned domains exist in DOMAIN_SPECS."""

    def test_electrical_exists(self):
        assert "electrical" in DOMAIN_SPECS

    def test_translational_exists(self):
        assert "translational" in DOMAIN_SPECS

    def test_rotational_exists(self):
        assert "rotational" in DOMAIN_SPECS

    def test_thermal_exists(self):
        assert "thermal" in DOMAIN_SPECS

    def test_get_domain_spec_electrical(self):
        spec = get_domain_spec("electrical")
        assert spec.across_var == "v"
        assert spec.through_var == "i"

    def test_get_domain_spec_translational(self):
        spec = get_domain_spec("translational")
        assert spec.across_var == "s"
        assert spec.through_var == "f"

    def test_power_order_electrical_zero(self):
        """Electrical: effort ≡ across → power_order = 0."""
        spec = get_domain_spec("electrical")
        assert spec.power_order == 0

    def test_power_order_translational_one(self):
        """Translational: flow = der(across) → power_order = 1."""
        spec = get_domain_spec("translational")
        assert spec.power_order == 1

    def test_each_spec_has_effort_flow(self):
        for name, spec in DOMAIN_SPECS.items():
            assert spec.effort_var, f"{name} missing effort_var"
            assert spec.flow_var, f"{name} missing flow_var"

    def test_each_spec_to_domain_bridge(self):
        """Every DomainSpec can produce a legacy Domain."""
        for name, spec in DOMAIN_SPECS.items():
            d = spec.to_domain()
            assert isinstance(d, Domain)
            assert d.name


# =====================================================================
# 3. Independent pipeline operation
# =====================================================================


class TestIndependentPipelines:
    """Electrical symbolic pipeline and mechanical string pipeline
    don't interfere with each other."""

    def test_electrical_flatten_works(self):
        """RC circuit flattening produces equations (symbolic path)."""
        from app.core.symbolic.symbolic_flattener import flatten

        g = SystemGraph()
        vs = g.add_component(VoltageSource("vs1", V=1.0))
        r = g.add_component(Resistor("r1", R=1.0))
        c = g.add_component(Capacitor("c1", C=1.0))
        gnd = g.add_component(ElectricalGround("gnd1"))

        g.connect(vs.ports[0].id, r.ports[0].id)
        g.connect(r.ports[1].id, c.ports[0].id)
        g.connect(c.ports[1].id, gnd.ports[0].id)
        g.connect(vs.ports[1].id, gnd.ports[0].id)

        flat = flatten(g, input_symbol_names=["vs1__value"])
        assert len(flat.equations) > 0
        assert len(flat.state_symbols) >= 1

    def test_mechanical_string_equations_still_work(self):
        """Mass-spring-damper string equations unaffected."""
        m = Mass("m1", mass=1.0)
        k = Spring("k1", stiffness=100.0)
        d = Damper("d1", damping=10.0)

        all_eqs = (
            m.constitutive_equations()
            + k.constitutive_equations()
            + d.constitutive_equations()
        )
        assert len(all_eqs) == 8  # 3 + 3 + 2

    def test_no_cross_contamination_of_sym_cache(self):
        """Using _sym on one component doesn't pollute another."""
        r = Resistor("r1", R=1.0)
        k = Spring("k1", stiffness=100.0)

        r_sym = r._sym("test")
        k_sym = k._sym("test")

        assert str(r_sym) == "r1__test"
        assert str(k_sym) == "k1__test"
        assert r_sym != k_sym


# =====================================================================
# 4. Multi-domain SystemGraph
# =====================================================================


class TestMultiDomainGraph:
    """SystemGraph can hold components from different domains."""

    def test_add_electrical_and_mechanical(self):
        g = SystemGraph()
        r = g.add_component(Resistor("r1", R=100.0))
        k = g.add_component(Spring("k1", stiffness=100.0))
        assert len(g.components) == 2

    def test_connect_within_same_domain(self):
        """Intra-domain connections work for both domains."""
        g = SystemGraph()
        r = g.add_component(Resistor("r1", R=100.0))
        c = g.add_component(Capacitor("c1", C=1e-6))

        # Electrical connection — should work
        g.connect(r.ports[1].id, c.ports[0].id)
        assert r.ports[1].node_id is not None
        assert c.ports[0].node_id == r.ports[1].node_id

    def test_mixed_graph_node_count(self):
        """Each domain's connections produce separate nodes."""
        g = SystemGraph()

        # Electrical side
        r = g.add_component(Resistor("r1", R=100.0))
        c = g.add_component(Capacitor("c1", C=1e-6))
        g.connect(r.ports[1].id, c.ports[0].id)  # 1 shared node

        # Mechanical side
        k = g.add_component(Spring("k1", stiffness=100.0))
        d = g.add_component(Damper("d1", damping=10.0))
        g.connect(k.ports[1].id, d.ports[0].id)  # 1 shared node

        # We should have at least 2 nodes (one electrical, one mechanical)
        assert len(g.nodes) >= 2
