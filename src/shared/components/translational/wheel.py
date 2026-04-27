from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.types.component import BaseComponent
from src.shared.types.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from src.shared.types.port import Port
from src.shared.types.variable import Variable

if TYPE_CHECKING:
    from src.shared.types.contribution import MatrixContribution
    from src.shared.types.state_contribution import StateContribution


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
        from src.shared.types.state_contribution import StateContribution
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
        from src.shared.types.contribution import MatrixContribution

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

    def contribute_stiffness(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Faz 4f-1.5 — Polymorphic K-matrix branch for the road-contact port.

        Mirrors Spring.contribute_stiffness for the (port_a ↔ road_contact_port)
        pair, with coefficient = contact_stiffness. This is the polymorphic
        twin of the string-based dae_reducer Wheel branch added in 4f-1; the
        legacy DAEReducer reads `parameters["contact_stiffness"]` directly,
        the PolymorphicDAEReducer reads via this method. Without this
        polymorphic implementation the symbolic backends running under
        DEFAULT_FLAGS (parity_mode=PRIMARY) silently lose the tire stiffness
        contribution when the template's tire_stiffness Spring is removed
        and replaced by Wheel.road_contact_port.

        Returns [] when:
          * The wheel is in transducer mode (mass==0). Faz 4j will revisit
            this once the algebraic-passthrough story for transducers is
            in place.
          * road_contact_port is unconnected (free wheel — no contact law
            emitted, nothing to contribute to K).
          * Contact is disabled via disable_contact_force (tuning flag).

        For an active road contact we emit the standard graph-Laplacian
        4-entry pattern (i,i / j,j / i,j / j,i) just like Spring does. When
        the road_contact_port maps to a displacement-source node (e.g.
        RandomRoad), the PolymorphicDAEReducer's extended_index will return
        a negative sentinel for that port: the off-diagonal coupling entry
        then ends up in the input_matrix (B) rather than K, which is the
        correct way to drive the wheel from a road profile. This mirrors
        how Spring's `tire_stiffness ↔ road_source` branch worked
        bit-for-bit pre-4j-1.
        """
        if self._is_transducer():
            return []
        if self.parameters.get("disable_contact_force", False):
            return []
        port_a = self.port("port_a")
        port_road = self.port("road_contact_port")
        if port_a.node_id is None or port_road.node_id is None:
            return []

        import sympy
        from src.shared.types.contribution import MatrixContribution

        i = node_index.get(port_a.node_id)
        j = node_index.get(port_road.node_id)

        # If the road_contact_port's node is not in the (extended) node
        # index — neither an active DOF nor a displacement-source sentinel —
        # then the port is essentially "wired to nothing meaningful".
        # CanvasCompiler may have allocated a fresh atomic node for an
        # unconnected required=False port, but with no other component
        # sharing that node there is no physical path for the contact
        # branch. Behave like an unwired road_contact_port and emit no
        # contribution (matches `_has_road_contact() == False` semantics
        # at the polymorphic-API layer).
        if j is None:
            return []

        k_sym = sympy.Symbol(f"k_contact_{self.id}")
        k_val = self.parameters["contact_stiffness"]
        node_ids = (port_a.node_id, port_road.node_id)
        contribs: list[MatrixContribution] = []

        # Diagonal entries (only emit for active DOFs — i.e. row/col >= 0).
        if i is not None and i >= 0:
            contribs.append(MatrixContribution(
                row=i, col=i, value=k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-stiffness of {self.name} road contact "
                    f"(contact_stiffness={k_val} N/m) at DOF {i}"
                ),
                equation_reference=f"K[{i},{i}] += k_contact_{self.id}",
            ))
        if j is not None and j >= 0:
            contribs.append(MatrixContribution(
                row=j, col=j, value=k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-stiffness of {self.name} road contact "
                    f"(contact_stiffness={k_val} N/m) at DOF {j}"
                ),
                equation_reference=f"K[{j},{j}] += k_contact_{self.id}",
            ))

        # Off-diagonal coupling. j may be a negative sentinel (road as a
        # displacement source); the reducer uses that sentinel to route
        # this entry to the input_matrix instead of K.
        if i is not None and j is not None:
            contribs.append(MatrixContribution(
                row=i, col=j, value=-k_sym,
                component_id=self.id,
                contribution_kind="stiffness",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling stiffness of {self.name} road contact "
                    f"between port_a (DOF {i}) and road_contact_port (col {j})"
                ),
                equation_reference=f"K[{i},{j}] -= k_contact_{self.id}",
            ))
            # Symmetric entry j,i — only emitted when j is an active DOF.
            # When j is a negative displacement-source sentinel there is no
            # row j to write into, so we skip (matches Spring's behavior).
            if j >= 0 and i >= 0:
                contribs.append(MatrixContribution(
                    row=j, col=i, value=-k_sym,
                    component_id=self.id,
                    contribution_kind="stiffness",
                    connected_node_ids=node_ids,
                    physical_meaning=(
                        f"Coupling stiffness of {self.name} road contact "
                        f"between road_contact_port (DOF {j}) and port_a (DOF {i})"
                    ),
                    equation_reference=f"K[{j},{i}] -= k_contact_{self.id}",
                ))

        return contribs

    def contribute_damping(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Faz 4f-1.5 — Polymorphic D-matrix branch for the road-contact port.

        Mirror of contribute_stiffness with coefficient=contact_damping. See
        contribute_stiffness for the why; this method exists for the same
        reason. When contact_damping=0 (the legacy default for the deleted
        tire_stiffness Spring) we still emit the four entries with value=0,
        so that downstream traceability tools see the structural connectivity
        — a 0-coefficient Damper-equivalent is not the same thing as no
        connection at all. (Spring/Damper do the same.)
        """
        if self._is_transducer():
            return []
        if self.parameters.get("disable_contact_force", False):
            return []
        port_a = self.port("port_a")
        port_road = self.port("road_contact_port")
        if port_a.node_id is None or port_road.node_id is None:
            return []

        import sympy
        from src.shared.types.contribution import MatrixContribution

        i = node_index.get(port_a.node_id)
        j = node_index.get(port_road.node_id)

        # Symmetric to contribute_stiffness: if road_contact_port's node
        # is not in the extended index, behave as if the port is unwired
        # and emit nothing.
        if j is None:
            return []

        c_sym = sympy.Symbol(f"c_contact_{self.id}")
        c_val = self.parameters["contact_damping"]
        node_ids = (port_a.node_id, port_road.node_id)
        contribs: list[MatrixContribution] = []

        if i is not None and i >= 0:
            contribs.append(MatrixContribution(
                row=i, col=i, value=c_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-damping of {self.name} road contact "
                    f"(contact_damping={c_val} N·s/m) at DOF {i}"
                ),
                equation_reference=f"D[{i},{i}] += c_contact_{self.id}",
            ))
        if j is not None and j >= 0:
            contribs.append(MatrixContribution(
                row=j, col=j, value=c_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Self-damping of {self.name} road contact "
                    f"(contact_damping={c_val} N·s/m) at DOF {j}"
                ),
                equation_reference=f"D[{j},{j}] += c_contact_{self.id}",
            ))

        if i is not None and j is not None:
            contribs.append(MatrixContribution(
                row=i, col=j, value=-c_sym,
                component_id=self.id,
                contribution_kind="damping",
                connected_node_ids=node_ids,
                physical_meaning=(
                    f"Coupling damping of {self.name} road contact "
                    f"between port_a (DOF {i}) and road_contact_port (col {j})"
                ),
                equation_reference=f"D[{i},{j}] -= c_contact_{self.id}",
            ))
            if j >= 0 and i >= 0:
                contribs.append(MatrixContribution(
                    row=j, col=i, value=-c_sym,
                    component_id=self.id,
                    contribution_kind="damping",
                    connected_node_ids=node_ids,
                    physical_meaning=(
                        f"Coupling damping of {self.name} road contact "
                        f"between road_contact_port (DOF {j}) and port_a (DOF {i})"
                    ),
                    equation_reference=f"D[{j},{i}] -= c_contact_{self.id}",
                ))

        return contribs
