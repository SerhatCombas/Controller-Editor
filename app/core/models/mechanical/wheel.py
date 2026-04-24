from __future__ import annotations

from app.core.models.mechanical.mass import Mass


class Wheel(Mass):
    def __init__(self, component_id: str, *, mass: float, radius: float = 0.32, name: str = "Wheel") -> None:
        super().__init__(component_id, mass=mass, name=name)
        self.parameters["radius"] = radius
