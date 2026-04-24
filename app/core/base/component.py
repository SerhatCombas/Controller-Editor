from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.base.domain import Domain
from app.core.base.port import Port

if TYPE_CHECKING:
    from app.core.base.contribution import MatrixContribution
    from app.core.base.linearity import LinearityProfile
    from app.core.base.source_descriptor import SourceDescriptor
    from app.core.base.state_contribution import StateContribution


@dataclass(slots=True)
class BaseComponent:
    id: str
    name: str
    domain: Domain
    ports: list[Port]
    parameters: dict[str, float] = field(default_factory=dict)
    initial_conditions: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def get_states(self) -> list[str]:
        return []

    def get_parameters(self) -> dict[str, float]:
        return dict(self.parameters)

    def constitutive_equations(self) -> list[str]:
        raise NotImplementedError

    def dae_equations(self) -> list[str]:
        return self.constitutive_equations()

    def initial_condition_map(self) -> dict[str, float]:
        return dict(self.initial_conditions)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for port in self.ports:
            if port.required and port.node_id is None:
                errors.append(f"{self.name}:{port.name} is not connected.")
        return errors

    def port(self, name: str) -> Port:
        for port in self.ports:
            if port.name == name:
                return port
        raise KeyError(f"Port {name!r} not found on component {self.id!r}")

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface — opt-in, zero behaviour change
    # Subclasses override these; the default implementations are neutral
    # (LTI, no state, no source) so that any component that does NOT
    # override stays fully backwards-compatible.
    # ------------------------------------------------------------------

    def linearity_profile(self) -> LinearityProfile:
        """Return the component's linearity characteristics.

        Default: fully linear and time-invariant (LTI-safe default).
        Override in nonlinear or time-varying subclasses.
        """
        from app.core.base.linearity import LinearityProfile
        return LinearityProfile()

    def get_state_contribution(self) -> StateContribution | None:
        """Return energy-storage metadata if this component carries state.

        Default: None (stateless component).
        Override in inertial/potential-energy-storing subclasses (e.g. Mass, Wheel).
        """
        return None

    def get_source_descriptor(self) -> SourceDescriptor | None:
        """Return input-source topology descriptor if this component drives the system.

        Default: None (passive component, not an input source).
        Override in source components (e.g. StepForce, RandomRoad).
        InputRouter reads this; PolymorphicDAEReducer never inspects component types directly.
        """
        return None

    def contribute_mass(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Return mass-matrix contributions for this component.

        Default: [] (component does not contribute to mass matrix).
        Override in inertial components (e.g. Mass, Wheel).

        Args:
            node_index: mapping from node_id → integer DOF index in the assembled matrix.
        """
        return []

    def contribute_damping(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Return damping-matrix contributions for this component.

        Default: [] (component does not contribute to damping matrix).
        Override in dissipative components (e.g. Damper).

        Args:
            node_index: mapping from node_id → integer DOF index in the assembled matrix.
        """
        return []

    def contribute_stiffness(self, node_index: dict[str, int]) -> list[MatrixContribution]:
        """Return stiffness-matrix contributions for this component.

        Default: [] (component does not contribute to stiffness matrix).
        Override in elastic components (e.g. Spring).

        Args:
            node_index: mapping from node_id → integer DOF index in the assembled matrix.
        """
        return []
