"""
Portfolio Optimization using Linopy with FICO Xpress Solver

Linopy is a pandas-native optimization library designed for energy system
modeling. It uses xarray/pandas data structures for variables and constraints,
making it ideal for time-indexed problems and data-heavy workflows.

This example demonstrates a comprehensive MIQP portfolio model with:
  - Quadratic objective (minimize variance)
  - Binary variables (cardinality constraints)
  - Solver parameter configuration (TIMELIMIT, WORKLIMIT, MIPRELSTOP)

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import linopy
import pandas as pd
import numpy as np

from data import (
    ASSETS, N_ASSETS, EXPECTED_RETURNS, SECTORS, COVARIANCE,
    BUDGET, MIN_RETURN, MAX_SECTOR_ALLOCATION, MIN_INVESTMENT, MAX_ASSETS,
    TIME_LIMIT, WORK_LIMIT, MIP_GAP, print_solution
)


def solve_portfolio():
    """
    Comprehensive MIQP portfolio optimization demonstrating all Xpress features
    accessible through Linopy:

    - QP objective: minimize portfolio variance (quadratic)
    - MIP: binary variables for cardinality constraints
    - Pandas-native: variables indexed by pandas Index objects
    - Solver params: time limit, gap tolerance
    """
    print("\n" + "=" * 60)
    print("Linopy: Comprehensive MIQP Portfolio (Pandas-Native)")
    print("  Features: QP + MIP + Solver Params")
    print("=" * 60)

    # =========================================================================
    # MODEL SETUP
    # =========================================================================
    model = linopy.Model()

    # Create pandas index for assets - Linopy's native indexing
    asset_idx = pd.Index(ASSETS, name="asset")

    # =========================================================================
    # DECISION VARIABLES
    # =========================================================================

    # Continuous: portfolio weights
    w = model.add_variables(
        lower=0,
        upper=1,
        coords=[asset_idx],
        name="weight"
    )

    # Binary: whether to invest in each asset
    y = model.add_variables(
        coords=[asset_idx],
        name="invest",
        binary=True
    )

    # =========================================================================
    # OBJECTIVE: Minimize portfolio variance (QUADRATIC)
    # =========================================================================
    # Variance = w' * Covariance * w = sum_i sum_j w_i * Cov(i,j) * w_j
    # Linopy supports quadratic expressions via variable multiplication

    # Build quadratic objective using pandas-native syntax
    # Note: We build the variance term by term
    variance_expr = 0
    for i, asset_i in enumerate(ASSETS):
        for j, asset_j in enumerate(ASSETS):
            variance_expr = variance_expr + COVARIANCE[i, j] * w.loc[asset_i] * w.loc[asset_j]

    model.add_objective(variance_expr, sense="min")

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    # Budget constraint: fully invested
    model.add_constraints(w.sum() == BUDGET, name="budget")

    # Minimum return target
    returns_series = pd.Series(EXPECTED_RETURNS, index=asset_idx)
    model.add_constraints(
        (returns_series * w).sum() >= MIN_RETURN,
        name="min_return"
    )

    # Sector diversification limits
    for sector, indices in SECTORS.items():
        sector_assets = [ASSETS[i] for i in indices]
        model.add_constraints(
            w.loc[sector_assets].sum() <= MAX_SECTOR_ALLOCATION,
            name=f"sector_{sector}"
        )

    # Cardinality constraint: at most MAX_ASSETS assets
    model.add_constraints(y.sum() <= MAX_ASSETS, name="cardinality")

    # Linking constraints: w[i] <= y[i] and w[i] >= MIN_INVESTMENT * y[i]
    # Option 1: Explicit loop (beginner-friendly)
    for asset in ASSETS:
        model.add_constraints(w.loc[asset] <= y.loc[asset], name=f"link_upper_{asset}")

    # Option 2: Vectorized operations (Linopy's pandas-like syntax)
    model.add_constraints(w >= MIN_INVESTMENT * y, name="link_lower")

    print(f"\n[Model] MIQP: {N_ASSETS} continuous + {N_ASSETS} binary variables")

    # =========================================================================
    # SOLVER CONFIGURATION
    # =========================================================================
    print(f"\n[Solver Params]")
    print(f"  TIMELIMIT = {TIME_LIMIT}s")
    print(f"  WORKLIMIT = {WORK_LIMIT:.0e}")
    print(f"  MIPRELSTOP = {MIP_GAP} (1% gap)")

    # =========================================================================
    # SOLVE
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress via Linopy (file I/O)")

    result = model.solve(
        solver_name="xpress",
        **{
            "OUTPUTLOG": 1,
            "TIMELIMIT": TIME_LIMIT,
            "WORKLIMIT": WORK_LIMIT,
            "MIPRELSTOP": MIP_GAP
        }
    )

    # =========================================================================
    # EXTRACT RESULTS
    # =========================================================================
    solution_weights = w.solution.values

    # Calculate variance and risk
    variance = solution_weights @ COVARIANCE @ solution_weights
    risk = np.sqrt(variance)

    print(f"\n[Result] Status: {model.status}")
    print(f"[Result] Objective (Variance): {variance:.6f}")
    print(f"[Result] Risk (Std Dev): {risk:.4f}")

    print_solution(solution_weights, "Linopy MIQP Solution")

    # Show selected assets
    selected = [ASSETS[i] for i in range(N_ASSETS) if solution_weights[i] > 0.001]
    print(f"\n[Selected] {len(selected)} assets: {selected}")

    return solution_weights


if __name__ == "__main__":
    # Check Xpress availability
    if "xpress" not in linopy.available_solvers:
        print("ERROR: Xpress solver not available for Linopy.")
        print("  Ensure xpress package is installed: pip install xpress")
        exit(1)

    print("=" * 60)
    print("Portfolio Optimization with Linopy + FICO Xpress")
    print("=" * 60)

    solve_portfolio()

    print("\n" + "=" * 60)
    print("Linopy example completed successfully!")
    print("=" * 60)