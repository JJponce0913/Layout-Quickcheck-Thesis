from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_SUMMARY_DIRS = [Path("bug_reports") / "tester"]
DEFAULT_OUTPUT_DIR = Path("graphs") / "r3"
SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")
DATA_FILE = Path(__file__).resolve().parents[1] / "data.tex"
TITLE_FONT_SIZE = 24
LABEL_FONT_SIZE = 22
TICK_FONT_SIZE = 20
LEGEND_FONT_SIZE = 20
FIREFOX_SORTING_MACROS = {
    "FirefoxSortingReports": "bugs_found",
    "FirefoxSortingGroups": "bug_group_count",
    "FirefoxSortingSingleBugs": "single_bug_count",
}


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Create RQ3 bug uniqueness graphs.")
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
        help="Local folder where graph outputs should be saved.",
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DATA_FILE,
        help="data.tex file containing the Firefox sorting endpoint macros.",
    )
    parser.add_argument(
        "--update-firefox-sorting-macros",
        action="store_true",
        help=(
            "Update Firefox sorting endpoint macros from the final snapshot. "
            "Requires exactly one summary directory."
        ),
    )
    args = parser.parse_args()

    if args.update_firefox_sorting_macros and len(args.summary_dirs) != 1:
        parser.error("--update-firefox-sorting-macros requires exactly one summary directory.")

    for summary_dir in args.summary_dirs:
        output_dir = args.output_dir / summary_dir.name
        snapshots = create_graphs(summary_dir, output_dir)
        if args.update_firefox_sorting_macros:
            update_firefox_sorting_macros(args.data_file, snapshots[-1])


def create_graphs(summary_dir: Path, output_dir: Path) -> list[dict[str, float]]:
    snapshots = load_snapshots(summary_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    elapsed_hours = [snapshot["runtime_seconds"] / 3600 for snapshot in snapshots]
    bug_groups = [snapshot["bug_group_count"] for snapshot in snapshots]
    single_bugs = [snapshot["single_bug_count"] for snapshot in snapshots]
    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.plot(elapsed_hours, bug_groups, marker="o", linewidth=2, label="Bug groups")
    ax.plot(elapsed_hours, single_bugs, marker="o", linewidth=2, label="Single bugs")

    ax.set_title("Bug Groups and Single Bugs Over Time")
    ax.set_xlabel("Execution time (hours)")
    ax.set_ylabel("Count")
    ax.set_xlim(0, max(elapsed_hours))
    ax.set_ylim(0, max(max(bug_groups), max(single_bugs)) + 2)
    ax.grid(True, alpha=0.3)
    ax.legend()
    increase_plot_font_sizes(ax)
    fig.tight_layout()

    output_path = (
        output_dir
        / "bug_groups_and_single_bugs_over_time.png"
    )
    fig.savefig(output_path)
    plt.close(fig)
    print(f"Saved plot to {output_path}")
    return snapshots


def update_firefox_sorting_macros(data_file: Path, snapshot: dict[str, float]) -> None:
    """Update Firefox sorting endpoint values in data.tex."""
    contents = data_file.read_text(encoding="utf-8")

    for macro, field in FIREFOX_SORTING_MACROS.items():
        pattern = re.compile(rf"(\\newcommand\{{\\{macro}\}}\{{)[^}}]*(\}})")
        value = str(int(snapshot[field]))
        contents, replacements = pattern.subn(rf"\g<1>{value}\g<2>", contents, count=1)
        if replacements != 1:
            raise ValueError(f"Could not find exactly one {macro} macro in {data_file}.")

    data_file.write_text(contents, encoding="utf-8")
    print(f"Updated Firefox sorting endpoint macros in {data_file}")


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
                "bugs_found": data["bugs_found"],
                "bug_group_count": data["bug_group_count"],
                "single_bug_count": data["single_bug_count"],
            }
        )

    if not snapshots:
        raise SystemExit(f"No timestamped run_summary_*s.json snapshots found in {summary_dir}")

    return sorted(snapshots, key=lambda snapshot: snapshot["runtime_seconds"])


if __name__ == "__main__":
    main()
