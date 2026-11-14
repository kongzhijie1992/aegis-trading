"""Fail on undeclared sibling dependencies, reverse app imports or cycles."""

import ast
import re
import tomllib
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    graph = {}
    for project in sorted((root / "libs").iterdir()):
        metadata = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        name = metadata["name"].replace("-", "_")
        declared = {
            re.split(r"[<>=;\[ ]", d)[0].replace("-", "_") for d in metadata["dependencies"]
        }
        graph[name] = {d for d in declared if d.startswith("trading_")}
        source = project / "src" / name
        if not (source / "py.typed").exists():
            raise RuntimeError(f"{name}: missing py.typed")
        for file in source.glob("*.py"):
            for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports = [node.module.split(".")[0]]
                for imported in imports:
                    if imported == "paper_trader":
                        raise RuntimeError(f"{file}: reverse application import")
                    if imported.startswith("trading_") and imported not in declared | {name}:
                        raise RuntimeError(f"{file}: undeclared dependency {imported}")
                    if imported == "ib_async" and name != "trading_ibkr":
                        raise RuntimeError(f"{file}: SDK outside adapter")

    def visit(name, trail):
        if name in trail:
            raise RuntimeError(f"Circular libraries: {trail + [name]}")
        if name not in graph:
            raise RuntimeError(f"Missing library {name}")
        for dependency in graph[name]:
            visit(dependency, trail + [name])

    for name in graph:
        visit(name, [])
    print(f"Package boundaries passed: {len(graph)} libraries; no cycles or reverse imports.")


if __name__ == "__main__":
    main()
