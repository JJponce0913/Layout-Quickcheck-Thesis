"""Create a descending bar chart of Firefox bug-group sizes.

Run from any directory:
    python scripts/graph_firefox_bug_groups.py

Optional arguments:
    graph_firefox_bug_groups.cmd C:/runs/firefox-sort C:/reports/groups.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_RESULTS_DIRECTORY = Path(r"D:\bug\postfix\firefox-sort")
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "figures"
    / "rq3"
    / "firefox_bug_group_sizes.png"
)


def get_group_sizes(results_directory: Path) -> list[tuple[str, int]]:
    if not results_directory.is_dir():
        raise FileNotFoundError(f"Firefox results directory not found: {results_directory}")

    groups = []
    for group in results_directory.glob("bug-group-*"):
        if group.is_dir():
            instance_count = sum(
                item.is_dir() and item.name.startswith("bug-") for item in group.iterdir()
            )
            groups.append((group.name, instance_count))

    single_bug_count = sum(
        item.is_dir()
        and item.name.startswith("bug-")
        and not item.name.startswith("bug-group-")
        for item in results_directory.iterdir()
    )
    if single_bug_count:
        groups.append(("Single bugs", single_bug_count))

    if not groups:
        raise ValueError(f"No bug-group-* or bug-* directories found in: {results_directory}")

    return sorted(groups, key=lambda item: (-item[1], item[0]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Chart Firefox bug groups by number of bug instances.")
    parser.add_argument("results_directory", nargs="?", type=Path, default=DEFAULT_RESULTS_DIRECTORY)
    parser.add_argument("output", nargs="?", type=Path, help="PNG output path")
    args = parser.parse_args()

    results_directory = args.results_directory.resolve()
    output = (args.output or DEFAULT_OUTPUT).resolve()
    groups = get_group_sizes(results_directory)

    names, counts = zip(*groups)
    figure_width = max(12, len(groups) * 0.32)
    figure, axis = plt.subplots(figsize=(figure_width, 7), dpi=140)
    positions = range(len(groups))
    axis.bar(positions, counts, color="#2563eb")
    axis.set_xticks(list(positions), labels=names, rotation=60, ha="right")
    axis.set_ylabel("Bug instances")
    axis.set_title(f"Firefox bug groups by instance count ({len(groups)} groups)")
    axis.grid(axis="y", alpha=0.3)
    axis.set_axisbelow(True)

    largest_count = max(counts)
    axis.set_ylim(0, largest_count * 1.12)
    for position, count in zip(positions, counts):
        axis.text(position, count + largest_count * 0.01, str(count), ha="center", fontweight="bold")

    figure.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    print(f"Saved plot to {output} ({len(groups)} groups; largest group has {largest_count} instances).")


if __name__ == "__main__":
    main()
