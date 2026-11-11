# pykmclib

**pykmclib** 是 [KMCLib](https://github.com/leetmaa/KMCLib)（格点动力学蒙特卡洛，lattice kMC
框架）的 Python 重新发布与二次开发版本：C++ 后端沿用 KMCLib 原始实现，用 **pybind11** 绑定，
用 **scikit-build-core + CMake** 构建，可直接从 PyPI / conda-forge 安装。

> 状态：`0.0.1`（alpha）。Python 层与上游 KMCLib 的 API 保持一致，上游自带的 188 个单测
> 全部通过（另有 2 个与平台/numpy 版本相关的已知失败，见
> [docs/porting-notes.md](docs/porting-notes.md)），8 个端到端功能测试通过。

## 安装

```bash
pip install pykmclib
# 或
conda install -c conda-forge pykmclib
```

从源码安装需要 CMake ≥ 3.21 与 C++17 编译器（pybind11 与 scikit-build-core 会作为构建期
依赖自动装好）：

```bash
pip install --no-binary pykmclib pykmclib   # 走 sdist（自包含，含 C++ 源码）
```

支持的平台：Linux（manylinux x86_64）、macOS（x86_64 / arm64）、Windows（x86_64），
CPython 3.10–3.14。

## 快速上手

一个 1D 扩散模型：一条 10 个格点的周期链，中间一个 B 原子在 A 原子海中随机游走。

```python
import numpy as np
from pykmclib import (KMCUnitCell, KMCLattice, KMCConfiguration, KMCProcess,
                      KMCInteractions, KMCLatticeModel, KMCControlParameters,
                      OnTheFlyMSD)

unit_cell = KMCUnitCell(cell_vectors=np.array([[5.2, 0.0, 0.0],
                                               [0.0, 1.0, 0.0],
                                               [0.0, 0.0, 1.0]]),
                        basis_points=[[0.0, 0.0, 0.0]])
lattice = KMCLattice(unit_cell=unit_cell, repetitions=(10, 1, 1), periodic=(True, False, False))

types = ["A"] * 10
types[5] = "B"
configuration = KMCConfiguration(lattice=lattice, types=types, possible_types=["A", "B"])

left = KMCProcess([[0.0, 0.0, 0.0], [-1.0, 0.0, 0.0]],
                  elements_before=["B", "A"], elements_after=["A", "B"],
                  basis_sites=[0], rate_constant=1.5)
right = KMCProcess([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                   elements_before=["B", "A"], elements_after=["A", "B"],
                   basis_sites=[0], rate_constant=1.5)
interactions = KMCInteractions(processes=[left, right], implicit_wildcards=True)

model = KMCLatticeModel(configuration=configuration, interactions=interactions)
msd = OnTheFlyMSD(history_steps=200, n_bins=100, t_max=2500.0, track_type="B")

model.run(KMCControlParameters(number_of_steps=200_000, dump_interval=50_000, seed=1234),
          trajectory_filename="traj.xyz", trajectory_type="xyz",
          analysis=[msd])
```

`sites`、`rates`、`interactions` 等概念与上游手册一致
（<http://leetmaa.github.io/KMCLib/manual-v1.1/>）；上游手册与示例只需把
`from KMCLib import ...` 改成 `from pykmclib import ...`。

## 相对上游的改动

保持 API 兼容的前提下，目前做了这些事：

| 改动 | 说明 |
| --- | --- |
| 打包与构建 | scikit-build-core + CMake 3.21+，C++17；`mpiflag.h`、md5 全部在构建目录生成/解出，不再写回源码树；去掉上游的 `-Werror`、`cmake_force_cxx_compiler`（CMake 4 已不兼容） |
| 绑定层 | SWIG → **pybind11**，三平台可用（含 Windows），回调（Python 自定义速率）用 trampoline 实现 |
| 命名空间 | `KMCLib` → `pykmclib`（上游 Python 层使用绝对导入，由脚本机械重写） |
| 依赖 | 运行时只依赖 `numpy`；pybind11/cmake 只在构建期需要 |
| 导入副作用 | 去掉 import 时打印的 banner；MPI 仍只初始化/终结一次 |

## 仓库结构

```
CMakeLists.txt         PEP 517 入口
cxx/                   构建适配层：CMake 逻辑 + pybind11 绑定（bindings/）
third_party/KMCLib/    上游 KMCLib 的 git subtree 快照（永不编辑）
src/pykmclib/          Python 包（含改名后的上游前端 + Backend 门面）
tests/                 本仓库测试
scripts/               gen_python_layer.py / run_upstream_tests.py / upstream_info.py
docs/                  upstream-notes.md（快照与同步）、porting-notes.md（绑定层）、
                       build-and-release.md（构建与发布）
conda/                 conda-forge recipe 草稿
```

**为什么用 git subtree 而不是 submodule**：PyPI sdist 与 conda-forge 都要求源码自包含，
而 scikit-build-core 打 sdist 时不会初始化 submodule；上游构建系统又必须被改造。
subtree 既让源码在树里，又用 `git-subtree-split` 记下上游 commit 号。完整对比见
[docs/upstream-notes.md](docs/upstream-notes.md)。

## 开发

```bash
uv sync                                          # 建环境 + 编译 C++ 扩展
uv run pytest -q                                 # 本仓库测试
uv run python scripts/run_upstream_tests.py --units      # 上游 188 个单测
uv run python scripts/run_upstream_tests.py --functests  # 上游端到端用例
uv build                                         # wheel + sdist
uv run python scripts/upstream_info.py           # 当前钉住的上游 commit
```

细节见 [docs/build-and-release.md](docs/build-and-release.md)。

## 引用

使用本软件发表研究时请引用 KMCLib 的两篇论文：

> Mikael Leetmaa and Natalia V. Skorodumova,
> *KMCLib: A general framework for lattice kinetic Monte Carlo (KMC) simulations*,
> Comput. Phys. Commun. **185** (2014) 2340. DOI: [10.1016/j.cpc.2014.04.017](https://doi.org/10.1016/j.cpc.2014.04.017)

> Mikael Leetmaa and Natalia V. Skorodumova,
> *KMCLib 1.1: Extended random number support and technical updates*,
> Comput. Phys. Commun. (2015). DOI: [10.1016/j.cpc.2015.06.016](https://doi.org/10.1016/j.cpc.2015.06.016)

MSD 算法请另引：*Mean square displacements with error estimates from non-equidistant time-step
kinetic Monte Carlo simulations*, Comput. Phys. Commun. (2015),
DOI: [10.1016/j.cpc.2015.02.006](https://doi.org/10.1016/j.cpc.2015.02.006)

## 许可证

**GPL-3.0-or-later**。pykmclib 链接并分发 KMCLib（Copyright © 2012–2016 Mikael Leetmaa，
GPL-3.0-or-later），因此作为衍生作品整体适用 GPLv3；仓库根目录的 `LICENSE` 为 GPLv3 全文，
上游原始许可见 `third_party/KMCLib/LICENSE.txt`。MD5 实现为 public domain。
