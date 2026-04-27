"""Translational force and position sources.

MSL equivalents:
  - Modelica.Mechanics.Translational.Sources.ConstantForce
  - Modelica.Mechanics.Translational.Sources.Position

Pattern: OnePort pair (add_one_port_pair) + prescribed variable.

Source kind naming follows SIGN_CONVENTION.md §3.3:
  - prescribed_across: fixes across difference (PositionSource → s_rel)
  - prescribed_through: fixes through variable (ForceSource → f)
"""

from __future__ import annotations

from typing import Literal

from src.shared.types.component import BaseComponent
from src.shared.utils.component_helpers import add_one_port_pair
from src.shared.types.equation import SymbolicEquation

import sympy

SourceKind = Literal["prescribed_across", "prescribed_through"]


class TranslationalIdealSource(BaseComponent):
    """Ideal translational source — prescribes position (across) or force (through).

    See SIGN_CONVENTION.md §3.3.
    """

    def __init__(
        self,
        component_id: str,
        *,
        value: float = 1.0,
        source_kind: SourceKind = "prescribed_through",
        name: str = "TranslationalSource",
    ) -> None:
        setup = add_one_port_pair(
            component_id=component_id,
            domain_name="translational",
            port_a_name="flange_a",
            port_b_name="flange_b",
            visual_anchor_a=(0.0, 0.5),
            visual_anchor_b=(1.0, 0.5),
        )

        super().__init__(
            id=component_id,
            name=name,
            domain=setup.ports[0].domain,
            ports=setup.ports,
            parameters={"value": value},
            metadata={"source_kind": source_kind},
            category="source",
            tags=("translational", "source", source_kind),
        )

        self._setup = setup
        self._source_kind = source_kind

    @property
    def source_kind(self) -> SourceKind:
        return self._source_kind

    def symbolic_equations(self) -> list[SymbolicEquation]:
        s = self._setup.symbols
        signal = self._sym("value")

        if self._source_kind == "prescribed_across":
            # Position source: v_diff (= s_rel) = prescribed value
            constitutive = SymbolicEquation(
                lhs=s["v_diff"],
                rhs=signal,
                provenance="prescribed_across",
            )
        else:
            # Force source: through (= f) = prescribed value
            constitutive = SymbolicEquation(
                lhs=s["through"],
                rhs=signal,
                provenance="prescribed_through",
            )

        return self._setup.equations + [constitutive]

    def constitutive_equations(self) -> list[str]:
        val = self.parameters["value"]
        if self._source_kind == "prescribed_across":
            return [f"s_rel_{self.id} = {val}"]
        else:
            return [f"f_{self.id} = {val}"]


# ---------------------------------------------------------------------------
# Convenience factories
# ---------------------------------------------------------------------------


def ForceSource(
    component_id: str,
    *,
    F: float = 1.0,
    name: str = "ForceSource",
) -> TranslationalIdealSource:
    """Create an ideal force source (prescribed_through)."""
    return TranslationalIdealSource(
        component_id,
        value=F,
        source_kind="prescribed_through",
        name=name,
    )


def PositionSource(
    component_id: str,
    *,
    s: float = 0.0,
    name: str = "PositionSource",
) -> TranslationalIdealSource:
    """Create an ideal position source (prescribed_across)."""
    return TranslationalIdealSource(
        component_id,
        value=s,
        source_kind="prescribed_across",
        name=name,
    )
