# 绑定层移植记录：SWIG → pybind11

pykmclib 把 KMCLib 的 C++ 后端换成 pybind11 绑定，以支持 Windows / macOS / Linux 三端
wheel（SWIG 路线在 Windows 上从未验证过）。本文记录这次移植的语义差异、平台注意事项，
以及上游测试的已知失败清单。

## 1. 布局

```
cxx/bindings/              每个类一个翻译单元
  common.h                 公共 include + bind_* 声明
  module.cpp               PYBIND11_MODULE(_backend)
  coordinate.cpp typebucket.cpp configuration.cpp latticemap.cpp
  process.cpp interactions.cpp latticemodel.cpp timer.cpp
  ontheflymsd.cpp ratecalculator.cpp mpicommons.cpp random.cpp custom.cpp
src/pykmclib/Backend/
  Backend.py               门面：re-export _backend + std::vector/std::map façade
  Custom.py                门面：C++ 示例速率计算器
  _backend.<abi>.so/.pyd   编译产物（wheel 内）
```

上游 Python 前端（4.5k 行）**一行未改**，只是由
`scripts/gen_python_layer.py` 把绝对导入 `KMCLib` 重写为 `pykmclib`。

## 2. 关键语义差异与对策

### 2.1 容器：SWIG `StdVector*` → Python façade

上游前端直接构造 `Backend.StdVectorInt(...)`、`Backend.StdMapStringInt(...)`，并对返回值调用
`.size()`、`[i]`、`push_back`。pybind11 在调用边界把 list/dict 转成 STL 容器，所以
`src/pykmclib/Backend/Backend.py` 提供了 `list`/`dict` 子类作为 façade：

| 上游用法 | 实现 |
| --- | --- |
| `StdVectorInt([1,2])` / `StdVectorDouble(n)` / `StdVectorString(1, "A")` | `_StdVector.__init__` 支持无参、序列、尺寸、尺寸+填充四种形式 |
| `.push_back(x)` / `.size()` | `push_back = list.append`，`size()` 返回 `len()` |
| `StdVectorTypeBucket(4, TypeBucket(3))` 再逐个改元素 | 填充构造用 `copy.deepcopy`，元素互相独立（SWIG 也是这么做的） |
| 返回值与 tuple 比较（上游测试写法） | façade 实现按元素比较的 `__eq__`，嵌套 list/tuple 归一化 |
| `StdMapStringInt({"A": 1})` | `dict` 子类；C++ 侧签名是 `std::map<std::string,int>` |

为避免"从 C++ 返回的容器是裸 list"，`Backend.py` 里给 `Configuration` / `Interactions` /
`OnTheFlyMSD` 定义了薄子类，把查询结果包成对应 façade（上游测试对这些返回值的类型、
`.size()`、与 tuple 的相等性都有断言）。

### 2.2 引用与生命周期

C++ 侧多处保存引用，pybind11 需要显式保活：

| 位置 | 处理 |
| --- | --- |
| `Interactions(const std::vector<CustomRateProcess>&, bool, const RateCalculator&)` 内部存 `const RateCalculator&` | `py::keep_alive<1, 4>()` |
| `LatticeModel(Configuration&, SimulationTimer&, …)` 存配置与计时器引用 | `keep_alive<1,2>`、`keep_alive<1,3>`，另 `keep_alive<1,5>` 保住 interactions（其中含 calculator 引用） |
| `OnTheFlyMSD(const Configuration&, …)` | `keep_alive<1,2>` |
| `BucketsTestCalculator(const Configuration&)` / `IsingTestCalculator` | `keep_alive<1,2>` |
| `interactions()` / `configuration()` / `latticeMap()` / `rateCalculator()` | `reference_internal` |

`setUpdateInfo` 必须就地修改（上游 `KMCInteractions` 依赖 `cpp_config2 = cpp_config1` 的别名语义），
pybind11 绑定天然满足。

### 2.3 director / trampoline

`RateCalculator::backendRateCallback` 与 `backendRateCallbackBuckets` 是 `const` 虚函数，
`SimpleDummyBaseClass::whoAmI` 同理。trampoline 类用 `PYBIND11_OVERRIDE` 转发到 Python。
`KMCRateCalculatorPlugin.__init__` 里的 `Backend.RateCalculator.__init__(self)` 在 pybind11 下
等价于 `super().__init__()`，工作正常。

### 2.4 打印格式

上游 `KMCLatticeModel.__printMatchInfo` 直接 `print(i, p.sites())`，而 SWIG 的 vector proxy
打印成 tuple。因此 `Process.sites()` 绑定返回 **tuple**，保持输出兼容（上游测试比对这段输出）。

## 3. Windows

可行性扫描结论（`third_party/KMCLib/c++/src`）：

- 无 `unistd.h` / `gettimeofday` / `strptime` / `localtime_r` / VLA 等 POSIX 依赖；
- 全树在 `-std=c++17` 下语法通过（21 个编译单元）；
- 已知风险点只有 `hash.cpp` 的 `sprintf`（用 `_CRT_SECURE_NO_WARNINGS` 关掉告警）与
  `PRIx64`（文件已 `#include <cinttypes>`）。

编译选项：`/W3 /EHsc /bigobj /utf-8` + `NOMINMAX`、`_USE_MATH_DEFINES`、
`_CRT_SECURE_NO_WARNINGS`。`md5.c` 用 C++ 编译这条在 MSVC 下同样必须保留
（否则 `MD5_*` 是 C 修饰名，import 时找不到符号）。

## 4. 上游测试的已知失败

上游测试在 vendored 子树里（`python/unittest`、`python/functest`），由
`scripts/run_upstream_tests.py` 以 `KMCLib → pykmclib` 别名方式离线运行。当前：

- 单元测试：188 passed，3 个 known failure（脚本内 `XFAIL`，`--strict` 可强制失败）
  - `CheckUtilitiesTest.testCheckCellVectors` —— numpy ≥ 1.24 拒绝 ragged 数组（测试本身写法过时）
  - `KMCLatticeModelTest.testRunRngTypeDevice` —— 本机 `std::random_device` 有真实熵，DEVICE 被接受
  - `TrajectoryTest.testAppendAndFlushTime` —— 断言两次 append 的 wall-clock 间隔小于 0.1 s，
    机器负载高时偶发失败（与绑定层无关）
- 功能测试：8 个端到端用例（1D/3D 扩散、buckets、Ising、on-the-fly 速率、时间步长分布）全通过。

## 5. 修改指引

- 新增/修改绑定：只动 `cxx/bindings/`；若改了 C++ 侧可见接口，跑
  `uv run pytest -q` + `uv run python scripts/run_upstream_tests.py --units`。
- 不要为了让上游测试通过去改 `src/pykmclib/`（那是上游代码）；改 `Backend.py` 门面或绑定层。
- 如果上游 Python 前端升级，先 `git subtree pull`，再
  `uv run python scripts/gen_python_layer.py`，然后审阅 `git diff src/pykmclib`。
