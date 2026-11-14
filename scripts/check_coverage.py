"""Require >=90% statement+branch coverage per library; >=95% risk/execution."""

import json
from pathlib import Path


def main():
    report = json.loads(Path("coverage.json").read_text(encoding="utf-8"))
    totals = {}
    for name, data in report["files"].items():
        parts = name.replace("\\", "/").split("/")
        if "libs" not in parts:
            continue
        library = parts[parts.index("libs") + 1]
        summary = data["summary"]
        covered = summary["covered_lines"] + summary["covered_branches"]
        possible = summary["num_statements"] + summary["num_branches"]
        a, b = totals.get(library, (0, 0))
        totals[library] = (a + covered, b + possible)
    if len(totals) != 11:
        raise RuntimeError("Coverage must include all 11 libraries")
    failures = []
    for name, (covered, possible) in sorted(totals.items()):
        threshold = 95 if name in ("trading-risk", "trading-execution") else 90
        percent = 100 * covered / possible if possible else 100
        print(f"{name}: {percent:.2f}% (required {threshold}%)")
        if percent < threshold:
            failures.append(name)
    if failures:
        raise SystemExit("Coverage gates failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
