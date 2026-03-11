"""
Portfolio Optimization using PuLP with FICO Xpress Solver

PuLP is a beginner-friendly Python optimization library, offering
simple syntax and excellent documentation. It supports LP and MIP problems.

This example demonstrates a comprehensive MILP portfolio model with:
  - Linear objective (maximize return - PuLP doesn't support QP)
  - Binary variables (cardinality constraints)
  - MIP warm start
  - Solver parameter configuration (TIMELIMIT, WORKLIMIT, MIPRELSTOP)

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pulp

from data import (
    ASSETS, N_ASSETS, EXPECTED_RETURNS, SECTORS, COVARIANCE,
    BUDGET, MIN_RETURN, MAX_SECTOR_ALLOCATION, MIN_INVESTMENT, MAX_ASSETS,
    TIME_LIMIT, WORK_LIMIT, MIP_GAP, print_solution
)


def solve_portfolio():
    """
    Comprehensive MILP portfolio optimization demonstrating all Xpress features
    accessible through PuLP:

    - LP objective: maximize expected return (PuLP doesn't support QP)
    - MIP: binary variables for cardinality constraints
    - MIP start: initial solution to seed branch-and-bound
    - Solver params: time limit, gap tolerance, heuristic settings
    """
    print("\n" + "=" * 60)
    print("PuLP: Comprehensive MILP Portfolio")
    print("  Features: LP + MIP + Warm Start + Solver Params")
    print("=" * 60)

    # =========================================================================
    # MODEL SETUP
    # =========================================================================
    model = pulp.LpProblem("Portfolio_MILP", pulp.LpMaximize)

    # =========================================================================
    # DECISION VARIABLES
    # =========================================================================

    # Continuous: portfolio weights
    w = [pulp.LpVariable(f"w_{ASSETS[i]}", lowBound=0, upBound=1)
         for i in range(N_ASSETS)]

    # Binary: whether to invest in each asset
    y = [pulp.LpVariable(f"y_{ASSETS[i]}", cat=pulp.LpBinary)
         for i in range(N_ASSETS)]

    # =========================================================================
    # OBJECTIVE: Maximize expected return (LINEAR)
    # =========================================================================
    # PuLP doesn't support quadratic objectives, so we maximize return
    # instead of minimizing variance like the QP libraries

    model += pulp.lpSum(EXPECTED_RETURNS[i] * w[i] for i in range(N_ASSETS))

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    # Budget constraint: fully invested
    model += pulp.lpSum(w) == BUDGET, "budget"

    # Minimum return target
    model += (pulp.lpSum(EXPECTED_RETURNS[i] * w[i] for i in range(N_ASSETS))
              >= MIN_RETURN, "min_return")

    # Sector diversification limits
    for sector, indices in SECTORS.items():
        model += (pulp.lpSum(w[i] for i in indices) <= MAX_SECTOR_ALLOCATION,
                  f"sector_{sector}")

    # Cardinality constraint: at most MAX_ASSETS assets
    model += pulp.lpSum(y) <= MAX_ASSETS, "cardinality"

    # Linking constraints: w[i] <= y[i] and w[i] >= MIN_INVESTMENT * y[i]
    for i in range(N_ASSETS):
        model += w[i] <= y[i], f"link_upper_{i}"
        model += w[i] >= MIN_INVESTMENT * y[i], f"link_lower_{i}"

    # =========================================================================
    # WARM START: Provide initial feasible solution
    # =========================================================================
    # Select top assets by return to seed branch-and-bound

    initial_assets = sorted(range(N_ASSETS), key=lambda i: EXPECTED_RETURNS[i],
                           reverse=True)[:MAX_ASSETS]

    # Set initial values for warm start
    for i in range(N_ASSETS):
        if i in initial_assets:
            y[i].setInitialValue(1)
            w[i].setInitialValue(BUDGET / len(initial_assets))
        else:
            y[i].setInitialValue(0)
            w[i].setInitialValue(0)

    print(f"\n[Warm Start] Initial solution: {len(initial_assets)} assets")
    print(f"  Assets: {[ASSETS[i] for i in initial_assets]}")

    # =========================================================================
    # SOLVER CONFIGURATION
    # =========================================================================
    solver = pulp.XPRESS_PY(
        msg=True,
        timeLimit=TIME_LIMIT,
        gapRel=MIP_GAP,
        warmStart=True,
        options=[
            ("OUTPUTLOG", 1),
            ("WORKLIMIT", WORK_LIMIT),
            ("HEUREMPHASIS", 2),
            ("PRESOLVE", 1),
        ]
    )

    print(f"\n[Solver Params]")
    print(f"  TIMELIMIT = {TIME_LIMIT}s")
    print(f"  WORKLIMIT = {WORK_LIMIT:.0e}")
    print(f"  gapRel = {MIP_GAP} (1% gap)")
    print(f"  HEUREMPHASIS = 2 (aggressive)")

    # =========================================================================
    # SOLVE
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress via PuLP")
    print(f"[Problem] MILP: {N_ASSETS} continuous + {N_ASSETS} binary variables")

    status = model.solve(solver)

    # =========================================================================
    # EXTRACT RESULTS
    # =========================================================================
    solution_weights = [pulp.value(w[i]) for i in range(N_ASSETS)]

    print(f"\n[Result] Status: {pulp.LpStatus[status]}")
    print(f"[Result] Objective (Expected Return): {pulp.value(model.objective):.4f}")

    print_solution(solution_weights, "PuLP MILP Solution")

    # Show selected assets
    selected = [ASSETS[i] for i in range(N_ASSETS) if solution_weights[i] > 0.001]
    print(f"\n[Selected] {len(selected)} assets: {selected}")

    return solution_weights


if __name__ == "__main__":
    # Check Xpress availability
    solver = pulp.XPRESS_PY()
    if not solver.available():
        print("ERROR: Xpress solver not available. Please install xpress package.")
        print("  pip install xpress")
        exit(1)

    print("=" * 60)
    print("Portfolio Optimization with PuLP + FICO Xpress")
    print("=" * 60)

    solve_portfolio()

    print("\n" + "=" * 60)
    print("PuLP example completed successfully!")
    print("=" * 60)