"""One fail-fast local/CI entry point. Does not connect to IBKR."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    commands = [
        ["poetry", "check", "--strict"],
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "mypy"],
        [sys.executable, "scripts/check_boundaries.py"],
        [sys.executable, "scripts/check_workflow.py"],
        [sys.executable, "-m", "coverage", "run", "scripts/run_tests.py"],
        [sys.executable, "-m", "coverage", "json"],
        [sys.executable, "-m", "coverage", "xml"],
        [sys.executable, "scripts/check_coverage.py"],
    ]
    for command in commands:
        print("Checking:", " ".join(command), flush=True)
        subprocess.run(command, cwd=root, check=True)
    print(
        "All local quality gates passed. Run dependency audit and clean-wheel validation separately."
    )


if __name__ == "__main__":
    main()
