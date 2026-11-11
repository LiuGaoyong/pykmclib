#!/usr/bin/env python3
"""Regenerate the pykmclib Python front end from the vendored upstream tree.

The upstream KMCLib Python layer lives in ``third_party/KMCLib/python/src/KMCLib``
(a git subtree, so it is always present and always in sync with whatever commit
is vendored).  pykmclib re-ships it under its own namespace, which only requires
rewriting the absolute imports::

    from KMCLib.Backend import Backend   ->  from pykmclib.Backend import Backend

Everything else is byte-identical to upstream, so a refresh is a mechanical,
reviewable diff.  Three files are maintained by hand and are never touched:

    __init__.py
    Backend/Backend.py
    Backend/Custom.py

Usage
-----
    python scripts/gen_python_layer.py           # refresh src/pykmclib
    python scripts/gen_python_layer.py --check   # verify no drift (CI)
    python scripts/gen_python_layer.py --force   # also overwrite hand-written files
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DIR = REPO_ROOT / "third_party" / "KMCLib" / "python" / "src" / "KMCLib"
DEST_DIR = REPO_ROOT / "src" / "pykmclib"

# Hand-written modules that must survive a regeneration.
OURS = {
    Path("__init__.py"),
    Path("Backend/Backend.py"),
    Path("Backend/Custom.py"),
}

IMPORT_RE = re.compile(r"^(?P<indent>\s*)(?P<kw>from|import)\s+KMCLib\b", re.MULTILINE)


def rewrite(text: str) -> str:
    """Rewrite absolute ``KMCLib`` imports to ``pykmclib`` (imports only)."""
    return IMPORT_RE.sub(lambda m: f"{m.group('indent')}{m.group('kw')} pykmclib", text)


def iter_upstream_files() -> list[Path]:
    """All Python files of the upstream front end, relative to its root."""
    return sorted(p.relative_to(UPSTREAM_DIR) for p in UPSTREAM_DIR.rglob("*.py"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    parser.add_argument("--force", action="store_true", help="also overwrite the hand-written modules")
    args = parser.parse_args(argv)

    if not UPSTREAM_DIR.is_dir():
        print(f"error: {UPSTREAM_DIR} is missing (run 'git subtree pull' first)", file=sys.stderr)
        return 2

    stale: list[Path] = []
    written: list[Path] = []
    for relative in iter_upstream_files():
        if relative in OURS and not args.force:
            continue
        source = UPSTREAM_DIR / relative
        target = DEST_DIR / relative
        content = rewrite(source.read_text(encoding="utf-8"))
        if target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        if args.check:
            stale.append(relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(relative)

    if args.check:
        if stale:
            print("stale files (run scripts/gen_python_layer.py):")
            for relative in stale:
                print(f"  {relative}")
            return 1
        print("python layer is up to date")
        return 0

    for relative in written:
        print(f"wrote {relative}")
    print(f"{len(written)} file(s) regenerated from {UPSTREAM_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
