# FICO&reg; Xpress third-party interface examples

Integration examples for using [FICO&reg; Xpress Solver](https://www.fico.com/en/products/fico-xpress-optimization) with third-party optimization modeling libraries.

## Contents

| Library | Website | Language | Description |
|---------|---------|----------|-------------|
| [OR-Tools](ortools/) | [developers.google.com](https://developers.google.com/optimization) | C++, Python | Google's Operations Research tools with Linear Solver and MathOpt interfaces |
| [CVXPY](cvxpy/) | [cvxpy.org](https://www.cvxpy.org/) | Python | Disciplined convex programming with automatic reformulation |
| [Linopy](linopy/) | [linopy.readthedocs.io](https://linopy.readthedocs.io/) | Python | Pandas-native optimization for data-driven workflows |
| [PuLP](pulp/) | [coin-or.github.io/pulp](https://coin-or.github.io/pulp/) | Python | Beginner-friendly LP/MIP modeling library |
| [Pyomo](pyomo/) | [pyomo.org](https://www.pyomo.org/) | Python | Powerful algebraic modeling language for LP, MIP, QP, and more |
| [PyOptInterface](pyoptinterface/) | [github.com/metab0t/PyOptInterface](https://github.com/metab0t/PyOptInterface) | Python | Direct C++ bindings with callbacks and full solver control |

**Note**: Some library folders contain examples that are part of the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000nwyvMAA/fico6892) on the FICO&reg; Xpress Optimization Blog.

## Python Examples

The Python library examples share a common portfolio optimization problem defined in the [data/](data/) folder. Each library demonstrates different capabilities:

| Library | QP Support | MIP | SOS | Warm Start | Callbacks |
|---------|------------|-----|-----|------------|-----------|
| CVXPY | Yes | Yes | No | Yes | No |
| Linopy | Yes | Yes | No | No | No |
| PuLP | No (LP only) | Yes | No | Yes | No |
| Pyomo | Yes | Yes | Yes | Yes | No |
| PyOptInterface | Yes | Yes | Yes | Yes | Yes |

### Running the Python examples

```bash
# Install dependencies (each library needs xpress package)
pip install xpress cvxpy pyomo pulp linopy pyoptinterface

# Run from repository root
cd xpress-3rdparty-interfaces
python cvxpy/portfolio_cvxpy.py
python linopy/portfolio_linopy.py
python pulp/portfolio_pulp.py
python pyomo/portfolio_pyomo.py
python pyoptinterface/portfolio_pyoptinterface.py
```

## Requirements

- [FICO&reg; Xpress](https://www.fico.com/en/products/fico-xpress-optimization) (Community Edition or full license)
- Language-specific requirements vary by example (see individual READMEs)

## Running the Python examples using GitHub Codespaces

1. **Open Codespaces and create a codespace**:
   - Click on the **"Code"** (green) button on this [repository page](https://github.com/fico-xpress/xpress-3rdparty-interfaces).
   - On the **"Codespaces"** tab, select **"Create a Codespace on main"**. This will set up a cloud-based development environment for you.

2. **Run a Python example**:
   - Once the Codespace is created and the environment is ready, open the terminal.
   - Install the required library and run an example:

     ```bash
     pip install xpress pulp
     python pulp/portfolio_pulp.py
     ```

3. **Try different libraries**:
   - Each library folder contains a `portfolio_<library>.py` example solving the same optimization problem.
   - Install the library you want to try and run its example.

## Related Resources

- [FICO&reg; Xpress Documentation](https://www.fico.com/fico-xpress-optimization/docs/latest/overview.html)
- [python-notebooks](https://github.com/fico-xpress/python-notebooks) - FICO&reg; Xpress Python notebook examples
- [xpress-community](https://github.com/fico-xpress/xpress-community) - Community contributed Xpress examples

## Legal

See source code files for copyright notices.

## License

The examples in this repository are licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full license text. The examples use FICO&reg; Xpress software. By running it, you agree to the Community License terms of the [Xpress Shrinkwrap License Agreement](https://www.fico.com/en/shrinkwrap-license-agreement-fico-xpress-optimization-suite-on-premises) with respect to the FICO&reg; Xpress software. See the [licensing options](https://www.fico.com/en/fico-xpress-trial-and-licensing-options) overview for additional details and information about obtaining a paid license.