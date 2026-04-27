from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from src.shared.types.domain import Domain


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    domain: Domain
    kind: Literal["across", "through", "state", "parameter", "input", "output"]
