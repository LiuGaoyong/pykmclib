#!/usr/bin/env python3
"""Run the upstream KMCLib test suites against the installed pykmclib.

The upstream tests live in the vendored subtree and import ``KMCLib``; this
runner aliases every ``pykmclib`` module to the matching ``KMCLib`` name, so the
tests exercise pykmclib unchanged.  Nothing is downloaded - the subtree always
holds the tests of the vendored commit.

Usage
-----
    python scripts/run_upstream_tests.py --units      # upstream unit tests (~2 s)
    python scripts/run_upstream_tests.py --functests  # end-to-end runs (a few minutes)
    python scripts/run_upstream_tests.py --units -k OnTheFlyMSD
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import pkgutil
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_PY = REPO_ROOT / "third_party" / "KMCLib" / "python"
UNITTEST_DIR = UPSTREAM_PY / "unittest"
FUNCTEST_DIR = UPSTREAM_PY / "functest"

# Failures that come from the platform / the installed numpy, not from pykmclib.
# ``--strict`` turns them into failures.
XFAIL = {
    # numpy >= 1.24 refuses to build an array from a ragged list of lists.
    "KMCLibTest.Utilities.CheckUtilitiesTest.CheckUtilitiesTest.testCheckCellVectors": "numpy>=1.24 rejects ragged arrays",
    # std::random_device has real entropy here, so the DEVICE rng is accepted.
    "KMCLibTest.CoreComponents.KMCLatticeModelTest.KMCLatticeModelTest.testRunRngTypeDevice": "std::random_device has entropy on this platform",
}


def alias_kmclib() -> None:
    """Make ``import KMCLib...`` resolve to pykmclib, without re-executing modules."""
    import pykmclib

    for info in pkgutil.walk_packages(pykmclib.__path__, prefix="pykmclib."):
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # pragma: no cover - optional (ATK) modules
            print(f"warning: could not import {info.name}: {exc}", file=sys.stderr)

    sys.modules["KMCLib"] = pykmclib
    for name, module in list(sys.modules.items()):
        if name.startswith("pykmclib."):
            sys.modules["KMCLib" + name[len("pykmclib") :]] = module


def load_file(path: Path, name: str) -> unittest.TestSuite:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


def iter_cases(suite: unittest.TestSuite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_cases(test)
        else:
            yield test


def test_id(test: unittest.TestCase) -> str:
    cls = type(test)
    return f"{cls.__module__}.{cls.__name__}.{test._testMethodName}"


class Recorder(unittest.TextTestResult):
    """Collect ids of failures and errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failed_ids: list[str] = []

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failed_ids.append(test_id(test))

    def addError(self, test, err):
        super().addError(test, err)
        self.failed_ids.append(test_id(test))


def run_suite(suite: unittest.TestSuite, title: str, strict: bool, workdir: Path | None = None) -> list[str]:
    """Run one suite in a scratch directory, skipping known failures."""
    known = []
    selected = unittest.TestSuite()
    for test in iter_cases(suite):
        identifier = test_id(test)
        if identifier in XFAIL and not strict:
            known.append(identifier)
            continue
        selected.addTest(test)

    if workdir is None:
        workdir = Path(tempfile.mkdtemp(prefix="pykmclib-upstream-"))
    previous = os.getcwd()
    os.chdir(workdir)
    try:
        print(f"\n=== {title} ===", flush=True)
        result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout, resultclass=Recorder).run(selected)
    finally:
        os.chdir(previous)

    for identifier in known:
        print(f"known failure: {identifier} ({XFAIL[identifier]})")
    if result.skipped:
        print(f"{len(result.skipped)} skipped by the test framework")
    print(f"ran {result.testsRun} test(s): {len(result.failed_ids)} failed, {len(known)} known failure(s) skipped")
    return result.failed_ids


def collect_units(filter_text: str | None) -> list[unittest.TestSuite]:
    sys.path.insert(0, str(UNITTEST_DIR))
    discovered = unittest.TestLoader().discover(str(UNITTEST_DIR), pattern="*Test.py", top_level_dir=str(UNITTEST_DIR))
    seen: set[str] = set()
    suite = unittest.TestSuite()
    for test in iter_cases(discovered):
        identifier = test_id(test)
        if identifier in seen:
            continue
        seen.add(identifier)
        if filter_text and filter_text not in identifier:
            continue
        suite.addTest(test)
    return [suite]


def collect_functests(filter_text: str | None) -> list[tuple[str, Path, unittest.TestSuite]]:
    suites = []
    for path in sorted(FUNCTEST_DIR.rglob("*Test.py")):
        relative = path.relative_to(FUNCTEST_DIR).with_suffix("")
        name = "functest." + ".".join(relative.parts)
        suite = load_file(path, name)
        if filter_text:
            filtered = unittest.TestSuite()
            for test in iter_cases(suite):
                if filter_text in test_id(test):
                    filtered.addTest(test)
            suite = filtered
        if suite.countTestCases():
            # Upstream runs each functional test from its own directory (some of
            # them load config.py / process scripts by relative path).
            suites.append((name, path.parent, suite))
    return suites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--units", action="store_true", help="run the upstream unit test suite (default)")
    group.add_argument("--functests", action="store_true", help="run the upstream end-to-end suites")
    parser.add_argument("-k", "--filter", default=None, help="only run tests whose id contains this substring")
    parser.add_argument("--strict", action="store_true", help="treat known-failing tests as failures")
    args = parser.parse_args(argv)

    alias_kmclib()

    failures: list[str] = []
    if args.functests:
        for name, directory, suite in collect_functests(args.filter):
            # Upstream runs each functional test from its own directory because
            # some of them load config.py by relative path; copy the directory to
            # scratch space so the vendored tree stays pristine.
            scratch = Path(tempfile.mkdtemp(prefix="pykmclib-functest-"))
            shutil.copytree(directory, scratch, dirs_exist_ok=True)
            failures.extend(run_suite(suite, name, args.strict, workdir=scratch))
    else:
        for suite in collect_units(args.filter):
            failures.extend(run_suite(suite, "upstream unit tests", args.strict))

    if failures:
        print("\nfailed:")
        for identifier in failures:
            print(f"  {identifier}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
