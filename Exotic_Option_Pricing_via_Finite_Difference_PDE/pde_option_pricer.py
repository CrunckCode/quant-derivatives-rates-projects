"""
Exotic Option Pricing via Finite-Difference PDE (Crank-Nicolson)
=====================================================================
Solves the Black-Scholes PDE via Crank-Nicolson finite differences on a real AAPL option
(real spot, real market-quoted implied vol from the live option chain), validates against
the closed-form Black-Scholes price for a European option, then extends to American
(early-exercise) and barrier (knock-out) variants, with Greeks via grid finite-differences.
"""
import numpy as np
import yfinance as yf
import pandas as pd
from scipy.stats import norm
from scipy.linalg import solve_banded

# ===========================================================================
# 1. Real AAPL spot + real market-quoted implied vol (same discipline as the
#    FRTB project - pull the live option chain rather than assuming a vol)
# ===========================================================================
aapl = yf.Ticker("AAPL")
spot = float(aapl.history(period="1d")["Close"].iloc[-1])
expiries = aapl.options
target_days = 45
expiry = min(expiries, key=lambda e: abs((pd.Timestamp(e) - pd.Timestamp.today()).days - target_days))
chain = aapl.option_chain(expiry).calls
chain["dist"] = (chain["strike"] - spot).abs()
atm = chain.sort_values("dist").iloc[0]
K = float(atm["strike"])
sigma = float(atm["impliedVolatility"])
T = (pd.Timestamp(expiry) - pd.Timestamp.today()).days / 365
r = 0.045
print(f"Real AAPL spot: ${spot:.2f}")
print(f"Real market option: strike ${K:.2f}, expiry {expiry}, real market IV = {sigma:.1%}, "
      f"T={T:.3f} years, r={r:.2%}")

# ===========================================================================
# 2. Crank-Nicolson finite-difference PDE solver
# ===========================================================================
def crank_nicolson_price(S0, K, T, r, sigma, option_type="call", exercise="european",
                          barrier=None, barrier_type=None, M=400, N=2000, S_max_mult=4):
    """
    M = number of price grid steps, N = number of time steps.
    exercise: 'european' or 'american'
    barrier: barrier level (for 'up-out' or 'down-in' style knock-out), None if vanilla
    """
    S_max = S_max_mult * K
    dS = S_max / M
    dt = T / N
    S_grid = np.linspace(0, S_max, M + 1)

    if option_type == "call":
        payoff = np.maximum(S_grid - K, 0)
    else:
        payoff = np.maximum(K - S_grid, 0)

    if barrier is not None and barrier_type == "up-out":
        payoff = np.where(S_grid >= barrier, 0, payoff)

    V = payoff.copy()

    i = np.arange(1, M)
    alpha = 0.25 * dt * (sigma**2 * i**2 - r * i)
    beta = -0.5 * dt * (sigma**2 * i**2 + r)
    gamma = 0.25 * dt * (sigma**2 * i**2 + r * i)

    # Tridiagonal matrices M1 (implicit, LHS) and M2 (explicit, RHS) for Crank-Nicolson
    lower_M1 = -alpha
    diag_M1 = 1 - beta
    upper_M1 = -gamma
    lower_M2 = alpha
    diag_M2 = 1 + beta
    upper_M2 = gamma

    for n in range(N):
        rhs = np.zeros(M - 1)
        rhs[0] = lower_M2[0] * V[0] + diag_M2[0] * V[1] + upper_M2[0] * V[2]
        rhs[-1] = lower_M2[-1] * V[-2] + diag_M2[-1] * V[-1] + upper_M2[-1] * V[-1]  # V[M] boundary approx
        for k in range(1, M - 2):
            rhs[k] = lower_M2[k] * V[k] + diag_M2[k] * V[k + 1] + upper_M2[k] * V[k + 2]

        ab = np.zeros((3, M - 1))
        ab[0, 1:] = upper_M1[:-1]
        ab[1, :] = diag_M1
        ab[2, :-1] = lower_M1[1:]
        V_inner = solve_banded((1, 1), ab, rhs)

        V_new = V.copy()
        V_new[1:M] = V_inner
        if option_type == "call":
            V_new[0] = 0
            V_new[M] = S_max - K * np.exp(-r * (n + 1) * dt)
        else:
            V_new[0] = K * np.exp(-r * (n + 1) * dt)
            V_new[M] = 0

        if exercise == "american":
            V_new = np.maximum(V_new, payoff)

        if barrier is not None and barrier_type == "up-out":
            V_new = np.where(S_grid >= barrier, 0, V_new)

        V = V_new

    price = np.interp(S0, S_grid, V)
    # Greeks via grid finite differences around S0
    idx = np.searchsorted(S_grid, S0)
    idx = np.clip(idx, 1, M - 1)
    delta = (V[idx + 1] - V[idx - 1]) / (2 * dS)
    gamma_greek = (V[idx + 1] - 2 * V[idx] + V[idx - 1]) / (dS ** 2)
    return price, delta, gamma_greek

def bs_price(S0, K, T, r, sigma, option_type="call"):
    d1 = (np.log(S0 / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        return S0 * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S0 * norm.cdf(-d1)

# ===========================================================================
# 3. Validate: European call, PDE vs. closed-form Black-Scholes
# ===========================================================================
print("\n" + "=" * 70)
print("VALIDATION: European Call - PDE vs. closed-form Black-Scholes")
print("=" * 70)
euro_pde_price, euro_delta, euro_gamma = crank_nicolson_price(
    spot, K, T, r, sigma, option_type="call", exercise="european")
euro_bs_price = bs_price(spot, K, T, r, sigma, option_type="call")
d1 = (np.log(spot / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
bs_delta = norm.cdf(d1)
diff_bps = (euro_pde_price / euro_bs_price - 1) * 10000
print(f"PDE (Crank-Nicolson) price: ${euro_pde_price:.4f}")
print(f"Closed-form Black-Scholes price: ${euro_bs_price:.4f}")
print(f"Difference: {diff_bps:.1f} bps")
print(f"PDE delta: {euro_delta:.4f}  |  Closed-form delta: {bs_delta:.4f}")

# ===========================================================================
# 4. American option (early-exercise premium)
# ===========================================================================
print("\n" + "=" * 70)
print("AMERICAN OPTION (early-exercise premium)")
print("=" * 70)
amer_price, amer_delta, amer_gamma = crank_nicolson_price(
    spot, K, T, r, sigma, option_type="put", exercise="american")
euro_put_pde, _, _ = crank_nicolson_price(spot, K, T, r, sigma, option_type="put", exercise="european")
euro_put_bs = bs_price(spot, K, T, r, sigma, option_type="put")
early_ex_premium = amer_price - euro_put_pde
print(f"American put (PDE): ${amer_price:.4f}")
print(f"European put (PDE): ${euro_put_pde:.4f}  |  European put (closed-form): ${euro_put_bs:.4f}")
print(f"Early-exercise premium: ${early_ex_premium:.4f} "
      f"({early_ex_premium/euro_put_pde:.1%} of the European put value)")

# ===========================================================================
# 5. Barrier option (up-and-out call)
# ===========================================================================
print("\n" + "=" * 70)
print("BARRIER OPTION (up-and-out call)")
print("=" * 70)
barrier_level = spot * 1.15
barrier_price, barrier_delta, barrier_gamma = crank_nicolson_price(
    spot, K, T, r, sigma, option_type="call", exercise="european",
    barrier=barrier_level, barrier_type="up-out")
barrier_discount = 1 - barrier_price / euro_pde_price
print(f"Barrier level (up-and-out, 15% above spot): ${barrier_level:.2f}")
print(f"Vanilla European call: ${euro_pde_price:.4f}")
print(f"Up-and-out barrier call: ${barrier_price:.4f}")
print(f"Barrier discount vs. vanilla: {barrier_discount:.1%}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"{'Instrument':<30}{'Price':>10}{'Delta':>10}{'Gamma':>10}")
print(f"{'European call (PDE)':<30}${euro_pde_price:>9.4f}{euro_delta:>10.4f}{euro_gamma:>10.5f}")
print(f"{'American put (PDE)':<30}${amer_price:>9.4f}{amer_delta:>10.4f}{amer_gamma:>10.5f}")
print(f"{'Up-and-out barrier call':<30}${barrier_price:>9.4f}{barrier_delta:>10.4f}{barrier_gamma:>10.5f}")
