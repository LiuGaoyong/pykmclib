#!/usr/bin/env python3
"""Regenerate the type stub of the compiled backend (``_backend.pyi``).

The extension module ``pykmclib.Backend._backend`` is built with pybind11 and
carries no type information of its own.  ``pybind11-stubgen`` derives a stub
from the signatures pybind11 embeds in the docstrings; the result is committed
next to the module so that editors and type checkers see the backend classes.

The stub describes the *installed* extension, so build it first (``uv sync``).
Regenerate after changing ``cxx/bindings`` or after a pybind11 upgrade that
changes how signatures are rendered.

Usage
-----
    python scripts/gen_stubs.py           # refresh src/pykmclib/Backend/_backend.pyi
    python scripts/gen_stubs.py --check   # verify no drift (CI)
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE = "pykmclib.Backend._backend"
STUB = REPO_ROOT / "src" / "pykmclib" / "Backend" / "_backend.pyi"


def generate() -> str:
    """Run pybind11-stubgen on the installed extension and return the stub text."""
    with tempfile.TemporaryDirectory(prefix="pykmclib-stubs-") as scratch:
        subprocess.run(
            [sys.executable, "-m", "pybind11_stubgen", MODULE, "--output-dir", scratch, "--exit-code"],
            check=True,
        )
        return Path(scratch, *MODULE.split(".")).with_suffix(".pyi").read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = parser.parse_args(argv)

    content = generate()
    current = STUB.read_text(encoding="utf-8") if STUB.is_file() else ""

    if args.check:
        if current == content:
            print("backend stub is up to date")
            return 0
        diff = difflib.unified_diff(
            current.splitlines(), content.splitlines(), "committed", "generated", lineterm="", n=1
        )
        print("\n".join(diff))
        print(f"\n{STUB.relative_to(REPO_ROOT)} is stale (run scripts/gen_stubs.py)")
        return 1

    if current == content:
        print("backend stub is up to date")
    else:
        STUB.write_text(content, encoding="utf-8", newline="\n")
        print(f"wrote {STUB.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
