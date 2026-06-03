# =============================================================================
# Unit commitment problem - using XpressAPI.jl low-level C API
# =============================================================================
#
# This example solves the same unit commitment problem as unit_commitment_jump.jl
# using XpressAPI.jl's direct C API interface instead of JuMP.
#
# It demonstrates how XpressAPI.jl provides clean Julia access to the full
# Xpress C API, with:
#   - Automatic resource management via do-block pattern
#   - Direct function calls (no Xpress.Lib. prefix)
#   - Lambda-style callbacks (no @cfunction boilerplate)
#   - Native indicator constraints via XPRSsetindicators
#   - Warm start via XPRSaddmipsol
#
# Problem description:
#   - A grid operator must decide which power generators to run each hour
#   - Each generator has startup costs, fuel costs, and technical constraints
#   - Electricity demand must be met in every time period
#   - System must maintain adequate security reserves for reliability
#   - Generators have minimum up/down times and ramping limits
#
#   (c) 2026 Fair Isaac Corporation. All rights reserved.
# =============================================================================

using XpressAPI
using Printf

# =============================================================================
# Problem data (identical to JuMP version)
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

const GENERATORS = [
    GeneratorData("Coal_1",      "Coal",      100, 400, 25,    5000,  4, 4, 80,  80,  1),
    GeneratorData("Gas_CCGT_1",  "Gas_CCGT",   50, 300, 35,    2000,  2, 2, 100, 100, 1),
    GeneratorData("Gas_Peaker_1","Gas_Peaker",  20, 150, 60,     500,  1, 1, 150, 150, 0),
    GeneratorData("Nuclear_1",   "Nuclear",    300, 500, 15,   15000,  8, 8, 30,  30,  1),
    GeneratorData("Wind_1",      "Wind",         0, 200,  0,       0,  0, 0, 200, 200, 1),
]

const DEMAND = [
    600, 550, 520, 510, 530, 600, 750, 900, 950, 980, 1000, 1020,
    1000, 1030, 1050, 1040, 1020, 1000, 950, 900, 850, 780, 700, 650
]

const T      = length(DEMAND)
const N_GEN  = length(GENERATORS)

# =============================================================================
# Variable index helpers
# =============================================================================
# Xpress uses 0-based column indices. These helpers map (generator, time) to
# the flat column index used internally.
#
# Column layout: [on variables | power variables | start variables]
#   on[g,t]    -> col  on_idx(g,t)
#   power[g,t] -> col  power_idx(g,t)
#   start[g,t] -> col  start_idx(g,t)

const N_ON    = N_GEN * T
const N_POWER = N_GEN * T
const N_START = N_GEN * T
const N_VARS  = N_ON + N_POWER + N_START

on_idx(g, t)    = (g-1) * T + (t-1)                    # 0-based
power_idx(g, t) = N_ON + (g-1) * T + (t-1)             # 0-based
start_idx(g, t) = N_ON + N_POWER + (g-1) * T + (t-1)  # 0-based

# =============================================================================
# Main: build and solve
# =============================================================================

build_time_ref = Ref(0.0)
solve_time_ref = Ref(0.0)
total_time = @elapsed begin

XPRScreateprob("") do prob

    # -------------------------------------------------------------------------
    # Message callback — print solver log to console
    # -------------------------------------------------------------------------
    XPRSaddcbmessage(prob,
        (p, msg, len, msgtype) ->
            if msgtype > 0 println(msg) end,
        0)

    # =========================================================================
    # STEP 1: Add variables (columns)
    # =========================================================================
    # XPRSaddcols adds all variables in one call using sparse column format.
    # We define: objective coefficients, column bounds, and (empty) initial
    # constraint matrix. Constraints are added separately via XPRSaddrows.

    build_time_ref[] = @elapsed begin

    obj  = Vector{Float64}(undef, N_VARS)
    lb   = Vector{Float64}(undef, N_VARS)
    ub   = Vector{Float64}(undef, N_VARS)

    for g in 1:N_GEN, t in 1:T
        # on[g,t]: binary, objective coefficient = 0 (cost is in power and start)
        obj[on_idx(g,t) + 1]    = 0.0
        lb[on_idx(g,t) + 1]     = 0.0
        ub[on_idx(g,t) + 1]     = 1.0

        # power[g,t]: continuous, objective = fuel cost
        obj[power_idx(g,t) + 1] = GENERATORS[g].fuel_cost
        lb[power_idx(g,t) + 1]  = 0.0
        ub[power_idx(g,t) + 1]  = GENERATORS[g].p_max

        # start[g,t]: binary, objective = startup cost
        obj[start_idx(g,t) + 1] = GENERATORS[g].startup_cost
        lb[start_idx(g,t) + 1]  = 0.0
        ub[start_idx(g,t) + 1]  = 1.0
    end

    # Add all columns with empty constraint matrix (constraints added via addrows)
    XPRSaddcols(prob, N_VARS, 0, obj, zeros(Int32, N_VARS + 1), Int32[], Float64[], lb, ub)

    # =========================================================================
    # STEP 2: Set binary variables
    # =========================================================================
    # Mark on[g,t] and start[g,t] columns as binary

    bin_cols  = Int32[]
    bin_types = UInt8[]

    for g in 1:N_GEN, t in 1:T
        push!(bin_cols, Int32(on_idx(g,t)));    push!(bin_types, UInt8('B'))
        push!(bin_cols, Int32(start_idx(g,t))); push!(bin_types, UInt8('B'))
    end

    XPRSchgcoltype(prob, length(bin_cols), bin_cols, bin_types)

    # =========================================================================
    # STEP 3: Add constraints (rows)
    # =========================================================================
    # Each call to XPRSaddrows adds one or more constraints in sparse row format.
    # rowtype: 'G' (>=), 'L' (<=), 'E' (=)

    # --- Demand balance: sum(power[g,t]) >= DEMAND[t]  for all t ---
    for t in 1:T
        colind = Int32[power_idx(g, t) for g in 1:N_GEN]
        coefs  = ones(Float64, N_GEN)
        XPRSaddrows(prob, 1, N_GEN,
            UInt8['G'], [Float64(DEMAND[t])], Float64[],
            Int32[0, N_GEN], colind, coefs)
    end

    # --- Spinning reserve: sum(p_max * on[g,t]) >= 1.1 * demand[t]  for all t ---
    for t in 1:T
        colind = Int32[on_idx(g, t) for g in 1:N_GEN]
        coefs  = [GENERATORS[g].p_max for g in 1:N_GEN]
        XPRSaddrows(prob, 1, N_GEN,
            UInt8['G'], [1.1 * DEMAND[t]], Float64[],
            Int32[0, N_GEN], colind, coefs)
    end

    # --- Capacity limits: p_min * on[g,t] <= power[g,t] <= p_max * on[g,t] ---
    for g in 1:N_GEN, t in 1:T
        p_min = GENERATORS[g].p_min
        p_max = GENERATORS[g].p_max

        # power[g,t] - p_min * on[g,t] >= 0
        XPRSaddrows(prob, 1, 2,
            UInt8['G'], [0.0], Float64[],
            Int32[0, 2],
            Int32[power_idx(g,t), on_idx(g,t)],
            [1.0, -p_min])

        # power[g,t] - p_max * on[g,t] <= 0
        XPRSaddrows(prob, 1, 2,
            UInt8['L'], [0.0], Float64[],
            Int32[0, 2],
            Int32[power_idx(g,t), on_idx(g,t)],
            [1.0, -p_max])
    end

    # --- Startup definition: start[g,t] >= on[g,t] - on[g,t-1] ---
    # For t=1: start[g,1] >= on[g,1] - initial_status
    for g in 1:N_GEN
        init = Float64(GENERATORS[g].initial_status)
        XPRSaddrows(prob, 1, 2,
            UInt8['G'], [-init], Float64[],
            Int32[0, 2],
            Int32[start_idx(g, 1), on_idx(g, 1)],
            [-1.0, 1.0])
    end
    # For t>1: start[g,t] - on[g,t] + on[g,t-1] >= 0
    for g in 1:N_GEN, t in 2:T
        XPRSaddrows(prob, 1, 3,
            UInt8['G'], [0.0], Float64[],
            Int32[0, 3],
            Int32[start_idx(g,t), on_idx(g,t), on_idx(g,t-1)],
            [1.0, -1.0, 1.0])
    end

    # --- Ramping limits ---
    # For t=1: compare against initial power level
    for g in 1:N_GEN
        init_power = GENERATORS[g].initial_status * GENERATORS[g].p_min
        ramp_up    = GENERATORS[g].ramp_up
        ramp_down  = GENERATORS[g].ramp_down

        # power[g,1] - initial_power <= ramp_up
        XPRSaddrows(prob, 1, 1,
            UInt8['L'], [init_power + ramp_up], Float64[],
            Int32[0, 1], Int32[power_idx(g,1)], [1.0])

        # initial_power - power[g,1] <= ramp_down  =>  -power[g,1] <= ramp_down - init_power
        XPRSaddrows(prob, 1, 1,
            UInt8['G'], [init_power - ramp_down], Float64[],
            Int32[0, 1], Int32[power_idx(g,1)], [1.0])
    end
    # For t>1: |power[g,t] - power[g,t-1]| <= ramp
    for g in 1:N_GEN, t in 2:T
        ramp_up   = GENERATORS[g].ramp_up
        ramp_down = GENERATORS[g].ramp_down

        # power[g,t] - power[g,t-1] <= ramp_up
        XPRSaddrows(prob, 1, 2,
            UInt8['L'], [ramp_up], Float64[],
            Int32[0, 2],
            Int32[power_idx(g,t), power_idx(g,t-1)],
            [1.0, -1.0])

        # power[g,t-1] - power[g,t] <= ramp_down
        XPRSaddrows(prob, 1, 2,
            UInt8['L'], [ramp_down], Float64[],
            Int32[0, 2],
            Int32[power_idx(g,t-1), power_idx(g,t)],
            [1.0, -1.0])
    end

    # --- Minimum down time: big-M formulation ---
    # sum(1 - on[g,n] for n in t-min_down+1:t) >= min_down * (on[g,t-min_down] - on[g,t-min_down+1])
    # Note: on[g,t-min_down+1] (= window[1]) appears in both the window sum AND the RHS expansion,
    # so its coefficients are merged to avoid duplicate column indices in the sparse row.
    for g in 1:N_GEN
        min_down = GENERATORS[g].min_down_time
        if min_down > 1
            for t in (min_down+1):T
                colind  = Int32[]
                coefs   = Float64[]
                # on[g,t-min_down]: coef -min_down (from RHS expansion, not in window)
                push!(colind, Int32(on_idx(g, t-min_down)));    push!(coefs, -Float64(min_down))
                # on[g,t-min_down+1] = window[1]: merged coef = -1 (window) + min_down (RHS)
                push!(colind, Int32(on_idx(g, t-min_down+1)));  push!(coefs, Float64(min_down) - 1.0)
                # remaining window elements: coef -1 each
                for n in (t-min_down+2):t
                    push!(colind, Int32(on_idx(g, n)))
                    push!(coefs,  -1.0)
                end
                n_terms = length(colind)
                XPRSaddrows(prob, 1, n_terms,
                    UInt8['G'], [-Float64(min_down)], Float64[],
                    Int32[0, n_terms], colind, coefs)
            end
        end
    end

    # =========================================================================
    # STEP 4: Indicator constraints - minimum up time
    # =========================================================================
    # Each indicator row is conditional on the value of a binary variable.
    # Workflow: add the constraint as a normal row, then register it as an
    # indicator. Collect all indicator rows and register them in one call.

    indicator_rows     = Int32[]
    indicator_bincols  = Int32[]
    indicator_complement = Int32[]

    # We need the current row count to know indices of new rows
    nrows_before = XPRSgetintattrib(prob, XPRS_ROWS)

    for g in 1:N_GEN
        min_up = GENERATORS[g].min_up_time
        if min_up > 1
            for t in 1:(T-min_up+1)
                # Add row: sum(on[g,n] for n in t:t+min_up-1) >= min_up
                window = t:(t+min_up-1)
                colind = Int32[on_idx(g, n) for n in window]
                coefs  = ones(Float64, length(window))
                row_idx = XPRSgetintattrib(prob, XPRS_ROWS)  # current last row index (0-based)
                XPRSaddrows(prob, 1, length(window),
                    UInt8['G'], [Float64(min_up)], Float64[],
                    Int32[0, length(window)], colind, coefs)
                # Register this row as indicator on start[g,t] = 1
                push!(indicator_rows,       Int32(row_idx))
                push!(indicator_bincols,    Int32(start_idx(g, t)))
                push!(indicator_complement, Int32(1))   # ACTIVATE_ON_ONE
            end
        end
    end

    if !isempty(indicator_rows)
        XPRSsetindicators(prob, length(indicator_rows),
                          indicator_rows, indicator_bincols, indicator_complement)
    end

    # =========================================================================
    # STEP 5: Warm start
    # =========================================================================
    # Provide an initial feasible solution: all generators off except Nuclear
    # (always-on in our data). This gives the solver an incumbent to start with.

    warm_sol = zeros(Float64, N_VARS)
    for g in 1:N_GEN, t in 1:T
        if GENERATORS[g].initial_status == 1
            warm_sol[on_idx(g,t) + 1]    = 1.0
            warm_sol[power_idx(g,t) + 1] = GENERATORS[g].p_min
        end
    end
    XPRSaddmipsol(prob, N_VARS, warm_sol, Int32[], "warm_start")

    end  # build_time

    # =========================================================================
    # STEP 6: Solver parameters
    # =========================================================================

    XPRSsetdblcontrol(prob, XPRS_MIPRELSTOP,  1e-4)
    XPRSsetdblcontrol(prob, XPRS_TIMELIMIT,   120.0)
    XPRSsetintcontrol(prob, XPRS_HEUREMPHASIS, 1)
    XPRSsetintcontrol(prob, XPRS_CUTSTRATEGY,  2)
    XPRSsetintcontrol(prob, XPRS_PRESOLVE,     2)
    XPRSsetintcontrol(prob, XPRS_THREADS,      4)
    XPRSsetintcontrol(prob, XPRS_OUTPUTLOG,    1)

    # =========================================================================
    # STEP 7: Solve
    # =========================================================================

    solve_time_ref[] = @elapsed begin
        solvestatus, solstatus = XPRSoptimize(prob, "")
    end

    # =========================================================================
    # STEP 8: Extract results
    # =========================================================================

    mipstatus = XPRSgetintattrib(prob, XPRS_MIPSTATUS)

    if mipstatus == XPRS_MIP_OPTIMAL || mipstatus == XPRS_MIP_SOLUTION
        obj_val   = XPRSgetdblattrib(prob, XPRS_MIPOBJVAL)
        best_bnd  = XPRSgetdblattrib(prob, XPRS_BESTBOUND)
        gap       = abs((obj_val - best_bnd) / obj_val) * 100
        @printf("\nObjective value : %.2f\n", obj_val)
        @printf("Best bound      : %.2f\n",   best_bnd)
        @printf("MIP gap         : %.4f%%\n", gap)
    else
        println("No feasible MIP solution found. Status: $mipstatus")
    end

end  # XPRScreateprob do block

end  # total_time

@printf("\nTiming summary:\n")
@printf("  Build time : %.4f s\n", build_time_ref[])
@printf("  Solve time : %.4f s\n", solve_time_ref[])
@printf("  Total time : %.4f s\n", total_time)
