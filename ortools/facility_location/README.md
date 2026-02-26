# Facility Location Problem

Capacitated Facility Location Problem solved using three different approaches, all leveraging FICO Xpress Solver.

## Related Blog Post

See the ["Xpress Everywhere" blog series](https://community.fico.com/s/xpress-blog) for detailed explanations of these implementations.

## Problem Description

Given a set of potential facility locations and a set of customers with demands, determine which facilities to open and how to assign customers to facilities to minimize total cost (opening costs + transportation costs + congestion costs), and as a secondary goal, minimize the number of open facilities.

### Mathematical Formulation

**Sets:**

- $I$ = set of potential facility locations
- $J$ = set of customers

**Parameters:**

- $f_i$ = fixed cost to open facility $i$
- $c_{ij}$ = transportation cost per unit from facility $i$ to customer $j$
- $q_i$ = capacity of facility $i$
- $d_j$ = demand of customer $j$
- $\alpha_i$ = congestion cost coefficient for facility $i$

**Decision Variables:**

- $y_i \in \{0, 1\}$ = 1 if facility $i$ is opened
- $x_{ij} \geq 0$ = quantity shipped from facility $i$ to customer $j$

**Lexicographic Multi-Objective Formulation:**

Primary objective (priority 0) - minimize total cost (opening costs, flow costs and congestion costs):

$$\min z_1 = \sum_{i \in I} f_i y_i + \sum_{i \in I} \sum_{j \in J} c_{ij} x_{ij} + \sum_{i \in I} \alpha_i \left( \sum_{j \in J} x_{ij} \right)^2$$

Secondary objective (priority 1) - minimize number of open facilities:

$$\min z_2 = \sum_{i \in I} y_i$$

Subject to:

$$\sum_{i \in I} x_{ij} \geq d_j \quad \forall j \in J \quad \text{(demand satisfaction)}$$

$$x_{ij} = 0 \text{ if } y_i = 0 \quad \forall i \in I, j \in J \quad \text{(indicator constraints)}$$

$$x_{ij} \leq q_i \quad \forall i \in I, j \in J \quad \text{(capacity bounds)}$$

$$y_i + y_{i+1} \leq 1 \quad \forall i \in I \setminus \{|I|\} \quad \text{(pairwise exclusion - lazy)}$$

The lexicographic approach first optimizes $z_1$, then optimizes $z_2$ while keeping $z_1$ at its optimal value. The pairwise exclusion constraints are marked as lazy, meaning they are only enforced when violated during branch-and-bound.

## Implementations

| File | Interface | Language |
| ---- | --------- | -------- |
| `facility_location_xpress.cc` | OR-Tools MathOpt | C++ |
| `facility_location_xpress.py` | OR-Tools MathOpt | Python |
| `facility_location_xpress_api.cpp` | Native Xpress C++ API | C++ |

All implementations demonstrate equivalent features:

- Basic MIP modeling (binary + continuous variables)
- Indicator constraints (avoiding big-M formulations)
- Quadratic constraints for congestion costs
- Lexicographic multi-objective optimization
- Solution hints (MIP starts)
- Message callbacks
- Solver parameter tuning

## Requirements

### FICO Xpress

All examples require FICO Xpress Optimizer:

- [Download Xpress](https://www.fico.com/en/products/fico-xpress-optimization) - includes free Community License (limited problem size)
- [Licensing options](https://www.fico.com/en/fico-xpress-trial-and-licensing-options) - trial and full license information

Ensure the `XPRESSDIR` environment variable points to your Xpress installation.

### Python (MathOpt)

Requirements:

- [Python 3.9+](https://www.python.org/downloads/)
- [OR-Tools](https://developers.google.com/optimization/install) with Xpress support

Installation options:

```bash
# Option 1: pip (recommended)
pip install ortools

# Option 2: conda
conda install -c conda-forge ortools
```

Run:

```bash
python facility_location_xpress.py
```

### C++ (OR-Tools MathOpt)

Requirements:

- [CMake 3.18+](https://cmake.org/download/)
- C++17 compiler ([GCC](https://gcc.gnu.org/), [Clang](https://clang.llvm.org/), or [MSVC](https://visualstudio.microsoft.com/downloads/))
- [OR-Tools C++ library](https://developers.google.com/optimization/install/cpp)

Build with CMake (using installed OR-Tools):

```bash
mkdir build && cd build
cmake -DCMAKE_PREFIX_PATH=/path/to/ortools ..
cmake --build .
./facility_location_xpress
```

Build within OR-Tools source tree:

Place the file in `ortools/math_opt/samples/` and add to `BUILD.bazel`:

```python
cc_binary(
    name = "facility_location_xpress",
    srcs = ["facility_location_xpress.cc"],
    deps = ["//ortools/math_opt/cpp:math_opt"],
)
```

Then build with Bazel:

```bash
bazel build -c opt //ortools/math_opt/samples:facility_location_xpress --define=use_xpress=on
```

### C++ (Native Xpress API)

Requirements:

- C++17 compiler ([GCC](https://gcc.gnu.org/), [Clang](https://clang.llvm.org/), or [MSVC](https://visualstudio.microsoft.com/downloads/))
- FICO Xpress installation (see above)

Linux:

```bash
g++ -std=c++17 -o facility_location_xpress_api facility_location_xpress_api.cpp \
    -I$XPRESSDIR/include -L$XPRESSDIR/lib -lxprs -Wl,-rpath,$XPRESSDIR/lib

./facility_location_xpress_api
```

macOS:

```bash
clang++ -std=c++17 -o facility_location_xpress_api facility_location_xpress_api.cpp \
    -I$XPRESSDIR/include -L$XPRESSDIR/lib -lxprs -Wl,-rpath,$XPRESSDIR/lib

./facility_location_xpress_api
```

Windows (MSVC):

```cmd
cl /EHsc /std:c++17 facility_location_xpress_api.cpp /I"%XPRESSDIR%\include" /link /LIBPATH:"%XPRESSDIR%\lib" xprs.lib

facility_location_xpress_api.exe
```

Windows (MinGW):

```bash
g++ -std=c++17 -o facility_location_xpress_api.exe facility_location_xpress_api.cpp \
    -I"$XPRESSDIR/include" -L"$XPRESSDIR/lib" -lxprs

./facility_location_xpress_api.exe
```

## Troubleshooting

Xpress not found or license errors:

- Verify `XPRESSDIR` is set correctly
- Run `xpress` command to check license status
- On Linux, ensure `LD_LIBRARY_PATH` includes `$XPRESSDIR/lib`
- On macOS, ensure `DYLD_LIBRARY_PATH` includes `$XPRESSDIR/lib`

OR-Tools Xpress support not available:

- Check OR-Tools was built with Xpress support (`--define=use_xpress=on` for Bazel)
- Pre-built pip wheels include Xpress support by default
