"""
Portfolio Optimization using CVXPY with FICO Xpress Solver

CVXPY is a Python-embedded modeling language for convex optimization problems.
It uses Disciplined Convex Programming (DCP) rules to verify problem convexity
and automatically reformulates problems for different solver backends.

This example demonstrates a comprehensive MIQP portfolio model with:
  - Quadratic objective (minimize variance)
  - Binary variables (cardinality constraints)
  - Warm start (MIP hints)
  - Solver parameter configuration

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cvxpy as cp
import numpy as np

from data import (
    ASSETS, N_ASSETS, EXPECTED_RETURNS, SECTORS, COVARIANCE,
    BUDGET, MIN_RETURN, MAX_SECTOR_ALLOCATION, MIN_INVESTMENT, MAX_ASSETS,
    TIME_LIMIT, MIP_GAP, print_solution
)


def solve_portfolio():
    """
    Comprehensive MIQP portfolio optimization demonstrating all Xpress features
    accessible through CVXPY:

    - QP objective: minimize portfolio variance (quadratic)
    - MIP: binary variables for cardinality constraints
    - Warm start: initial solution to seed branch-and-bound
    - Solver params: time limit, gap tolerance
    """
    print("\n" + "=" * 60)
    print("CVXPY: Comprehensive MIQP Portfolio")
    print("  Features: QP + MIP + Warm Start + Solver Params")
    print("=" * 60)

    # =========================================================================
    # DECISION VARIABLES
    # =========================================================================

    # Continuous: portfolio weights
    w = cp.Variable(N_ASSETS, name="weights")

    # Binary: whether to invest in each asset
    y = cp.Variable(N_ASSETS, boolean=True, name="invest")

    # =========================================================================
    # OBJECTIVE: Minimize portfolio variance (QUADRATIC)
    # =========================================================================
    # Variance = w' * Covariance * w = sum_i sum_j w_i * Cov(i,j) * w_j
    # CVXPY's quad_form verifies this is convex (covariance is PSD)

    portfolio_variance = cp.quad_form(w, COVARIANCE)

    objective = cp.Minimize(portfolio_variance)

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    constraints = []

    # Budget constraint: fully invested
    constraints.append(cp.sum(w) == BUDGET)

    # No short selling
    constraints.append(w >= 0)

    # Minimum return target
    portfolio_return = EXPECTED_RETURNS @ w
    constraints.append(portfolio_return >= MIN_RETURN)

    # Sector diversification limits
    for sector, indices in SECTORS.items():
        constraints.append(cp.sum(w[indices]) <= MAX_SECTOR_ALLOCATION)

    # Cardinality constraint: at most MAX_ASSETS assets
    constraints.append(cp.sum(y) <= MAX_ASSETS)

    # Linking constraints: w[i] <= y[i] and w[i] >= MIN_INVESTMENT * y[i]
    constraints.append(w <= y)
    constraints.append(w >= MIN_INVESTMENT * y)

    print(f"\n[Model] MIQP: {N_ASSETS} continuous + {N_ASSETS} binary variables")

    # =========================================================================
    # WARM START: Provide initial feasible solution
    # =========================================================================
    # Select top assets by return, distribute weight equally

    top_assets = sorted(range(N_ASSETS), key=lambda i: EXPECTED_RETURNS[i],
                       reverse=True)[:MAX_ASSETS]

    y.value = np.array([1.0 if i in top_assets else 0.0 for i in range(N_ASSETS)])
    w.value = np.array([BUDGET / MAX_ASSETS if i in top_assets else 0.0
                       for i in range(N_ASSETS)])

    print(f"\n[Warm Start] Initial solution: {len(top_assets)} assets")
    print(f"  Assets: {[ASSETS[i] for i in top_assets]}")

    # =========================================================================
    # CREATE PROBLEM AND VERIFY DCP
    # =========================================================================
    problem = cp.Problem(objective, constraints)

    print(f"\n[DCP] Problem is DCP compliant: {problem.is_dcp()}")

    # =========================================================================
    # SOLVER CONFIGURATION
    # =========================================================================
    print(f"\n[Solver Params]")
    print(f"  MAXTIME = {TIME_LIMIT}s")
    print(f"  MIPRELSTOP = {MIP_GAP} (1% gap)")

    # =========================================================================
    # SOLVE
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress via CVXPY")

    result = problem.solve(
        solver=cp.XPRESS,
        verbose=True,
        warm_start=True,
        MIPRELSTOP=MIP_GAP,
        MAXTIME=TIME_LIMIT
    )

    # =========================================================================
    # EXTRACT RESULTS
    # =========================================================================
    solution_weights = w.value

    print(f"\n[Result] Status: {problem.status}")
    print(f"[Result] Objective (Variance): {problem.value:.6f}")
    print(f"[Result] Risk (Std Dev): {np.sqrt(problem.value):.4f}")

    print_solution(solution_weights, "CVXPY MIQP Solution")

    # Show selected assets
    selected = [ASSETS[i] for i in range(N_ASSETS) if solution_weights[i] > 0.001]
    print(f"\n[Selected] {len(selected)} assets: {selected}")

    return solution_weights


if __name__ == "__main__":
    # Check Xpress availability
    if cp.XPRESS not in cp.installed_solvers():
        print("ERROR: Xpress solver not available for CVXPY.")
        print("  Ensure xpress package is installed: pip install xpress")
        exit(1)

    print("=" * 60)
    print("Portfolio Optimization with CVXPY + FICO Xpress")
    print("=" * 60)

    solve_portfolio()

    print("\n" + "=" * 60)
    print("CVXPY example completed successfully!")
    print("=" * 60)