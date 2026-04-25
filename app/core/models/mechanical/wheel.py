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

    Faz 4d-2a status:
      * No longer inherits from Mass — Wheel is its own first-class
        component. The mass-related logic (port_a / reference_port,
        get_states, constitutive_equations, contribute_mass,
        get_state_contribution) is reproduced inline so behavior is
        bit-for-bit identical to the previous Mass-based implementation
        when mass > 0.
      * road_contact_port (added in 4d-1) is preserved.
      * mass=0.0 still produces a Mass-like component with a zero
        contribution; in Faz 4d-2b that case will switch to "transducer
        mode" (no state, contribute_mass returns []).

    Why split from Mass:
      * Single responsibility: Wheel will gain transducer behavior
        (force output, contact dynamics) that Mass should not carry.
      * Future parameters (rotational_inertia, rolling_resistance) live
        naturally on Wheel, awkwardly on Mass.
      * Lets mass=0 mean "no inertia" cleanly in 4d-2b, without
        spilling that semantics back into Mass.

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
      * contact_mode="kinematic_follow" — wheel always follows the road
        (Mode A). Mode B (dynamic_contact, lift-off mümkün) 4g'de gelir.
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
    # Mass-equivalent dynamics — copied from Mass so simulations of the
    # legacy quarter-car template produce identical results. 4d-2b will
    # introduce a mass=0 short-circuit that switches to transducer mode.
    # ------------------------------------------------------------------

    def get_states(self) -> list[str]:
        return [f"x_{self.id}", f"v_{self.id}"]

    def constitutive_equations(self) -> list[str]:
        m = self.parameters["mass"]
        return [
            f"d/dt x_{self.id} = v_{self.id}",
            f"v_{self.id} = v_{self.id}_a - v_{self.id}_ref",
            f"{m} * d/dt v_{self.id} = f_{self.id}_a - f_{self.id}_ref",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_state_contribution(self) -> StateContribution:
        from app.core.base.state_contribution import StateContribution
        return StateContribution(
            stores_inertial_energy=True,
            stores_potential_energy=False,
            state_kind="inertial",
            dof_count=1,
            owning_port_name="port_a",
        )

    def contribute_mass(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Diagonal mass-matrix entry: M[i,i] += m.

        Behavior is identical to the Mass implementation that Wheel
        previously inherited from. 4d-2b will add a `mass == 0.0`
        short-circuit returning [], which switches the wheel to
        transducer mode (no inertial DOF contribution).
        """
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
