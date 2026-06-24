"""Compare CSS style-element volume across Firefox triage stages."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_RESULTS_DIRECTORY = Path(r"D:\bug\postfix\firefox-sort")
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "figures"
    / "rq3"
    / "firefox_style_elements.png"
)
STYLE_ASSIGNMENT = re.compile(r"\.style\s*\[")
DATA_FILE = Path(__file__).resolve().parents[1] / "data.tex"
STYLE_REDUCTION_MACROS = (
    "StyleElementOriginalToMinimizedReduction",
    "StyleElementOriginalToClusteredReduction",
    "StyleElementMinimizedToClusteredReduction",
)


def minified_file(bug_directory: Path) -> Path | None:
    for filename in ("minified_bug.html", "minified.html"):
        candidate = bug_directory / filename
        if candidate.is_file():
            return candidate
    return None


def bug_directories(parent: Path) -> list[Path]:
    return sorted(
        directory
        for directory in parent.glob("bug-*")
        if directory.is_dir() and not directory.name.startswith("bug-group-")
    )


def html_style_element_count(path: Path) -> int:
    """Count dynamic CSS property assignments in a generated bug HTML file."""
    return len(STYLE_ASSIGNMENT.findall(path.read_text(encoding="utf-8")))


def extracted_rule_style_element_count(path: Path) -> int:
    """Count base and modified CSS declarations in an extracted rule."""
    with path.open("r", encoding="utf-8") as file:
        rule = json.load(file)
    rule_class = rule.get("rule_class", {})
    return len(rule_class.get("base_style", [])) + len(rule_class.get("modified_style", []))


def collect_counts(results_directory: Path) -> tuple[int, int, int]:
    if not results_directory.is_dir():
        raise FileNotFoundError(f"Firefox results directory not found: {results_directory}")

    group_directories = sorted(
        directory
        for directory in results_directory.glob("bug-group-*")
        if directory.is_dir()
    )
    all_bug_directories = [
        bug_directory
        for group_directory in group_directories
        for bug_directory in bug_directories(group_directory)
    ]
    original_files = [
        directory / "original_bug.html"
        for directory in all_bug_directories
        if (directory / "original_bug.html").is_file()
    ]
    minified_files = [
        minified
        for directory in all_bug_directories
        if (minified := minified_file(directory)) is not None
    ]
    if not original_files or not minified_files:
        raise ValueError("No complete original/minified bug-report pairs found.")

    clustered_count = 0
    for group_directory in group_directories:
        rule_path = group_directory / "extracted_rule.json"
        representatives = bug_directories(group_directory)
        if not rule_path.is_file() or not representatives:
            raise ValueError(f"Incomplete bug group: {group_directory}")
        representative = minified_file(representatives[0])
        if representative is None:
            raise ValueError(f"No minified representative in: {group_directory}")
        clustered_count += extracted_rule_style_element_count(rule_path)
        clustered_count += html_style_element_count(representative)

    return (
        sum(html_style_element_count(path) for path in original_files),
        sum(html_style_element_count(path) for path in minified_files),
        clustered_count,
    )


def update_data_file(reductions: tuple[float, float, float]) -> None:
    """Update the grouped style-element reduction macros."""
    contents = DATA_FILE.read_text(encoding="utf-8")
    for macro, reduction in zip(STYLE_REDUCTION_MACROS, reductions):
        pattern = re.compile(rf"(\\newcommand\{{\\{macro}\}}\{{)[^}}]*(\}})")
        contents, replacements = pattern.subn(
            lambda match: f"{match.group(1)}{reduction:.2f}\\%{match.group(2)}",
            contents,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"Could not find {macro} in {DATA_FILE}")
    DATA_FILE.write_text(contents, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Chart CSS style-element volume across Firefox triage stages."
    )
    parser.add_argument("results_directory", nargs="?", type=Path, default=DEFAULT_RESULTS_DIRECTORY)
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    counts = collect_counts(args.results_directory)
    labels = ["Grouped original\nreports", "Grouped minimized\nreports", "Clustered\ngroup output"]
    colors = ["#64748b", "#2563eb", "#16a34a"]

    figure, axis = plt.subplots(figsize=(7, 5), dpi=140)
    bars = axis.bar(labels, counts, color=colors)
    axis.set_title("CSS Style Elements")
    axis.set_ylabel("Total CSS Properties")
    axis.grid(axis="y", alpha=0.3)
    axis.set_axisbelow(True)
    for bar, count in zip(bars, counts):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            count,
            f"{count:,}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    original_to_minimized = 100 * (1 - counts[1] / counts[0])
    original_to_clustered = 100 * (1 - counts[2] / counts[0])
    minimized_to_clustered = 100 * (1 - counts[2] / counts[1])
    update_data_file(
        (original_to_minimized, original_to_clustered, minimized_to_clustered)
    )
    figure.tight_layout()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output)
    plt.close(figure)
    print(f"Saved plot to {output} (grouped original/minimized/clustered: {counts}).")
    print(f"Original to minimized reduction: {original_to_minimized:.2f}%")
    print(f"Original to clustered reduction: {original_to_clustered:.2f}%")
    print(f"Minimized to clustered reduction: {minimized_to_clustered:.2f}%")
    print(f"Updated {DATA_FILE}")


if __name__ == "__main__":
    main()
