# PuLP Integration

Examples demonstrating FICO&reg; Xpress integration with [PuLP](https://coin-or.github.io/pulp/).

## Examples

| Example | Description |
|---------|-------------|
| [portfolio_pulp.py](portfolio_pulp.py) | Portfolio optimization with LP approximation and MIP constraints |

## About PuLP

PuLP is a beginner-friendly LP/MIP modeling library for Python. It provides an intuitive algebraic modeling interface that's easy to learn and use, making it popular for educational purposes and rapid prototyping.

Key features:
- Simple, readable syntax
- Support for LP and MIP problems
- Warm start capability
- Multiple solver backends

Xpress can be used as the underlying solver through PuLP's solver interface.

**Note**: PuLP supports only linear programming. The portfolio example uses a linear approximation of the quadratic objective.

## Requirements

- Python 3.9+
- PuLP: `pip install pulp`
- FICO Xpress: `pip install xpress`
- Valid Xpress license (Community Edition or full license)

## Running the Example

```bash
cd xpress-3rdparty-interfaces/pulp
python portfolio_pulp.py
```
