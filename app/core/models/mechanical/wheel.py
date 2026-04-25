from __future__ import annotations

from app.core.base.domain import MECHANICAL_TRANSLATIONAL_DOMAIN
from app.core.base.port import Port
from app.core.base.variable import Variable
from app.core.models.mechanical.mass import Mass


# Allowed values for the new mode parameters. Defined as module-level
# constants so other faz steps (4f Mode A, 4g Mode B) can import these
# instead of duplicating string literals.
WHEEL_CONTACT_MODES = ("kinematic_follow", "dynamic_contact")
WHEEL_OUTPUT_MODES = ("displacement", "force")


class Wheel(Mass):
    """Wheel component — mechanical inertia plus a road-contact interface.

    Faz 4d-1 status:
      * Inheritance from Mass is preserved (port_a, reference_port, mass
        contribution, state).  Mevcut quarter-car template ve testleri
        etkilenmez — Wheel geçmişteki gibi Mass davranışı sürdürür.
      * Yeni `road_contact_port` eklenir (mechanical_translational domain).
        4d-1'de bu port boşta kalır; mevcut template onu bağlamaz.
        4e/4f/4g'de RandomRoad ile bağlanacak ve aktif rol alacak.
      * Yeni parametreler tanımlanır (sözleşme: hepsi parameters dict'ine
        yazılır, ama 4d-1 davranışı etkilemez — 4f/4g ve gelecek longitudinal
        dynamics fazları bunları okuyacak):
            contact_mode             — "kinematic_follow" (default) / "dynamic_contact"
            contact_stiffness        — 200000.0 (otomotiv tipik) [N/m]
            contact_damping          — 500.0    (otomotiv tipik) [N·s/m]
            disable_contact_force    — False; True ise kontak kuvveti hesaplanmaz
            rotational_inertia       — 1.0 [kg·m²]; 0.0 = dönme ataleti yok
            rolling_resistance       — 0.015; 0.0 = yuvarlanma direnci yok
            output_mode              — "displacement" (default) / "force"

    Parameter philosophy:
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
        super().__init__(component_id, mass=mass, name=name)
        # Existing parameters from Mass: {"mass": ...}. Extend with wheel-specific.
        # The user can disable the entire contact-force computation via
        # disable_contact_force=True. The contact_stiffness/contact_damping
        # values themselves are preserved (so toggling the switch off later
        # restores the previous tuning) — Mode A/B implementations in 4f/4g
        # will read the flag and skip the contact-force term when set.
        # User can also set values to 0.0 directly for "no spring/damper"
        # semantics; the flag and 0.0 produce equivalent simulations but the
        # flag preserves intent across UI edits.
        self.parameters["radius"] = radius
        self.parameters["contact_mode"] = contact_mode
        self.parameters["contact_stiffness"] = float(contact_stiffness)
        self.parameters["contact_damping"] = float(contact_damping)
        self.parameters["disable_contact_force"] = bool(disable_contact_force)
        # Rotational degrees of freedom — present in the parameter dict so
        # users of the new API can specify them today, even though Faz 4d-1
        # does not yet wire them into any equation. Drive/brake dynamics
        # (which would consume rotational_inertia) and longitudinal
        # rolling-resistance forces are out of scope for the Mode A/Mode B
        # quarter-car work; they will be activated by a future faz that
        # introduces longitudinal vehicle dynamics. Set either to 0.0 to
        # disable the corresponding effect when those modules ship.
        self.parameters["rotational_inertia"] = float(rotational_inertia)
        self.parameters["rolling_resistance"] = float(rolling_resistance)
        self.parameters["output_mode"] = output_mode

        # New port — road contact interface. Mechanical translational domain
        # (Newtonian force/velocity), separate through/across variables so
        # downstream pipelines can distinguish suspension-side from road-side
        # interactions on the same wheel. The port is required=False so a
        # Wheel instance can be constructed and used without connecting it
        # (current template uses port_a only; Faz 4e will rewire to road_contact_port).
        self.ports.append(
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
            )
        )
