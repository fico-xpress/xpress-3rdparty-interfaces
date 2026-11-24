/*
 * Portfolio Optimization using ojAlgo with FICO Xpress Solver
 *
 * ojAlgo is an open source, pure Java library for mathematical optimization. Its modeling API,
 * ExpressionsBasedModel, builds LP, QP and MIP models as plain Java objects, and the integration
 * module ojalgo-xpress hands them to Xpress through the Xpress Java API, in memory.
 *
 * This example solves the shared portfolio problem (see ../data/portfolio_data.py) as an MIQP:
 *   - Quadratic objective (minimize portfolio variance)
 *   - Binary variables (cardinality and minimum investment)
 *   - Solver parameter configuration (time limit, MIP gap, HEUREMPHASIS)
 *
 * (c) 2026 Optimatika. Licensed under the Apache License, Version 2.0.
 */

import java.util.LinkedHashMap;
import java.util.Map;

import org.ojalgo.data.domain.finance.FinanceUtils;
import org.ojalgo.matrix.MatrixR064;
import org.ojalgo.matrix.store.R064Store;
import org.ojalgo.matrix.store.RawStore;
import org.ojalgo.optimisation.Expression;
import org.ojalgo.optimisation.ExpressionsBasedModel;
import org.ojalgo.optimisation.Optimisation;
import org.ojalgo.optimisation.Variable;
import org.ojalgo.optimisation.integer.IntegerStrategy;
import org.ojalgo.optimisation.solver.xpress.SolverXpress;
import org.ojalgo.type.CalendarDateUnit;
import org.ojalgo.type.context.NumberContext;

import com.dashoptimization.XPRSconstants;
import com.dashoptimization.XPRSprob;

public class PortfolioOjAlgo {

    // =========================================================================
    // DATA - the same as ../data/portfolio_data.py
    // =========================================================================

    static final String[] ASSETS = { "TECH_A", "TECH_B", "TECH_C", "HEALTH_A", "HEALTH_B", "HEALTH_C", "ENERGY_A", "ENERGY_B", "FINANCE_A",
            "FINANCE_B" };

    static final double[] EXPECTED_RETURNS = { 0.12, 0.10, 0.14, 0.08, 0.07, 0.09, 0.11, 0.06, 0.09, 0.08 };

    static final double[] VOLATILITIES = { 0.25, 0.22, 0.30, 0.15, 0.12, 0.18, 0.28, 0.20, 0.16, 0.14 };

    static final double[][] CORRELATIONS = { //
            { 1.00, 0.70, 0.65, 0.30, 0.25, 0.28, 0.20, 0.15, 0.40, 0.35 }, //
            { 0.70, 1.00, 0.60, 0.28, 0.22, 0.25, 0.18, 0.12, 0.38, 0.32 }, //
            { 0.65, 0.60, 1.00, 0.32, 0.28, 0.30, 0.22, 0.18, 0.42, 0.38 }, //
            { 0.30, 0.28, 0.32, 1.00, 0.55, 0.50, 0.15, 0.10, 0.25, 0.22 }, //
            { 0.25, 0.22, 0.28, 0.55, 1.00, 0.48, 0.12, 0.08, 0.22, 0.20 }, //
            { 0.28, 0.25, 0.30, 0.50, 0.48, 1.00, 0.14, 0.10, 0.24, 0.21 }, //
            { 0.20, 0.18, 0.22, 0.15, 0.12, 0.14, 1.00, 0.45, 0.30, 0.28 }, //
            { 0.15, 0.12, 0.18, 0.10, 0.08, 0.10, 0.45, 1.00, 0.25, 0.22 }, //
            { 0.40, 0.38, 0.42, 0.25, 0.22, 0.24, 0.30, 0.25, 1.00, 0.60 }, //
            { 0.35, 0.32, 0.38, 0.22, 0.20, 0.21, 0.28, 0.22, 0.60, 1.00 } };

    static final Map<String, int[]> SECTORS = new LinkedHashMap<>();
    static {
        SECTORS.put("Technology", new int[] { 0, 1, 2 });
        SECTORS.put("Healthcare", new int[] { 3, 4, 5 });
        SECTORS.put("Energy", new int[] { 6, 7 });
        SECTORS.put("Finance", new int[] { 8, 9 });
    }

    static final double BUDGET = 1.0;
    static final double MIN_RETURN = 0.08;
    static final double MAX_SECTOR_ALLOCATION = 0.40;
    static final double MIN_INVESTMENT = 0.05;
    static final int MAX_ASSETS = 6;
    static final int TIME_LIMIT = 60;

    /**
     * Xpress controls that ojAlgo does not set itself are set with a configurator.
     */
    static class XpressControls extends SolverXpress.Configurator {

        @Override
        protected void configure(final XPRSprob problem, final Optimisation.Options options) {
            super.configure(problem, options); // time limit, gap, threads... from model.options
            problem.setIntControl(XPRSconstants.HEUREMPHASIS, 2); // aggressive primal heuristics
        }
    }

    public static void main(final String[] args) {

        System.out.println("============================================================");
        System.out.println("ojAlgo: MIQP Portfolio");
        System.out.println("  Features: QP + MIP + Solver Params");
        System.out.println("============================================================");

        // Covariance(i,j) = sigma_i * sigma_j * rho_ij
        MatrixR064 covariance = FinanceUtils.toCovariances(R064Store.FACTORY.column(VOLATILITIES), RawStore.wrap(CORRELATIONS));

        int n = ASSETS.length;

        // =====================================================================
        // MODEL SETUP
        // =====================================================================
        ExpressionsBasedModel model = new ExpressionsBasedModel();

        // Continuous: portfolio weights, and binary: whether to invest in each asset
        Variable[] w = new Variable[n];
        Variable[] y = new Variable[n];
        for (int i = 0; i < n; i++) {
            w[i] = model.newVariable("w_" + ASSETS[i]).lower(0).upper(1);
            y[i] = model.newVariable("y_" + ASSETS[i]).binary();
        }

        // Objective: minimize portfolio variance, w' * Covariance * w (quadratic)
        Expression variance = model.newExpression("Variance").weight(1);
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                variance.set(w[i], w[j], covariance.doubleValue(i, j));
            }
        }

        // Budget: fully invested
        Expression budget = model.newExpression("Budget").level(BUDGET);
        // Minimum return target
        Expression minReturn = model.newExpression("MinReturn").lower(MIN_RETURN);
        // Cardinality: invest in at most MAX_ASSETS assets
        Expression cardinality = model.newExpression("Cardinality").upper(MAX_ASSETS);
        for (int i = 0; i < n; i++) {
            budget.set(w[i], 1);
            minReturn.set(w[i], EXPECTED_RETURNS[i]);
            cardinality.set(y[i], 1);
        }

        // Sector diversification: max allocation per sector
        for (Map.Entry<String, int[]> sector : SECTORS.entrySet()) {
            Expression limit = model.newExpression("Sector_" + sector.getKey()).upper(MAX_SECTOR_ALLOCATION);
            for (int i : sector.getValue()) {
                limit.set(w[i], 1);
            }
        }

        // Linking: w[i] <= y[i], and w[i] >= MIN_INVESTMENT * y[i]
        for (int i = 0; i < n; i++) {
            model.newExpression("LinkUpper_" + ASSETS[i]).upper(0).set(w[i], 1).set(y[i], -1);
            model.newExpression("LinkLower_" + ASSETS[i]).lower(0).set(w[i], 1).set(y[i], -MIN_INVESTMENT);
        }

        // =====================================================================
        // SOLVER CONFIGURATION
        // =====================================================================
        ExpressionsBasedModel.addIntegration(SolverXpress.INTEGRATION); // solve with Xpress
        ExpressionsBasedModel.setConfigurator(new XpressControls());

        model.options.abort(CalendarDateUnit.SECOND.newDuration(TIME_LIMIT)); // Xpress MAXTIME
        model.options.integer(IntegerStrategy.DEFAULT.withGapTolerance(NumberContext.of(3, 8))); // MIPRELSTOP 1%

        System.out.println();
        System.out.println("[Solver Params]");
        System.out.println("  MAXTIME = " + TIME_LIMIT + "s");
        System.out.println("  MIPRELSTOP = 0.01 (1% gap)");
        System.out.println("  HEUREMPHASIS = 2 (aggressive)");

        // =====================================================================
        // SOLVE
        // =====================================================================
        System.out.println();
        System.out.println("[Solver] Using FICO Xpress via ojAlgo (ojalgo-xpress)");
        System.out.println("[Problem] MIQP: " + n + " continuous + " + n + " binary variables");

        Optimisation.Result result = model.minimise();

        System.out.println();
        System.out.println("[Result] State: " + result.getState());
        System.out.printf("[Result] Objective (Variance): %.6f%n", result.getValue());

        double[] weights = new double[n];
        for (int i = 0; i < n; i++) {
            weights[i] = w[i].getValue().doubleValue();
        }
        PortfolioOjAlgo.printSolution(weights, covariance, "ojAlgo + Xpress MIQP Solution");
    }

    static void printSolution(final double[] weights, final MatrixR064 covariance, final String title) {

        int n = weights.length;
        double portfolioReturn = 0.0;
        double portfolioVariance = 0.0;
        for (int i = 0; i < n; i++) {
            portfolioReturn += weights[i] * EXPECTED_RETURNS[i];
            for (int j = 0; j < n; j++) {
                portfolioVariance += weights[i] * covariance.doubleValue(i, j) * weights[j];
            }
        }
        double portfolioRisk = Math.sqrt(portfolioVariance);

        System.out.println();
        System.out.println("============================================================");
        System.out.println(title);
        System.out.println("============================================================");
        System.out.printf("%nExpected Return: %.2f%%%n", 100.0 * portfolioReturn);
        System.out.printf("Portfolio Risk (Std Dev): %.2f%%%n", 100.0 * portfolioRisk);
        System.out.printf("Sharpe Ratio (approx): %.3f%n", portfolioReturn / portfolioRisk);

        System.out.println();
        System.out.println("Asset Allocations:");
        int held = 0;
        for (Map.Entry<String, int[]> sector : SECTORS.entrySet()) {
            for (int i : sector.getValue()) {
                if (weights[i] > 1e-6) {
                    System.out.printf("  %-12s (%-10s): %6.2f%%%n", ASSETS[i], sector.getKey(), 100.0 * weights[i]);
                    held++;
                }
            }
        }

        System.out.println();
        System.out.println("Sector Allocations:");
        for (Map.Entry<String, int[]> sector : SECTORS.entrySet()) {
            double sectorWeight = 0.0;
            for (int i : sector.getValue()) {
                sectorWeight += weights[i];
            }
            if (sectorWeight > 1e-6) {
                System.out.printf("  %-12s: %6.2f%%%n", sector.getKey(), 100.0 * sectorWeight);
            }
        }

        System.out.println();
        System.out.println("Number of assets in portfolio: " + held);
    }
}
