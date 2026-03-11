"""
Portfolio Optimization using Pyomo with FICO Xpress Solver

Pyomo is a powerful algebraic modeling language for Python, supporting
LP, MIP, QP, and more. The Xpress connector provides both direct solver interfaces
(xpress_direct and xpress_persistent) for in-memory solving.

This example demonstrates a comprehensive MIQP portfolio model with:
  - Quadratic objective (minimize variance)
  - Binary variables (cardinality constraints)
  - SOS Type 1 constraints (sector exclusivity)
  - Warm start (MIP hints)
  - Solver parameter configuration (TIMELIMIT, WORKLIMIT, MIPRELSTOP)

Note: The xpress_direct interface rebuilds the entire Xpress model from the
Pyomo model on each solve, while xpress_persistent keeps the model alive
between solves for incremental updates.

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import numpy as np

from data import (
    ASSETS, N_ASSETS, EXPECTED_RETURNS, SECTORS, COVARIANCE,
    BUDGET, MIN_RETURN, MAX_SECTOR_ALLOCATION, MIN_INVESTMENT, MAX_ASSETS,
    TIME_LIMIT, WORK_LIMIT, MIP_GAP, print_solution
)


def solve_portfolio():
    """
    Comprehensive MIQP portfolio optimization demonstrating all Xpress
     direct API features accessible through Pyomo:

    - QP objective: minimize portfolio variance (quadratic)
    - MIP: binary variables for cardinality constraints
    - SOS1: at most one asset per sector
    - Warm start: initial solution to seed branch-and-bound
    - Solver params: time limit, gap tolerance, heuristic settings

    This creates a Mixed-Integer Quadratic Program (MIQP) that Xpress solves
    using branch-and-bound with quadratic relaxations.
    """
    print("\n" + "=" * 60)
    print("Pyomo: Comprehensive MIQP Portfolio")
    print("  Features: QP + MIP + SOS1 + Warm Start + Solver Params")
    print("=" * 60)

    # =========================================================================
    # MODEL SETUP
    # =========================================================================
    model = pyo.ConcreteModel("Portfolio_MIQP")

    # Index set for assets
    model.assets = pyo.RangeSet(0, N_ASSETS - 1)

    # =========================================================================
    # DECISION VARIABLES
    # =========================================================================

    # Continuous: portfolio weights (what fraction to invest in each asset)
    model.w = pyo.Var(model.assets, domain=pyo.NonNegativeReals, bounds=(0, 1))

    # Binary: whether to invest in each asset (for cardinality constraint)
    model.y = pyo.Var(model.assets, domain=pyo.Binary)

    # =========================================================================
    # OBJECTIVE: Minimize portfolio variance (QUADRATIC)
    # =========================================================================
    # Variance = w' * Covariance * w = sum_i sum_j w_i * Cov(i,j) * w_j
    # This is a convex quadratic function (covariance matrix is positive semi-definite)

    def variance_rule(m):
        return sum(m.w[i] * COVARIANCE[i, j] * m.w[j]
                   for i in m.assets for j in m.assets)

    model.objective = pyo.Objective(rule=variance_rule, sense=pyo.minimize)

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    # Budget constraint: fully invested (weights sum to 1)
    model.budget = pyo.Constraint(
        expr=sum(model.w[i] for i in model.assets) == BUDGET
    )

    # Minimum return target
    model.min_return = pyo.Constraint(
        expr=sum(EXPECTED_RETURNS[i] * model.w[i] for i in model.assets) >= MIN_RETURN
    )

    # Sector diversification: max allocation per sector
    model.sector_limits = pyo.ConstraintList()
    for sector, indices in SECTORS.items():
        model.sector_limits.add(
            sum(model.w[i] for i in indices) <= MAX_SECTOR_ALLOCATION
        )

    # Cardinality constraint: invest in at most MAX_ASSETS assets (MIP)
    model.cardinality = pyo.Constraint(
        expr=sum(model.y[i] for i in model.assets) <= MAX_ASSETS
    )

    # Linking constraints: w[i] > 0 implies y[i] = 1
    # Upper bound: w[i] <= y[i] (if y=0, then w must be 0)
    # Lower bound: w[i] >= MIN_INVESTMENT * y[i] (if y=1, invest at least minimum)
    model.link_upper = pyo.ConstraintList()
    model.link_lower = pyo.ConstraintList()
    for i in model.assets:
        model.link_upper.add(model.w[i] <= model.y[i])
        model.link_lower.add(model.w[i] >= MIN_INVESTMENT * model.y[i])

    # =========================================================================
    # SOS TYPE 1 CONSTRAINTS: At most one asset per sector
    # =========================================================================
    # SOS1 tells the solver: among these variables, at most one can be non-zero
    # The weights (returns) guide branching order - higher return assets explored first

    # Create one SOS1 constraint per sector using rule-based syntax
    sector_list = list(SECTORS.keys())
    model.sector_idx = pyo.Set(initialize=sector_list)

    def sos1_rule(m, sector):
        """Return (variables, weights) tuple for this sector's SOS1 constraint"""
        var_list = [m.w[i] for i in SECTORS[sector]]
        weight_list = [float(EXPECTED_RETURNS[i]) for i in SECTORS[sector]]
        return (var_list, weight_list)

    model.sos1 = pyo.SOSConstraint(
        model.sector_idx,
        rule=sos1_rule,
        sos=1  # Type 1: at most one non-zero
    )

    # =========================================================================
    # WARM START: Provide initial feasible solution
    # =========================================================================
    # Select top assets by return, distribute weight equally among them
    # This gives the solver a good starting point for branch-and-bound

    # With SOS1 (one per sector), we pick the best asset from each sector
    initial_assets = []
    for sector, indices in SECTORS.items():
        best_in_sector = max(indices, key=lambda i: EXPECTED_RETURNS[i])
        initial_assets.append(best_in_sector)

    # Limit to MAX_ASSETS
    initial_assets = sorted(initial_assets, key=lambda i: EXPECTED_RETURNS[i], reverse=True)[:MAX_ASSETS]

    for i in model.assets:
        if i in initial_assets:
            model.y[i].value = 1
            model.w[i].value = BUDGET / len(initial_assets)
        else:
            model.y[i].value = 0
            model.w[i].value = 0

    print(f"\n[Warm Start] Initial solution: {len(initial_assets)} assets")
    print(f"  Assets: {[ASSETS[i] for i in initial_assets]}")

    # =========================================================================
    # SOLVER CONFIGURATION
    # =========================================================================
    solver = SolverFactory('xpress_direct')

    # Solver parameters - these map directly to Xpress controls
    solver.options['OUTPUTLOG'] = 1           # 0=silent, 1=summary, 2=full
    solver.options['TIMELIMIT'] = TIME_LIMIT  # Maximum solve time (seconds)
    solver.options['WORKLIMIT'] = WORK_LIMIT  # Deterministic work limit
    solver.options['MIPRELSTOP'] = MIP_GAP    # Stop when gap < 1%
    solver.options['HEUREMPHASIS'] = 2        # Aggressive primal heuristics

    print(f"\n[Solver Params]")
    print(f"  TIMELIMIT = {TIME_LIMIT}s")
    print(f"  WORKLIMIT = {WORK_LIMIT:.0e}")
    print(f"  MIPRELSTOP = {MIP_GAP} (1% gap)")
    print(f"  HEUREMPHASIS = 2 (aggressive)")

    # =========================================================================
    # SOLVE
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress via Pyomo (xpress_direct)")
    print(f"[Problem] MIQP: {N_ASSETS} continuous + {N_ASSETS} binary variables")

    results = solver.solve(model, tee=True, warmstart=True)

    # =========================================================================
    # EXTRACT RESULTS
    # =========================================================================
    solution_weights = [pyo.value(model.w[i]) for i in model.assets]

    print(f"\n[Result] Status: {results.solver.status}")
    print(f"[Result] Termination: {results.solver.termination_condition}")
    print(f"[Result] Objective (Variance): {pyo.value(model.objective):.6f}")
    print(f"[Result] Risk (Std Dev): {np.sqrt(pyo.value(model.objective)):.4f}")

    print_solution(solution_weights, "Pyomo MIQP Solution")

    # Show which SOS1 constraints are active
    print("\n[SOS1] One asset per sector:")
    for sector, indices in SECTORS.items():
        active = [ASSETS[i] for i in indices if solution_weights[i] > 0.001]
        if active:
            print(f"  {sector}: {active[0]}")
        else:
            print(f"  {sector}: (none)")

    return solution_weights


if __name__ == "__main__":
    # Check Xpress availability
    solver = SolverFactory('xpress_direct')
    if not solver.available():
        print("ERROR: Xpress solver not available for Pyomo.")
        print("  Ensure xpress package is installed: pip install xpress")
        exit(1)

    print("=" * 60)
    print("Portfolio Optimization with Pyomo + FICO Xpress")
    print("=" * 60)

    solve_portfolio()

    print("\n" + "=" * 60)
    print("Pyomo example completed successfully!")
    print("=" * 60)