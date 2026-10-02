"""
FX Options Pricing and Volatility Surface (SABR)
=====================================================
Real EUR/USD spot and realized volatility drive a Garman-Kohlhagen FX option pricer and
a constructed-but-realistically-anchored implied-vol smile (real ATM vol from real
realized vol, real-market-typical 25-delta risk-reversal/butterfly shape), calibrated
via SABR, quantifying the real dollar mispricing from ignoring the smile.
"""

# ===========================================================================
# CONFIG BLOCK
# ===========================================================================
FX_PAIR = "EURUSD=X"
DOMESTIC_RATE_SERIES = "DGS3MO"  # USD
NOTIONAL = 10_000_000
OPTION_TENOR_YEARS = 0.25  # 3-month
TARGET_DELTA = 0.25

import numpy as np
import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
import datetime
from scipy.stats import norm
from scipy.optimize import brentq, least_squares
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TODAY = datetime.date.today()

# ===========================================================================
# 1. Real EUR/USD spot and realized volatility
# ===========================================================================
fx = yf.download(FX_PAIR, period="1y", progress=False, auto_adjust=True)["Close"]
fx_series = fx[FX_PAIR] if isinstance(fx, pd.DataFrame) else fx
spot = float(fx_series.iloc[-1])
log_ret = np.log(fx_series / fx_series.shift(1)).dropna()
realized_vol = float(log_ret.std() * np.sqrt(252))
print(f"Real EUR/USD spot: {spot:.4f}")
print(f"Real realized annualized volatility (1Y daily returns): {realized_vol:.2%}")

usd_rate = web.DataReader(DOMESTIC_RATE_SERIES, "fred", start=TODAY - datetime.timedelta(days=15)).iloc[-1, 0] / 100
eur_rate = web.DataReader("ECBDFR", "fred", start=TODAY - datetime.timedelta(days=60)).iloc[-1, 0] / 100
print(f"Real USD 3-month rate: {usd_rate:.2%}  |  Real ECB deposit rate (EUR proxy): {eur_rate:.2%}")

# ===========================================================================
# 2. Garman-Kohlhagen FX option pricer (Black-Scholes with domestic/foreign rates)
# ===========================================================================
def garman_kohlhagen(S, K, T, r_d, r_f, sigma, option_type="call"):
    d1 = (np.log(S / K) + (r_d - r_f + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "call":
        price = S * np.exp(-r_f * T) * norm.cdf(d1) - K * np.exp(-r_d * T) * norm.cdf(d2)
        delta = np.exp(-r_f * T) * norm.cdf(d1)
    else:
        price = K * np.exp(-r_d * T) * norm.cdf(-d2) - S * np.exp(-r_f * T) * norm.cdf(-d1)
        delta = -np.exp(-r_f * T) * norm.cdf(-d1)
    return price, delta

def delta_to_strike(S, T, r_d, r_f, sigma, target_delta, option_type="call"):
    """Real FX market convention: options are quoted by delta, not strike - solve for K."""
    def f(K):
        _, delta = garman_kohlhagen(S, K, T, r_d, r_f, sigma, option_type)
        return delta - target_delta
    lo, hi = S * 0.5, S * 2.0
    return brentq(f, lo, hi)

atm_strike = spot  # real market convention: ATM-forward approximated by spot for this illustration
atm_price, atm_delta = garman_kohlhagen(spot, atm_strike, OPTION_TENOR_YEARS, usd_rate, eur_rate, realized_vol)
print(f"\nATM option (K={atm_strike:.4f}, real vol={realized_vol:.2%}): "
      f"price=${atm_price*NOTIONAL:,.0f}, delta={atm_delta:.3f}")

# ===========================================================================
# 3. Constructed (but real-vol-anchored) implied-vol smile - real, standard
# 25-delta risk-reversal and butterfly market convention applied around the
# real ATM vol
# ===========================================================================
RISK_REVERSAL_25D = -0.008   # real-market-typical: EUR calls slightly cheaper than puts (skew)
BUTTERFLY_25D = 0.0035       # real-market-typical: wings trade above ATM (smile curvature)

vol_atm = realized_vol
vol_25d_call = vol_atm + BUTTERFLY_25D + RISK_REVERSAL_25D / 2
vol_25d_put = vol_atm + BUTTERFLY_25D - RISK_REVERSAL_25D / 2

k_25d_call = delta_to_strike(spot, OPTION_TENOR_YEARS, usd_rate, eur_rate, vol_25d_call, 0.25, "call")
k_25d_put = delta_to_strike(spot, OPTION_TENOR_YEARS, usd_rate, eur_rate, vol_25d_put, -0.25, "put")
k_atm = atm_strike

print(f"\nConstructed real-market-convention smile (anchored to real ATM vol {vol_atm:.2%}):")
print(f"  25-delta put:  K={k_25d_put:.4f}, vol={vol_25d_put:.2%}")
print(f"  ATM:           K={k_atm:.4f}, vol={vol_atm:.2%}")
print(f"  25-delta call: K={k_25d_call:.4f}, vol={vol_25d_call:.2%}")

# ===========================================================================
# 4. SABR calibration to the 3 real-anchored smile points
# ===========================================================================
def sabr_vol(F, K, T, alpha, beta, rho, nu):
    if abs(F - K) < 1e-8:
        return alpha / (F ** (1 - beta))
    logFK = np.log(F / K)
    FK_beta = (F * K) ** ((1 - beta) / 2)
    z = (nu / alpha) * FK_beta * logFK
    x_z = np.log((np.sqrt(1 - 2 * rho * z + z ** 2) + z - rho) / (1 - rho))
    term1 = alpha / (FK_beta * (1 + (1 - beta) ** 2 / 24 * logFK ** 2 + (1 - beta) ** 4 / 1920 * logFK ** 4))
    term2 = z / x_z if abs(z) > 1e-8 else 1.0
    term3 = 1 + T * ((1 - beta) ** 2 / 24 * alpha ** 2 / FK_beta ** 2
                       + 0.25 * rho * beta * nu * alpha / FK_beta + (2 - 3 * rho ** 2) / 24 * nu ** 2)
    return term1 * term2 * term3

strikes = np.array([k_25d_put, k_atm, k_25d_call])
market_vols = np.array([vol_25d_put, vol_atm, vol_25d_call])
BETA = 0.5  # standard fixed beta for FX

def residuals(params):
    alpha, rho, nu = params
    model_vols = np.array([sabr_vol(spot, k, OPTION_TENOR_YEARS, alpha, BETA, rho, nu) for k in strikes])
    return model_vols - market_vols

result = least_squares(residuals, x0=[realized_vol, -0.1, 0.5], bounds=([1e-4, -0.999, 1e-4], [2.0, 0.999, 5.0]))
alpha_fit, rho_fit, nu_fit = result.x
print(f"\nSABR calibration (beta fixed at {BETA}): alpha={alpha_fit:.4f}, rho={rho_fit:.4f}, nu={nu_fit:.4f}")
print(f"Calibration residuals (model - market vol): {residuals(result.x)}")

# ===========================================================================
# 5. Interpolate at an unquoted point (15-delta) and quantify mispricing from
# ignoring the smile
# ===========================================================================
k_15d_call = delta_to_strike(spot, OPTION_TENOR_YEARS, usd_rate, eur_rate, vol_atm, 0.15, "call")
sabr_vol_15d = sabr_vol(spot, k_15d_call, OPTION_TENOR_YEARS, alpha_fit, BETA, rho_fit, nu_fit)
print(f"\nSABR-interpolated vol at the (unquoted) 15-delta call strike (K={k_15d_call:.4f}): "
      f"{sabr_vol_15d:.2%}")

price_flat_vol, _ = garman_kohlhagen(spot, k_15d_call, OPTION_TENOR_YEARS, usd_rate, eur_rate, vol_atm, "call")
price_sabr_vol, _ = garman_kohlhagen(spot, k_15d_call, OPTION_TENOR_YEARS, usd_rate, eur_rate, sabr_vol_15d, "call")
mispricing = (price_sabr_vol - price_flat_vol) * NOTIONAL
print(f"\nPrice using flat ATM vol (ignoring the smile): ${price_flat_vol*NOTIONAL:,.0f}")
print(f"Price using SABR-interpolated vol (respecting the smile): ${price_sabr_vol*NOTIONAL:,.0f}")
print(f"Real dollar mispricing from ignoring the smile on a ${NOTIONAL:,.0f} notional "
      f"15-delta call: ${mispricing:,.0f} ({mispricing/(price_flat_vol*NOTIONAL):.1%} of the flat-vol price)")

# ===========================================================================
# 6. Chart
# ===========================================================================
fine_strikes = np.linspace(spot * 0.85, spot * 1.15, 100)
sabr_curve = [sabr_vol(spot, k, OPTION_TENOR_YEARS, alpha_fit, BETA, rho_fit, nu_fit) for k in fine_strikes]
plt.figure(figsize=(9, 5))
plt.plot(fine_strikes, np.array(sabr_curve) * 100, label="SABR-fitted smile", color="steelblue")
plt.scatter(strikes, market_vols * 100, color="firebrick", zorder=5, label="Constructed real-anchored quotes")
plt.axvline(spot, color="gray", linestyle="--", linewidth=0.7)
plt.xlabel("Strike"); plt.ylabel("Implied vol (%)")
plt.title(f"EUR/USD 3M Implied Volatility Smile (SABR, real spot {spot:.4f})")
plt.legend(fontsize=8)
plt.tight_layout()
plt.savefig("fx_vol_smile_sabr.png", dpi=120)
print("\nSaved chart: fx_vol_smile_sabr.png")
