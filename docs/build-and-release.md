# 构建与发布

本文描述 pykmclib 的构建链路、本地开发流程，以及发布到 PyPI / conda-forge 的步骤。
"上游源码怎么引入"见 [upstream-notes.md](upstream-notes.md)，"绑定层怎么移植"见
[porting-notes.md](porting-notes.md)。

---

## 1. 构建链路一图流

```
pyproject.toml            PEP 517: scikit-build-core + pybind11（构建期依赖）
      │
      ▼
CMakeLists.txt            add_subdirectory(cxx)
      │
      ├── cxx/CMakeLists.txt
      │     ├─ gen/mpiflag.h           由 cxx/mpiflag.h.in 生成（上游写回源码树）
      │     ├─ md5/                    从 c++/externals/zip/md5.tar.gz 解出
      │     ├─ kmc_core                静态库 ← third_party/KMCLib/c++/src/*.cpp + md5
      │     ├─ kmc_custom              静态库 ← third_party/KMCLib/c++/custom/*.cpp
      │     └─ _backend.<soabi>        单模块 ← cxx/bindings/*.cpp + pybind11
      │
      └── install() → wheel 内的 pykmclib/Backend/_backend.*
```

要点：

- **pybind11 的 CMake 目录必须显式取**：pybind11 wheel 把配置放在
  `site-packages/pybind11/share/cmake/pybind11`，而 scikit-build-core 只把 site-packages
  本身加入 `CMAKE_PREFIX_PATH`，`find_package(pybind11 CONFIG)` 找不到。构建脚本用
  `python -m pybind11 --cmakedir` 把路径加进去。
- **C++ 标准是 17**（pybind11 3.x 的要求），上游代码在 C++17 下可直接编译。
- **生成物一律落构建目录**，源码树保持只读可用（sdist、conda 沙箱都依赖这一点）。

---

## 2. 本地开发

```bash
uv sync                     # 建 .venv（Python 3.12，见 .python-version）并编译扩展
uv run pytest -q            # 本仓库测试
uv build                    # wheel + sdist

# 改 C++/绑定时，uv 的 cache-keys 会触发重编；强制重编：
uv sync --reinstall-package pykmclib
```

### 上游回归

上游测试在 vendored 子树里，脚本以 `KMCLib → pykmclib` 别名方式离线运行：

```bash
uv run python scripts/run_upstream_tests.py --units      # ~2 s，188 passed
uv run python scripts/run_upstream_tests.py --functests  # ~3 min，8 个端到端用例
uv run python scripts/run_upstream_tests.py --units -k OnTheFlyMSD   # 过滤
```

### 同步上游

```bash
uv run python scripts/upstream_info.py            # 当前钉住的 SHA + 同步/审阅命令
uv run python scripts/gen_python_layer.py         # 从快照重生成改名后的 Python 前端
uv run python scripts/gen_python_layer.py --check # CI 用：无漂移则通过
```

---

## 3. 版本号

唯一来源是 `src/pykmclib/__init__.py` 的 `__version__`，`pyproject.toml` 用
scikit-build-core 的 `metadata.regex` provider 读取，`conda/recipe/meta.yaml` 手动同步。
发版示例（`0.0.1 → 0.0.2`）：

```bash
# 1) 改 __version__ = "0.0.2"，同步 conda/recipe/meta.yaml 的 version
# 2) 刷新锁文件（建议）
uv lock
# 3) 打 tag 触发发布
git tag v0.0.2 && git push origin main --tags
```

---

## 4. 发布到 PyPI

1. 在 PyPI 上创建项目 `pykmclib`，并配置 **Trusted Publishing**：
   Owner `LiuGaoyong`、Repository `pykmclib`、Workflow `wheels.yml`、Environment `pypi`。
   配好之后不需要 API token。
2. 推送 `v*` tag 会触发 `.github/workflows/wheels.yml`：
   - `ubuntu-latest` / `macos-13` / `macos-14` / `windows-latest` 上用 cibuildwheel 构建
     cp310–cp314 的 wheel（Linux 走 manylinux；swig 已不需要，pybind11 由
     `build-system.requires` 提供）；
   - 单独的 job 构建 sdist；
   - 全部成功后 `pypa/gh-action-pypi-publish` 上传。
3. 发布后自检：

```bash
uv venv /tmp/pypi-check
uv pip install --python /tmp/pypi-check/bin/python pykmclib
/tmp/pypi-check/bin/python -c "import pykmclib; print(pykmclib.__version__)"
```

---

## 5. 发布到 conda-forge

前置条件：PyPI 上已有该版本的 sdist（conda-forge 用 sdist 构建）。

1. 取 sdist 的 sha256 填进 `conda/recipe/meta.yaml`
   （`conda/README.md` 里有可直接复制的一行命令）。
2. 把 `conda/recipe/` 拷成 `conda-forge/staged-recipes` 的 `recipes/pykmclib/` 提 PR。
   recipe 的 build 依赖是编译器 + `cmake` + `ninja`，host 里是
   `python`/`pip`/`scikit-build-core`/`pybind11`/`numpy`。
3. 合并后自动生成 `pykmclib-feedstock`，之后的版本由 autotick bot 自动提 PR。

---

## 6. 已知限制

| 项目 | 状态 |
| --- | --- |
| MPI 并行 | 代码路径保留（`-DKMC_ENABLE_MPI=ON`），**未验证**；默认串行构建 |
| Windows | 三平台 wheel 之一；CI 覆盖，MSVC 下若需补丁只允许放在 `cxx/` |
| Python 3.14 | 已列入 classifiers 与 cibuildwheel 矩阵 |
| 上游 cppunit 单测 | 未接入（`third_party/KMCLib/c++/unittest` 保留但不编译） |
| `KMCConfiguration._script()` | 上游对"每个位点多粒子"的配置会抛 `TypeError`（2.0-alpha 遗留），未修 |
| 轨迹默认格式 | `KMCLatticeModel.run()` 默认 lattice 脚本格式；要 XYZ 需显式传 `trajectory_type="xyz"` |
