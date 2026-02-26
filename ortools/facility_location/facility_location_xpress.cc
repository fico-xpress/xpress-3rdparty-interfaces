// =============================================================================
// Facility Location Problem - Showcasing FICO Xpress Features in OR-Tools
// =============================================================================
//
// This comprehensive example demonstrates multiple Xpress features through
// a single optimization problem: Capacitated Facility Location with extensions.
//
// Problem Description:
//   - A company must decide which warehouses to open
//   - Each warehouse has a fixed cost, capacity, and operating characteristics
//   - Customers have demands that must be satisfied
//   - Transportation costs depend on distance
//   - Additional real-world constraints are modeled using advanced features
//
// Features Demonstrated:
//   1. Basic MIP: Binary open/close + continuous flow variables
//   2. Indicator Constraints: "If warehouse closed, no shipments allowed"
//   3. Quadratic Constraints: Congestion costs modeled via transfer variables
//   4. Multi-Objective: Lexicographic optimization with primary/secondary objectives
//   5. Lazy Constraints: Static constraint annotation for branch-and-cut
//   6. Solution Hints: Provide warm-start solutions to accelerate solving
//   7. Message Callbacks: Real-time solver progress monitoring
//   8. Solver Parameters: Fine-tuning Xpress behavior
//
//   (c) 2026 Fair Isaac Corporation. All rights reserved.
// =============================================================================

#include <cmath>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "ortools/math_opt/cpp/math_opt.h"

namespace operations_research::math_opt {

// =============================================================================
// Problem Data
// =============================================================================

struct FacilityData {
  std::string name;
  double fixed_cost;        // Cost to open facility
  double capacity;          // Maximum throughput
  double congestion_coef;   // Quadratic congestion cost coefficient
};

struct CustomerData {
  std::string name;
  double demand;
  std::vector<double> transport_costs;  // Cost per unit shipped from each facility
};

// Sample problem: 4 potential warehouse locations, 5 customers
const std::vector<FacilityData> facilities = {
    {"Warehouse_North",  500,  100, 0.02},
    {"Warehouse_South",  400,   80, 0.03},
    {"Warehouse_East",   700,  150, 0.01},
    {"Warehouse_West",   450,   90, 0.025},
};

const std::vector<CustomerData> customers = {
    {"Customer_A", 25, {8,  12, 15, 10}},
    {"Customer_B", 30, {10, 6,  9,  14}},
    {"Customer_C", 20, {14, 8,  7,  11}},
    {"Customer_D", 35, {9,  15, 6,  8}},
    {"Customer_E", 15, {11, 9,  12, 7}},
};

// =============================================================================
// FEATURE 1: Basic MIP Setup
// =============================================================================
// This section shows how to create a model with binary and continuous variables.

void SetupBasicMIP(Model& model,
                   std::vector<Variable>& y,           // Binary: facility open?
                   std::vector<std::vector<Variable>>& flow) {  // Continuous: flow

  const int num_facilities = facilities.size();
  const int num_customers = customers.size();

  // Binary variables: y[i] = 1 if facility i is open
  for (int i = 0; i < num_facilities; ++i) {
    y.push_back(model.AddBinaryVariable("open_" + facilities[i].name));
  }

  // Continuous variables: flow[i][j] = quantity shipped from facility i to customer j
  flow.resize(num_facilities);
  for (int i = 0; i < num_facilities; ++i) {
    for (int j = 0; j < num_customers; ++j) {
      flow[i].push_back(model.AddContinuousVariable(
          0, facilities[i].capacity,
          "flow_" + facilities[i].name + "_to_" + customers[j].name));
    }
  }

  // Demand satisfaction constraints: each customer's demand must be met
  for (int j = 0; j < num_customers; ++j) {
    LinearExpression total_supply;
    for (int i = 0; i < num_facilities; ++i) {
      total_supply += flow[i][j];
    }
    model.AddLinearConstraint(total_supply >= customers[j].demand,
                              "demand_" + customers[j].name);
  }

  std::cout << "[Setup] Created " << num_facilities << " facility variables, "
            << num_facilities * num_customers << " flow variables\n";
}

// =============================================================================
// FEATURE 2: Indicator Constraints
// =============================================================================
// Instead of big-M formulations, we use indicator constraints:
// "If facility i is closed (y[i]=0), then all flows from i must be zero"
//
// This is cleaner, more numerically stable, and often solves faster.

void AddIndicatorConstraints(Model& model,
                             const std::vector<Variable>& y,
                             const std::vector<std::vector<Variable>>& flow) {

  const int num_facilities = facilities.size();
  const int num_customers = customers.size();

  for (int i = 0; i < num_facilities; ++i) {
    for (int j = 0; j < num_customers; ++j) {
      // When y[i] = 0 (facility closed), enforce flow[i][j] <= 0
      model.AddIndicatorConstraint(
          y[i],                    // Indicator variable
          flow[i][j] <= 0,            // Implied constraint when indicator is 0
          /*activate_on_zero=*/true,
          "no_flow_if_closed_" + facilities[i].name + "_" + customers[j].name);
    }
  }

  std::cout << "[Indicators] Added " << num_facilities * num_customers
            << " indicator constraints\n";
}

// =============================================================================
// FEATURE 3: Quadratic Objective (Congestion Costs)
// =============================================================================
// Xpress supports quadratic objectives directly:
//   min ... + coef * (total_flow[i])^2
//
// The natural approach is to put quadratic terms directly in the objective.

// =============================================================================
// FEATURE 4: Multi-Objective Optimization
// =============================================================================
// Xpress multi-objective requires LINEAR objectives. To combine quadratic costs
// with multi-objective, we use transfer variables to move quadratic terms into
// constraints:
//   min ... + congestion[i]
//   s.t. congestion[i] >= coef * (total_flow[i])^2
//
// This keeps the objective linear while preserving the quadratic behavior.

void SetupObjectiveWithQuadraticConstraints(
    Model& model,
    const std::vector<Variable>& y,
    const std::vector<std::vector<Variable>>& flow) {

  const int num_facilities = facilities.size();
  const int num_customers = customers.size();

  // Linear costs: fixed costs + transportation
  LinearExpression linear_cost;

  for (int i = 0; i < num_facilities; ++i) {
    // Fixed cost for opening facility
    linear_cost += facilities[i].fixed_cost * y[i];

    // Transportation costs
    for (int j = 0; j < num_customers; ++j) {
      linear_cost += customers[j].transport_costs[i] * flow[i][j];
    }
  }

  // ==========================================================================
  // Transfer Variables: Move quadratic costs to constraints for multi-objective
  // ==========================================================================
  // Without multi-objective, we could simply add quadratic terms to the objective.
  // But Xpress multi-objective requires linear objectives, so we use this workaround.

  std::vector<Variable> congestion;
  for (int i = 0; i < num_facilities; ++i) {
    // Transfer variable for congestion cost at facility i
    congestion.push_back(model.AddContinuousVariable(
        0, std::numeric_limits<double>::infinity(),
        "congestion_" + facilities[i].name));

    // Add congestion to objective (linear term)
    linear_cost += congestion[i];

    // Quadratic constraint: congestion[i] >= coef * (sum_j flow[i][j])^2
    double coef = facilities[i].congestion_coef;
    QuadraticExpression quad_term;
    for (int j = 0; j < num_customers; ++j) {
      for (int k = 0; k < num_customers; ++k) {
        quad_term += coef * flow[i][j] * flow[i][k];
      }
    }
    // congestion[i] - coef * (flow)^2 >= 0
    model.AddQuadraticConstraint(congestion[i] - quad_term >= 0,
                                 "congestion_constraint_" + facilities[i].name);
  }

  std::cout << "[Quadratic] Added " << num_facilities
            << " quadratic constraints for congestion costs\n";

  // PRIMARY OBJECTIVE: Minimize total cost (linear, includes congestion vars)
  model.Minimize(linear_cost);
  std::cout << "[Objective] Set up linear objective with quadratic constraints\n";

  // ==========================================================================
  // Multi-Objective: Secondary objective
  // ==========================================================================
  // SECONDARY OBJECTIVE (priority 1): Minimize number of open facilities
  // When costs are similar, prefer fewer facilities for operational simplicity.
  LinearExpression num_facilities_open;
  for (int i = 0; i < num_facilities; ++i) {
    num_facilities_open += y[i];
  }
  model.AddAuxiliaryObjective(num_facilities_open,
                              /*is_maximize=*/false,
                              /*priority=*/1,
                              "minimize_facilities");
  std::cout << "[Multi-Obj] Added secondary objective: minimize number of facilities\n";
}

// =============================================================================
// FEATURE 5: Lazy Constraints (Static Annotation)
// =============================================================================
// Some constraint families are large or rarely binding. Lazy constraints are
// added to the model but only enforced when violated during branch-and-bound.
//
// MathOpt supports two approaches:
// 1. Static lazy constraints: Add constraints to the model and mark them lazy
//    via ModelSolveParameters::lazy_linear_constraints (supported for Xpress)
// 2. Dynamic lazy constraints: Add constraints via callbacks during solve
//    (not yet supported for Xpress in MathOpt)
//
// Here we demonstrate pairwise facility exclusion constraints - business rules
// that prevent certain facility pairs from being open simultaneously (e.g.,
// due to regional regulations or competitive concerns). With n facilities,
// there are O(n^2) such constraints, making lazy enforcement efficient.

std::vector<LinearConstraint> AddLazyConstraints(
    Model& model,
    const std::vector<Variable>& y) {

  std::vector<LinearConstraint> lazy_constraints;
  const int num_facilities = facilities.size();

  // Pairwise exclusion constraints: certain facility pairs cannot both be open
  // In practice, these come from business rules, regulations, or market analysis
  // Here we demonstrate with pairs that are "too close" (indices differ by 1)
  for (int i = 0; i < num_facilities - 1; ++i) {
    // Business rule: adjacent facilities cannot both be open
    // (e.g., anti-competition regulation in adjacent regions)
    auto exclusion = model.AddLinearConstraint(
        y[i] + y[i + 1] <= 1,
        absl::StrCat("exclusion_", facilities[i].name, "_", facilities[i + 1].name));
    lazy_constraints.push_back(exclusion);
  }

  std::cout << "[Lazy] Added " << lazy_constraints.size()
            << " lazy constraint(s) (enforced only when violated)\n";

  return lazy_constraints;
}

// =============================================================================
// FEATURE 6: Solution Hints (MIP Starts)
// =============================================================================
// Providing a starting solution can speed up MIP solving. Hints can be complete
// or partial - you can specify values for just some variables (e.g., strategic
// decisions) and let the solver determine the rest (e.g., operational details).

ModelSolveParameters GetSolutionHint(
    const std::vector<Variable>& y,
    const std::vector<std::vector<Variable>>& flow) {

  ModelSolveParameters model_params;

  // Create a feasible hint: open the largest facility (East) and serve all demand
  ModelSolveParameters::SolutionHint hint;

  const int num_facilities = facilities.size();
  const int num_customers = customers.size();

  // Hint: Open only Warehouse_East (index 2, largest capacity)
  // This is a PARTIAL hint - we only specify y variables, not x (flow) variables
  // The solver will complete the missing values automatically
  for (int i = 0; i < num_facilities; ++i) {
    hint.variable_values[y[i]] = (i == 2) ? 1.0 : 0.0;
  }

  // NOTE: Flow variables (flow) are intentionally NOT hinted - demonstrating partial hints
  // Uncomment below to provide a complete hint:
  // for (int i = 0; i < num_facilities; ++i) {
  //   for (int j = 0; j < num_customers; ++j) {
  //     if (i == 2) {
  //       hint.variable_values[flow[i][j]] = customers[j].demand;
  //     } else {
  //       hint.variable_values[flow[i][j]] = 0.0;
  //     }
  //   }
  // }

  model_params.solution_hints.push_back(hint);
  std::cout << "[Hint] Provided PARTIAL solution hint: only y variables (facility open/close)\n";

  return model_params;
}

// =============================================================================
// FEATURE 7: Message Callback (Solver Progress Monitoring)
// =============================================================================
// Real-time feedback during optimization. Useful for:
// - Progress bars in applications
// - Logging for long-running solves
// - Early termination decisions

class ProgressMonitor {
 public:
  int message_count = 0;
  double best_bound = std::numeric_limits<double>::infinity();
  double best_solution = std::numeric_limits<double>::infinity();

  void ProcessMessage(const std::vector<std::string>& messages) {
    for (const auto& msg : messages) {
      message_count++;
      std::cout << "  [Progress] " << msg << "\n";
    }
  }
};

// =============================================================================
// FEATURE 8: Solver Parameters
// =============================================================================
// Fine-tune Xpress behavior for your specific problem characteristics.

SolveParameters GetXpressParameters() {
  SolveParameters params;

  // Basic settings
  params.enable_output = true;       // Show solver log
  params.time_limit = absl::Seconds(60);  // Max solve time

  // MIP settings
  params.relative_gap_tolerance = 0.01;  // Stop at 1% gap

  // Xpress-specific parameters via param_values map (string key-value pairs)
  // See: https://www.fico.com/fico-xpress-optimization/docs/latest/solver/optimizer/HTML/chapter7.html
  params.xpress.param_values["HEUREMPHASIS"] = "2";    // Increase heuristic effort

  // For deterministic behavior (reproducible results across runs), use WORKLIMIT
  // instead of time_limit. WORKLIMIT counts deterministic "work units" rather
  // than wall-clock time, ensuring identical behavior regardless of machine speed.
  params.xpress.param_values["WORKLIMIT"] = "1000000";  // Deterministic limit

  return params;
}

// =============================================================================
// Main: Putting It All Together
// =============================================================================

void SolveFacilityLocation() {
  std::cout << "\n========================================\n";
  std::cout << "Facility Location with FICO Xpress\n";
  std::cout << "========================================\n\n";

  // Create the optimization model
  Model model("facility_location");

  // Variables
  std::vector<Variable> y;                    // Open/close decisions
  std::vector<std::vector<Variable>> flow;       // Flow variables

  // FEATURE 1: Basic MIP setup
  SetupBasicMIP(model, y, flow);

  // FEATURE 2: Indicator constraints (no big-M needed!)
  AddIndicatorConstraints(model, y, flow);

  // FEATURE 3: Quadratic constraints + Multi-objective
  SetupObjectiveWithQuadraticConstraints(model, y, flow);

  // FEATURE 5: Lazy constraints (static annotation)
  std::vector<LinearConstraint> lazy_constraints = AddLazyConstraints(model, y);

  // FEATURE 6: Solution hint
  ModelSolveParameters model_params = GetSolutionHint(y, flow);

  // Add lazy constraints to model parameters
  for (const auto& lc : lazy_constraints) {
    model_params.lazy_linear_constraints.insert(lc);
  }
  std::cout << "[Lazy] Marked " << model_params.lazy_linear_constraints.size()
            << " constraint(s) as lazy in solve parameters\n";

  // Configure solve arguments
  SolveArguments args;

  // FEATURE 7 & 8: Message callback and parameters
  args.parameters = GetXpressParameters();
  args.model_parameters = model_params;

  ProgressMonitor monitor;
  args.message_callback = [&monitor](const std::vector<std::string>& msgs) {
    monitor.ProcessMessage(msgs);
  };

  // Solve with Xpress
  std::cout << "\n[Solver] Solving with FICO Xpress...\n\n";
  auto result = Solve(model, SolverType::kXpress, args);

  if (!result.ok()) {
    std::cerr << "Solve failed: " << result.status() << "\n";
    std::cerr << "Make sure XPRESSDIR environment variable is set.\n";
    return;
  }

  // Report results
  std::cout << "\n========================================\n";
  std::cout << "RESULTS\n";
  std::cout << "========================================\n";

  if (result->termination.reason == TerminationReason::kOptimal ||
      result->termination.reason == TerminationReason::kFeasible) {

    std::cout << "Status: " << result->termination.reason << "\n";
    std::cout << "Objective: $" << result->objective_value() << "\n";
    std::cout << "Messages processed: " << monitor.message_count << "\n\n";

    // Facility decisions
    std::cout << "Facility Decisions:\n";
    double total_fixed = 0;
    for (size_t i = 0; i < facilities.size(); ++i) {
      double yi = result->variable_values().at(y[i]);
      if (yi > 0.5) {
        std::cout << "  [OPEN]   " << facilities[i].name
                  << " (fixed cost: $" << facilities[i].fixed_cost << ")\n";
        total_fixed += facilities[i].fixed_cost;

        // Show flows from this facility
        double total_flow = 0;
        for (size_t j = 0; j < customers.size(); ++j) {
          double flow_val = result->variable_values().at(flow[i][j]);
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

    double transport_cost = 0;
    for (size_t i = 0; i < facilities.size(); ++i) {
      for (size_t j = 0; j < customers.size(); ++j) {
        double flow_val = result->variable_values().at(flow[i][j]);
        transport_cost += customers[j].transport_costs[i] * flow_val;
      }
    }
    std::cout << "  Transport costs: $" << transport_cost << "\n";

    double congestion = result->objective_value() - total_fixed - transport_cost;
    std::cout << "  Congestion costs: $" << congestion << "\n";

  } else {
    std::cout << "Termination: " << result->termination << "\n";
  }
}

}  // namespace operations_research::math_opt

// =============================================================================
// Entry Point
// =============================================================================

int main(int argc, char** argv) {
  operations_research::math_opt::SolveFacilityLocation();
  return 0;
}
