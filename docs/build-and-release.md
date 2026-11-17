# Build and release

This document describes pykmclib's build pipeline, the local development workflow, and the steps
for releasing to PyPI / conda-forge. For how the upstream sources are brought in, see
[upstream-notes.md](upstream-notes.md); for how the binding layer was ported, see
[porting-notes.md](porting-notes.md).

---

## 1. The build pipeline at a glance

```
pyproject.toml            PEP 517: scikit-build-core + pybind11 (build-time dependencies)
      │
      ▼
CMakeLists.txt            add_subdirectory(cxx)
      │
      ├── cxx/CMakeLists.txt
      │     ├─ gen/mpiflag.h           generated from cxx/mpiflag.h.in (upstream writes it back into the source tree)
      │     ├─ md5/                    extracted from c++/externals/zip/md5.tar.gz
      │     ├─ kmc_core                static library ← third_party/KMCLib/c++/src/*.cpp + md5
      │     ├─ kmc_custom              static library ← third_party/KMCLib/c++/custom/*.cpp
      │     └─ _backend.<soabi>        single module ← cxx/bindings/*.cpp + pybind11
      │
      └── install() → pykmclib/Backend/_backend.* inside the wheel
```

Key points:

- **pybind11's CMake directory must be looked up explicitly**: the pybind11 wheel puts its config
  under `site-packages/pybind11/share/cmake/pybind11`, whereas scikit-build-core only adds
  site-packages itself to `CMAKE_PREFIX_PATH`, so `find_package(pybind11 CONFIG)` cannot find it.
  The build script adds the path using `python -m pybind11 --cmakedir`.
- **The C++ standard is 17** (required by pybind11 3.x); the upstream code compiles as-is under
  C++17.
- **All generated files go into the build directory**, so the source tree stays usable when
  read-only (the sdist and the conda sandbox both depend on this).

---

## 2. Local development

```bash
uv sync                     # create .venv (Python 3.12, see .python-version) and compile the extension
uv run pytest -q            # tests for this repository
uv build                    # wheel + sdist

# When C++/bindings change, uv's cache-keys trigger a rebuild; to force one:
uv sync --reinstall-package pykmclib
```

### Upstream regression

The upstream tests live in the vendored subtree; the script runs them offline by aliasing
`KMCLib → pykmclib`:

```bash
uv run python scripts/run_upstream_tests.py --units      # ~2 s, 187 passed + 3 known failures
uv run python scripts/run_upstream_tests.py --functests  # ~3 min, 8 end-to-end cases
uv run python scripts/run_upstream_tests.py --units -k OnTheFlyMSD   # filter
```

### Syncing upstream

```bash
uv run python scripts/upstream_info.py            # currently pinned SHA + sync/review commands
uv run python scripts/gen_python_layer.py         # regenerate the renamed Python front end from the snapshot
uv run python scripts/gen_python_layer.py --check # for CI: passes if there is no drift
```

---

## 3. Version number

The single source of truth is `__version__` in `src/pykmclib/__init__.py`. `pyproject.toml` reads it
through scikit-build-core's `metadata.regex` provider, and `conda/recipe/meta.yaml` is synced by
hand. Release example (`0.0.1 → 0.0.2`):

```bash
# 1) Set __version__ = "0.0.2" and sync the version in conda/recipe/meta.yaml
#    (the publish job refuses to upload if the tag and __version__ disagree)
# 2) Refresh the lock file (recommended)
uv lock
# 3) Tag to trigger the release
git tag v0.0.2 && git push origin main --tags
```

---

## 4. Releasing to PyPI

1. Create the `pykmclib` project on PyPI and configure **Trusted Publishing**:
   Owner `LiuGaoyong`, Repository `pykmclib`, Workflow `wheels.yml`, Environment `pypi`.
   Once that is set up, no API token is needed.
2. Pushing a `v*` tag triggers `.github/workflows/wheels.yml`:
   - a pinned cibuildwheel builds cp310–cp314 wheels in seven jobs, each on a native runner:

     | Job | Runner | Wheel tag |
     | --- | --- | --- |
     | Linux x86_64 | `ubuntu-latest` | `manylinux2014_x86_64` and `manylinux_2_28_x86_64` (one job each) |
     | Linux arm64 | `ubuntu-24.04-arm` | `manylinux2014_aarch64` and `manylinux_2_28_aarch64` (one job each) |
     | macOS x86_64 | `macos-15-intel` | `macosx_10_15_x86_64` |
     | macOS arm64 | `macos-15` | `macosx_11_0_arm64` |
     | Windows x86_64 | `windows-latest` | `win_amd64` |

     The architecture and the manylinux image are set per job through `CIBW_ARCHS` and
     `CIBW_MANYLINUX_*_IMAGE`; the shared settings live in `[tool.cibuildwheel]` in
     `pyproject.toml`. Every wheel is tested with `pytest` inside its build environment, except
     cp314 on manylinux2014, because numpy publishes no manylinux2014 wheel for CPython 3.14;
   - the publish job first checks that the tag matches `__version__`;
   - a separate job builds the sdist;
   - once everything succeeds, `pypa/gh-action-pypi-publish` uploads the artifacts.
3. Post-release sanity check:

```bash
uv venv /tmp/pypi-check
uv pip install --python /tmp/pypi-check/bin/python pykmclib
/tmp/pypi-check/bin/python -c "import pykmclib; print(pykmclib.__version__)"
```

---

## 5. Releasing to conda-forge

Prerequisite: the sdist for that version is already on PyPI (conda-forge builds from the sdist).

1. Take the sdist's sha256 and fill it into `conda/recipe/meta.yaml`
   (`conda/README.md` has a one-liner you can copy).
2. Copy `conda/recipe/` to `recipes/pykmclib/` in `conda-forge/staged-recipes` and open a PR.
   The recipe's build dependencies are the compilers + `cmake` + `ninja`; the host section has
   `python`/`pip`/`scikit-build-core`/`pybind11`/`numpy`.
3. After the merge, `pykmclib-feedstock` is generated automatically, and the autotick bot opens PRs
   for later versions.

---

## 6. Known limitations

| Item | Status |
| --- | --- |
| MPI parallelism | The code path is kept (`-DKMC_ENABLE_MPI=ON`) but is **unverified**; the default build is serial |
| Windows | x86_64 only; covered by CI. If MSVC needs patches, they may only go in `cxx/` |
| musllinux (Alpine) | No wheels are built; installing there compiles from the sdist |
| manylinux2014 + CPython 3.14 | The wheel is built but not tested in CI, and numpy itself offers no wheel for that combination |
| Python 3.14 | Listed in the classifiers and in the cibuildwheel matrix |
| Upstream cppunit unit tests | Not wired in (`third_party/KMCLib/c++/unittest` is kept but not compiled) |
| `KMCConfiguration._script()` | Upstream raises `TypeError` for configurations with multiple particles per site (left over from 2.0-alpha); not fixed |
| Default trajectory format | `KMCLatticeModel.run()` defaults to the lattice script format; for XYZ you must pass `trajectory_type="xyz"` explicitly |
