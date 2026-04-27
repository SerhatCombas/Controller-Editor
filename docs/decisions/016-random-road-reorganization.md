# ADR-016 — RandomRoad Reorganization to Components/Road

**Status:** Deferred to Faz 6  
**Date:** 2026-04-27

## Context

RandomRoad currently lives under `app/core/models/sources/random_road.py` and is
classified as a "source" in the palette hierarchy. However, it is not a signal
source — it is a physical environment component that represents the road surface
profile. The road is closer to a Fixed/Ground (environmental boundary condition)
than to a ForceSource or VoltageSource.

The SVGModel directory structure has `Mechanics/Translational/Components/road.svg`,
which is the correct organizational home.

## Decision

Defer reorganization to Faz 6. When implemented:

1. Move `random_road.py` from `sources/` to a new `components/road.py` (or keep
   under `mechanical/` with proper categorization).
2. Update `PALETTE_GROUP_ASSIGNMENTS` to place Road under
   `("Mechanical", "Translational", "Components")` instead of Sources.
3. Update all imports throughout the codebase.
4. Consider renaming to `RoadProfile` to better reflect its role.

## Rationale

- RandomRoad has unique domain coupling behavior (displacement source for
  Wheel.road_contact_port) that makes it distinct from both passive components
  and signal sources.
- The reorganization touches many test files and the registry — doing it during
  the MVP cleanup (Faz 5) would increase risk for no user-facing benefit.
- Keeping it as a deferred decision ensures we don't forget.

## Consequences

- Until Faz 6, RandomRoad stays in `sources/` and appears under "Sources" in
  the palette (if visible at all — currently it is not in the palette since
  it's not in PALETTE_GROUP_ASSIGNMENTS).
- Tests using RandomRoad import from `app.core.models.sources` as before.
