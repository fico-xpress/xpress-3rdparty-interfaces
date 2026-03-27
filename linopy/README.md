# Linopy Integration

Examples demonstrating FICO&reg; Xpress integration with [Linopy](https://linopy.readthedocs.io/).

## Examples

| Example | Description | Notes |
|---------|-------------|-------|
| [portfolio_linopy.py](portfolio_linopy.py) | Portfolio optimization with pandas-native variable and constraint definitions | Part of the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000nwyvMAA/fico6892) |

## About Linopy

Linopy is a pandas-native optimization library designed for data-driven workflows. It uses labeled coordinates (similar to xarray/pandas) to define variables and constraints, making it natural to work with real-world tabular data.

Key features:
- Pandas/xarray-like labeled dimensions
- Vectorized operations across coordinates
- Efficient handling of large-scale linear models
- Built-in support for LP, MIP, and QP problems

Xpress can be used as the underlying solver through Linopy's solver interface.

## Requirements

- Python 3.9+
- Linopy: `pip install linopy`
- FICO Xpress: `pip install xpress`
- Valid Xpress license (Community Edition or full license)

## Running the Example

```bash
cd xpress-3rdparty-interfaces/linopy
python portfolio_linopy.py
```
