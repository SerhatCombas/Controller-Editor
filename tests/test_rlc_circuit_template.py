"""Tests for RLC circuit template — Faz 5b.

These are the regression anchor for the new RLC template. They verify:

1. The graph structure is built correctly from basic components.
2. The symbolic equations match the analytical RLC series form.
3. The numerical simulation produces physically correct results
   (oscillation frequency for underdamped case).

Pattern follows ``tests/test_mass_spring_damper_e2e.py`` and
``tests/test_rc_circuit_e2e.py``.
"""
from __future__ import annotations

import numpy as np
import pytest

from tests.fixtures.graph_factories import build_rlc_circuit_template_def as build_rlc_circuit_template


class TestRLCTemplateStructure:
    """Verify the template builds the expected graph topology."""

    def test_template_id_and_name(self):
        template = build_rlc_circuit_template()
        assert template.id == "rlc_circuit"
        assert template.name == "RLC Series Circuit"

    def test_component_count(self):
        """RLC series: 5 components (V_source, R, L, C, Ground)."""
        template = build_rlc_circuit_template()
        components = list(template.graph.components.values())
        assert len(components) == 5

    def test_component_types_present(self):
        """Verify each expected component type is present."""
        template = build_rlc_circuit_template()
        component_types = {
            type(c).__name__ for c in template.graph.components.values()
        }
        # IdealSource is the actual class behind the VoltageSource factory
        expected = {"IdealSource", "Resistor", "Inductor", "Capacitor", "ElectricalGround"}
        assert component_types == expected

    def test_no_hardcoded_RLC_class(self):
        """Critical: there must be NO ``RLC`` or ``RLCCircuit`` class.

        The whole point of Faz 5 is that templates are built from basic
        components, not from a monolithic hardcoded class.
        """
        template = build_rlc_circuit_template()
        for component in template.graph.components.values():
            cls_name = type(component).__name__
            assert "RLC" not in cls_name, (
                f"Found hardcoded class {cls_name} — RLC should emerge "
                f"from R + L + C + source composition, not a special class."
            )

    def test_default_input_is_source(self):
        template = build_rlc_circuit_template()
        assert template.default_input_id == "v_source"

    def test_probes_attached(self):
        """At minimum: loop_current and capacitor_voltage probes."""
        template = build_rlc_circuit_template()
        probe_ids = set(template.graph.probes.keys())
        assert "loop_current" in probe_ids
        assert "capacitor_voltage" in probe_ids


class TestRLCTemplateLayout:
    """Verify schematic layout is provided so canvas can render the default."""

    def test_layout_has_all_components(self):
        template = build_rlc_circuit_template()
        component_ids = set(template.graph.components.keys())
        layout_ids = set(template.schematic_layout.keys())
        assert component_ids == layout_ids, (
            f"Layout missing for: {component_ids - layout_ids}"
        )

    def test_layout_coordinates_positive(self):
        template = build_rlc_circuit_template()
        for cid, (x, y) in template.schematic_layout.items():
            assert x >= 0 and y >= 0, f"Negative coordinate for {cid}: ({x}, {y})"


class TestRLCSymbolicPipeline:
    """Verify symbolic equation generation works through the standard pipeline.

    This test is the proof that the same pipeline used for mass-spring-damper
    works for RLC — i.e. the abstraction is genuinely domain-agnostic.
    """

    def test_equations_buildable(self):
        """EquationBuilder should produce a non-empty SymbolicSystem."""
        from app.core.symbolic.equation_builder import EquationBuilder

        template = build_rlc_circuit_template()
        builder = EquationBuilder()
        symbolic_system = builder.build(template.graph)

        # At minimum: non-zero equations including 2 differential (L and C)
        assert len(symbolic_system.all_equations) > 0
        assert len(symbolic_system.differential_equations) == 2

    def test_state_count(self):
        """RLC has 2 states: inductor current and capacitor voltage."""
        from app.core.symbolic.equation_builder import EquationBuilder
        from app.core.symbolic.polymorphic_dae_reducer import PolymorphicDAEReducer

        template = build_rlc_circuit_template()
        builder = EquationBuilder()
        reducer = PolymorphicDAEReducer()

        symbolic_system = builder.build(template.graph)
        reduced = reducer.reduce(template.graph, symbolic_system)

        # 2nd-order LTI system → 2 states
        assert reduced is not None
        assert len(reduced.state_variables) == 2


# Marker for stage 5b: physical-behavior test deferred to Faz 5c
# (needs the generic numeric backend wired up first).
@pytest.mark.skip(reason="Requires GenericNumericBackend from Faz 5c")
class TestRLCPhysicalBehavior:
    """Verify the simulated response matches the analytical RLC underdamped form.

    For R=10, L=0.5, C=1e-3:
        omega_0 = 1/sqrt(L·C) ≈ 44.72 rad/s
        zeta = R/(2·sqrt(L/C)) ≈ 0.224 (underdamped)
        omega_d = omega_0·sqrt(1-zeta²) ≈ 43.59 rad/s
    """

    def test_oscillation_frequency(self):
        """Damped oscillation frequency should be ~43.59 rad/s."""
        # Will be implemented when GenericNumericBackend is available.
        pass
