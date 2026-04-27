from __future__ import annotations

from typing import TYPE_CHECKING

from src.shared.components._base.signal_source import SignalSource

if TYPE_CHECKING:
    from src.shared.types.source_descriptor import SourceDescriptor


class StepForce(SignalSource):
    def __init__(
        self,
        component_id: str,
        *,
        amplitude: float,
        start_time: float = 0.0,
        name: str = "Step Force",
    ) -> None:
        super().__init__(component_id, name=name)
        self.parameters.update({"amplitude": amplitude, "start_time": start_time})
        self.metadata["source_kind"] = "force"

    def displacement_output(self, _time: float) -> float:
        return 0.0

    def velocity_output(self, _time: float) -> float:
        return 0.0

    def force_output(self, time: float) -> float:
        return self.parameters["amplitude"] if time >= self.parameters["start_time"] else 0.0

    def constitutive_equations(self) -> list[str]:
        return [
            f"u_{self.id}(t) = step(t - {self.parameters['start_time']}) * {self.parameters['amplitude']}",
            f"f_{self.id}_out = u_{self.id}(t)",
        ]

    # ------------------------------------------------------------------
    # Wave 1 polymorphic interface
    # ------------------------------------------------------------------

    def get_source_descriptor(self) -> SourceDescriptor:
        """StepForce injects a step-shaped force at its output port.

        The InputRouter uses this descriptor to wire the input vector entry
        into the assembled force vector without inspecting the class name.
        """
        from src.shared.types.source_descriptor import SourceDescriptor
        return SourceDescriptor(
            kind="force",
            driven_port_name="port",
            reference_port_name="reference_port",
            input_variable_name=f"f_{self.id}_out",
            amplitude_parameter="amplitude",
        )
