# Pyomo Integration

Examples demonstrating FICO&reg; Xpress integration with [Pyomo](https://www.pyomo.org/).

## Examples

| Example | Description |
|---------|-------------|
| [portfolio_pyomo.py](portfolio_pyomo.py) | Portfolio optimization with comprehensive MIQP model and solver parameters |

## About Pyomo

Pyomo is a powerful Python-based algebraic modeling language for optimization. It's designed for large-scale optimization applications and supports a wide range of problem types including linear, nonlinear, and mixed-integer programs.

Key features:
- Expressive algebraic modeling syntax
- Support for LP, MIP, QP, NLP, and MINLP
- Abstract and concrete model formulations
- Extensive solver interfaces (direct and file-based)
- SOS constraints and warm start support

Xpress can be used through two interfaces:
- **xpress_direct**: In-memory communication (LP, MIP, QP)
- **xpress_persistent**: Incremental model updates between solves

## Requirements

- Python 3.9+
- Pyomo: `pip install pyomo`
- FICO Xpress: `pip install xpress`
- Valid Xpress license (Community Edition or full license)

## Running the Example

```bash
cd xpress-3rdparty-interfaces/pyomo
python portfolio_pyomo.py
```
