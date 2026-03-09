# OR-Tools Integration

Examples demonstrating FICO&reg; Xpress integration with [Google OR-Tools](https://developers.google.com/optimization).

## Examples

| Example | Description | Notes |
|---------|-------------|-------|
| [facility_location](facility_location/) | Capacitated Facility Location Problem | Part of the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000mC3hMAE/fico6620) |

## About OR-Tools

OR-Tools is Google's open-source software suite for optimization, including:
- Linear and mixed-integer programming
- Constraint programming
- Vehicle routing
- Graph algorithms

Xpress can be used as the underlying solver through OR-Tools' solver-agnostic interfaces.

## Requirements

- OR-Tools (see [installation guide](https://developers.google.com/optimization/install))
- FICO Xpress with valid license
- CMake 3.14+ (for C++ examples)
- Python 3.8+ (for Python examples)
