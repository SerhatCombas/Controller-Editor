"""Symbolic equation primitives for the generic DAE pipeline (T0.3).

This module provides a thin wrapper around sympy that components use
to declare their constitutive laws symbolically.  The existing
string-based ``constitutive_equations()`` path is untouched — both
systems coexist so that migration is incremental.

Usage in a component::

    from src.shared.types.equation import SymbolicEquation, der

    class Resistor(BaseComponent):
        def symbolic_equations(self):
            v, i, R = self._sym('v'), self._sym('i'), self._sym('R')
            return [SymbolicEquation(lhs=v, rhs=R * i, provenance='Ohm')]

    class Capacitor(BaseComponent):
        def symbolic_equations(self):
            v, i, C = self._sym('v'), self._sym('i'), self._sym('C')
            return [SymbolicEquation(lhs=i, rhs=C * der(v), provenance='capacitor')]
"""

from __future__ import annotations

from dataclasses import dataclass, field

import sympy


# ---------------------------------------------------------------------------
# Derivative placeholder — der(x) means dx/dt
# ---------------------------------------------------------------------------

# We use a sympy UndefinedFunction so that der(v) behaves like a symbolic
# atom until the reducer differentiates / linearises.
_der_func = sympy.Function("der")


def der(expr: sympy.Expr) -> sympy.Expr:
    """Symbolic time-derivative wrapper — ``der(v)`` represents dv/dt.

    The generic reducer will recognise ``der(...)`` calls and convert them
    into state-space form.
    """
    return _der_func(expr)


# ---------------------------------------------------------------------------
# SymbolicEquation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SymbolicEquation:
    """A single implicit equation: ``lhs == rhs`` (i.e. lhs − rhs = 0).

    Attributes:
        lhs:        Left-hand side sympy expression.
        rhs:        Right-hand side sympy expression.
        provenance: Human-readable origin tag (e.g. ``'Ohm'``, ``'KCL'``).
    """

    lhs: sympy.Expr
    rhs: sympy.Expr
    provenance: str = ""

    @property
    def residual(self) -> sympy.Expr:
        """Return ``lhs - rhs`` (residual form for implicit DAE solvers)."""
        return sympy.simplify(self.lhs - self.rhs)

    def free_symbols(self) -> set[sympy.Symbol]:
        """All free symbols appearing in this equation."""
        return self.lhs.free_symbols | self.rhs.free_symbols

    def has_derivative(self) -> bool:
        """True if the equation contains ``der(...)`` terms."""
        return bool(self.lhs.atoms(sympy.Function) | self.rhs.atoms(sympy.Function))

    def substitute(self, mapping: dict[sympy.Symbol, sympy.Expr]) -> SymbolicEquation:
        """Return a new equation with symbols substituted."""
        return SymbolicEquation(
            lhs=self.lhs.subs(mapping),
            rhs=self.rhs.subs(mapping),
            provenance=self.provenance,
        )

    def __repr__(self) -> str:
        tag = f" [{self.provenance}]" if self.provenance else ""
        return f"Eq({self.lhs} = {self.rhs}){tag}"
