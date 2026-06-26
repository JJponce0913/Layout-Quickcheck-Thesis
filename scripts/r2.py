from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


DEFAULT_SUMMARY_DIRS = [Path("bug_reports") / "tester"]
DEFAULT_OUTPUT_DIR = Path("files") / "rq2"
SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
HOURS_THRESHOLD_MINUTES = 240
TITLE_FONT_SIZE = 24
LABEL_FONT_SIZE = 22
TICK_FONT_SIZE = 20
LEGEND_FONT_SIZE = 20
LINE_COLORS = ["#1f77b4", "#7b2cbf"]


def format_run_name(name: str) -> str:
    words = name.replace("-", " ").split()
    replacements = {
        "chromium": "Chromium",
        "firefox": "Firefox",
        "sort": "Sort",
    }
    return " ".join(replacements.get(word, word.capitalize()) for word in words)


def execution_time_axis(max_minutes: float) -> tuple[float, str, float]:
    """Return the scale, label, and major tick interval for a time axis."""
    if max_minutes > HOURS_THRESHOLD_MINUTES:
        return 60, "Execution time (hours)", 1
    return 1, "Execution time (minutes)", 10


def increase_plot_font_sizes(axis) -> None:
    axis.title.set_fontsize(TITLE_FONT_SIZE)
    axis.xaxis.label.set_fontsize(LABEL_FONT_SIZE)
    axis.yaxis.label.set_fontsize(LABEL_FONT_SIZE)
    axis.tick_params(axis="both", which="major", labelsize=TICK_FONT_SIZE)
    axis.tick_params(axis="both", which="minor", labelsize=TICK_FONT_SIZE)

    legend = axis.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontsize(LEGEND_FONT_SIZE)


def line_color(index: int) -> str:
    return LINE_COLORS[index % len(LINE_COLORS)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create RQ2 minimization and clustering graphs.")
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
        comparison_series.append(create_comparison_series(summary_dir, args.max_minutes))

    if len(comparison_series) > 1:
        create_processing_time_comparison(
            comparison_series,
            args.output_dir,
            args.max_minutes,
        )


def create_graphs(
    summary_dir: Path,
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    snapshots = load_snapshots(summary_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_seconds = snapshots[0]["runtime_seconds"]
    minutes = [
        (snapshot["runtime_seconds"] - start_seconds) / 60
        for snapshot in snapshots
    ]
    # Exclude samples outside the requested execution-time window. Merely
    # limiting the x-axis would leave later samples affecting the y-axis.
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
        minutes = [
            (snapshot["runtime_seconds"] - start_seconds) / 60
            for snapshot in snapshots
        ]

    tests_run = [snapshot["tests_run"] for snapshot in snapshots]
    minimize_seconds = [snapshot["true_minification_seconds"] for snapshot in snapshots]
    sorting_seconds = [snapshot["sorting_seconds"] for snapshot in snapshots]
    endpoint_minutes = minutes[-1]
    time_limit_minutes = max_minutes if max_minutes is not None else endpoint_minutes
    time_scale, time_label, _ = execution_time_axis(time_limit_minutes)
    execution_time = [minute / time_scale for minute in minutes]
    execution_limit = time_limit_minutes / time_scale

    save_line_plot(
        x=execution_time,
        y=tests_run,
        title=f"Cumulative Test Cases Executed Over Time ({endpoint_minutes:g} min Run)",
        xlabel=time_label,
        ylabel="Test cases executed",
        output_path=output_dir / "cumulative_test_cases_executed_over_time.png",
        max_x=execution_limit,
    )

    save_line_plot(
        x=execution_time,
        y=minimize_seconds,
        title=f"Cumulative Minimization Time Over Time ({endpoint_minutes:g} min Run)",
        xlabel=time_label,
        ylabel="Minimization time (seconds)",
        output_path=output_dir / "cumulative_minimization_time_over_time.png",
        max_x=execution_limit,
    )

    save_line_plot(
        x=execution_time,
        y=sorting_seconds,
        title=f"Cumulative Sorting Time Over Time ({endpoint_minutes:g} min Run)",
        xlabel=time_label,
        ylabel="Sorting time (seconds)",
        output_path=output_dir / "cumulative_sorting_time_over_time.png",
        max_x=execution_limit,
    )

def create_processing_time_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    create_combined_processing_time_over_time_comparison(
        comparison_series, output_dir, max_minutes
    )


def create_comparison_series(
    summary_dir: Path,
    max_minutes: float | None,
) -> dict[str, object]:
    snapshots = load_snapshots(summary_dir)
    start_seconds = snapshots[0]["runtime_seconds"]
    runtime_minutes = [
        (snapshot["runtime_seconds"] - start_seconds) / 60
        for snapshot in snapshots
    ]

    if max_minutes is not None:
        snapshots = [
            snapshot
            for snapshot, minute in zip(snapshots, runtime_minutes)
            if minute <= max_minutes
        ]
        runtime_minutes = [
            (snapshot["runtime_seconds"] - start_seconds) / 60
            for snapshot in snapshots
        ]

    if not snapshots:
        raise SystemExit(
            f"No snapshots in {summary_dir} fall within the {max_minutes:g}-minute execution window"
        )

    return {
        "name": summary_dir.name,
        "label": format_run_name(summary_dir.name),
        "runtime_minutes": runtime_minutes,
        "tests_run": [snapshot["tests_run"] for snapshot in snapshots],
        "sorting_seconds": [snapshot["sorting_seconds"] for snapshot in snapshots],
        "combined_processing_seconds": [
            snapshot["true_minification_seconds"] + snapshot["sorting_seconds"]
            for snapshot in snapshots
        ],
    }


def create_total_runtime_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    max_runtime_minutes = (
        max_minutes
        if max_minutes is not None
        else max(max(series["runtime_minutes"]) for series in comparison_series)
    )
    time_scale, time_label, time_tick_interval = execution_time_axis(max_runtime_minutes)
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)

    for index, series in enumerate(comparison_series):
        ax.plot(
            [minute / time_scale for minute in series["runtime_minutes"]],
            series["tests_run"],
            marker="o",
            linewidth=2,
            color=line_color(index),
            label=series["label"],
        )

    max_tests_run = max(max(series["tests_run"]) for series in comparison_series)
    ax.set_title("Test Cases Executed Over Execution Time Across Configurations")
    ax.set_xlabel(time_label)
    ax.set_ylabel("Test cases executed")
    ax.set_xlim(0, max_runtime_minutes / time_scale)
    ax.set_ylim(0, max_tests_run * 1.05 if max_tests_run else 1)
    ax.xaxis.set_major_locator(MultipleLocator(time_tick_interval))
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        output_dir
        / "test_cases_executed_over_execution_time_across_configurations.png"
    )
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def create_combined_processing_time_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)

    for index, series in enumerate(comparison_series):
        ax.plot(
            series["tests_run"],
            series["combined_processing_seconds"],
            marker="o",
            linewidth=2,
            color=line_color(index),
            label=series["label"],
        )

    max_tests_run = max(max(series["tests_run"]) for series in comparison_series)
    max_processing_seconds = max(
        max(series["combined_processing_seconds"])
        for series in comparison_series
    )

    ax.set_title("Combined Minimization and Clustering Time by Test Cases Executed")
    ax.set_xlabel("Test cases executed")
    ax.set_ylabel("Minimization and clustering time (seconds)")
    ax.set_xlim(0, max_tests_run)
    ax.set_ylim(0, max_processing_seconds * 1.05 if max_processing_seconds else 1)
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        output_dir
        / "combined_minimization_and_clustering_time_by_test_cases_executed.png"
    )
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def create_combined_processing_time_over_time_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    max_runtime_minutes = (
        max_minutes
        if max_minutes is not None
        else max(max(series["runtime_minutes"]) for series in comparison_series)
    )
    time_scale, time_label, time_tick_interval = execution_time_axis(max_runtime_minutes)
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)

    for index, series in enumerate(comparison_series):
        ax.plot(
            [minute / time_scale for minute in series["runtime_minutes"]],
            series["combined_processing_seconds"],
            marker="o",
            linewidth=2,
            color=line_color(index),
            label=series["label"],
        )

    max_processing_seconds = max(
        max(series["combined_processing_seconds"])
        for series in comparison_series
    )

    ax.set_title("Post-Processing Time Over Time")
    ax.set_xlabel(time_label)
    ax.set_ylabel("Post-Processing time (seconds)")
    ax.set_xlim(0, max_runtime_minutes / time_scale)
    ax.set_ylim(0, max_processing_seconds * 1.05 if max_processing_seconds else 1)
    ax.xaxis.set_major_locator(MultipleLocator(time_tick_interval))
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "combined_minimization_and_clustering_time_over_time.png"
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def create_sorting_time_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)

    for index, series in enumerate(comparison_series):
        ax.plot(
            series["tests_run"],
            series["sorting_seconds"],
            marker="o",
            linewidth=2,
            color=line_color(index),
            label=series["label"],
        )

    max_tests_run = max(max(series["tests_run"]) for series in comparison_series)
    max_sorting_seconds = max(
        max(series["sorting_seconds"])
        for series in comparison_series
    )

    ax.set_title("Cumulative Sorting Time by Test Cases Executed")
    ax.set_xlabel("Test cases executed")
    ax.set_ylabel("Sorting time (seconds)")
    ax.set_xlim(0, max_tests_run)
    ax.set_ylim(0, max_sorting_seconds * 1.05 if max_sorting_seconds else 1)
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "cumulative_sorting_time_by_test_cases_executed.png"
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def create_sorting_time_over_time_comparison(
    comparison_series: list[dict[str, object]],
    output_dir: Path,
    max_minutes: float | None,
) -> None:
    max_runtime_minutes = (
        max_minutes
        if max_minutes is not None
        else max(max(series["runtime_minutes"]) for series in comparison_series)
    )
    time_scale, time_label, time_tick_interval = execution_time_axis(max_runtime_minutes)
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)

    for index, series in enumerate(comparison_series):
        ax.plot(
            [minute / time_scale for minute in series["runtime_minutes"]],
            series["sorting_seconds"],
            marker="o",
            linewidth=2,
            color=line_color(index),
            label=series["label"],
        )

    max_sorting_seconds = max(
        max(series["sorting_seconds"])
        for series in comparison_series
    )

    ax.set_title("Cumulative Sorting Time Over Time")
    ax.set_xlabel(time_label)
    ax.set_ylabel("Sorting time (seconds)")
    ax.set_xlim(0, max_runtime_minutes / time_scale)
    ax.set_ylim(0, max_sorting_seconds * 1.05 if max_sorting_seconds else 1)
    ax.xaxis.set_major_locator(MultipleLocator(time_tick_interval))
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "cumulative_sorting_time_over_time_by_configuration.png"
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def load_snapshots(summary_dir: Path) -> list[dict[str, float]]:
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
                "runtime_seconds": float(data["runtime_seconds"]),
                "tests_run": data["tests_run"],
                "true_minification_seconds": data["true_minification_seconds"],
                "sorting_seconds": data["sorting_seconds"],
            }
        )

    if not snapshots:
        raise SystemExit(f"No timestamped run_summary_*s.json snapshots found in {summary_dir}")

    return sorted(snapshots, key=lambda snapshot: snapshot["runtime_seconds"])


def save_line_plot(
    x: list[float],
    y: list[float],
    title: str,
    xlabel: str,
    ylabel: str,
    output_path: Path,
    max_x: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.plot(x, y, marker="o", linewidth=2)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, max_x if max_x is not None else max(x))
    ax.set_ylim(0, maximize(y) * 1.05)
    if xlabel.startswith("Execution time"):
        ax.xaxis.set_major_locator(
            MultipleLocator(1 if xlabel.endswith("hours)") else 10)
        )
    ax.grid(True, alpha=0.3)
    increase_plot_font_sizes(ax)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")


def maximize(values: list[float]) -> float:
    value = max(values)
    if value == 0:
        return 1
    return value


if __name__ == "__main__":
    main()
