"""Build independent wheels and the composition app. Does not publish anything."""

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    output = root / "dist" / "wheels"
    output.mkdir(parents=True, exist_ok=True)
    # Remove only this project's prior built wheels inside the verified output
    # directory, so a version bump cannot leave a stale candidate installable.
    for wheel in output.glob("*.whl"):
        if wheel.name.startswith(("trading_", "ibkr_paper_trader")):
            if wheel.resolve().parent != output.resolve():
                raise RuntimeError("Wheel escaped the intended output directory")
            wheel.unlink()
    for project in [*sorted((root / "libs").iterdir()), root]:
        if not (project / "pyproject.toml").exists():
            continue
        subprocess.run(
            ["poetry", "build", "--format", "wheel", "--output", str(output)],
            cwd=project,
            check=True,
        )
    print("Wheels built locally:", output)


if __name__ == "__main__":
    main()
