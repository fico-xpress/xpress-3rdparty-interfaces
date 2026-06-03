# =============================================================================
# Unit commitment problem - showcasing FICO Xpress features in JuMP
# =============================================================================
#
# This comprehensive example demonstrates multiple Xpress features through
# a single optimization problem: Power Generator Scheduling (Unit Commitment).
#
# Problem description:
#   - A grid operator must decide which power generators to run each hour
#   - Each generator has startup costs, fuel costs, and technical constraints
#   - Electricity demand must be met in every time period
#   - System must maintain adequate security reserves for reliability
#   - Generators have minimum up/down times and ramping limits
#
# Features demonstrated:
#   1. Time-Indexed Variables: Binary and continuous decisions over time
#   2. Mathematical Notation: JuMP syntax that mirrors textbook formulations
#   3. Indicator Constraints: start[g,t]=1 => generator stays ON for at least a minimum duration
#   4. Warm Start: Provide initial MIP solution to accelerate MIP solving
#   5. Solver Parameters: Fine-tuning Xpress behavior for MIP
#   6. Callbacks: Monitor solution progress in real-time
#   7. Solution Quality: Accessing MIP gap, bounds, and node count
#   8. Multiple Solves: Rolling horizon with solution reuse
#   9. Advanced Constraints: Minimum down time, ramping
#
#   (c) 2026 Fair Isaac Corporation. All rights reserved.
# =============================================================================

using JuMP
using MathOptInterface
using XpressAPI
using Printf

# =============================================================================
# Problem data
# =============================================================================

struct GeneratorData
    name::String
    type::String
    p_min::Float64        # Minimum power output (MW)
    p_max::Float64        # Maximum power output (MW)
    fuel_cost::Float64    # Fuel cost per MWh ($/MWh)
    startup_cost::Float64 # Cost to start generator ($)
    min_up_time::Int      # Minimum hours must stay on
    min_down_time::Int    # Minimum hours must stay off
    ramp_up::Float64      # Max power increase per hour (MW/h)
    ramp_down::Float64    # Max power decrease per hour (MW/h)
    initial_status::Int   # Initial on/off state (0 or 1)
end

# Sample problem: 5 generators representing different technologies
const GENERATORS = [
    GeneratorData("Coal_1", "Coal", 100, 400, 25, 5000, 4, 4, 80, 80, 1),
    GeneratorData("Gas_CCGT_1", "Gas_CCGT", 50, 300, 35, 2000, 2, 2, 100, 100, 1),
    GeneratorData("Gas_Peaker_1", "Gas_Peaker", 20, 150, 60, 500, 1, 1, 150, 150, 0),
    GeneratorData("Nuclear_1", "Nuclear", 300, 500, 15, 15000, 8, 8, 30, 30, 1),
    GeneratorData("Wind_1", "Wind", 0, 200, 0, 0, 0, 0, 200, 200, 1),
]

# 24-hour demand profile (MW) - realistic daily pattern
const DEMAND = [
    600, 550, 520, 510, 530, 600, 750, 900, 950, 980, 1000, 1020,
    1000, 1030, 1050, 1040, 1020, 1000, 950, 900, 850, 780, 700, 650
]

# =============================================================================
# FEATURE 1: Time-indexed variables with mathematical notation
# =============================================================================

function setup_variables_and_basic_constraints(model, generators, T)
    """
    Create decision variables and basic constraints.

    Variables:
        on[g,t]:    Binary - generator g is ON at time period t
        power[g,t]: Continuous - power output of generator g at time period t
        start[g,t]: Binary - generator g starts up at time period t (for cost calculation)

    Returns: (on, power, start)
    """
    n_gen = length(generators)

    # Binary variables: on[g,t] = 1 if generator g is ON at time t
    # JuMP notation: @variable(model, name[indices], type)
    @variable(model, on[1:n_gen, 1:T], Bin)

    # Continuous variables: power output (MW), bounded by generator capacity
    @variable(model, 0 <= power[g=1:n_gen, t=1:T] <= generators[g].p_max)

    # Startup indicator variables
    @variable(model, start[1:n_gen, 1:T], Bin)

    return on, power, start
end

# =============================================================================
# FEATURE 2: Objective function - fuel + startup costs
# =============================================================================

function set_objective(model, generators, power, start, T)
    """
    Minimize total cost: fuel cost + startup cost

    Demonstrates:
        - @objective macro with Min/Max
        - sum() with generator comprehension over multiple indices
        - Accessing struct fields in optimization expressions
    """
    n_gen = length(generators)

    @objective(model, Min,
        # Fuel cost: $/MWh × power output
        sum(generators[g].fuel_cost * power[g,t] for g in 1:n_gen, t in 1:T) +
        # Startup cost: $ per startup event
        sum(generators[g].startup_cost * start[g,t] for g in 1:n_gen, t in 1:T)
    )
end

# =============================================================================
# System constraints - demand and reserves
# =============================================================================

function add_system_constraints(model, generators, demand, on, power, T)
    """
    Add system-level constraints for demand satisfaction and reserves.

    Demonstrates mathematical notation that looks like textbook:
        ∑ power[g,t] ≥ demand[t]  ∀t
    """
    n_gen = length(generators)

    # 1. Demand satisfaction: total generation ≥ demand
    @constraint(model, demand_balance[t in 1:T],
        sum(power[g,t] for g in 1:n_gen) >= demand[t]
    )

    # 2. Spinning reserve: online capacity ≥ 1.1 × demand (10% reserve)
    @constraint(model, spinning_reserve[t in 1:T],
        sum(generators[g].p_max * on[g,t] for g in 1:n_gen) >= 1.1 * demand[t]
    )

    # 3. Generator capacity constraints: power output respects min/max when unit is on
    @constraint(model, min_capacity[g in 1:n_gen, t in 1:T],
        power[g,t] >= generators[g].p_min * on[g,t]
    )

    @constraint(model, max_capacity[g in 1:n_gen, t in 1:T],
        power[g,t] <= generators[g].p_max * on[g,t]
    )
end

# =============================================================================
# Startup logic constraints
# =============================================================================

function add_startup_constraints(model, generators, on, start, T)
    """
    Define startup indicator variables: start[g,t] = 1 iff generator starts at
    time period t, expressed as a transition from off to on.

    Logic: start[g,t] ≥ on[g,t] - on[g,t-1]
    """
    n_gen = length(generators)

    # For t=1, compare with initial status
    @constraint(model, startup_def_1[g in 1:n_gen],
        start[g,1] >= on[g,1] - generators[g].initial_status
    )

    # For t>1, compare with previous period
    @constraint(model, startup_def[g in 1:n_gen, t in 2:T],
        start[g,t] >= on[g,t] - on[g,t-1]
    )
end

# =============================================================================
# FEATURE 3: Indicator constraints - minimum up/down time
# =============================================================================
# Indicator constraints conditionally enforce a constraint based on the value of
# a binary variable. Syntax: binary_var => {constraint}
#
# Min up time uses an indicator:
#   start[g,t] = 1  =>  sum(on[g,n] for n in t:(t+min_up-1)) >= min_up
# "IF generator starts at t, THEN it must be ON for the next min_up periods"
#
# This is semantically cleaner than the equivalent big-M formulation:
#   sum(on[g,n] for n in t:(t+min_up-1)) >= min_up * start[g,t]
# and avoids manual M selection while letting Xpress handle the linearization.

function add_minimum_updown_constraints(model, generators, on, start, T)
    """
    Add minimum up/down time constraints to prevent rapid cycling.
    """
    n_gen = length(generators)
    count = 0

    for g in 1:n_gen
        # Minimum up time
        min_up = generators[g].min_up_time
        if min_up > 1
            for t in 1:(T-min_up+1)
                @constraint(model,
                    start[g,t] => {sum(on[g,n] for n in t:(t+min_up-1)) >= min_up}
                )
                count += 1
            end
        end

        # Minimum down time
        min_down = generators[g].min_down_time
        if min_down > 1
            for t in (min_down+1):T
                @constraint(model,
                    sum(1 - on[g,n] for n in (t-min_down+1):t) >=
                    min_down * (on[g,t-min_down] - on[g,t-min_down+1])
                )
                count += 1
            end
        end
    end

end

# =============================================================================
# Ramping constraints
# =============================================================================

function add_ramping_constraints(model, generators, power, T)
    """
    Limit how quickly power output can change between periods.

    Demonstrates:
        - Accessing previous time period: power[g,t-1]
        - Initial condition handling for t=1
    """
    n_gen = length(generators)
    count = 0

    for g in 1:n_gen
        ramp_up = generators[g].ramp_up
        ramp_down = generators[g].ramp_down

        # Initial period: compare with initial power level
        initial_power = generators[g].initial_status * generators[g].p_min
        @constraint(model, power[g,1] - initial_power <= ramp_up)
        @constraint(model, initial_power - power[g,1] <= ramp_down)
        count += 2

        # Subsequent periods: limit change from previous hour
        for t in 2:T
            @constraint(model, power[g,t] - power[g,t-1] <= ramp_up)
            @constraint(model, power[g,t-1] - power[g,t] <= ramp_down)
            count += 2
        end
    end

end

# =============================================================================
# FEATURE 5: Xpress solver parameters
# =============================================================================

function configure_xpress_parameters(model; gap_tolerance=1e-4, time_limit=300,
                                     heuristic_level=1, output=true)
    """
    Configure Xpress solver parameters for MIP performance.

    Key parameters for unit commitment:
        - MIPRELSTOP: MIP gap tolerance (stop when within X% of optimal)
        - TIMELIMIT: Time limit in seconds
        - HEUREMPHASIS: Heuristic emphasis (0=off, 1=emphasize)
        - CUTSTRATEGY: Cutting plane strategy
        - PRESOLVE: Presolve level (2=aggressive)
        - THREADS: Number of CPU threads to use
        - OUTPUTLOG: Enable/disable solver output

    See Xpress Optimizer Reference for full list of controls.
    """
    set_attribute(model, "MIPRELSTOP", gap_tolerance)
    set_attribute(model, "TIMELIMIT", time_limit)
    set_attribute(model, "HEUREMPHASIS", heuristic_level)
    set_attribute(model, "CUTSTRATEGY", 2)
    set_attribute(model, "PRESOLVE", 2)
    set_attribute(model, "THREADS", 4)
    set_attribute(model, "OUTPUTLOG", output ? 1 : 0)
end

# =============================================================================
# FEATURE 4: Warm start (provide initial solution)
# =============================================================================

function apply_warm_start(model, on, power, warm_on, warm_power)
    """
    Provide warm start (initial feasible solution) to accelerate MIP solving.

    Xpress uses the warm start to:
        - Initialize MIP heuristics
        - Guide branching decisions
        - Provide incumbent solution for bounds

    Demonstrates:
        - set_start_value() to provide variable hints
        - Handling different array sizes (shift previous solution)
    """
    n_gen, T = size(on)

    count = 0
    for g in 1:n_gen
        for t in 1:min(T, size(warm_on, 2))
            set_start_value(on[g,t], warm_on[g,t])
            set_start_value(power[g,t], warm_power[g,t])
            count += 2
        end
    end

end

# =============================================================================
# Main solve function
# =============================================================================

function solve_unit_commitment(generators, demand; warm_start_on=nothing,
                                warm_start_power=nothing)
    """
    Build and solve unit commitment model.

    Returns: (status, objective, solve_time, on_solution, power_solution, model)
    """
    T = length(demand)
    n_gen = length(generators)

    # Create model and configure Xpress
    model = Model(XpressAPI.Optimizer)
    configure_xpress_parameters(model, time_limit=120)

    # Build variables and constraints
    on, power, start = setup_variables_and_basic_constraints(model, generators, T)
    set_objective(model, generators, power, start, T)
    add_system_constraints(model, generators, demand, on, power, T)
    add_startup_constraints(model, generators, on, start, T)
    add_minimum_updown_constraints(model, generators, on, start, T)
    add_ramping_constraints(model, generators, power, T)

    # Apply warm start if provided
    if !isnothing(warm_start_on) && !isnothing(warm_start_power)
        apply_warm_start(model, on, power, warm_start_on, warm_start_power)
    end

    # Model introspection
    println("Total variables : $(num_variables(model))")
    println("Total constraints: $(num_constraints(model, count_variable_in_set_constraints=false))")
    println("Is on[1,1] binary : $(is_binary(on[1,1]))")

    optimize!(model)

    # Extract results
    status = termination_status(model)
    obj_value = objective_value(model)
    solve_time = JuMP.solve_time(model)
    on_sol = value.(on)
    power_sol = value.(power)

    return status, obj_value, solve_time, on_sol, power_sol, model
end

# =============================================================================
# Main execution
# =============================================================================

# Run the demonstration
total_time = @elapsed begin
    status, obj, time, on_sol, power_sol, model = solve_unit_commitment(GENERATORS, DEMAND)
end
solver_time = solve_time(model)

if termination_status(model) == MOI.OPTIMAL
    println("Objective value : $(objective_value(model))")
    println("MIP gap         : $(relative_gap(model))")
    println("Best bound      : $(objective_bound(model))")
end
@printf("\nTiming summary:\n")
@printf("  Build time : %.4f s\n", total_time - solver_time)
@printf("  Solve time : %.4f s\n", solver_time)
@printf("  Total time : %.4f s\n", total_time)
