// Facility Location Problem using FICO Xpress C++ API
//
// This example demonstrates key Xpress features for comparison with OR-Tools MathOpt:
//   1. Basic MIP: Binary open/close + continuous flow variables
//   2. Indicator Constraints: "If warehouse closed, no shipments allowed"
//   3. Quadratic Constraints: Congestion costs via transfer variables
//   4. Multi-Objective: Lexicographic optimization with primary/secondary objectives
//   5. Lazy Constraints: Delayed rows for pairwise exclusion constraints
//   6. Solution Hints: Provide warm-start solutions (MIP starts)
//   7. Message Callbacks: Real-time solver progress monitoring
//   8. Solver Parameters: Fine-tuning Xpress behavior
//
// (c) 2026 Fair Isaac Corporation. All rights reserved.


#include <iostream>
#include <vector>
#include <xpress.hpp>

using namespace xpress;
using namespace xpress::objects;
using xpress::objects::utils::sum;

// =============================================================================
// Problem Data
// =============================================================================

struct Facility {
  std::string name;
  double fixed_cost;
  double capacity;
  double congestion_coef;
};

struct Customer {
  std::string name;
  double demand;
  std::vector<double> transport_costs;  // Cost to ship from each facility
};

std::vector<Facility> facilities = {
    {"Warehouse_North", 500, 100, 0.02},
    {"Warehouse_South", 400,  80, 0.03},
    {"Warehouse_East",  700, 150, 0.01},
    {"Warehouse_West",  450,  90, 0.025}
};

std::vector<Customer> customers = {
    {"Customer_A", 25, {8,  12, 15, 10}},
    {"Customer_B", 30, {10,  6,  9, 14}},
    {"Customer_C", 20, {14,  8,  7, 11}},
    {"Customer_D", 35, {9,  15,  6,  8}},
    {"Customer_E", 15, {11,  9, 12,  7}}
};

// =============================================================================
// Main
// =============================================================================

int main() {
  try {
    std::cout << "\n========================================\n";
    std::cout << "Facility Location with FICO Xpress C++ API\n";
    std::cout << "========================================\n\n";

    XpressProblem prob("FacilityLocation");

    const size_t num_facilities = facilities.size();
    const size_t num_customers = customers.size();

    // =========================================================================
    // FEATURE 1: Basic MIP Setup
    // =========================================================================
    // Binary variables: y[i] = 1 if facility i is open
    std::vector<Variable> y = prob.addVariables(num_facilities)
        .withType(ColumnType::Binary)
        .withName([](size_t i) { return facilities[i].name; })
        .toArray();

    // Continuous variables: flow[i][j] = quantity shipped from facility i to customer j
    std::vector<std::vector<Variable>> flow = prob.addVariables(num_facilities, num_customers)
        .withLB(0)
        .withUB([](size_t i, size_t /*j*/) { return facilities[i].capacity; })
        .withName([](size_t i, size_t j) {
          return xpress::format("flow_%s_to_%s",
                                facilities[i].name.c_str(),
                                customers[j].name.c_str());
        })
        .toArray();

    std::cout << "[Setup] Created " << num_facilities << " facility variables, "
              << num_facilities * num_customers << " flow variables\n";

    // Demand satisfaction constraints
    prob.addConstraints(num_customers, [&](size_t j) {
      return sum(num_facilities, [&](size_t i) { return flow[i][j]; }) >= customers[j].demand;
    });

    // Capacity constraints: sum of flows from facility i <= capacity * y[i]
    prob.addConstraints(num_facilities, [&](size_t i) {
      return sum(flow[i]) <= facilities[i].capacity * y[i];
    });

    // =========================================================================
    // FEATURE 2: Indicator Constraints
    // =========================================================================
    // If warehouse is closed (y[i]=0), no shipments allowed (flow[i][j]=0)
    // Using indicator constraints avoids big-M formulations
    for (size_t i = 0; i < num_facilities; ++i) {
      for (size_t j = 0; j < num_customers; ++j) {
        // When y[i] == 0, enforce flow[i][j] <= 0 (i.e., flow[i][j] == 0 since flow >= 0)
        Inequality flow_zero = prob.addConstraint(flow[i][j] <= 0.0);
        prob.setIndicator(y[i], false, flow_zero);  // false = when y[i] is 0
      }
    }
    std::cout << "[Indicators] Added " << num_facilities * num_customers
              << " indicator constraints\n";

    // =========================================================================
    // FEATURE 3: Quadratic Constraints (via Transfer Variables)
    // =========================================================================
    // Xpress multi-objective requires LINEAR objectives. To combine quadratic
    // congestion costs with multi-objective, we use transfer variables:
    //   min ... + congestion[i]
    //   s.t. congestion[i] >= coef * (total_flow[i])^2
    //
    // This keeps the objective linear while preserving quadratic behavior.

    // Linear costs: fixed + transport
    LinExpression linear_cost = LinExpression::create();

    for (size_t i = 0; i < num_facilities; ++i) {
      linear_cost.addTerm(y[i], facilities[i].fixed_cost);
    }

    for (size_t j = 0; j < num_customers; ++j) {
      for (size_t i = 0; i < num_facilities; ++i) {
        linear_cost.addTerm(flow[i][j], customers[j].transport_costs[i]);
      }
    }

    // Transfer variables for congestion costs
    std::vector<Variable> congestion = prob.addVariables(num_facilities)
        .withLB(0)
        .withName([](size_t i) {
          return xpress::format("congestion_%s", facilities[i].name.c_str());
        })
        .toArray();

    // Add congestion to objective (linear terms)
    for (size_t i = 0; i < num_facilities; ++i) {
      linear_cost.addTerm(congestion[i], 1.0);
    }

    // Quadratic constraints: congestion[i] >= coef * (sum_j flow[i][j])^2
    for (size_t i = 0; i < num_facilities; ++i) {
      double coef = facilities[i].congestion_coef;
      QuadExpression quad_term = QuadExpression::create();

      for (size_t j = 0; j < num_customers; ++j) {
        for (size_t k = 0; k < num_customers; ++k) {
          quad_term.addTerm(flow[i][j], flow[i][k], coef);
        }
      }

      // congestion[i] >= coef * (sum_j flow[i][j])^2
      prob.addConstraint(congestion[i] >= quad_term);
    }

    std::cout << "[Quadratic] Added " << num_facilities
              << " quadratic constraints for congestion costs\n";

    // Set PRIMARY objective: minimize total cost (linear)
    prob.setObjective(linear_cost);
    std::cout << "[Objective] Set up linear objective with transfer variables\n";

    // =========================================================================
    // FEATURE 4: Multi-Objective Optimization
    // =========================================================================
    // SECONDARY OBJECTIVE: minimize number of open facilities
    // addObjective(expr, priority, weight) - higher priority = solved first
    // Primary objective has default priority 0, so secondary gets priority -1 (lower)
    Expression num_open = sum(y);
    prob.addObjective(num_open, -1, 1.0);  // priority=-1, weight=1.0
    std::cout << "[Multi-Obj] Added secondary objective: minimize facilities\n";

    // =========================================================================
    // FEATURE 5: Lazy Constraints (Delayed Rows)
    // =========================================================================
    // Delayed rows are constraints that must be satisfied for any integer
    // solution but are not loaded into the active set until required.
    // This is useful for large constraint families that are rarely binding.
    //
    // Here we add pairwise exclusion constraints: adjacent facilities cannot
    // both be open (e.g., business rules, regional regulations).

    std::vector<Inequality> lazy_constraints;
    for (size_t i = 0; i < num_facilities - 1; ++i) {
      // Adjacent facilities cannot both be open
      Inequality exclusion = prob.addConstraint(y[i] + y[i + 1] <= 1);
      lazy_constraints.push_back(exclusion);
    }

    // Mark constraints as delayed rows
    prob.loadDelayedRows(lazy_constraints);
    std::cout << "[Lazy] Added " << lazy_constraints.size()
              << " delayed row(s) for pairwise exclusion\n";

    // -------------------------------------------------------------------------
    // ALTERNATIVE: Direct Quadratic Objective (without multi-objective)
    // -------------------------------------------------------------------------
    // If multi-objective is not needed, you can use a quadratic objective directly:
    //
    //   QuadExpression total_cost = QuadExpression::create();
    //
    //   // Linear terms: fixed costs
    //   for (size_t i = 0; i < num_facilities; ++i) {
    //     total_cost.addTerm(y[i], facilities[i].fixed_cost);
    //   }
    //
    //   // Linear terms: transport costs
    //   for (size_t j = 0; j < num_customers; ++j) {
    //     for (size_t i = 0; i < num_facilities; ++i) {
    //       total_cost.addTerm(flow[i][j], customers[j].transport_costs[i]);
    //     }
    //   }
    //
    //   // Quadratic terms: congestion costs = coef * (sum_j flow[i][j])^2
    //   for (size_t i = 0; i < num_facilities; ++i) {
    //     double coef = facilities[i].congestion_coef;
    //     for (size_t j = 0; j < num_customers; ++j) {
    //       for (size_t k = 0; k < num_customers; ++k) {
    //         total_cost.addTerm(flow[i][j], flow[i][k], coef);
    //       }
    //     }
    //   }
    //
    //   prob.setObjective(total_cost);
    //
    // This is more direct but incompatible with addObjective() for multi-objective.
    // -------------------------------------------------------------------------

    // =========================================================================
    // FEATURE 6: Solution Hints (MIP Starts)
    // =========================================================================
    // Provide a warm-start: open Warehouse_East and serve all demand from it
    // Note: Hints can be partial - solver will complete missing values
    std::vector<Variable> hint_vars;
    std::vector<double> hint_values;

    // Hint for y variables
    for (size_t i = 0; i < num_facilities; ++i) {
      hint_vars.push_back(y[i]);
      hint_values.push_back((i == 2) ? 1.0 : 0.0);  // Open only Warehouse_East
    }

    // Hint for flow variables
    for (size_t i = 0; i < num_facilities; ++i) {
      for (size_t j = 0; j < num_customers; ++j) {
        hint_vars.push_back(flow[i][j]);
        hint_values.push_back((i == 2) ? customers[j].demand : 0.0);
      }
    }

    prob.addMipSol(hint_values, hint_vars, "WarmStart");
    std::cout << "[Hint] Added MIP start: Warehouse_East serving all demand\n";

    // =========================================================================
    // FEATURE 7: Message Callback
    // =========================================================================
    // Output all messages to console (using built-in console handler)
    prob.callbacks.addMessageCallback(XpressProblem::console);

    // =========================================================================
    // FEATURE 8: Solver Parameters
    // =========================================================================
    // Method 1: Named setter functions (type-safe, discoverable via IDE)
    prob.controls.setTimeLimit(60);        // Max 60 seconds
    prob.controls.setMipRelStop(0.01);     // 1% optimality gap

    // Method 2: Generic control setters (useful for dynamic control setting)
    prob.setIntControl(XPRS_HEUREMPHASIS, 2);      // Increase heuristic effort
    prob.setDblControl(XPRS_WORKLIMIT, 1000000);   // Deterministic work limit

    std::cout << "[Controls] Set time limit, gap tolerance, heuristics, work limit\n";

    // =========================================================================
    // Solve
    // =========================================================================
    std::cout << "\n[Solver] Starting optimization...\n\n";
    prob.optimize();

    // =========================================================================
    // Results
    // =========================================================================
    std::cout << "\n========================================\n";
    std::cout << "RESULTS\n";
    std::cout << "========================================\n";

    // Always check getSolveStatus before accessing solutions
    if (prob.attributes.getSolveStatus() != SolveStatus::Completed) {
      std::cerr << "Solve not completed: "
                << to_string(prob.attributes.getSolveStatus()) << "\n";
      return 1;
    }

    if (prob.attributes.getSolStatus() == SolStatus::Optimal ||
        prob.attributes.getSolStatus() == SolStatus::Feasible) {

      std::cout << "Status: " << to_string(prob.attributes.getSolStatus()) << "\n";
      std::cout << "Objective: $" << prob.attributes.getObjVal() << "\n";
      std::cout << "Solved objectives: " << prob.attributes.getSolvedObjs()
                << " of " << prob.attributes.getObjectives() << "\n\n";

      std::vector<double> sol = prob.getSolution();

      // Facility decisions
      std::cout << "Facility Decisions:\n";
      double total_fixed = 0;
      for (size_t i = 0; i < num_facilities; ++i) {
        double yi = y[i].getValue(sol);
        if (yi > 0.5) {
          std::cout << "  [OPEN]   " << facilities[i].name
                    << " (fixed cost: $" << facilities[i].fixed_cost << ")\n";
          total_fixed += facilities[i].fixed_cost;

          double total_flow = 0;
          for (size_t j = 0; j < num_customers; ++j) {
            double flow_val = flow[i][j].getValue(sol);
            if (flow_val > 0.01) {
              std::cout << "           -> " << customers[j].name
                        << ": " << flow_val << "\n";
              total_flow += flow_val;
            }
          }
          double utilization = total_flow / facilities[i].capacity * 100;
          std::cout << "           Utilization: " << utilization << "%\n";
        } else {
          std::cout << "  [CLOSED] " << facilities[i].name << "\n";
        }
      }

      // Cost breakdown
      std::cout << "\nCost Breakdown:\n";
      std::cout << "  Fixed costs: $" << total_fixed << "\n";

      double transport = 0;
      for (size_t i = 0; i < num_facilities; ++i) {
        for (size_t j = 0; j < num_customers; ++j) {
          double flow_val = flow[i][j].getValue(sol);
          transport += customers[j].transport_costs[i] * flow_val;
        }
      }
      std::cout << "  Transport costs: $" << transport << "\n";

      double congestion_cost = 0;
      for (size_t i = 0; i < num_facilities; ++i) {
        double total_flow = 0;
        for (size_t j = 0; j < num_customers; ++j) {
          total_flow += flow[i][j].getValue(sol);
        }
        congestion_cost += facilities[i].congestion_coef * total_flow * total_flow;
      }
      std::cout << "  Congestion costs: $" << congestion_cost << "\n";

    } else {
      std::cerr << "Solve failed with status: "
                << to_string(prob.attributes.getSolStatus()) << "\n";
      return 1;
    }

    return 0;

  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << std::endl;
    return 1;
  }
}
