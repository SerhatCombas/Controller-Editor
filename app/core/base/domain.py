from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Legacy Domain (backward-compatible — do NOT remove)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Domain:
    name: str
    across_variable: str
    through_variable: str


MECHANICAL_TRANSLATIONAL_DOMAIN = Domain(
    name="mechanical_translational",
    across_variable="velocity",
    through_variable="force",
)

ELECTRICAL_DOMAIN = Domain(
    name="electrical",
    across_variable="voltage",
    through_variable="current",
)


# ---------------------------------------------------------------------------
# DomainSpec — enriched domain metadata (MSL-derived)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DomainSpec:
    """Rich domain descriptor derived from MSL interface patterns.

    Two distinct variable pairs are tracked:

    **Connector variables (across/through)** — what lives in the Modelica
    connector.  Used for topology (connection sets, flattening).
    - Electrical: across=v (voltage), through=i (current)
    - Translational: across=s (position), through=f (force)
    - Rotational: across=phi (angle), through=tau (torque)

    **Power-conjugate variables (effort/flow)** — the pair whose product
    is *always* power (W).  Used by the reducer and analysis.
    - Electrical: effort=v, flow=i  →  v·i = W
    - Translational: effort=f, flow=v  →  f·v = W  (note: flow = der(across))
    - Rotational: effort=tau, flow=omega  →  tau·omega = W

    For electrical, across≡effort and through≡flow.  For mechanical
    domains, effort and flow are DIFFERENT from across and through —
    flow = der(across).  This distinction is critical for the reducer.

    Attributes:
        name:         Canonical domain key.
        across_var:   Connector across variable symbol (e.g. 'v', 's', 'phi').
        through_var:  Connector through variable symbol (e.g. 'i', 'f', 'tau').
        across_unit:  SI unit for across variable.
        through_unit: SI unit for through variable.
        effort_var:   Power-conjugate effort symbol (effort × flow = power).
        flow_var:     Power-conjugate flow symbol.
        effort_unit:  SI unit for effort variable.
        flow_unit:    SI unit for flow variable.
        power_order:  Derivative order: 0 if effort=across (electrical),
                      1 if flow=der(across) (mechanical).
        color:        Hex color for UI rendering.
        flange_kinds: Port-kind names (positive/negative) or (a/b).
    """

    name: str
    # Connector variables (Modelica semantics)
    across_var: str
    through_var: str
    across_unit: str
    through_unit: str
    # Power-conjugate variables (bond-graph semantics)
    effort_var: str
    flow_var: str
    effort_unit: str
    flow_unit: str
    power_order: int          # 0 = effort≡across, 1 = flow=der(across)
    # UI / visual
    color: str
    flange_kinds: tuple[str, str]

    # -- bridge to legacy Domain ------------------------------------------

    def to_domain(self) -> Domain:
        """Convert to a legacy Domain instance for backward compatibility.

        Legacy Domain convention:
          electrical:    across_variable='voltage',  through_variable='current'
          translational: across_variable='velocity', through_variable='force'

        Note the legacy translational mapping uses velocity (=flow) as
        'across' and force (=effort) as 'through'.  This does NOT match
        Modelica connector semantics (across=position, through=force)
        but it IS what the existing codebase expects.  We preserve it.
        """
        # Map from DomainSpec to legacy Domain long names
        # Key = (domain_name) → (across_variable, through_variable)
        _legacy_map: dict[str, tuple[str, str]] = {
            "electrical":    ("voltage", "current"),
            "translational": ("velocity", "force"),
            "rotational":    ("angular_velocity", "torque"),
            "thermal":       ("temperature", "heat_flow"),
        }
        if self.name in _legacy_map:
            across, through = _legacy_map[self.name]
        else:
            across = self.across_var
            through = self.through_var
        return Domain(
            name=self.name,
            across_variable=across,
            through_variable=through,
        )


# ---------------------------------------------------------------------------
# DOMAIN_SPECS registry
# ---------------------------------------------------------------------------

DOMAIN_SPECS: dict[str, DomainSpec] = {
    # ---------------------------------------------------------------
    # Electrical: across≡effort (voltage), through≡flow (current)
    # Power = v · i  (power_order=0, no derivative needed)
    # ---------------------------------------------------------------
    "electrical": DomainSpec(
        name="electrical",
        across_var="v",    through_var="i",
        across_unit="V",   through_unit="A",
        effort_var="v",    flow_var="i",
        effort_unit="V",   flow_unit="A",
        power_order=0,
        color="#0000FF",
        flange_kinds=("positive", "negative"),
    ),
    # ---------------------------------------------------------------
    # Translational: across=position(s), through=force(f)
    # BUT effort=force(f), flow=velocity(v=ds/dt)
    # Power = f · v  (power_order=1, flow=der(across))
    # ---------------------------------------------------------------
    "translational": DomainSpec(
        name="translational",
        across_var="s",    through_var="f",
        across_unit="m",   through_unit="N",
        effort_var="f",    flow_var="v",
        effort_unit="N",   flow_unit="m/s",
        power_order=1,
        color="#007F00",
        flange_kinds=("a", "b"),
    ),
    # ---------------------------------------------------------------
    # Rotational: across=angle(phi), through=torque(tau)
    # effort=torque(tau), flow=angular_velocity(omega=dphi/dt)
    # Power = tau · omega  (power_order=1)
    # ---------------------------------------------------------------
    "rotational": DomainSpec(
        name="rotational",
        across_var="phi",  through_var="tau",
        across_unit="rad", through_unit="N·m",
        effort_var="tau",  flow_var="omega",
        effort_unit="N·m", flow_unit="rad/s",
        power_order=1,
        color="#FF8C00",
        flange_kinds=("a", "b"),
    ),
    # ---------------------------------------------------------------
    # Thermal: across=temperature(T), through=heat_flow(Phi)
    # Thermal is NOT a true power domain (T·Phi ≠ power in general),
    # but we set effort=T, flow=Phi for structural consistency.
    # power_order=0 (no derivative relationship).
    # ---------------------------------------------------------------
    "thermal": DomainSpec(
        name="thermal",
        across_var="T",    through_var="Phi",
        across_unit="K",   through_unit="W",
        effort_var="T",    flow_var="Phi",
        effort_unit="K",   flow_unit="W",
        power_order=0,
        color="#FF0000",
        flange_kinds=("a", "b"),
    ),
}


def get_domain_spec(name: str) -> DomainSpec:
    """Look up a DomainSpec by canonical name. Raises KeyError if unknown."""
    return DOMAIN_SPECS[name]
