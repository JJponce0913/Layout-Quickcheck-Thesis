"""Populate RQ1 table macros from 60-minute run-summary snapshots.

The table's speed is executed tests divided by the intended 60-minute
snapshot window, and its rate is bugs found divided by executed tests.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Mapping


SNAPSHOT_SECONDS = 3_600
SNAPSHOT_FILENAME = f"run_summary_{SNAPSHOT_SECONDS}s.json"
DATA_FILE = Path(__file__).resolve().parents[1] / "data.tex"
DEFAULT_RUNS = {
    "ChromiumNoWeights": Path(r"D:\bug\postfix\chromium-no-weights"),
    "ChromiumWeights": Path(r"D:\bug\postfix\chromium-sort"),
    "FirefoxNoWeights": Path(r"D:\bug\postfix\firefox-no-weights"),
    "FirefoxWeights": Path(r"D:\bug\postfix\firefox-sort"),
}


def snapshot_metrics(summary: Mapping[str, object]) -> dict[str, str]:
    """Calculate formatted table values from one 60-minute summary."""
    try:
        tests_run = int(summary["tests_run"])
        bugs_found = int(summary["bugs_found"])
    except KeyError as error:
        raise ValueError(f"Missing required field: {error.args[0]}") from error
    except (TypeError, ValueError) as error:
        raise ValueError("tests_run and bugs_found must be integers.") from error

    if tests_run <= 0:
        raise ValueError("tests_run must be greater than zero.")
    if bugs_found < 0:
        raise ValueError("bugs_found cannot be negative.")

    return {
        "Speed": f"{tests_run / (SNAPSHOT_SECONDS / 60):.1f}",
        "Bugs": str(bugs_found),
        "Rate": f"{bugs_found / tests_run * 100:.3f}\\%",
    }


def replace_macro(contents: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\\newcommand\{{\\{re.escape(name)}\}}\{{)[^}}]*(\}})")
    updated, replacements = pattern.subn(rf"\g<1>{value}\g<2>", contents, count=1)
    if replacements != 1:
        raise ValueError(f"Could not find exactly one {name} macro.")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update RQ1 data.tex macros from 3,600-second snapshots."
    )
    parser.add_argument("--data-file", type=Path, default=DATA_FILE)
    parser.add_argument("--chromium-no-weights", type=Path, default=DEFAULT_RUNS["ChromiumNoWeights"])
    parser.add_argument("--chromium-weights", type=Path, default=DEFAULT_RUNS["ChromiumWeights"])
    parser.add_argument("--firefox-no-weights", type=Path, default=DEFAULT_RUNS["FirefoxNoWeights"])
    parser.add_argument("--firefox-weights", type=Path, default=DEFAULT_RUNS["FirefoxWeights"])
    args = parser.parse_args()

    run_dirs = {
        "ChromiumNoWeights": args.chromium_no_weights,
        "ChromiumWeights": args.chromium_weights,
        "FirefoxNoWeights": args.firefox_no_weights,
        "FirefoxWeights": args.firefox_weights,
    }
    contents = args.data_file.read_text(encoding="utf-8")
    for prefix, run_dir in run_dirs.items():
        snapshot_path = run_dir / SNAPSHOT_FILENAME
        try:
            summary = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise SystemExit(f"Snapshot not found: {snapshot_path}") from error
        except json.JSONDecodeError as error:
            raise SystemExit(f"Invalid JSON in {snapshot_path}: {error}") from error

        for suffix, value in snapshot_metrics(summary).items():
            contents = replace_macro(contents, f"{prefix}{suffix}", value)
        print(f"{prefix}: {snapshot_metrics(summary)}")

    args.data_file.write_text(contents, encoding="utf-8")
    print(f"Updated {args.data_file}")


if __name__ == "__main__":
    main()
