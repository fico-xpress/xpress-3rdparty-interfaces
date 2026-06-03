# Unit Commitment Problem

Power generator scheduling (Unit Commitment) solved using two different Julia interfaces to FICO Xpress Optimizer.

## Related Blog Post

See the ["Xpress Everywhere" blog series](https://community.fico.com/s/blog-post/a5QQp000000vjQDMAY/fico7419) for detailed explanations of these implementations.

## Problem Description

A grid operator must decide which power generators to run each hour over a 24-hour horizon. Generators have startup costs, fuel costs, and technical constraints. Electricity demand must be met in every time period and the system must maintain spinning reserves for reliability. The horizon is non-cyclic: generators have a fixed initial on/off state but no constraint linking the final period back to the start.

### Mathematical Formulation

**Sets:**

- $G$ = set of generators
- $T$ = set of time periods

**Parameters:**

- $c_g^{\text{fuel}}$ = fuel cost per MWh for generator $g$
- $c_g^{\text{start}}$ = startup cost for generator $g$
- $p_g^{\min}, p_g^{\max}$ = minimum/maximum power output (MW)
- $r_g^{\text{up}}, r_g^{\text{down}}$ = ramp-up/ramp-down limits (MW/h)
- $u_g^{\min}, d_g^{\min}$ = minimum up/down time (hours)
- $D_t$ = demand at time $t$

**Decision Variables:**

- $\text{on}_{g,t} \in \{0,1\}$ = 1 if generator $g$ is ON at time $t$
- $p_{g,t} \geq 0$ = power output of generator $g$ at time $t$ (MW)
- $\text{start}_{g,t} \in \{0,1\}$ = 1 if generator $g$ starts up at time $t$

**Objective:**

$$\min \sum_{g \in G} \sum_{t \in T} \left( c_g^{\text{fuel}} \cdot p_{g,t} + c_g^{\text{start}} \cdot \text{start}_{g,t} \right)$$

**Subject to:**

Total generation must meet demand in every time period:

$$\sum_{g \in G} p_{g,t} \geq D_t \quad \forall t \in T$$

ON capacity must exceed demand by 10% to ensure reliability:

$$\sum_{g \in G} p_g^{\max} \cdot \text{on}_{g,t} \geq 1.1 \cdot D_t \quad \forall t \in T$$

Power output is bounded by the generator's minimum and maximum when ON, and forced to zero when OFF:

$$p_g^{\min} \cdot \text{on}_{g,t} \leq p_{g,t} \leq p_g^{\max} \cdot \text{on}_{g,t} \quad \forall g, t$$

Startup indicator is 1 whenever a generator transitions from OFF to ON:

$$\text{start}_{g,t} \geq \text{on}_{g,t} - \text{on}_{g,t-1} \quad \forall g, t$$

Once started, a generator must remain ON for its minimum up time (enforced as an indicator constraint):

$$\text{start}_{g,t} = 1 \Rightarrow \sum_{n=t}^{t+u_g^{\min}-1} \text{on}_{g,n} \geq u_g^{\min} \quad \forall g, t$$

Power output cannot change faster than the generator's ramp-up or ramp-down rate between consecutive periods:

$$p_{g,t} - p_{g,t-1} \leq r_g^{\text{up}}, \quad p_{g,t-1} - p_{g,t} \leq r_g^{\text{down}} \quad \forall g, t$$

## Implementations

| File | Interface | Language |
| ---- | --------- | -------- |
| `unit_commitment_jump.jl` | JuMP / MOI high-level | Julia |
| `unit_commitment_xpressapi.jl` | XpressAPI.jl direct C API | Julia |

Features demonstrated:

- Time-indexed binary and continuous variables
- Indicator constraints for minimum up time
- Startup cost modeled via binary startup indicator variables
- Ramping and minimum down time constraints
- Warm start: loading an initial MIP solution provided by the user
- Solver parameter tuning (gap tolerance, time limit, threads)
- Solution quality metrics (MIP gap, best bound, node count)

## Requirements

### FICO Xpress

Both examples require FICO Xpress Optimizer:

- [Download Xpress](https://www.fico.com/en/products/fico-xpress-optimization) - includes free Community License (limited problem size)
- [Licensing options](https://www.fico.com/en/fico-xpress-trial-and-licensing-options) - trial and full license information

Ensure the `XPRESSDIR` environment variable points to your Xpress installation.

### Julia

Requirements:

- [Julia 1.9+](https://julialang.org/downloads/)
- [JuMP.jl](https://jump.dev/) (for `unit_commitment_jump.jl`)
- [XpressAPI.jl](https://github.com/fico-xpress/xprs.julia) (for both files)

Install Julia dependencies:

```julia
using Pkg
Pkg.add("JuMP")
Pkg.add("XpressAPI")
```

Run:

```bash
julia unit_commitment_jump.jl
julia unit_commitment_xpressapi.jl
```
