# JuMP Integration

Examples demonstrating FICO&reg; Xpress integration with [JuMP](https://jump.dev/), Julia's algebraic modeling language.

## Examples

| Example | Description | Notes |
|---------|-------------|-------|
| [unit_commitment](unit_commitment/) | Power Generator Scheduling (Unit Commitment) | Part of the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000vjQDMAY/fico7419) |

## About JuMP

[JuMP](https://jump.dev/) (Julia for Mathematical Programming) is an algebraic modeling language embedded in Julia. It provides:

- Expressive macros (`@variable`, `@constraint`, `@objective`) that mirror mathematical notation
- Solver-agnostic interface via MathOptInterface (MOI)
- Support for LP, MIP, QP, SOCP, and more
- Callbacks, warm starts, and solver parameter access

FICO&reg; Xpress is available to JuMP users through **XpressAPI.jl**, FICO's official Julia package. It provides both a full MOI implementation (for seamless JuMP integration) and a direct Julia wrapper for the Xpress C API.

## Requirements

- [Julia 1.9+](https://julialang.org/downloads/)
- [JuMP.jl](https://jump.dev/) (`Pkg.add("JuMP")`)
- [XpressAPI.jl](https://github.com/fico-xpress/xprs.julia) (`Pkg.add("XpressAPI")`)
- FICO&reg; Xpress with valid license