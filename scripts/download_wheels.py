"""Download platform wheels at runtime lock versions, verifying locked hashes."""

import subprocess
import sys
import tomllib
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((root / "poetry.lock").read_text(encoding="utf-8"))
    output = root / "dist/wheels"
    output.mkdir(parents=True, exist_ok=True)
    lines = []
    for package in lock["package"]:
        if "main" not in package["groups"] or package.get("source", {}).get("type") == "directory":
            continue
        hashes = " ".join("--hash=" + f["hash"] for f in package["files"])
        if not hashes:
            raise RuntimeError(f"Missing hashes for {package['name']}")
        lines.append(f"{package['name']}=={package['version']} {hashes}")
    requirements = output.parent / "runtime-requirements.txt"
    requirements.write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--no-deps",
            "--require-hashes",
            "--dest",
            str(output),
            "-r",
            str(requirements),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
