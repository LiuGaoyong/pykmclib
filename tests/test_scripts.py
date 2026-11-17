"""The repository maintenance scripts (only testable from a source checkout)."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "gen_python_layer.py"
UPSTREAM = REPO_ROOT / "third_party" / "KMCLib" / "python" / "src" / "KMCLib"

pytestmark = pytest.mark.skipif(
    not (SCRIPT.is_file() and UPSTREAM.is_dir()),
    reason="needs a source checkout with the vendored upstream tree",
)


@pytest.fixture
def gen_python_layer():
    spec = importlib.util.spec_from_file_location("gen_python_layer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_layer_matches_the_vendored_snapshot(gen_python_layer):
    assert gen_python_layer.main(["--check"]) == 0


def test_check_reports_files_without_upstream_counterpart(
    gen_python_layer, tmp_path, monkeypatch, capsys
):
    package = tmp_path / "pykmclib"
    shutil.copytree(
        gen_python_layer.DEST_DIR,
        package,
        ignore=shutil.ignore_patterns("__pycache__", "*.so", "*.pyd"),
    )
    (package / "Utilities" / "Stray.py").write_text("# not part of upstream\n")
    monkeypatch.setattr(gen_python_layer, "DEST_DIR", package)

    assert gen_python_layer.main(["--check"]) == 1
    assert "Utilities/Stray.py" in capsys.readouterr().out.replace("\\", "/")
