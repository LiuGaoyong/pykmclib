# 上游 KMCLib：快照、许可证与同步方式

`third_party/KMCLib/` 是 [leetmaa/KMCLib](https://github.com/leetmaa/KMCLib) 的
**git subtree 快照**。当前钉住的提交可以用下面的命令查（它也打印同步和审阅命令）：

```bash
uv run python scripts/upstream_info.py
```

当前值：`747ff805fd32308fd4b5e8d893bf58ad8670a814`（2020-12-29，上游共 458 个提交，全树约 3.5 MB）。

## 1. 为什么是 subtree，而不是 submodule

| 维度 | submodule | **subtree（本仓库）** |
| --- | --- | --- |
| sdist 自包含（PyPI / conda-forge 都从 sdist 构建） | ❌ scikit-build-core 不跑 `git submodule update`，sdist 里是空目录 | ✅ 源码在树里 |
| 必须改造上游构建（mpiflag.h、md5、-Werror） | ❌ 改动写在 submodule 工作区 → 变脏、丢失 | ✅ 改动全在 `cxx/` |
| 按 commit 号跟进上游 | ✅ gitlink | ✅ 每次同步提交记 `git-subtree-split: <sha>` |
| 审"这次同步改了什么" | ⚠️ 换 gitlink 后看不到内容 diff | ✅ 一次同步 = 一个补丁 |
| 全新 clone / ZIP 下载 / 沙箱 CI / conda 沙箱 | ❌ 需要额外初始化步骤 | ✅ 零特判 |
| 上游逐条 `git log`/`blame` | ✅ | ❌ 除非同步时去掉 `--squash` |

上游 2020 年后停更，实际同步频率 ≈ 0，所以"每次同步一个可审补丁 + 记下 commit 号"比"458 条上游提交混进本项目历史"更有用。

## 2. 同步上游

```bash
# 拉上游 master 的最新提交（一次同步 = 一个 squash 提交）
git subtree pull --prefix=third_party/KMCLib https://github.com/leetmaa/KMCLib.git master --squash

# 审阅本次同步带进来的改动
git log -1 --format=%B                      # 提交消息里列出 <旧>..<新> 的上游 commit 号与标题
git diff HEAD^1 HEAD -- third_party/KMCLib  # 内容改动

# 想逐条浏览上游提交（需要网络）
git fetch https://github.com/leetmaa/KMCLib.git master
git log --oneline <旧SHA>..FETCH_HEAD
```

若确定要"上游提交原样进入本仓库历史"（`git blame` 保留原作者），把 `--squash` 去掉即可；
其余设计不受影响，代价是 458 条上游提交会出现在 `git log` 里。

## 3. 冻结规则

1. **不要编辑 `third_party/KMCLib/` 里的任何文件。** 所有构建适配都在 `cxx/`：
   - `mpiflag.h` 由 `cxx/mpiflag.h.in` 生成到构建目录（上游会写回源码树）；
   - md5 从 `c++/externals/zip/md5.tar.gz` 在构建期解出（见 §4）；
   - 编译器选项、C++ 标准、pybind11 绑定全部在 `cxx/CMakeLists.txt` 与 `cxx/bindings/`。
2. CI 会检查这一点：`git status --porcelain third_party/KMCLib` 必须为空。
3. `src/pykmclib/` 里的上游 Python 前端由 `scripts/gen_python_layer.py` 从
   `third_party/KMCLib/python/src/KMCLib` 重写 `KMCLib → pykmclib` 生成，
   CI 用 `--check` 校验无漂移。手写文件（`__init__.py`、`Backend/Backend.py`、
   `Backend/Custom.py`）不会被覆盖。

## 4. md5

上游把 MD5 实现放在 `c++/externals/zip/md5.tar.gz`（3.4 KB，内部 `md5/{md5.h,md5.c}`），
`hash.cpp` 以 `#include "externals/md5.h"` 引用它。构建期用 CMake 解压到构建目录，
并复制成 `externals/md5.h`、`externals/md5.c` 两份以满足该 include 路径。

**`md5.c` 必须按 C++ 编译**：上游 `hash.cpp` 没有 `extern "C"`，链接的是 C++ 修饰名的
`MD5_*` 符号；用 C 编译器编会在 `import` 时报
`symbol not found in flat namespace '__Z10MD5_Update...'`。

## 5. 许可证

KMCLib 是 **GPL-3.0-or-later**（Copyright 2012–2016 Mikael Leetmaa），pykmclib 链接并分发它，
因此 pykmclib 整体也是 GPL-3.0-or-later。仓库根目录 `LICENSE` 是 GPLv3 全文，
上游原始许可见 `third_party/KMCLib/LICENSE.txt`。MD5 实现为 public domain。

用于发表时请引用：

> Mikael Leetmaa and Natalia V. Skorodumova, *KMCLib: A general framework for lattice kinetic
> Monte Carlo (KMC) simulations*, Comput. Phys. Commun. **185** (2014) 2340.
> DOI: 10.1016/j.cpc.2014.04.017

> Mikael Leetmaa and Natalia V. Skorodumova, *KMCLib 1.1*, Comput. Phys. Commun. (2015).
> DOI: 10.1016/j.cpc.2015.06.016

## 6. 上游构建系统为什么不用

上游 `c++/CMakeLists.txt`：

- `cmake_minimum_required(VERSION 2.8)` —— CMake ≥ 4 直接拒绝；
- 使用 CMake 3.6 已移除的 `cmake_force_cxx_compiler` 模块；
- 全局 `-Werror -pedantic`，2016 年代的代码在现代 clang/MSVC 下几乎必然失败；
- `file(WRITE …/src/mpiflag.h …)` 与 `wrap/custom.i` 把生成物写回**源码树**，
  在只读源码目录（sdist 解包、conda 构建沙箱、`pip install --no-build-isolation`）会失败。

这些目录里的 `CMakeLists.txt` 仅作为出处凭证保留，不参与构建。
