# conda-forge

`meta.yaml` is a **draft PR** for
[conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes).
This directory takes no part in the Python build; it only keeps the recipe next to the code.

## Steps

1. Publish to PyPI first (`git tag v0.0.1 && git push --tags` runs `.github/workflows/wheels.yml`).
   conda-forge builds from the PyPI **sdist**, so the sdist has to exist first.
2. Compute the sdist checksum and fill it into `meta.yaml`:

   ```bash
   curl -sL https://pypi.org/pypi/pykmclib/json | python -c "
   import json, sys
   d = json.load(sys.stdin)
   print([f['digests']['sha256'] for f in d['urls'] if f['packagetype'] == 'sdist'][0])"
   ```

3. Fork `conda-forge/staged-recipes`, copy this directory to `recipes/pykmclib/`, and open a PR.
   The bot lints the recipe and builds it on Linux/macOS/Windows; once merged, the feedstock is
   created automatically.
4. After that, releasing a new version only requires bumping the version number (the feedstock is
   registered with the autotick bot, which opens PRs from PyPI automatically).

## Notes

- `pybind11` and `scikit-build-core` are **host** dependencies (needed at build time, not at
  runtime); `pip install --no-build-isolation` relies on them being present in the host environment.
- `cmake >=3.21` and `ninja` go in the **build** section; the build script locates pybind11's CMake
  package with `python -m pybind11 --cmakedir`, so no extra environment variables are needed.
- The sdist ships `third_party/KMCLib/c++/{src,custom}` and
  `third_party/KMCLib/c++/externals/zip/md5.tar.gz`; CMake extracts md5 at build time, so the build
  works in a sandbox without network access.
- The `tests` directory is shipped with the sdist, so `test.source_files` can reference it directly.
- `LICENSE` is GPL-3.0-or-later and `third_party/KMCLib/LICENSE.txt` is the upstream copy; both must
  appear in `license_file`.
