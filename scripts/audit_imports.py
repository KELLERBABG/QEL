"""Import-audit: every module in the package must import cleanly.

A single stale name in a package ``__init__`` takes down the whole package, the
CLI, the demo and every test module that touches them -- while a file listing
still looks perfectly healthy.  That is exactly how this repository ended up
with 11 pytest collection errors and an advertised test count.

Run from the repository root:

    py scripts/audit_imports.py

Exit status is 0 when every module imports, 1 otherwise.  Intended as a
pre-flight check before running the suite, and as a cheap guard in CI.
"""

from __future__ import annotations

import importlib
import pathlib
import sys


def discover_modules(package_root: pathlib.Path) -> list[str]:
    """Every importable dotted module name under ``package_root``."""
    names: set[str] = set()
    for path in sorted(package_root.rglob("*.py")):
        rel = path.relative_to(package_root.parent).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            names.add(".".join(parts))
    return sorted(names)


def main() -> int:
    try:
        import quantumnet
    except ImportError:
        print("quantumnet is not importable; run `py -m pip install -e .` first",
              file=sys.stderr)
        return 2

    root = pathlib.Path(quantumnet.__file__).parent
    modules = discover_modules(root)

    failures: list[tuple[str, str]] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report everything
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")

    print(f"\n{len(modules)} modules, {len(failures)} failed to import")
    if failures:
        print("\nA package whose __init__ imports these names is broken.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
