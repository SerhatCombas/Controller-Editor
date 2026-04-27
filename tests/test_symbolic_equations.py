"""Tests for symbolic equation infrastructure (T0.3)."""

from __future__ import annotations

import sympy

from app.core.base.domain import ELECTRICAL_DOMAIN, MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.equation import SymbolicEquation, der
from app.core.base.component import BaseComponent
from app.core.base.port import Port


# ---------------------------------------------------------------------------
# SymbolicEquation basics
# ---------------------------------------------------------------------------


def test_residual_simple():
    v, R, i = sympy.symbols("v R i")
    eq = SymbolicEquation(lhs=v, rhs=R * i, provenance="Ohm")
    assert eq.residual == v - R * i


def test_free_symbols():
    v, R, i = sympy.symbols("v R i")
    eq = SymbolicEquation(lhs=v, rhs=R * i)
    assert eq.free_symbols() == {v, R, i}


def test_substitute():
    v, R, i = sympy.symbols("v R i")
    eq = SymbolicEquation(lhs=v, rhs=R * i, provenance="Ohm")
    eq2 = eq.substitute({R: sympy.Integer(100)})
    assert eq2.rhs == 100 * i
    assert eq2.provenance == "Ohm"


def test_has_derivative_false():
    v, i = sympy.symbols("v i")
    eq = SymbolicEquation(lhs=v, rhs=i)
    # No der() calls → may or may not be True depending on atoms
    # This equation has no Function atoms
    assert eq.has_derivative() is False


def test_has_derivative_true():
    v = sympy.Symbol("v")
    C = sympy.Symbol("C")
    eq = SymbolicEquation(lhs=sympy.Symbol("i"), rhs=C * der(v), provenance="capacitor")
    assert eq.has_derivative() is True


def test_repr():
    v, i = sympy.symbols("v i")
    eq = SymbolicEquation(lhs=v, rhs=i, provenance="test")
    r = repr(eq)
    assert "test" in r
    assert "Eq(" in r


# ---------------------------------------------------------------------------
# der() function
# ---------------------------------------------------------------------------


def test_der_creates_function_call():
    x = sympy.Symbol("x")
    dx = der(x)
    # der(x) should be an applied function
    assert isinstance(dx, sympy.Basic)
    assert str(dx) == "der(x)"


def test_der_different_args_different_results():
    x, y = sympy.symbols("x y")
    assert der(x) != der(y)


# ---------------------------------------------------------------------------
# BaseComponent._sym() and symbolic_equations()
# ---------------------------------------------------------------------------


def _make_component(comp_id: str = "c1") -> BaseComponent:
    return BaseComponent(
        id=comp_id,
        name="test_comp",
        domain=ELECTRICAL_DOMAIN,
        ports=[
            Port(id="p1", name="p", domain=ELECTRICAL_DOMAIN, component_id=comp_id),
            Port(id="n1", name="n", domain=ELECTRICAL_DOMAIN, component_id=comp_id),
        ],
    )


def test_sym_returns_symbol():
    comp = _make_component()
    v = comp._sym("v")
    assert isinstance(v, sympy.Symbol)


def test_sym_caches():
    comp = _make_component()
    v1 = comp._sym("v")
    v2 = comp._sym("v")
    assert v1 is v2


def test_sym_scoped_to_component():
    comp1 = _make_component("c1")
    comp2 = _make_component("c2")
    v1 = comp1._sym("v")
    v2 = comp2._sym("v")
    assert v1 != v2  # Different component → different symbol
    assert "c1" in str(v1)
    assert "c2" in str(v2)


def test_symbolic_equations_default_empty():
    comp = _make_component()
    assert comp.symbolic_equations() == []


def test_constitutive_equations_still_raises():
    """Existing string-based path unchanged — base still raises NotImplementedError."""
    comp = _make_component()
    try:
        comp.constitutive_equations()
        assert False, "Should have raised"
    except NotImplementedError:
        pass


# ---------------------------------------------------------------------------
# Example: Ohm's law v = R * i using the component helpers
# ---------------------------------------------------------------------------


class _MockResistor(BaseComponent):
    """Minimal resistor to test symbolic equation flow."""

    def symbolic_equations(self) -> list[SymbolicEquation]:
        v = self._sym("v")
        i = self._sym("i")
        R = self._sym("R")
        return [SymbolicEquation(lhs=v, rhs=R * i, provenance="Ohm")]

    def constitutive_equations(self) -> list[str]:
        return ["v = R * i"]


def test_mock_resistor_symbolic():
    r = _MockResistor(
        id="r1",
        name="R1",
        domain=ELECTRICAL_DOMAIN,
        ports=[
            Port(id="p1", name="p", domain=ELECTRICAL_DOMAIN, component_id="r1"),
            Port(id="n1", name="n", domain=ELECTRICAL_DOMAIN, component_id="r1"),
        ],
        parameters={"R": 100.0},
    )
    eqs = r.symbolic_equations()
    assert len(eqs) == 1
    eq = eqs[0]
    assert eq.provenance == "Ohm"
    # Substituting R=100, i=0.5 should give v=50
    R_sym = r._sym("R")
    i_sym = r._sym("i")
    v_sym = r._sym("v")
    residual = eq.residual.subs({R_sym: 100, i_sym: 0.5, v_sym: 50})
    assert float(residual) == 0.0


# ---------------------------------------------------------------------------
# Example: Capacitor i = C * der(v) — derivative equation
# ---------------------------------------------------------------------------


class _MockCapacitor(BaseComponent):
    def symbolic_equations(self) -> list[SymbolicEquation]:
        v = self._sym("v")
        i = self._sym("i")
        C = self._sym("C")
        return [SymbolicEquation(lhs=i, rhs=C * der(v), provenance="capacitor")]

    def constitutive_equations(self) -> list[str]:
        return ["i = C * dv/dt"]


def test_mock_capacitor_has_derivative():
    c = _MockCapacitor(
        id="c1",
        name="C1",
        domain=ELECTRICAL_DOMAIN,
        ports=[
            Port(id="p1", name="p", domain=ELECTRICAL_DOMAIN, component_id="c1"),
            Port(id="n1", name="n", domain=ELECTRICAL_DOMAIN, component_id="c1"),
        ],
        parameters={"C": 1e-6},
    )
    eqs = c.symbolic_equations()
    assert len(eqs) == 1
    assert eqs[0].has_derivative() is True
    assert "der" in str(eqs[0].rhs)


# ---------------------------------------------------------------------------
# Backward compat: existing mechanical components unaffected
# ---------------------------------------------------------------------------


def test_existing_components_have_empty_symbolic():
    """A BaseComponent subclass that doesn't override symbolic_equations returns []."""
    comp = BaseComponent(
        id="m1",
        name="mass",
        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
        ports=[
            Port(id="p1", name="a", domain=MECHANICAL_TRANSLATIONAL_DOMAIN, component_id="m1"),
        ],
    )
    assert comp.symbolic_equations() == []
