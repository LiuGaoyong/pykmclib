#!/usr/bin/env python3
"""Report which upstream KMCLib commit is vendored, and how to follow it.

The C++/Python sources of KMCLib live in a git subtree at third_party/KMCLib.
With ``--squash`` every sync is one commit whose message records the upstream
commit range plus ``git-subtree-split: <sha>``; this script surfaces that.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFIX = "third_party/KMCLib"
UPSTREAM_URL = "https://github.com/leetmaa/KMCLib"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True).stdout


def split_shas() -> list[str]:
    """Upstream SHAs recorded by the subtree sync commits, newest first.

    Each sync is a merge whose second parent is the squashed upstream import;
    that commit carries ``git-subtree-split: <sha>`` in its message.
    """
    shas: list[str] = []
    merges = git("log", "--first-parent", "--format=%H", "--", PREFIX).split()
    for merge in merges:
        try:
            parent = git("rev-parse", f"{merge}^2").strip()
        except subprocess.CalledProcessError:
            continue
        body = git("log", "-1", "--format=%B", parent)
        for line in body.splitlines():
            if line.startswith("git-subtree-split:"):
                shas.append(line.split(":", 1)[1].strip())
                break
    return shas


def main() -> int:
    if not (REPO_ROOT / PREFIX).is_dir():
        print(f"{PREFIX} is missing", file=sys.stderr)
        return 1

    shas = split_shas()
    if not shas:
        print("no git-subtree-split record found", file=sys.stderr)
        return 1

    current = shas[0]
    print(f"vendored upstream commit : {current}")
    print(f"upstream repository      : {UPSTREAM_URL}")
    print(f"subtree prefix           : {PREFIX}")
    if len(shas) > 1:
        print(f"previous sync            : {shas[1]}")
        print(f"changes since then       : {UPSTREAM_URL}/compare/{shas[1]}...{current}")
    print()
    print("sync a newer upstream commit:")
    print(f"  git subtree pull --prefix={PREFIX} {UPSTREAM_URL}.git master --squash")
    print("review what a sync brought in:")
    print(f"  git log -1 --format=%B && git diff HEAD^1 HEAD -- {PREFIX}")
    print("browse the upstream commits between two syncs (needs network):")
    print(f"  git fetch {UPSTREAM_URL}.git master && git log --oneline {shas[-1]}..FETCH_HEAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
