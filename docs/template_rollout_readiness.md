# Template Rollout Readiness

This document describes the service-level rollout gate used before a template can expose live symbolic runtime in the product.

## Readiness Flags

- `parity_ready`
  Static numeric-vs-symbolic parity evidence exists for the template.
- `runtime_ready`
  Live runtime wiring is implemented and allowed to run for the template.
- `diagnostics_ready`
  The template participates in the shared diagnostics contract.
- `fallback_ready`
  Safe fallback semantics are defined and tested.
- `backend_selectable`
  The runtime selector may expose the backend as an active choice.
- `symbolic_equations_ready`
  The template has symbolic equation/state-space support.
- `smoke_test_ready`
  A runtime smoke test exists for the template.
- `capability_declared`
  The template/backend capability contract is explicitly declared.
- `current_rollout_status`
  Human-readable rollout phase used in diagnostics and UI summaries.

## Gate For Enabling Live Symbolic Runtime

Before live symbolic runtime can be enabled for a template, all of the following should be true:

1. `parity_ready = true`
2. `runtime_ready = true`
3. `diagnostics_ready = true`
4. `fallback_ready = true`
5. `backend_selectable = true`
6. `symbolic_equations_ready = true`
7. `smoke_test_ready = true`
8. `capability_declared = true`

## Current Template Status

| Template | Parity | Runtime | Diagnostics | Fallback | Backend Selectable | Symbolic Equations | Smoke Test | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `quarter_car` | Yes | Yes | Yes | Yes | Yes | Yes | Yes | `experimental_runtime_enabled` |
| `single_mass` | Yes | No | Yes | No | No | Yes | No | `symbolic_runtime_unavailable` |
| `two_mass` | Yes | No | Yes | No | No | Yes | No | `symbolic_runtime_unavailable` |

## How Quarter-Car Passed

Quarter-car is currently the reference rollout template because it has:

- exact static parity artifacts
- optional live symbolic runtime
- fallback back to numeric runtime
- lifecycle and diagnostics regression coverage
- deterministic backend ordering and trace contracts

## What Remains For `single_mass` And `two_mass`

To move `single_mass` or `two_mass` from diagnostics-only readiness to live symbolic runtime readiness, the next gates are:

1. add runtime backend implementation
2. add smoke runtime parity coverage
3. define and test fallback semantics
4. mark backend selectable only after the runtime path is stable

## Notes

- `UnavailableRuntimeBackend` is intentional. It prevents silent or ambiguous runtime behavior for templates that are not ready yet.
- UI should stay conservative: show readiness clearly, but do not expose unavailable live runtime paths as if they already work.
