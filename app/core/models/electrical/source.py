"""Ideal voltage and current sources.

MSL equivalents:
  - Modelica.Electrical.Analog.Sources.ConstantVoltage
  - Modelica.Electrical.Analog.Sources.ConstantCurrent

Pattern: OnePort pair (add_one_port_pair) + prescribed variable.

Source kind naming follows SIGN_CONVENTION.md §3.3:
  - prescribed_across: fixes across difference (VoltageSource)
  - prescribed_through: fixes through variable (CurrentSource)
"""

from __future__ import annotations

from typing import Literal

from app.core.base.component import BaseComponent
from app.core.base.component_helpers import add_one_port_pair
from app.core.base.equation import SymbolicEquation

import sympy

SourceKind = Literal["prescribed_across", "prescribed_through"]


class IdealSource(BaseComponent):
    """Ideal source that prescribes either across (voltage) or through (current).

    Parameters:
        value: The prescribed constant value.
        source_kind: 'prescribed_across' or 'prescribed_through'.

    See SIGN_CONVENTION.md §3.3.
    """

    def __init__(
        self,
        component_id: str,
        *,
        value: float = 1.0,
        source_kind: SourceKind = "prescribed_across",
        name: str = "IdealSource",
    ) -> None:
        setup = add_one_port_pair(
            component_id=component_id,
            domain_name="electrical",
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
            tags=("electrical", "source", source_kind),
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
            # Voltage source: v_diff = V_source
            constitutive = SymbolicEquation(
                lhs=s["v_diff"],
                rhs=signal,
                provenance="prescribed_across",
            )
        else:
            # Current source: through = I_source
            constitutive = SymbolicEquation(
                lhs=s["through"],
                rhs=signal,
                provenance="prescribed_through",
            )

        return self._setup.equations + [constitutive]

    def constitutive_equations(self) -> list[str]:
        val = self.parameters["value"]
        if self._source_kind == "prescribed_across":
            return [f"v_{self.id} = {val}"]
        else:
            return [f"i_{self.id} = {val}"]


# ---------------------------------------------------------------------------
# Convenience factories
# ---------------------------------------------------------------------------


def VoltageSource(
    component_id: str,
    *,
    V: float = 1.0,
    name: str = "VoltageSource",
) -> IdealSource:
    """Create an ideal voltage source (prescribed_across)."""
    return IdealSource(
        component_id,
        value=V,
        source_kind="prescribed_across",
        name=name,
    )


def CurrentSource(
    component_id: str,
    *,
    I: float = 1.0,
    name: str = "CurrentSource",
) -> IdealSource:
    """Create an ideal current source (prescribed_through)."""
    return IdealSource(
        component_id,
        value=I,
        source_kind="prescribed_through",
        name=name,
    )
