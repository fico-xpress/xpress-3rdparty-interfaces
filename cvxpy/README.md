# CVXPY Integration

Examples demonstrating FICO&reg; Xpress integration with [CVXPY](https://www.cvxpy.org/).

## Examples

| Example | Description | Notes |
|---------|-------------|-------|
| [portfolio_cvxpy.py](portfolio_cvxpy.py) | Portfolio optimization with quadratic objective and MIP constraints | Part of the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000nwyvMAA/fico6892) |

## About CVXPY

CVXPY is a Python-embedded modeling language for convex optimization problems. It allows you to express problems in a natural way that follows the mathematical notation, and automatically transforms the problem into a standard form for solving.

Key features:
- Disciplined convex programming (DCP) analysis
- Automatic problem transformation
- Support for LP, QP, SOCP, and SDP problems
- Warm start and solver parameter control

Xpress can be used as the underlying solver through CVXPY's solver interface.

## Requirements

- Python 3.9+
- CVXPY: `pip install cvxpy`
- FICO Xpress: `pip install xpress`
- Valid Xpress license (Community Edition or full license)

## Running the Example

```bash
cd xpress-3rdparty-interfaces/cvxpy
python portfolio_cvxpy.py
```
