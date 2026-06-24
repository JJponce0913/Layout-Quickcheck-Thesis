from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt


DEFAULT_SUMMARY_DIRS = [Path("bug_reports") / "tester"]
DEFAULT_OUTPUT_DIR = Path("graphs") / "r3"
SNAPSHOT_PATTERN = re.compile(r"^run_summary_(\d+)s\.json$")


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
    args = parser.parse_args()

    for summary_dir in args.summary_dirs:
        output_dir = args.output_dir / summary_dir.name
        create_graphs(summary_dir, output_dir)


def create_graphs(summary_dir: Path, output_dir: Path) -> None:
    snapshots = load_snapshots(summary_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    elapsed_hours = [snapshot["runtime_seconds"] / 3600 for snapshot in snapshots]
    bug_groups = [snapshot["bug_group_count"] for snapshot in snapshots]
    single_bugs = [snapshot["single_bug_count"] for snapshot in snapshots]
    endpoint_minutes = snapshots[-1]["runtime_seconds"] / 60

    fig, ax = plt.subplots(figsize=(11, 6), dpi=140)
    ax.plot(elapsed_hours, bug_groups, marker="o", linewidth=2, label="Bug groups")
    ax.plot(elapsed_hours, single_bugs, marker="o", linewidth=2, label="Single bugs")

    ax.set_title(
        f"Bug Groups and Single Bugs Over Time ({endpoint_minutes:g} min Test Run)"
    )
    ax.set_xlabel("Execution time (hours)")
    ax.set_ylabel("Count")
    ax.set_xlim(0, max(elapsed_hours))
    ax.set_ylim(0, max(max(bug_groups), max(single_bugs)) + 2)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    output_path = (
        output_dir
        / "bug_groups_and_single_bugs_over_time.png"
    )
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
