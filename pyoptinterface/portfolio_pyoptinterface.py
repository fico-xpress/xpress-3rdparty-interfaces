"""
Portfolio Optimization using PyOptInterface with FICO Xpress Solver

PyOptInterface provides direct C++ bindings to solver APIs, offering
fast performance and full access to solver-specific features like
callbacks, raw parameter access, and advanced variable/constraint types.

This example demonstrates a comprehensive MIQP portfolio model with:
  - Quadratic objective (minimize variance)
  - Binary variables (cardinality constraints)
  - SOS Type 1 constraints (sector exclusivity)
  - MIP start (warm start)
  - Solver parameter configuration (TIMELIMIT, WORKLIMIT, MIPRELSTOP)
  - Message callbacks for progress monitoring

PyOptInterface includes Xpress support by default. The Xpress library is
loaded dynamically at runtime - no special compiler flags needed. Install via:
  pip install pyoptinterface

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np

try:
    import pyoptinterface as poi
    from pyoptinterface import xpress
    XPRESS_AVAILABLE = True
except ImportError as e:
    XPRESS_AVAILABLE = False
    import_error = str(e)

from data import (
    ASSETS, N_ASSETS, EXPECTED_RETURNS, SECTORS, COVARIANCE,
    BUDGET, MIN_RETURN, MAX_SECTOR_ALLOCATION, MIN_INVESTMENT, MAX_ASSETS,
    TIME_LIMIT, WORK_LIMIT, MIP_GAP, print_solution
)


def solve_portfolio():
    """
    Comprehensive MIQP portfolio optimization demonstrating all Xpress features
    accessible through PyOptInterface:

    - QP objective: minimize portfolio variance (quadratic)
    - MIP: binary variables for cardinality constraints
    - SOS1: at most one asset per sector
    - MIP start: initial solution to seed branch-and-bound
    - Solver params: time limit, gap tolerance, heuristic settings
    - Callbacks: monitor solver progress in real-time

    This creates a Mixed-Integer Quadratic Program (MIQP) that Xpress solves
    using branch-and-bound with quadratic relaxations.
    """
    print("\n" + "=" * 60)
    print("PyOptInterface: Comprehensive MIQP Portfolio")
    print("  Features: QP + MIP + SOS1 + MIP Start + Params + Callbacks")
    print("=" * 60)

    # =========================================================================
    # CALLBACK SETUP (PyOptInterface exclusive feature)
    # =========================================================================
    # Access Xpress constants for callback contexts
    XPRS = xpress.XPRS

    # Track solver progress
    progress_log = []
    solutions_found = [0]  # Use list to allow mutation in closure

    def mip_callback(model, where):
        """
        Callback to monitor solver progress during MIP solve.

        PyOptInterface exposes Xpress callback contexts:
        - XPRS.CB_CONTEXT.MESSAGE: Solver log messages
        - XPRS.CB_CONTEXT.PRESOLVE: After presolve
        - XPRS.CB_CONTEXT.MIPNODE: At each B&B node
        - XPRS.CB_CONTEXT.MIPSOL: When integer solution found
        """
        if where == XPRS.CB_CONTEXT.MESSAGE:
            args = model.cb_get_arguments()
            # Check for None - some messages may be empty
            if args.msg is None:
                return
            msg = args.msg.strip()
            if msg:
                progress_log.append(msg)
                # Print MIP progress messages
                if "*** Solution found" in msg or "Best objective" in msg:
                    solutions_found[0] += 1
                    print(f"  [CB] Solution #{solutions_found[0]}: {msg}")

    # =========================================================================
    # MODEL SETUP
    # =========================================================================
    model = xpress.Model()

    # =========================================================================
    # SOLVER PARAMETERS (raw Xpress controls)
    # =========================================================================
    # PyOptInterface gives direct access to all Xpress control parameters
    model.set_raw_control("OUTPUTLOG", 1)           # 0=silent, 1=summary, 2=full
    model.set_raw_control("TIMELIMIT", float(TIME_LIMIT))
    model.set_raw_control("WORKLIMIT", WORK_LIMIT)  # Deterministic work limit
    model.set_raw_control("MIPRELSTOP", MIP_GAP)    # Stop when gap < 1%
    model.set_raw_control("HEUREMPHASIS", 2)        # Aggressive primal heuristics
    model.set_raw_control("THREADS", 4)             # Parallel threads

    print(f"\n[Solver Params]")
    print(f"  TIMELIMIT = {TIME_LIMIT}s")
    print(f"  WORKLIMIT = {WORK_LIMIT:.0e}")
    print(f"  MIPRELSTOP = {MIP_GAP} (1% gap)")
    print(f"  HEUREMPHASIS = 2 (aggressive)")
    print(f"  THREADS = 4")

    # =========================================================================
    # DECISION VARIABLES
    # =========================================================================

    # Continuous: portfolio weights
    w = [model.add_variable(lb=0.0, ub=1.0, name=f"w_{ASSETS[i]}")
         for i in range(N_ASSETS)]

    # Binary: whether to invest in each asset
    y = [model.add_variable(domain=poi.VariableDomain.Binary, name=f"y_{ASSETS[i]}")
         for i in range(N_ASSETS)]

    # =========================================================================
    # OBJECTIVE: Minimize portfolio variance (QUADRATIC)
    # =========================================================================
    # Option 1: ExprBuilder for efficient expression construction (fastest for large models)
    obj_expr = poi.ExprBuilder()
    for i in range(N_ASSETS):
        for j in range(N_ASSETS):
            obj_expr.add_quadratic_term(w[i], w[j], COVARIANCE[i, j])
    model.set_objective(obj_expr, poi.ObjectiveSense.Minimize)

    # Option 2: Cleaner algebraic syntax using quicksum (slightly slower for large models)
    # quad_terms = [w[i] * w[j] * COVARIANCE[i, j] for i in range(N_ASSETS) for j in range(N_ASSETS)]
    # model.set_objective(poi.quicksum(quad_terms), poi.ObjectiveSense.Minimize)
    # Note: The rest of this model uses the cleaner high-level syntax for linear constraints.

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================

    # Budget constraint: fully invested (using quicksum - cleaner syntax)
    model.add_linear_constraint(poi.quicksum(w) == BUDGET, name="budget")

    # Minimum return target (using quicksum with generator expression)
    model.add_linear_constraint(
        poi.quicksum(EXPECTED_RETURNS[i] * w[i] for i in range(N_ASSETS)) >= MIN_RETURN,
        name="min_return"
    )

    # Sector diversification limits
    for sector, indices in SECTORS.items():
        sector_expr = poi.ExprBuilder()
        for i in indices:
            sector_expr.add_affine_term(w[i], 1.0)
        model.add_linear_constraint(sector_expr, poi.ConstraintSense.LessEqual,
                                    MAX_SECTOR_ALLOCATION, name=f"sector_{sector}")

    # Cardinality constraint: at most MAX_ASSETS assets (using quicksum)
    model.add_linear_constraint(poi.quicksum(y) <= MAX_ASSETS, name="cardinality")

    # Linking constraints: w[i] <= y[i] and w[i] >= MIN_INVESTMENT * y[i]
    # Using direct algebraic syntax (cleaner than ExprBuilder for simple constraints)
    for i in range(N_ASSETS):
        model.add_linear_constraint(w[i] <= y[i], name=f"link_upper_{i}")
        model.add_linear_constraint(w[i] >= MIN_INVESTMENT * y[i], name=f"link_lower_{i}")

    # =========================================================================
    # SOS TYPE 1 CONSTRAINTS: At most one asset per sector
    # =========================================================================
    # add_sos_constraint(variables, type, weights)
    # Weights guide branching order - higher weight variables explored first

    for sector, indices in SECTORS.items():
        sector_vars = [w[i] for i in indices]
        sector_weights = [EXPECTED_RETURNS[i] for i in indices]  # Priorities
        model.add_sos_constraint(sector_vars, poi.SOSType.SOS1, sector_weights)

    print(f"\n[SOS1] One asset per sector constraint added for {len(SECTORS)} sectors")

    # =========================================================================
    # MIP START: Provide initial feasible solution
    # =========================================================================
    # With SOS1 (one per sector), pick the best asset from each sector

    initial_assets = []
    for sector, indices in SECTORS.items():
        best_in_sector = max(indices, key=lambda i: EXPECTED_RETURNS[i])
        initial_assets.append(best_in_sector)

    # Limit to MAX_ASSETS
    initial_assets = sorted(initial_assets, key=lambda i: EXPECTED_RETURNS[i],
                           reverse=True)[:MAX_ASSETS]

    # Build MIP start arrays
    start_vars = []
    start_vals = []
    for i in range(N_ASSETS):
        start_vars.extend([y[i], w[i]])
        if i in initial_assets:
            start_vals.extend([1.0, BUDGET / len(initial_assets)])
        else:
            start_vals.extend([0.0, 0.0])

    model.add_mip_start(start_vars, start_vals)

    print(f"\n[MIP Start] Initial solution: {len(initial_assets)} assets")
    print(f"  Assets: {[ASSETS[i] for i in initial_assets]}")

    # =========================================================================
    # REGISTER CALLBACK
    # =========================================================================
    model.set_callback(mip_callback, XPRS.CB_CONTEXT.MESSAGE)
    print(f"\n[Callback] Message callback registered for progress monitoring")

    # =========================================================================
    # SOLVE
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress via PyOptInterface (direct bindings)")
    print(f"[Problem] MIQP: {N_ASSETS} continuous + {N_ASSETS} binary variables")

    model.optimize()

    # =========================================================================
    # EXTRACT RESULTS
    # =========================================================================
    status = model.get_model_attribute(poi.ModelAttribute.TerminationStatus)
    obj_value = model.get_model_attribute(poi.ModelAttribute.ObjectiveValue)

    solution_weights = [model.get_value(w[i]) for i in range(N_ASSETS)]

    print(f"\n[Result] Status: {status}")
    print(f"[Result] Objective (Variance): {obj_value:.6f}")
    print(f"[Result] Risk (Std Dev): {np.sqrt(obj_value):.4f}")
    print(f"[Result] Callback captured {len(progress_log)} messages")
    print(f"[Result] Solutions found during search: {solutions_found[0]}")

    print_solution(solution_weights, "PyOptInterface MIQP Solution")

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
    print("=" * 60)
    print("Portfolio Optimization with PyOptInterface + FICO Xpress")
    print("=" * 60)

    if not XPRESS_AVAILABLE:
        print("\nERROR: PyOptInterface not available.")
        print(f"Import error: {import_error}")
        print("\nTo install PyOptInterface:")
        print("  pip install pyoptinterface")
        print("\nEnsure Xpress is also installed:")
        print("  pip install xpress")
        exit(1)

    solve_portfolio()

    print("\n" + "=" * 60)
    print("PyOptInterface example completed successfully!")
    print("=" * 60)