"""Create a standalone CSS-style-elements-by-report-type figure.

Usage:
    python css_style_elements_by_report_type.py LQC_DIR

``LQC_DIR`` must be a Layout QuickCheck directory containing ``bug-group-*``
directories. The script reads original and minimized reports plus each
group's extracted rule.

Optional parameters:
    --output PATH
        Output PNG path. Defaults to ``figures/firefox_style_elements.png``.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


STYLE_ASSIGNMENT = re.compile(r"\.style\s*\[")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "figures" / "firefox_style_elements.png"


def bug_directories(parent: Path, cutoff: datetime | None = None) -> list[Path]:
    return sorted(
        path
        for path in parent.glob("bug-*")
        if path.is_dir() and not path.name.startswith("bug-group-")
        and (
            cutoff is None
            or datetime.fromisoformat(
                json.loads((path / "data.json").read_text(encoding="utf-8"))["datetime"]
            )
            <= cutoff
        )
    )


def minified_file(directory: Path) -> Path | None:
    for name in ("minified_bug.html", "minified.html"):
        path = directory / name
        if path.is_file():
            return path
    return None


def html_count(path: Path) -> int:
    return len(STYLE_ASSIGNMENT.findall(path.read_text(encoding="utf-8")))


def rule_count(path: Path) -> int:
    rule = json.loads(path.read_text(encoding="utf-8")).get("rule_class", {})
    return len(rule.get("base_style", [])) + len(rule.get("modified_style", []))


def collect_counts(
    directory: Path, snapshot_seconds: int | None = None
) -> tuple[int, int, int]:
    cutoff = None
    allowed_groups = None
    if snapshot_seconds is not None:
        snapshot = json.loads(
            (directory / f"run_summary_{snapshot_seconds}s.json").read_text(
                encoding="utf-8"
            )
        )
        cutoff = datetime.fromisoformat(snapshot["updated_at"])
        allowed_groups = set(snapshot["bug_groups"])
    groups = sorted(
        path
        for path in directory.glob("bug-group-*")
        if path.is_dir() and (allowed_groups is None or path.name in allowed_groups)
    )
    bugs = [bug for group in groups for bug in bug_directories(group, cutoff)]
    originals = [bug / "original_bug.html" for bug in bugs if (bug / "original_bug.html").is_file()]
    minimized = [
        path
        for bug in bugs
        if (path := minified_file(bug)) is not None
        and (original := bug / "original_bug.html").is_file()
        and html_count(path) < html_count(original)
    ]
    if not originals:
        raise SystemExit(f"No complete grouped reports found in {directory}")

    clustered = 0
    for group in groups:
        representatives = bug_directories(group, cutoff)
        rule = group / "extracted_rule.json"
        if not representatives or not rule.is_file():
            raise SystemExit(f"Incomplete Layout QuickCheck bug group: {group}")
        representative = minified_file(representatives[0])
        if representative is None:
            raise SystemExit(f"No minimized representative found in {group}")
        clustered += rule_count(rule) + html_count(representative)
    return sum(map(html_count, originals)), sum(map(html_count, minimized)), clustered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lqc_dir", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snapshot-seconds", type=int)
    arguments = parser.parse_args()
    try:
        counts = collect_counts(arguments.lqc_dir, arguments.snapshot_seconds)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise SystemExit(f"Cannot read Layout QuickCheck results: {error}") from error

    figure, axis = plt.subplots(figsize=(7, 5), dpi=140)
    bars = axis.bar(
        ["Original\nReports", "Minimized\nReports", "Clustered\nReports"],
        counts,
        color=["#1e3a8a", "#16a34a", "#2563eb"],
    )
    axis.set_title("CSS Style Elements by Report Type", fontsize=20)
    axis.set_ylabel("Total CSS properties", fontsize=18)
    axis.tick_params(axis="x", labelsize=18)
    axis.tick_params(axis="y", labelsize=10)
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
            fontsize=10,
        )
    figure.tight_layout()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(arguments.output)
    plt.close(figure)
    print(f"Saved standalone figure to {arguments.output.resolve()}")


if __name__ == "__main__":
    main()
