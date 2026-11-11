# conda-forge

`meta.yaml` 是给 [conda-forge/staged-recipes](https://github.com/conda-forge/staged-recipes)
的 **PR 草稿**。这个目录不参与 Python 构建，只是让 recipe 和代码放在一起。

## 步骤

1. 先发布到 PyPI（`git tag v0.0.1 && git push --tags` 会跑 `.github/workflows/wheels.yml`）。
   conda-forge 从 PyPI 的 **sdist** 构建，所以 sdist 必须先存在。
2. 算出 sdist 的校验和填进 `meta.yaml`：

   ```bash
   curl -sL https://pypi.org/pypi/pykmclib/json | python -c "
   import json, sys
   d = json.load(sys.stdin)
   print([f['digests']['sha256'] for f in d['urls'] if f['packagetype'] == 'sdist'][0])"
   ```

3. fork `conda-forge/staged-recipes`，把本目录拷到 `recipes/pykmclib/`，提 PR。
   bot 会 lint recipe，并在 Linux/macOS/Windows 上构建；合并后会自动创建 feedstock。
4. 之后发新版本只需要改版本号（feedstock 注册了 autotick bot，会自动从 PyPI 提 PR）。

## 说明

- `pybind11` 与 `scikit-build-core` 是 **host** 依赖（构建期需要，运行时不需要）；
  `pip install --no-build-isolation` 依赖它们在 host 环境里存在。
- `cmake >=3.21` 与 `ninja` 放 **build** 段；构建脚本用 `python -m pybind11 --cmakedir`
  定位 pybind11 的 CMake 包，因此不需要额外的环境变量。
- sdist 自带 `third_party/KMCLib/c++/{src,custom}` 与
  `third_party/KMCLib/c++/externals/zip/md5.tar.gz`，构建期由 CMake 解出 md5，
  所以沙箱里不联网也能构建。
- `tests` 目录随 sdist 一起发布，因此 `test.source_files` 可以直接引用它。
- `LICENSE` 是 GPL-3.0-or-later，`third_party/KMCLib/LICENSE.txt` 是上游那份；
  两个都必须出现在 `license_file` 里。
