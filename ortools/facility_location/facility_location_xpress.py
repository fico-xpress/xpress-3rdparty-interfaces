"""
Facility Location Problem using OR-Tools MathOpt API with Xpress solver.

This example demonstrates MathOpt features available in Python with Xpress:
  1. Basic MIP: Binary open/close + continuous flow variables
  2. Indicator Constraints: "If warehouse closed, no shipments allowed"
  3. Quadratic Constraints: Congestion costs modeled via transfer variables
  4. Multi-Objective: Lexicographic optimization with primary/secondary objectives
  5. Lazy Constraints: Static constraint annotation for branch-and-cut
  6. Solution Hints: Provide warm-start solutions to accelerate solving
  7. Message Callbacks: Real-time solver progress monitoring
  8. Solver Parameters: Fine-tuning Xpress behavior

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

from ortools.math_opt.python import mathopt
from datetime import timedelta


# =============================================================================
# Problem Data
# =============================================================================

facilities = [
    # (name, fixed_cost, capacity, congestion_coef)
    ("Warehouse_North", 500, 100, 0.02),
    ("Warehouse_South", 400, 80, 0.03),
    ("Warehouse_East", 700, 150, 0.01),
    ("Warehouse_West", 450, 90, 0.025),
]

customers = [
    # (name, demand, transport_costs_from_each_facility)
    ("Customer_A", 25, [8, 12, 15, 10]),
    ("Customer_B", 30, [10, 6, 9, 14]),
    ("Customer_C", 20, [14, 8, 7, 11]),
    ("Customer_D", 35, [9, 15, 6, 8]),
    ("Customer_E", 15, [11, 9, 12, 7]),
]


# =============================================================================
# FEATURE 5: Lazy Constraints (Static Annotation)
# =============================================================================
# Lazy constraints are added to the model but only enforced when violated
# during branch-and-bound. Useful for problems with large constraint families.
#
# Here we demonstrate pairwise facility exclusion constraints - business rules
# that prevent certain facility pairs from being open simultaneously. With n
# facilities, there are O(n^2) such constraints, making lazy enforcement efficient.

def add_lazy_constraints(model, y):
    """Add constraints and return them for marking as lazy."""
    lazy_constraints = []
    num_facilities = len(facilities)

    # Pairwise exclusion constraints: certain facility pairs cannot both be open
    # In practice, these come from business rules, regulations, or market analysis
    # Here we demonstrate with pairs that are "too close" (adjacent indices)
    for i in range(num_facilities - 1):
        # Business rule: adjacent facilities cannot both be open
        # (e.g., anti-competition regulation in adjacent regions)
        exclusion = model.add_linear_constraint(
            y[i] + y[i + 1] <= 1,
            name=f"exclusion_{facilities[i][0]}_{facilities[i + 1][0]}")
        lazy_constraints.append(exclusion)

    print(f"[Lazy] Added {len(lazy_constraints)} lazy constraint(s) "
          "(enforced only when violated)")

    return lazy_constraints


# =============================================================================
# FEATURE 6: Solution Hints (MIP Starts)
# =============================================================================
# Providing a starting solution can speed up MIP solving. Hints can be complete
# or partial - you can specify values for just some variables (e.g., strategic
# decisions) and let the solver determine the rest (e.g., operational details).

def get_solution_hint(y, flow):
    """Create a feasible solution hint: open Warehouse_East, serve all demand."""
    hint = mathopt.SolutionHint()

    num_facilities = len(facilities)
    num_customers = len(customers)

    # Hint: Open only Warehouse_East (index 2, largest capacity)
    for i in range(num_facilities):
        hint.variable_values[y[i]] = 1.0 if i == 2 else 0.0

    # Hint: Route all demand through the open facility - OPTIONAL
    for i in range(num_facilities):
        for j in range(num_customers):
            if i == 2:
                hint.variable_values[flow[i][j]] = customers[j][1]  # demand
            else:
                hint.variable_values[flow[i][j]] = 0.0

    print("[Hint] Provided solution hint: Warehouse_East serving all demand")
    return hint


# =============================================================================
# FEATURE 6: Message Callback (Solver Progress Monitoring)
# =============================================================================

class ProgressMonitor:
    """Tracks solver progress via message callback."""

    def __init__(self):
        self.message_count = 0

    def process_messages(self, messages):
        """Called by solver with log messages."""
        for msg in messages:
            self.message_count += 1
            print(f"  [Progress] {msg}")


# =============================================================================
# FEATURE 7: Solver Parameters
# =============================================================================

def get_xpress_parameters():
    """Configure Xpress solver parameters."""
    params = mathopt.SolveParameters()
    params.enable_output = True
    params.time_limit = timedelta(seconds=60)
    params.relative_gap_tolerance = 0.01

    # Xpress-specific parameters (requires OR-Tools with solver-specific param support)
    # params.xpress.param_values["HEUREMPHASIS"] = "2"   # Increase heuristic effort
    # params.xpress.param_values["WORKLIMIT"] = "1000000"  # Deterministic work limit

    return params


# =============================================================================
# Main Solve Function
# =============================================================================

def solve_facility_location():
    """Solve the facility location problem demonstrating all MathOpt features."""

    num_facilities = len(facilities)
    num_customers = len(customers)

    print("\n" + "=" * 60)
    print("Facility Location with FICO Xpress (MathOpt Python API)")
    print("=" * 60 + "\n")

    # =========================================================================
    # FEATURE 1: Basic MIP Setup
    # =========================================================================
    print("[Setup] Creating model...")
    model = mathopt.Model(name="facility_location")

    # Binary variables: y[i] = 1 if facility i is open
    y = [model.add_binary_variable(name=f"open_{facilities[i][0]}")
         for i in range(num_facilities)]

    # Continuous variables: flow[i][j] = quantity shipped from facility i to customer j
    flow = [[model.add_variable(lb=0, ub=facilities[i][2],
                             name=f"flow_{facilities[i][0]}_to_{customers[j][0]}")
          for j in range(num_customers)]
         for i in range(num_facilities)]

    print(f"[Setup] Created {num_facilities} facility variables, "
          f"{num_facilities * num_customers} flow variables")

    # Demand satisfaction constraints
    for j in range(num_customers):
        model.add_linear_constraint(
            sum(flow[i][j] for i in range(num_facilities)) >= customers[j][1],
            name=f"demand_{customers[j][0]}")

    # =========================================================================
    # FEATURE 2: Indicator Constraints
    # =========================================================================
    print("[Indicators] Adding indicator constraints...")
    for i in range(num_facilities):
        for j in range(num_customers):
            model.add_indicator_constraint(
                indicator=y[i],
                activate_on_zero=True,
                implied_constraint=flow[i][j] <= 0,
                name=f"no_flow_if_closed_{facilities[i][0]}_{customers[j][0]}")

    print(f"[Indicators] Added {num_facilities * num_customers} indicator constraints")

    # =========================================================================
    # FEATURE 3: Quadratic Objective (Congestion Costs)
    # =========================================================================
    # Real warehouses experience congestion: costs increase non-linearly with load.
    # Xpress supports quadratic objectives directly: min ... + coef * (flow)^2
    #
    # FEATURE 4: Multi-Objective Optimization
    # =========================================================================
    # Xpress multi-objective requires LINEAR objectives. To combine quadratic
    # costs with multi-objective, we use transfer variables to move quadratic
    # terms into constraints:
    #   min ... + congestion[i]
    #   s.t. congestion[i] >= coef * (total_flow[i])^2

    print("[Objective] Setting up costs with quadratic constraints...")

    fixed_cost = sum(facilities[i][1] * y[i] for i in range(num_facilities))

    transport_cost = sum(
        customers[j][2][i] * flow[i][j]
        for i in range(num_facilities)
        for j in range(num_customers))

    # =========================================================================
    # Transfer Variables: Move quadratic costs to constraints for multi-objective
    # =========================================================================
    # Without multi-objective, we could put quadratic terms directly in objective.
    # But Xpress multi-objective requires linear objectives, so we use this workaround.

    congestion = []
    for i in range(num_facilities):
        # Transfer variable for congestion cost at facility i
        cong_var = model.add_variable(lb=0, name=f"congestion_{facilities[i][0]}")
        congestion.append(cong_var)

        # Quadratic constraint: congestion[i] >= coef * (sum_j flow[i][j])^2
        coef = facilities[i][3]
        quad_term = sum(
            coef * flow[i][j] * flow[i][k]
            for j in range(num_customers)
            for k in range(num_customers))

        # congestion[i] - coef * (flow)^2 >= 0
        model.add_quadratic_constraint(
            cong_var - quad_term >= 0,
            name=f"congestion_constraint_{facilities[i][0]}")

    print(f"[Quadratic] Added {num_facilities} quadratic constraints for congestion costs")

    # Total congestion cost (sum of transfer variables)
    total_congestion = sum(congestion)

    # PRIMARY OBJECTIVE: Minimize total cost (linear, includes congestion vars)
    model.minimize(fixed_cost + transport_cost + total_congestion)
    print("[Objective] Set up linear objective with quadratic constraints")

    # =========================================================================
    # Multi-Objective: Secondary objective
    # =========================================================================
    # SECONDARY OBJECTIVE (priority 1): Minimize number of open facilities
    # When costs are similar, prefer fewer facilities for operational simplicity.
    num_facilities_open = sum(y[i] for i in range(num_facilities))
    model.add_auxiliary_objective(
        priority=1,
        is_maximize=False,
        expr=num_facilities_open,
        name="minimize_facilities")
    print("[Multi-Obj] Added secondary objective: minimize number of facilities")

    # =========================================================================
    # FEATURE 5: Lazy Constraints (static annotation)
    # =========================================================================
    lazy_constraints = add_lazy_constraints(model, y)

    # =========================================================================
    # FEATURE 6: Solution Hint
    # =========================================================================
    model_params = mathopt.ModelSolveParameters()
    model_params.solution_hints.append(get_solution_hint(y, flow))

    # Mark constraints as lazy
    for lc in lazy_constraints:
        model_params.lazy_linear_constraints.add(lc)
    print(f"[Lazy] Marked {len(model_params.lazy_linear_constraints)} "
          "constraint(s) as lazy in solve parameters")

    # =========================================================================
    # FEATURES 7 & 8: Message Callback and Solver Parameters
    # =========================================================================
    print(f"\n[Solver] Using FICO Xpress ({mathopt.SolverType.XPRESS.name})")

    monitor = ProgressMonitor()
    params = get_xpress_parameters()

    print("[Solver] Starting optimization...\n")

    result = mathopt.solve(
        model,
        solver_type=mathopt.SolverType.XPRESS,
        params=params,
        model_params=model_params,
        msg_cb=monitor.process_messages)

    # =========================================================================
    # Results
    # =========================================================================
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    print(f"\nStatus: {result.termination.reason}")
    print(f"Objective: ${result.objective_value():,.2f}")
    print(f"Messages processed: {monitor.message_count}")

    var_vals = result.variable_values()

    print("\nFacility Decisions:")
    total_fixed = 0
    total_transport = 0

    for i in range(num_facilities):
        y_val = var_vals[y[i]]
        name, fixed, capacity, cong_coef = facilities[i]

        if y_val > 0.5:
            print(f"  [OPEN]   {name} (fixed cost: ${fixed})")
            total_fixed += fixed

            total_flow = 0
            for j in range(num_customers):
                flow_val = var_vals[flow[i][j]]
                if flow_val > 0.01:
                    print(f"           -> {customers[j][0]}: {flow_val:.1f}")
                    total_transport += customers[j][2][i] * flow_val
                    total_flow += flow_val

            utilization = total_flow / capacity * 100
            print(f"           Utilization: {utilization:.1f}%")
        else:
            print(f"  [CLOSED] {name}")

    congestion = result.objective_value() - total_fixed - total_transport

    print("\nCost Breakdown:")
    print(f"  Fixed costs:      ${total_fixed:,.2f}")
    print(f"  Transport costs:  ${total_transport:,.2f}")
    print(f"  Congestion costs: ${congestion:,.2f}")

    return result.objective_value()


if __name__ == "__main__":
    solve_facility_location()
