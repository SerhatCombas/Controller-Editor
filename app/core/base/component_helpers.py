"""MSL-derived helper methods for component port/equation setup (T0.4).

These helpers implement the three structural patterns discovered in the
Modelica Standard Library analysis:

1. **OnePort** (add_one_port) — single-port reference component (Ground/Fixed)
2. **OnePort pair** (add_one_port_pair) — 2-port with KCL + across_diff (R, C, L, Spring, Damper)
3. **Rigid pair** (add_rigid_pair) — 2-port WITHOUT KCL (Mass — Newton's law written by component)

Each helper:
- Creates Port objects with direction_hint from DomainSpec
- Generates SymbolicEquation objects (sympy-based)
- Stores them on the component for the generic reducer to consume
- Is fully opt-in: existing components don't need to use them

Usage::

    class Resistor(BaseComponent):
        def setup(self):
            ports, eqs, syms = add_one_port_pair(self, 'electrical')
            R = self._sym('R')
            eqs.append(SymbolicEquation(lhs=syms['v_diff'], rhs=R * syms['through'], provenance='Ohm'))
            return ports, eqs
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy

from app.core.base.domain import DomainSpec, get_domain_spec
from app.core.base.equation import SymbolicEquation, der
from app.core.base.port import Port


# ---------------------------------------------------------------------------
# Return type for helpers
# ---------------------------------------------------------------------------


@dataclass
class PortSetup:
    """Result of a helper method — ports, topology equations, and named symbols."""

    ports: list[Port]
    equations: list[SymbolicEquation]
    symbols: dict[str, sympy.Symbol]


# ---------------------------------------------------------------------------
# 1. add_one_port — single reference port (Ground, Fixed)
# ---------------------------------------------------------------------------


def add_one_port(
    component_id: str,
    domain_name: str,
    port_name: str = "port",
    direction_hint: str | None = None,
    visual_anchor: tuple[float, float] | None = None,
) -> PortSetup:
    """Create a single-port reference component setup.

    Used by Ground (electrical) and Fixed (mechanical).
    No equations generated — the reference constraint (v=0 or s=0)
    is the component's own constitutive law.
    """
    spec = get_domain_spec(domain_name)
    domain = spec.to_domain()

    hint = direction_hint or spec.flange_kinds[0]

    port = Port(
        id=f"{component_id}__{port_name}",
        name=port_name,
        domain=domain,
        component_id=component_id,
        direction_hint=hint,
        visual_anchor=visual_anchor,
    )

    # Symbol for the port's across variable
    across = sympy.Symbol(f"{component_id}__{port_name}_{spec.across_var}", real=True)

    return PortSetup(
        ports=[port],
        equations=[],  # Reference constraint written by component
        symbols={"across": across},
    )


# ---------------------------------------------------------------------------
# 2. add_one_port_pair — 2-port with KCL + across_diff
#    (Resistor, Capacitor, Inductor, Spring, Damper)
# ---------------------------------------------------------------------------


def add_one_port_pair(
    component_id: str,
    domain_name: str,
    port_a_name: str = "port_a",
    port_b_name: str = "port_b",
    visual_anchor_a: tuple[float, float] | None = None,
    visual_anchor_b: tuple[float, float] | None = None,
) -> PortSetup:
    """Create a 2-port OnePort pair with KCL and across-difference.

    MSL pattern: ``PartialCompliant`` / ``OnePort``

    Sign convention follows MSL exactly (see SIGN_CONVENTION.md):

    **Electrical** (power_order=0):
      - port_a = positive, port_b = negative
      - ``v_diff = v_a - v_b``  (= v_positive - v_negative, MSL: v = p.v - n.v)
      - ``through = i_a``       (current INTO positive port, MSL: i = p.i)

    **Translational** (power_order=1):
      - port_a = flange_a, port_b = flange_b
      - ``v_diff = v_b - v_a``  (= s_b - s_a, MSL: s_rel = flange_b.s - flange_a.s)
      - ``through = i_b``       (force at flange_b, MSL: f = flange_b.f)

    Both obey KCL: ``0 = i_a + i_b`` (through balance).

    The component adds its own constitutive law using ``v_diff`` and ``through``:
      - Resistor: v_diff = R × through
      - Spring:   through = k × v_diff
    """
    spec = get_domain_spec(domain_name)
    domain = spec.to_domain()

    port_a = Port(
        id=f"{component_id}__{port_a_name}",
        name=port_a_name,
        domain=domain,
        component_id=component_id,
        direction_hint=spec.flange_kinds[0],  # positive / a
        visual_anchor=visual_anchor_a,
    )
    port_b = Port(
        id=f"{component_id}__{port_b_name}",
        name=port_b_name,
        domain=domain,
        component_id=component_id,
        direction_hint=spec.flange_kinds[1],  # negative / b
        visual_anchor=visual_anchor_b,
    )

    # Named symbols
    v_a = sympy.Symbol(f"{component_id}__{port_a_name}_{spec.across_var}", real=True)
    v_b = sympy.Symbol(f"{component_id}__{port_b_name}_{spec.across_var}", real=True)
    i_a = sympy.Symbol(f"{component_id}__{port_a_name}_{spec.through_var}", real=True)
    i_b = sympy.Symbol(f"{component_id}__{port_b_name}_{spec.through_var}", real=True)
    v_diff = sympy.Symbol(f"{component_id}__v_diff", real=True)
    through = sympy.Symbol(f"{component_id}__through", real=True)

    # Sign convention depends on domain (see SIGN_CONVENTION.md §3.1)
    if spec.power_order == 0:
        # Electrical: v_diff = v_p - v_n, through = i_p (into positive)
        across_diff_eq = SymbolicEquation(
            lhs=v_diff, rhs=v_a - v_b, provenance="across_diff"
        )
        through_alias_eq = SymbolicEquation(
            lhs=through, rhs=i_a, provenance="through_alias"
        )
    else:
        # Mechanical: v_diff = v_b - v_a (= s_rel), through = i_b (at flange_b)
        across_diff_eq = SymbolicEquation(
            lhs=v_diff, rhs=v_b - v_a, provenance="across_diff"
        )
        through_alias_eq = SymbolicEquation(
            lhs=through, rhs=i_b, provenance="through_alias"
        )

    equations = [
        across_diff_eq,
        # KCL: i_a + i_b = 0 (same for all domains)
        SymbolicEquation(lhs=i_a + i_b, rhs=sympy.Integer(0), provenance="KCL"),
        through_alias_eq,
    ]

    symbols = {
        "v_a": v_a,
        "v_b": v_b,
        "i_a": i_a,
        "i_b": i_b,
        "v_diff": v_diff,
        "through": through,
    }

    return PortSetup(ports=[port_a, port_b], equations=equations, symbols=symbols)


# ---------------------------------------------------------------------------
# 3. add_rigid_pair — 2-port WITHOUT KCL (Mass)
#    Newton's law (m·a = ΣF) written by the component, not skeleton
# ---------------------------------------------------------------------------


def add_rigid_pair(
    component_id: str,
    domain_name: str,
    port_a_name: str = "port_a",
    port_b_name: str = "port_b",
    visual_anchor_a: tuple[float, float] | None = None,
    visual_anchor_b: tuple[float, float] | None = None,
) -> PortSetup:
    """Create a 2-port rigid pair WITHOUT KCL.

    MSL pattern: ``PartialRigid``

    This is the critical structural difference from OnePort:
    - Both ports share the same across variable (v_a = v_b = v_center)
    - NO through-balance (KCL) equation — the component writes Newton's
      law itself: ``m * der(v) = f_a + f_b``

    Generates one topology equation:
    - ``v_a = v_b``  (rigid coupling)

    The component adds its own dynamics (e.g., ``m * a = f_a + f_b``).
    """
    spec = get_domain_spec(domain_name)
    domain = spec.to_domain()

    port_a = Port(
        id=f"{component_id}__{port_a_name}",
        name=port_a_name,
        domain=domain,
        component_id=component_id,
        direction_hint=spec.flange_kinds[0],
        visual_anchor=visual_anchor_a,
    )
    port_b = Port(
        id=f"{component_id}__{port_b_name}",
        name=port_b_name,
        domain=domain,
        component_id=component_id,
        direction_hint=spec.flange_kinds[1],
        visual_anchor=visual_anchor_b,
    )

    # Named symbols
    v_a = sympy.Symbol(f"{component_id}__{port_a_name}_{spec.across_var}", real=True)
    v_b = sympy.Symbol(f"{component_id}__{port_b_name}_{spec.across_var}", real=True)
    f_a = sympy.Symbol(f"{component_id}__{port_a_name}_{spec.through_var}", real=True)
    f_b = sympy.Symbol(f"{component_id}__{port_b_name}_{spec.through_var}", real=True)
    v_center = sympy.Symbol(f"{component_id}__v_center", real=True)

    equations = [
        # Rigid coupling: v_a = v_center
        SymbolicEquation(lhs=v_a, rhs=v_center, provenance="rigid_a"),
        # Rigid coupling: v_b = v_center
        SymbolicEquation(lhs=v_b, rhs=v_center, provenance="rigid_b"),
        # NOTE: NO KCL here! Mass writes m*a = f_a + f_b itself.
    ]

    symbols = {
        "v_a": v_a,
        "v_b": v_b,
        "f_a": f_a,
        "f_b": f_b,
        "v_center": v_center,
    }

    return PortSetup(ports=[port_a, port_b], equations=equations, symbols=symbols)
