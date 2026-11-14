"""Package an explicit public source allowlist and verified wheel candidates."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "dist" / "release"
    output.mkdir(parents=True, exist_ok=True)
    # Never traverse the whole workspace: account configs and runtime are private.
    files = [
        p
        for p in root.iterdir()
        if p.name
        in {
            "pyproject.toml",
            "poetry.lock",
            "poetry.toml",
            "config.example.json",
            ".gitignore",
            ".gitattributes",
            ".editorconfig",
            "package.json",
            "package-lock.json",
            "build_libraries.py",
            "verify_wheels.py",
        }
        or p.is_file()
        and p.suffix == ".md"
    ]
    for directory in ("paper_trader", "tests", "libs", "scripts", "plans", ".github"):
        files += [
            p
            for p in (root / directory).rglob("*")
            if p.is_file()
            and "__pycache__" not in p.parts
            and p.suffix in (".py", ".md", ".toml", ".typed", ".yml", ".html")
        ]
    archives = [output / "ibkr-paper-trader.zip", output / "ibkr-trading-libraries-wheels.zip"]
    with ZipFile(archives[0], "w", ZIP_DEFLATED) as archive:
        for file in sorted(set(files)):
            archive.write(file, Path("ibkr_paper") / file.relative_to(root))
    with ZipFile(archives[1], "w", ZIP_DEFLATED) as archive:
        for file in sorted((root / "dist/wheels").glob("*.whl")):
            archive.write(file, Path("dist/wheels") / file.name)
    manifest = {}
    for path in archives:
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Corrupt archive")
            for name in archive.namelist():
                if "config.local" in name or "/runtime/" in name or ".sqlite" in name:
                    raise RuntimeError(f"Private data in release: {name}")
            manifest[path.name] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "files": len(archive.namelist()),
            }
    (output / "ibkr-release-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
