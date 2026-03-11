# PyOptInterface Integration

Examples demonstrating FICO&reg; Xpress integration with [PyOptInterface](https://github.com/metab0t/PyOptInterface).

## Examples

| Example | Description |
|---------|-------------|
| [portfolio_pyoptinterface.py](portfolio_pyoptinterface.py) | Portfolio optimization with direct C++ bindings, callbacks, and advanced solver features |

## About PyOptInterface

PyOptInterface provides direct C++ bindings to solver APIs, offering maximum performance and full access to solver-specific features. Unlike other modeling libraries that use file I/O or intermediate representations, PyOptInterface communicates directly with the solver's native C/C++ interface.

Key features:
- **Direct C++ bindings** - no file I/O overhead
- **Full solver control** - access to all solver parameters and features
- **Callbacks** - real-time progress monitoring and custom branching
- **Advanced features** - SOS constraints, warm starts, incremental solving
- **High performance** - minimal overhead between Python and solver

PyOptInterface supports both high-level algebraic syntax and low-level performance-oriented APIs:
- `quicksum()` - clean, readable expressions
- `ExprBuilder` - efficient C-style API (4-5x faster for large models)

## Requirements

- Python 3.9+
- PyOptInterface: `pip install pyoptinterface`
- FICO Xpress: `pip install xpress`
- Valid Xpress license (Community Edition or full license)

## Running the Example

```bash
cd xpress-3rdparty-interfaces/pyoptinterface
python portfolio_pyoptinterface.py
```
