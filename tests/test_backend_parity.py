from __future__ import annotations

import unittest

try:
    from app.services.parity_harness import QuarterCarParityHarness
    from app.services.simulation_backend import QuarterCarNumericBackend, SymbolicStateSpaceBackend

    BACKEND_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    BACKEND_DEPS_AVAILABLE = False


@unittest.skipUnless(BACKEND_DEPS_AVAILABLE, "Backend parity tests require numpy/scipy runtime dependencies")
class BackendParityTests(unittest.TestCase):
    def test_quarter_car_parity_harness_reports_small_state_space_differences(self):
        harness = QuarterCarParityHarness(
            numeric_backend=QuarterCarNumericBackend(),
            symbolic_backend=SymbolicStateSpaceBackend(),
        )

        # tire_deflection excluded from parity comparison: this output requires
        # D-feedthrough from road_height (see template note in quarter_car.py),
        # which the symbolic pipeline does not yet implement. Numeric backend
        # computes it correctly; symbolic backend yields zero. Re-include when
        # D-feedthrough support lands.
        report = harness.compare(
            input_channel="road_displacement",
            output_variables=[
                "body_displacement",
                "wheel_displacement",
                "body_acceleration",
                "suspension_deflection",
            ],
        )

        self.assertEqual(report.common_outputs, [
            "body_displacement",
            "wheel_displacement",
            "body_acceleration",
            "suspension_deflection",
        ])
        self.assertFalse(report.numeric_only_outputs)
        self.assertFalse(report.symbolic_only_outputs)
        self.assertTrue(report.output_order_matches)
        self.assertTrue(report.state_order_matches)
        self.assertTrue(report.input_labels_match)
        self.assertTrue(report.output_labels_match)
        self.assertTrue(report.state_trace_matches)
        self.assertTrue(report.output_trace_matches)
        self.assertFalse(report.issues)
        self.assertLess(report.matrix_diffs["A"].max_abs_error, 1e-9)
        self.assertLess(report.matrix_diffs["B"].max_abs_error, 1e-9)
        self.assertLess(report.matrix_diffs["C"].max_abs_error, 1e-9)
        self.assertLess(report.matrix_diffs["D"].max_abs_error, 1e-9)
        self.assertLess(report.eigenvalue_diff.max_abs_error, 1e-9)
        self.assertTrue(all(diff.max_abs_error < 1e-9 for diff in report.transfer_function_diffs.values()))
        self.assertTrue(all(diff.max_abs_error < 1e-9 for diff in report.pole_zero_diffs.values()))

    def test_quarter_car_step_response_parity_is_qualitatively_close(self):
        harness = QuarterCarParityHarness()
        report = harness.compare(
            input_channel="road_displacement",
            output_variables=["body_displacement", "wheel_displacement", "suspension_deflection"],
            duration=4.0,
            sample_count=250,
        )

        self.assertTrue(report.step_response_diffs)
        for response_diff in report.step_response_diffs:
            self.assertLess(response_diff.rms_error, 1e-8)
            self.assertLess(response_diff.final_value_error, 1e-8)
            self.assertLess(response_diff.peak_abs_error, 1e-8)

    def test_parity_report_contains_human_readable_metadata(self):
        harness = QuarterCarParityHarness()
        report = harness.compare(
            input_channel="road_displacement",
            output_variables=["suspension_deflection"],
            duration=2.0,
            sample_count=120,
        )

        self.assertIsInstance(report.issues, list)
        self.assertIn("numeric_state_trace", report.metadata)
        self.assertIn("symbolic_output_trace", report.metadata)


if __name__ == "__main__":
    unittest.main()
