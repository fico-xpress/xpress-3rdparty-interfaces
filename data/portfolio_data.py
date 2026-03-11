"""
Portfolio Optimization Problem Data

This module provides shared problem data for the Xpress Everywhere blog series
Part 2: Python Optimization Libraries.

Problem: Mean-Variance Portfolio Optimization with Cardinality Constraints
- 10 assets across 3 sectors
- Minimize portfolio variance (risk)
- Subject to: target return, budget, sector limits, cardinality

(c) 2026 Fair Isaac Corporation. All rights reserved.
"""

import numpy as np

# =============================================================================
# Asset Data
# =============================================================================

ASSETS = [
    "TECH_A", "TECH_B", "TECH_C",      # Technology sector (indices 0-2)
    "HEALTH_A", "HEALTH_B", "HEALTH_C", # Healthcare sector (indices 3-5)
    "ENERGY_A", "ENERGY_B",             # Energy sector (indices 6-7)
    "FINANCE_A", "FINANCE_B",           # Finance sector (indices 8-9)
]

N_ASSETS = len(ASSETS)

# Expected annual returns (%)
EXPECTED_RETURNS = np.array([
    0.12, 0.10, 0.14,   # Tech: higher returns, higher risk
    0.08, 0.07, 0.09,   # Healthcare: moderate returns
    0.11, 0.06,         # Energy: mixed returns
    0.09, 0.08,         # Finance: stable returns
])

# Sector assignments (for diversification constraints)
SECTORS = {
    "Technology": [0, 1, 2],
    "Healthcare": [3, 4, 5],
    "Energy": [6, 7],
    "Finance": [8, 9],
}

# Individual asset volatilities (standard deviations)
VOLATILITIES = np.array([
    0.25, 0.22, 0.30,   # Tech: high volatility
    0.15, 0.12, 0.18,   # Healthcare: low volatility
    0.28, 0.20,         # Energy: mixed volatility
    0.16, 0.14,         # Finance: moderate volatility
])

# Correlation matrix (symmetric, positive semi-definite)
CORRELATIONS = np.array([
    # TECH_A  TECH_B  TECH_C  HLTH_A  HLTH_B  HLTH_C  ENRG_A  ENRG_B  FIN_A   FIN_B
    [1.00,   0.70,   0.65,   0.30,   0.25,   0.28,   0.20,   0.15,   0.40,   0.35],  # TECH_A
    [0.70,   1.00,   0.60,   0.28,   0.22,   0.25,   0.18,   0.12,   0.38,   0.32],  # TECH_B
    [0.65,   0.60,   1.00,   0.32,   0.28,   0.30,   0.22,   0.18,   0.42,   0.38],  # TECH_C
    [0.30,   0.28,   0.32,   1.00,   0.55,   0.50,   0.15,   0.10,   0.25,   0.22],  # HEALTH_A
    [0.25,   0.22,   0.28,   0.55,   1.00,   0.48,   0.12,   0.08,   0.22,   0.20],  # HEALTH_B
    [0.28,   0.25,   0.30,   0.50,   0.48,   1.00,   0.14,   0.10,   0.24,   0.21],  # HEALTH_C
    [0.20,   0.18,   0.22,   0.15,   0.12,   0.14,   1.00,   0.45,   0.30,   0.28],  # ENERGY_A
    [0.15,   0.12,   0.18,   0.10,   0.08,   0.10,   0.45,   1.00,   0.25,   0.22],  # ENERGY_B
    [0.40,   0.38,   0.42,   0.25,   0.22,   0.24,   0.30,   0.25,   1.00,   0.60],  # FINANCE_A
    [0.35,   0.32,   0.38,   0.22,   0.20,   0.21,   0.28,   0.22,   0.60,   1.00],  # FINANCE_B
])

# Build covariance matrix from volatilities and correlations
# Cov(i,j) = sigma_i * sigma_j * rho_ij
COVARIANCE = np.outer(VOLATILITIES, VOLATILITIES) * CORRELATIONS


# =============================================================================
# Optimization Parameters
# =============================================================================

# Budget constraint (normalized to 1.0)
BUDGET = 1.0

# Minimum target return (8% annual)
MIN_RETURN = 0.08

# Maximum allocation per sector (40% of portfolio)
MAX_SECTOR_ALLOCATION = 0.40

# Cardinality constraint: minimum investment threshold
# If we invest in an asset, we must invest at least this fraction
MIN_INVESTMENT = 0.05

# Maximum number of assets in portfolio (for cardinality)
MAX_ASSETS = 6


# =============================================================================
# Solver Parameters
# =============================================================================

# Time limit in seconds
TIME_LIMIT = 60

# Work limit - alternative to TIMELIMIT for deterministic, machine-independent stopping
WORK_LIMIT = 1e9

# MIP relative gap tolerance (1%)
MIP_GAP = 0.01


# =============================================================================
# Utility Functions
# =============================================================================

def get_portfolio_stats(weights):
    """Calculate portfolio return and risk given weights."""
    weights = np.array(weights)
    portfolio_return = np.dot(weights, EXPECTED_RETURNS)
    portfolio_variance = np.dot(weights, np.dot(COVARIANCE, weights))
    portfolio_risk = np.sqrt(portfolio_variance)
    return portfolio_return, portfolio_risk


def print_solution(weights, title="Portfolio Solution"):
    """Print a formatted portfolio solution."""
    weights = np.array(weights)
    portfolio_return, portfolio_risk = get_portfolio_stats(weights)

    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"\nExpected Return: {portfolio_return:.2%}")
    print(f"Portfolio Risk (Std Dev): {portfolio_risk:.2%}")
    print(f"Sharpe Ratio (approx): {portfolio_return / portfolio_risk:.3f}")

    print(f"\nAsset Allocations:")
    for i, (asset, weight) in enumerate(zip(ASSETS, weights)):
        if weight > 1e-6:
            sector = [s for s, indices in SECTORS.items() if i in indices][0]
            print(f"  {asset:12s} ({sector:10s}): {weight:6.2%}")

    print(f"\nSector Allocations:")
    for sector, indices in SECTORS.items():
        sector_weight = sum(weights[i] for i in indices)
        if sector_weight > 1e-6:
            print(f"  {sector:12s}: {sector_weight:6.2%}")

    n_assets = sum(1 for w in weights if w > 1e-6)
    print(f"\nNumber of assets in portfolio: {n_assets}")


if __name__ == "__main__":
    # Verify covariance matrix is positive semi-definite
    eigenvalues = np.linalg.eigvalsh(COVARIANCE)
    print(f"Covariance matrix eigenvalues: min={eigenvalues.min():.6f}, max={eigenvalues.max():.6f}")
    print(f"Matrix is positive semi-definite: {eigenvalues.min() >= -1e-10}")

    # Example: equal-weight portfolio
    equal_weights = np.ones(N_ASSETS) / N_ASSETS
    print_solution(equal_weights, "Equal-Weight Portfolio")