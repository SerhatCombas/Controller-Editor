# Backend Parity Report

- Status: `exact_match`
- Input channel: `road_displacement`
- Common outputs: `body_displacement, wheel_displacement, suspension_deflection, body_acceleration, tire_deflection`
- Numeric-only outputs: `none`
- Symbolic-only outputs: `none`

## Exact Matches

- `output_order_matches`: `True`
- `state_order_matches`: `True`
- `input_labels_match`: `True`
- `output_labels_match`: `True`
- `state_trace_matches`: `True`
- `output_trace_matches`: `True`

## Matrix Differences

- `A`: abs=0.000e+00, rel_est=0.000e+00, left=[4, 4], right=[4, 4]
- `B`: abs=0.000e+00, rel_est=0.000e+00, left=[4, 1], right=[4, 1]
- `C`: abs=0.000e+00, rel_est=0.000e+00, left=[5, 4], right=[5, 4]
- `D`: abs=0.000e+00, rel_est=0.000e+00, left=[5, 1], right=[5, 1]

## Transfer Function Differences

- `body_displacement:numerator`: abs=0.000e+00, rel_est=0.000e+00
- `body_displacement:denominator`: abs=0.000e+00, rel_est=0.000e+00
- `wheel_displacement:numerator`: abs=0.000e+00, rel_est=0.000e+00
- `wheel_displacement:denominator`: abs=0.000e+00, rel_est=0.000e+00
- `suspension_deflection:numerator`: abs=0.000e+00, rel_est=0.000e+00
- `suspension_deflection:denominator`: abs=0.000e+00, rel_est=0.000e+00
- `body_acceleration:numerator`: abs=0.000e+00, rel_est=0.000e+00
- `body_acceleration:denominator`: abs=0.000e+00, rel_est=0.000e+00
- `tire_deflection:numerator`: abs=0.000e+00, rel_est=0.000e+00
- `tire_deflection:denominator`: abs=0.000e+00, rel_est=0.000e+00

## Pole / Zero Differences

- `body_displacement:zeros`: abs=0.000e+00, rel_est=0.000e+00
- `body_displacement:poles`: abs=0.000e+00, rel_est=0.000e+00
- `wheel_displacement:zeros`: abs=0.000e+00, rel_est=0.000e+00
- `wheel_displacement:poles`: abs=0.000e+00, rel_est=0.000e+00
- `suspension_deflection:zeros`: abs=0.000e+00, rel_est=0.000e+00
- `suspension_deflection:poles`: abs=0.000e+00, rel_est=0.000e+00
- `body_acceleration:zeros`: abs=0.000e+00, rel_est=0.000e+00
- `body_acceleration:poles`: abs=0.000e+00, rel_est=0.000e+00
- `tire_deflection:zeros`: abs=0.000e+00, rel_est=0.000e+00
- `tire_deflection:poles`: abs=0.000e+00, rel_est=0.000e+00

## Eigenvalue Difference

- abs=0.000e+00, rel_est=0.000e+00

## Step Response Metrics

- `body_displacement`: peak=0.000e+00, final=0.000e+00, rms=0.000e+00
- `wheel_displacement`: peak=0.000e+00, final=0.000e+00, rms=0.000e+00
- `suspension_deflection`: peak=0.000e+00, final=0.000e+00, rms=0.000e+00
- `body_acceleration`: peak=0.000e+00, final=0.000e+00, rms=0.000e+00
- `tire_deflection`: peak=0.000e+00, final=0.000e+00, rms=0.000e+00

## Semantic Mismatches

- none
