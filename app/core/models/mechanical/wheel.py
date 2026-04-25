from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.base.component import BaseComponent
from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port
from app.core.base.variable import Variable

if TYPE_CHECKING:
    from app.core.base.contribution import MatrixContribution
    from app.core.base.state_contribution import StateContribution


# Allowed values for the new mode parameters. Defined as module-level
# constants so other faz steps (4f Mode A, 4g Mode B) can import these
# instead of duplicating string literals.
WHEEL_CONTACT_MODES = ("kinematic_follow", "dynamic_contact")
WHEEL_OUTPUT_MODES = ("displacement", "force")


class Wheel(BaseComponent):
    """Wheel component — mechanical inertia plus a road-contact interface.

    Faz 4d-2b status (current):
      * mass == 0.0 → transducer mode (state-less passthrough).
        get_states returns [], get_state_contribution reports dof_count=0
        and state_kind="transducer", contribute_mass returns [],
        constitutive_equations returns [] (4f Mode A will populate the
        algebraic passthrough). Pipeline integration (dae_reducer,
        equation_builder) is deferred to 4d-2c.
      * mass > 0.0 → Mass-equivalent behavior, bit-for-bit identical to
        the pre-4d-2b implementation. Existing quarter-car simulations
        are unaffected.
      * road_contact_port (added in 4d-1) is preserved.

    Faz 4d-2a status (preserved):
      * No longer inherits from Mass — Wheel is its own first-class
        BaseComponent. Mass-related logic was reproduced inline.

    Why split from Mass:
      * Single responsibility: Wheel will gain transducer behavior
        (force output, contact dynamics) that Mass should not carry.
      * Future parameters (rotational_inertia, rolling_resistance) live
        naturally on Wheel, awkwardly on Mass.
      * mass=0 means "no inertia" cleanly, without spilling that
        semantics back into Mass.

    Parameter philosophy (from 4d-1, unchanged):
      * mass is required: kullanıcı bilinçli bir karar olarak verir.
        "Kütlesiz wheel istiyorum" diyenler `mass=0.0` yazar.
      * Diğer fiziksel parametreler default değerlere sahip (kullanıcı
        UI'dan yeni Wheel sürüklediğinde gerçekçi bir tekerlek elde eder).
      * Her bir efekt iki yolla devre dışı bırakılabilir: parametreyi
        0.0'a çekmek veya (kontak kuvveti için) `disable_contact_force=True`.
        Flag, kullanıcının tuning'ini kaybetmeden açıp kapatma imkanı verir.

    Defaults rationale (numerical parity):
      * contact_stiffness=200000.0, contact_damping=500.0 — typical car
        tire values. New Wheel instances start with realistic defaults;
        the legacy quarter-car template will explicitly pass 180000.0/0.0
        in Faz 4e to preserve numerical parity with the deprecated
        tire_stiffness Spring.
      * contact_mode="kinematic_follow" (Mode A) — wheel rigidly follows
        the road; the contact-force law is the linear elastic
        f_road = k*x_rel + c*(v_road - v).
        contact_mode="dynamic_contact" (Mode B, Faz 4g) — same RHS but
        clamped to non-negative via max(0, ...), so the tire can leave
        the ground when the rebound force would otherwise pull the wheel
        downward against the road. Mode A is the default and the only
        one whose linearization in the symbolic state-space is exact;
        Mode B silently linearizes to its always-in-contact form for
        the symbolic backend (4h surfaces this with explicit warnings).
      * output_mode="displacement" — preserves the current behavior where
        the wheel feeds the rest of the system as a displacement source
        (matches the way RandomRoad currently couples through tire_stiffness).
        4f Mode A'da "force" alternatifi de implement edilecek.
    """

    def __init__(
        self,
        component_id: str,
        *,
        mass: float,
        radius: float = 0.32,
        contact_mode: str = "kinematic_follow",
        contact_stiffness: float = 200000.0,
        contact_damping: float = 500.0,
        disable_contact_force: bool = False,
        rotational_inertia: float = 1.0,
        rolling_resistance: float = 0.015,
        output_mode: str = "displacement",
        name: str = "Wheel",
    ) -> None:
        if contact_mode not in WHEEL_CONTACT_MODES:
            raise ValueError(
                f"Unknown contact_mode {contact_mode!r}; "
                f"expected one of {WHEEL_CONTACT_MODES}."
            )
        if output_mode not in WHEEL_OUTPUT_MODES:
            raise ValueError(
                f"Unknown output_mode {output_mode!r}; "
                f"expected one of {WHEEL_OUTPUT_MODES}."
            )
        # Build the full port set in one super().__init__() call to mirror
        # the structure that Mass built and 4d-1 extended. port_a and
        # reference_port replicate Mass exactly (same names, variables,
        # domain). road_contact_port is the addition from 4d-1.
        super().__init__(
            id=component_id,
            name=name,
            domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
            ports=[
                Port(
                    id=f"{component_id}.port_a",
                    name="port_a",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_a",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_a",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                ),
                Port(
                    id=f"{component_id}.reference_port",
                    name="reference_port",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_ref",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_ref",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                ),
                Port(
                    id=f"{component_id}.road_contact_port",
                    name="road_contact_port",
                    domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                    component_id=component_id,
                    across_var=Variable(
                        name=f"v_{component_id}_road",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="across",
                    ),
                    through_var=Variable(
                        name=f"f_{component_id}_road",
                        domain=MECHANICAL_TRANSLATIONAL_DOMAIN,
                        kind="through",
                    ),
                    required=False,
                ),
            ],
            parameters={
                "mass": mass,
                "radius": radius,
                "contact_mode": contact_mode,
                "contact_stiffness": float(contact_stiffness),
                "contact_damping": float(contact_damping),
                "disable_contact_force": bool(disable_contact_force),
                # Rotational degrees of freedom — stored for future longitudinal
                # vehicle dynamics fazları; not yet wired into any equation.
                "rotational_inertia": float(rotational_inertia),
                "rolling_resistance": float(rolling_resistance),
                "output_mode": output_mode,
            },
            initial_conditions={"x": 0.0, "v": 0.0},
        )

    # ------------------------------------------------------------------
    # Dynamics — Mass-equivalent when mass > 0, transducer when mass == 0.
    #
    # Faz 4d-2b introduced the mass==0 branches: in transducer mode the
    # wheel owns no integration state and contributes nothing to the mass
    # matrix. Constitutive equations are returned empty for now — Faz 4f
    # (Mode A) will fill them with the algebraic passthrough relating
    # road_contact_port to port_a once that port is wired up.
    #
    # The mass>0 branches are bit-for-bit identical to the previous
    # Mass-based implementation so the legacy quarter-car template
    # continues to produce identical simulation output.
    # ------------------------------------------------------------------

    def _is_transducer(self) -> bool:
        """Whether this wheel currently behaves as a state-less transducer.

        Centralised here so all four polymorphic methods agree on the same
        criterion: mass exactly zero. The user expresses "no inertia" by
        passing mass=0.0 deliberately (mass is a required keyword arg).
        """
        return float(self.parameters["mass"]) == 0.0

    def _has_road_contact(self) -> bool:
        """Whether the road_contact_port is wired to a node.

        When True, the wheel additionally tracks a relative-displacement
        state x_rel_<id>_road (mass>0 path) and supplies a contact-force
        law. When False, the wheel behaves like a plain inertial Mass.
        """
        return self.port("road_contact_port").node_id is not None

    def get_states(self) -> list[str]:
        if self._is_transducer():
            return []
        # Mass>0: always two absolute-mechanical states (position + velocity).
        states = [f"x_{self.id}", f"v_{self.id}"]
        # Faz 4f-1 — When road_contact_port is wired up, the wheel also owns
        # a relative-displacement integrator x_rel_<id>_road tracking the
        # road-relative displacement. This is the same pattern Spring uses
        # (x_rel_<id>) and is the mechanism by which the contact stiffness
        # contribution actually lands in the reduced K matrix: a relative
        # state lets the reducer recognize "this DoF stores potential energy
        # and the road port is its other side".
        if self._has_road_contact():
            states.append(f"x_rel_{self.id}_road")
        return states

    def constitutive_equations(self) -> list[str]:
        if self._is_transducer():
            # Transducer mode: state-less algebraic passthrough.
            # Faz 4f-2 (mass=0) will populate the algebraic relation between
            # road_contact_port and port_a here. Until then we return [],
            # which keeps the behavior outside the (still pipeline-pending)
            # transducer path unchanged.
            return []
        m = self.parameters["mass"]
        # Mass>0 path. Two cases below: with vs without an active road
        # contact. The without-road-contact branch is bit-for-bit identical
        # to the pre-4f-1 implementation so the legacy quarter-car template
        # (tire_stiffness Spring still in place) stays at perfect parity.
        equations = [
            f"d/dt x_{self.id} = v_{self.id}",
            f"v_{self.id} = v_{self.id}_a - v_{self.id}_ref",
        ]
        if self._has_road_contact():
            # Faz 4f-1 — Active road contact (Mode A: kinematic_follow +
            # linear elastic). The wheel takes on the additional role of a
            # relative-displacement integrator between port_a and the road.
            #
            # State 1: x_<id>            (absolute wheel position)
            # State 2: v_<id>            (absolute wheel velocity)
            # State 3: x_rel_<id>_road   (road-relative displacement)
            #
            # The relative state's derivative is the velocity difference
            # across the contact port (mirrors how Spring tracks port_a
            # vs port_b). x_rel grows positive when the road outpaces the
            # wheel upward (road rising faster than wheel rises) — the
            # tire compresses, contact force on the wheel goes positive.
            #
            # Newton: m*dv/dt = f_a - f_ref + f_road
            # Mode A (kinematic_follow): f_road = k*x_rel + c*(v_road - v)
            # Mode B (dynamic_contact, Faz 4g): same RHS wrapped in
            #   max(0, ...) for one-sided contact (lift-off). When the
            #   wheel rises faster than the road, the rebound RHS would go
            #   negative — Mode B clamps it to zero, modeling tire leaving
            #   the ground. Mode A always sticks to the road.
            #
            # Mode B note for symbolic backends: the max(0, ...) wrapper
            # makes the constitutive law non-linear, but the dae_reducer
            # builds K/C matrices from contact_stiffness/contact_damping
            # parameters directly (string-based Wheel branch), not from
            # the constitutive equation. This means the reduced state-
            # space silently linearizes Mode B around a "wheel always in
            # contact" assumption — fine for small perturbations, but
            # masks lift-off. Faz 4h will surface this with explicit
            # warnings on the symbolic path.
            k = self.parameters["contact_stiffness"]
            c = self.parameters["contact_damping"]
            contact_law_rhs = (
                f"{k} * x_rel_{self.id}_road "
                f"+ {c} * (v_{self.id}_road - v_{self.id})"
            )
            if self.parameters["contact_mode"] == "dynamic_contact":
                contact_law = f"f_{self.id}_road = max(0, {contact_law_rhs})"
            else:
                # contact_mode == "kinematic_follow" (Mode A, default)
                contact_law = f"f_{self.id}_road = {contact_law_rhs}"
            equations.extend([
                f"d/dt x_rel_{self.id}_road = v_{self.id}_road - v_{self.id}",
                f"{m} * d/dt v_{self.id} = "
                f"f_{self.id}_a - f_{self.id}_ref + f_{self.id}_road",
                contact_law,
            ])
        else:
            equations.append(
                f"{m} * d/dt v_{self.id} = f_{self.id}_a - f_{self.id}_ref"
            )
        return equations

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_state_contribution(self) -> StateContribution:
        from app.core.base.state_contribution import StateContribution
        if self._is_transducer():
            # Transducer wheel owns no DoF; signal this via state_kind and
            # dof_count=0. The reducer/equation-builder pipeline does not
            # yet act on this (4d-2c will), but components and tests can
            # already inspect the contribution and reason about transducer
            # wheels at the API level.
            return StateContribution(
                stores_inertial_energy=False,
                stores_potential_energy=False,
                state_kind="transducer",
                dof_count=0,
                owning_port_name=None,
            )
        return StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )

    def contribute_mass(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Diagonal mass-matrix entry: M[i,i] += m.

        In transducer mode (mass == 0) returns [] — the wheel does not
        introduce any inertial DOF, so it cannot contribute to the mass
        matrix. The mass>0 path matches the prior Mass-inherited
        implementation bit-for-bit.
        """
        if self._is_transducer():
            return []
        import sympy
        from app.core.base.contribution import MatrixContribution

        port = self.port("port_a")
        if port.node_id is None or port.node_id not in node_index:
            return []

        i = node_index[port.node_id]
        m_sym = sympy.Symbol(f"m_{self.id}")
        return [
            MatrixContribution(
                row=i,
                col=i,
                value=m_sym,
                component_id=self.id,
                contribution_kind="mass",
                connected_node_ids=(port.node_id,),
                physical_meaning=(
                    f"Inertial resistance of {self.name} (m={self.parameters['mass']} kg) at DOF {i}"
                ),
                equation_reference=f"M[{i},{i}] += m_{self.id}",
            )
        ]
