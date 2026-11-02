"""Focused AST rules supplement import-linter; run from any working directory."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {"auth", "users", "restaurants", "menu", "orders", "payments"}


def check():
    failures = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        relative = path.relative_to(ROOT)
        parts = relative.parts
        feature = parts[1] if parts[1] in FEATURES else None
        layer = path.stem
        tree = ast.parse(path.read_text(), filename=str(relative))
        for node in ast.walk(tree):
            reason = None
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    package = list(parts[:-1])
                    module = ".".join(package[: len(package) - node.level + 1] + [module])
                imports = [module] + [f"{module}.{alias.name}" for alias in node.names]
            for name in imports:
                target = name.split(".")
                if len(target) >= 3 and target[0] == "app" and target[1] in FEATURES:
                    if feature != target[1] and target[2] in {"models", "repository"}:
                        if relative.as_posix() != "app/models.py":
                            reason = "cross-feature persistence access: use the feature service"
                    if feature != target[1] and target[2] == "service" and layer == "repository":
                        reason = "repositories cannot call another feature's service"
                if layer in {"service", "repository"} and target[0] in {"fastapi", "starlette"}:
                    reason = "services/repositories must remain HTTP-free"
                if layer == "router" and target[0] == "sqlalchemy":
                    reason = "routers cannot import query tools"
                if layer == "router" and name.endswith(".repository"):
                    reason = "routers must call services"
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else (node.func.id if isinstance(node.func, ast.Name) else "")
                )
                if layer == "router" and name in {
                    "query",
                    "execute",
                    "scalar",
                    "scalars",
                    "commit",
                    "flush",
                    "select",
                    "insert",
                    "update",
                    "delete",
                    "text",
                    "exec_driver_sql",
                }:
                    reason = "routers cannot query or manage transactions"
                if layer == "repository" and name == "commit":
                    reason = "only outer write services own commits"
                if layer in {"service", "repository"} and name == "HTTPException":
                    reason = "raise domain errors instead of HTTPException"
            if reason:
                failures.append(f"{relative}:{node.lineno}: {reason}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Architecture AST checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
