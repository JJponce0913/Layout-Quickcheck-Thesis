from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


DEFAULT_SUMMARY_DIRS = [Path("bug_reports") / "tester"]
DEFAULT_OUTPUT_DIR = Path("files") / "rq1"
SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
HOURS_THRESHOLD_MINUTES = 240
def execution_time_axis(max_minutes: float) -> tuple[float, str, float]:
    """Return the scale, label, and major tick interval for a time axis."""
    if max_minutes > HOURS_THRESHOLD_MINUTES:
        return 60, "Execution time (hours)", 1
    return 1, "Execution time (minutes)", 10


def main() -> None:
    parser = argparse.ArgumentParser(description="Create RQ1 bug discovery graphs.")
    parser.add_argument(
        "summary_dirs",
        nargs="*",
        type=Path,
        default=DEFAULT_SUMMARY_DIRS,
        help="Folders containing run_summary_<seconds>s.json snapshots.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Root output folder. Each input folder is saved under <output-dir>/<folder-name>/.",
    )
    parser.add_argument(
        "--max-minutes",
        type=float,
        default=None,
        help="Maximum time in minutes to display on time-based graphs. Defaults to the longest run.",
    )
    args = parser.parse_args()

    comparison_series = []
    for summary_dir in args.summary_dirs:
        output_dir = args.output_dir / summary_dir.name
        comparison_series.append(create_graphs(summary_dir, output_dir, args.max_minutes))

    if len(comparison_series) > 1:
        create_cumulative_comparison(comparison_series, args.output_dir, args.max_minutes)


def create_graphs(
    summary_dir: Path,
    output_dir: Path,
    max_minutes: float | None,
) -> dict[str, object]:
    snapshots = []

    for path in summary_dir.glob("run_summary_*s.json"):
        match = SNAPSHOT_PATTERN.match(path.name)
        if not match:
            continue

        snapshot_seconds = int(match.group(1))
        if snapshot_seconds % 60 != 0:
            continue

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        snapshots.append(
            {
                "snapshot_seconds": snapshot_seconds,
                "runtime_seconds": float(data["runtime_seconds"]),
                "bugs_found": data["bugs_found"],
                "tests_run": data["tests_run"],
            }
        )

    if not snapshots:
        raise SystemExit(f"No timestamped run_summary_*s.json snapshots found in {summary_dir}")

    snapshots.sort(key=lambda item: item["runtime_seconds"])

    # Snapshot filenames encode the intended elapsed-run timestamp.  Use that
    # value rather than wall-clock runtime, which can include setup overhead
    # and otherwise makes a 60-minute snapshot plot short of 60 minutes.
    minutes = [item["snapshot_seconds"] / 60 for item in snapshots]

    # ``set_xlim`` only hides later samples; it does not prevent them from
    # expanding the y-axis. Drop samples outside the requested execution-time
    # window before deriving any plotted values or axis limits.
    if max_minutes is not None:
        snapshots = [
            snapshot
            for snapshot, minute in zip(snapshots, minutes)
            if minute <= max_minutes
        ]
        if not snapshots:
            raise SystemExit(
                f"No snapshots in {summary_dir} fall within the {max_minutes:g}-minute execution window"
            )
        minutes = [item["snapshot_seconds"] / 60 for item in snapshots]

    bugs_found = [item["bugs_found"] for item in snapshots]
    tests_run = [item["tests_run"] for item in snapshots]
    endpoint_minutes = minutes[-1]
    time_limit_minutes = max_minutes if max_minutes is not None else endpoint_minutes
    time_scale, time_label, time_tick_interval = execution_time_axis(time_limit_minutes)
    execution_time = [minute / time_scale for minute in minutes]
    execution_limit = time_limit_minutes / time_scale
    output_dir.mkdir(parents=True, exist_ok=True)

    time_fig, time_ax = plt.subplots(figsize=(11, 6), dpi=140)
    time_ax.plot(execution_time, bugs_found, marker="o", linewidth=2)

    time_ax.set_title(
        f"Cumulative Bugs Detected Over Time ({summary_dir.name}, {endpoint_minutes:g} min Run)"
    )
    time_ax.set_xlabel(time_label)
    time_ax.set_ylabel("Detected bugs")
    time_ax.set_xlim(0, execution_limit)
    time_ax.set_ylim(0, max(bugs_found) + 2)
    time_ax.xaxis.set_major_locator(MultipleLocator(time_tick_interval))
    time_ax.grid(True, alpha=0.3)

    time_fig.tight_layout()

    time_output_path = (
        output_dir / f"cumulative_bugs_detected_over_time_{endpoint_minutes:g}min.png"
    )
    time_fig.savefig(time_output_path)
    print(f"Saved plot to {time_output_path}")

    tests_fig, tests_ax = plt.subplots(figsize=(11, 6), dpi=140)
    tests_ax.plot(tests_run, bugs_found, marker="o", linewidth=2)

    tests_ax.set_title(
        f"Cumulative Bugs Detected by Test Cases Executed ({summary_dir.name}, {endpoint_minutes:g} min Run)"
    )
    tests_ax.set_xlabel("Test cases executed")
    tests_ax.set_ylabel("Detected bugs")
    tests_ax.set_xlim(0, max(tests_run))
    tests_ax.set_ylim(0, max(bugs_found) + 2)
    tests_ax.grid(True, alpha=0.3)

    tests_fig.tight_layout()

    tests_output_path = (
        output_dir / "cumulative_bugs_detected_by_test_cases_executed.png"
    )
    tests_fig.savefig(tests_output_path)
    print(f"Saved plot to {tests_output_path}")

    return {
        "name": summary_dir.name,
        "minutes": minutes,
        "bugs_found": bugs_found,
        "endpoint_minutes": endpoint_minutes,
    }


def create_cumulative_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    x_limit_minutes = (
        max_minutes
        if max_minutes is not None
        else max(series["endpoint_minutes"] for series in comparison_series)
    )
    time_scale, time_label, time_tick_interval = execution_time_axis(x_limit_minutes)

    figure, axis = plt.subplots(figsize=(11, 6), dpi=140)
    for series in comparison_series:
        axis.plot(
            [minute / time_scale for minute in series["minutes"]],
            series["bugs_found"],
            marker="o",
            linewidth=2,
            label=series["name"],
        )

    max_bugs_found = max(max(series["bugs_found"]) for series in comparison_series)
    axis.set_title("Cumulative Bugs Detected Over Time by Configuration")
    axis.set_xlabel(time_label)
    axis.set_ylabel("Detected bugs")
    axis.set_xlim(0, x_limit_minutes / time_scale)
    axis.set_ylim(0, max_bugs_found + 2)
    axis.xaxis.set_major_locator(MultipleLocator(time_tick_interval))
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "cumulative_bugs_detected_over_time_by_configuration.png"
    figure.savefig(output_path)
    plt.close(figure)
    print(f"Saved plot to {output_path}")



if __name__ == "__main__":
    main()
