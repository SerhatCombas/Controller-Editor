from __future__ import annotations

from dataclasses import dataclass


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
