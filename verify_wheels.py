"""Verify wheel metadata, SDK isolation and clean installed integration tests."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import tomllib
import venv
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile


def main():
    root = Path(__file__).resolve().parent
    wheels = root / "dist" / "wheels"
    projects = [
        tomllib.loads(p.read_text(encoding="utf-8"))["project"]
        for p in [root / "pyproject.toml", *sorted((root / "libs").glob("*/pyproject.toml"))]
    ]
    expected = {p["name"]: p["version"] for p in projects}
    observed = {}
    lock = tomllib.loads((root / "poetry.lock").read_text(encoding="utf-8"))
    trusted = {f["hash"] for p in lock["package"] if "main" in p["groups"] for f in p["files"]}
    for wheel in wheels.glob("*.whl"):
        if not wheel.name.startswith(("trading_", "ibkr_paper_trader")):
            if "sha256:" + hashlib.sha256(wheel.read_bytes()).hexdigest() not in trusted:
                raise RuntimeError(f"Third-party wheel is not in the runtime lock: {wheel.name}")
            continue
        with ZipFile(wheel) as archive:
            metadata = archive.read(
                next(n for n in archive.namelist() if n.endswith(".dist-info/METADATA"))
            ).decode()
            if any(x in metadata for x in ("file://", " @ ", "C:\\Users\\")):
                raise RuntimeError(f"Nonportable package metadata: {wheel.name}")
            parsed = Parser().parsestr(metadata)
            name = parsed["Name"]
            if name in observed:
                raise RuntimeError(f"Duplicate/stale wheel: {name}")
            observed[name] = parsed["Version"]
            if name.startswith("trading-") and not any(
                n.endswith("/py.typed") for n in archive.namelist()
            ):
                raise RuntimeError(f"Missing typing marker: {name}")
    if observed != expected:
        raise RuntimeError("Built wheel names/versions do not match the source projects")
    with tempfile.TemporaryDirectory(prefix="trading-wheels-") as folder:
        work = Path(folder)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)

        def create(name):
            location = work / name
            venv.EnvBuilder(with_pip=True).create(location)
            return location / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(python, *args):
            subprocess.run([str(python), *args], cwd=work, env=env, check=True)

        minimal = create("minimal")
        run(
            minimal,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheels),
            f"trading-strategy=={expected['trading-strategy']}",
        )
        run(
            minimal,
            "-c",
            "import importlib.util; from trading_strategy import SmaStrategy; assert importlib.util.find_spec('ib_async') is None; assert importlib.util.find_spec('paper_trader') is None; print('Strategy installs without broker SDK or application')",
        )
        full = create("full")
        run(
            full,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheels),
            f"ibkr-paper-trader=={expected['ibkr-paper-trader']}",
        )
        run(full, "-m", "pip", "check")
        run(
            full,
            "-c",
            "import sys; from pathlib import Path; import trading_engine, trading_ibkr, paper_trader; assert all(Path(m.__file__).is_relative_to(Path(sys.prefix)) for m in (trading_engine,trading_ibkr,paper_trader)); print('Imports resolve to installed wheels, not editable source')",
        )
        shutil.copytree(
            root / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__")
        )
        shutil.copy(root / "scripts" / "run_tests.py", work / "run_tests.py")
        run(full, "run_tests.py")
        print("Independent and full application wheel verification passed.")


if __name__ == "__main__":
    main()
