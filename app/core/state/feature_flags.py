"""Centralized feature flag definitions.

This module is part of Wave 1. It introduces a single, explicit place
where migration / experimentation flags live, while retaining strict
dependency-injection discipline elsewhere in the codebase.

Usage rules — please respect these or the isolation benefits are lost:

1. Do **not** import DEFAULT_FLAGS or DEVELOPMENT_FLAGS from inside
   reducers, services, components, or anything that lives under
   `app/core/`. Those modules must accept a FeatureFlags instance via
   constructor injection.

2. The only legitimate importers of DEFAULT_FLAGS / DEVELOPMENT_FLAGS
   are composition roots: application entry points, backend factories,
   and test fixtures. Everything downstream receives the flags as
   parameters.

3. FeatureFlags is a frozen dataclass. To override a single field,
   construct a new instance: `dataclasses.replace(flags, parity_mode=...)`.
   Do not mutate existing instances — doing so defeats test isolation.

Wave 1 introduces only three flags. Later waves may extend this file
without modifying existing reducer or component code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ParityMode(Enum):
    """Controls how the polymorphic reducer runs alongside the legacy one.

    - OFF: only the legacy reducer runs. The polymorphic reducer and the
      parity harness stay dormant. This is the production default
      throughout Wave 1 — we do not want any user-visible behavior
      change until parity is fully proven.

    - SHADOW: both reducers run on every simulation. The legacy reducer
      remains authoritative (its output is what the rest of the pipeline
      consumes). The polymorphic reducer's output is compared against
      the legacy one and any discrepancies are logged through
      `parity_report`. This is the development / CI default.

    - PRIMARY: the polymorphic reducer becomes authoritative and the
      legacy reducer runs as the validator. Reserved for Wave 1 sign-off
      and the early part of Wave 2, before the legacy reducer is
      decommissioned entirely.
    """

    OFF = "off"
    SHADOW = "shadow"
    PRIMARY = "primary"


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    """Immutable bundle of feature flag values injected into backends.

    Attributes:
        parity_mode: Governs reducer parity execution; see ParityMode.
        enable_linearity_classifier: When True, services query the
            LinearityClassifier and expose its verdict to the UI. When
            False, the classifier is skipped entirely.
        enable_input_router: When True, the new InputRouter runs as part
            of the reducer pipeline. When False, only the legacy reducer
            path is active. Wave 1 treats this flag together with
            parity_mode: both must be aligned.
    """

    parity_mode: ParityMode = ParityMode.OFF
    enable_linearity_classifier: bool = True
    enable_input_router: bool = True


DEFAULT_FLAGS = FeatureFlags(
    parity_mode=ParityMode.PRIMARY,
    enable_linearity_classifier=True,
    enable_input_router=True,
)
"""Production default: Wave 2 PRIMARY cutover.

All six gate conditions confirmed before this change:
  Gate 1: Template parity (single_mass, two_mass, quarter_car) — zero divergence
  Gate 2: TF golden tests passing (36 tests across 3 templates)
  Gate 3: 200-iteration TF fuzz, zero structural anomalies
  Gate 4: OutputMapper parity (55 unit tests, zero failures)
  Gate 5: User-built topology parity (covered by Gate 1 + fuzz parity)
  Gate 6: Unsupported outputs return UnsupportedTFResult, never wrong TF

The polymorphic reducer is now authoritative.  The legacy reducer runs as a
background validator in PRIMARY mode; if it cannot run (e.g. incomplete
SymbolicSystem from a stub), a degraded-report is returned but the
polymorphic result is always delivered.
"""


DEVELOPMENT_FLAGS = FeatureFlags(
    parity_mode=ParityMode.SHADOW,
    enable_linearity_classifier=True,
    enable_input_router=True,
)
"""Development / CI default. Shadow mode exercises the polymorphic
reducer on every simulation so parity divergences surface quickly."""
