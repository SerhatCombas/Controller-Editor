from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.parity_harness import QuarterCarParityHarness

REPORT_DIR = ROOT / "docs"
JSON_PATH = REPORT_DIR / "backend_parity_report.json"
MD_PATH = REPORT_DIR / "backend_parity_report.md"


def matrix_diff_payload(diff) -> dict[str, object]:
    left_rows = diff.shape_left[0] if len(diff.shape_left) >= 1 else 0
    left_cols = diff.shape_left[1] if len(diff.shape_left) >= 2 else 1
    right_rows = diff.shape_right[0] if len(diff.shape_right) >= 1 else 0
    right_cols = diff.shape_right[1] if len(diff.shape_right) >= 2 else 1
    left_size = max(left_rows * left_cols, 1)
    return {
        "max_abs_error": diff.max_abs_error,
        "max_rel_error_estimate": diff.max_abs_error / left_size,
        "shape_left": list(diff.shape_left),
        "shape_right": list(diff.shape_right),
    }


def build_report() -> dict[str, object]:
    harness = QuarterCarParityHarness()
    report = harness.compare(input_channel="road_displacement")

    matrix_diffs = {
        name: matrix_diff_payload(diff)
        for name, diff in report.matrix_diffs.items()
    }
    tf_diffs = {
        name: matrix_diff_payload(diff)
        for name, diff in report.transfer_function_diffs.items()
    }
    pz_diffs = {
        name: matrix_diff_payload(diff)
        for name, diff in report.pole_zero_diffs.items()
    }
    step_metrics = [
        {
            "output_name": diff.output_name,
            "peak_abs_error": diff.peak_abs_error,
            "final_value_error": diff.final_value_error,
            "rms_error": diff.rms_error,
        }
        for diff in report.step_response_diffs
    ]

    return {
        "status": "exact_match" if not report.issues else "mismatch",
        "input_channel": report.input_channel,
        "common_outputs": report.common_outputs,
        "numeric_only_outputs": report.numeric_only_outputs,
        "symbolic_only_outputs": report.symbolic_only_outputs,
        "exact_matches": {
            "output_order_matches": report.output_order_matches,
            "state_order_matches": report.state_order_matches,
            "input_labels_match": report.input_labels_match,
            "output_labels_match": report.output_labels_match,
            "state_trace_matches": report.state_trace_matches,
            "output_trace_matches": report.output_trace_matches,
        },
        "tolerance_matches": {
            "matrix_diffs": matrix_diffs,
            "transfer_function_diffs": tf_diffs,
            "pole_zero_diffs": pz_diffs,
            "eigenvalue_diff": matrix_diff_payload(report.eigenvalue_diff),
            "step_response_metrics": step_metrics,
        },
        "semantic_mismatches": report.issues,
        "metadata": report.metadata,
    }


def write_markdown(report: dict[str, object]) -> str:
    exact = report["exact_matches"]
    tol = report["tolerance_matches"]
    lines = [
        "# Backend Parity Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Input channel: `{report['input_channel']}`",
        f"- Common outputs: `{', '.join(report['common_outputs'])}`",
        f"- Numeric-only outputs: `{', '.join(report['numeric_only_outputs']) or 'none'}`",
        f"- Symbolic-only outputs: `{', '.join(report['symbolic_only_outputs']) or 'none'}`",
        "",
        "## Exact Matches",
        "",
    ]
    for key, value in exact.items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Matrix Differences", ""])
    for key, value in tol["matrix_diffs"].items():
        lines.append(
            f"- `{key}`: abs={value['max_abs_error']:.3e}, rel_est={value['max_rel_error_estimate']:.3e}, "
            f"left={value['shape_left']}, right={value['shape_right']}"
        )

    lines.extend(["", "## Transfer Function Differences", ""])
    for key, value in tol["transfer_function_diffs"].items():
        lines.append(
            f"- `{key}`: abs={value['max_abs_error']:.3e}, rel_est={value['max_rel_error_estimate']:.3e}"
        )

    lines.extend(["", "## Pole / Zero Differences", ""])
    for key, value in tol["pole_zero_diffs"].items():
        lines.append(
            f"- `{key}`: abs={value['max_abs_error']:.3e}, rel_est={value['max_rel_error_estimate']:.3e}"
        )

    eig = tol["eigenvalue_diff"]
    lines.extend(
        [
            "",
            "## Eigenvalue Difference",
            "",
            f"- abs={eig['max_abs_error']:.3e}, rel_est={eig['max_rel_error_estimate']:.3e}",
            "",
            "## Step Response Metrics",
            "",
        ]
    )
    for metric in tol["step_response_metrics"]:
        lines.append(
            f"- `{metric['output_name']}`: peak={metric['peak_abs_error']:.3e}, "
            f"final={metric['final_value_error']:.3e}, rms={metric['rms_error']:.3e}"
        )

    lines.extend(["", "## Semantic Mismatches", ""])
    if report["semantic_mismatches"]:
        for issue in report["semantic_mismatches"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    JSON_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(write_markdown(report), encoding="utf-8")
    print(JSON_PATH)
    print(MD_PATH)


if __name__ == "__main__":
    main()
