"""Check YAML plus security invariants before running the workflow remotely."""

import re
from pathlib import Path

import yaml


def main():
    root = Path(__file__).resolve().parents[1]
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    if workflow["permissions"] != {"contents": "read"}:
        raise RuntimeError("Workflow must be read-only")
    if "pull_request_target" in workflow["on"]:
        raise RuntimeError("Privileged PR execution forbidden")
    for job in workflow["jobs"].values():
        if "timeout-minutes" not in job:
            raise RuntimeError("Every job needs timeout")
        for step in job["steps"]:
            if "uses" in step and not re.fullmatch(r"[\w-]+/[\w-]+@[0-9a-f]{40}", step["uses"]):
                raise RuntimeError("Every action must be pinned to a full commit SHA")
            if "continue-on-error" in step:
                raise RuntimeError("No advisory quality gates")
    if "required" not in workflow["jobs"]:
        raise RuntimeError("Missing aggregate required check")
    print("Workflow syntax and security invariants passed.")


if __name__ == "__main__":
    main()
