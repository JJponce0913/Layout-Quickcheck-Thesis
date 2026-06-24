"""Calculate minimization-and-sorting runtime as a percentage of a run."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping


REQUIRED_FIELDS = (
    "true_minification_seconds",
    "sorting_seconds",
    "runtime_seconds",
)
DATA_FILE = Path(__file__).resolve().parents[1] / "data.tex"
MACRO_PATTERN = re.compile(
    r"(\\newcommand\{\\RuntimePercentMinClust\}\{)[^}]*(\})"
)


def calculate_percentage(summary: Mapping[str, object]) -> tuple[float, float, float]:
    """Return post-processing seconds, runtime seconds, and their percentage."""
    try:
        minification_seconds = float(summary["true_minification_seconds"])
        sorting_seconds = float(summary["sorting_seconds"])
        runtime_seconds = float(summary["runtime_seconds"])
    except KeyError as error:
        raise ValueError(f"Missing required field: {error.args[0]}") from error
    except (TypeError, ValueError) as error:
        raise ValueError("All timing fields must be numeric.") from error

    if runtime_seconds <= 0:
        raise ValueError("runtime_seconds must be greater than zero.")

    post_processing_seconds = minification_seconds + sorting_seconds
    percentage = post_processing_seconds / runtime_seconds * 100
    return post_processing_seconds, runtime_seconds, percentage


def update_data_file(percentage: float, data_file: Path = DATA_FILE) -> None:
    """Replace the RuntimePercentMinClust macro in data.tex."""
    try:
        contents = data_file.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Cannot read {data_file}: {error}") from error

    updated_contents, replacements = MACRO_PATTERN.subn(
        lambda match: f"{match.group(1)}{percentage:.2f}\\%{match.group(2)}",
        contents,
        count=1,
    )
    if replacements != 1:
        raise ValueError(
            f"Could not find exactly one RuntimePercentMinClust macro in {data_file}"
        )

    try:
        data_file.write_text(updated_contents, encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Cannot write {data_file}: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate (true_minification_seconds + sorting_seconds) / "
            "runtime_seconds for a run summary."
        )
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing run_summary.json.",
    )
    parser.add_argument(
        "--latex",
        action="store_true",
        help="Print the value as a RuntimePercentMinClust LaTeX macro.",
    )
    args = parser.parse_args()

    summary_path = args.folder / "run_summary.json"
    if not summary_path.is_file():
        raise SystemExit(f"No run_summary.json found in {args.folder}")

    try:
        with summary_path.open("r", encoding="utf-8") as file:
            summary = json.load(file)
        post_processing_seconds, runtime_seconds, percentage = calculate_percentage(summary)
        update_data_file(percentage)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Cannot calculate percentage: {error}") from error

    if args.latex:
        print(f"\\newcommand{{\\RuntimePercentMinClust}}{{{percentage:.2f}\\%}}")
        return

    print(f"Minification and sorting: {post_processing_seconds:.2f} seconds")
    print(f"Runtime: {runtime_seconds:.2f} seconds")
    print(f"RuntimePercentMinClust: {percentage:.2f}%")
    print(f"Updated {DATA_FILE}")


if __name__ == "__main__":
    main()
