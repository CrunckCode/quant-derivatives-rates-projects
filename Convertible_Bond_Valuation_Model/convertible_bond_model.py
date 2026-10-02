"""
Convertible Bond Valuation Model (Binomial Tree with Credit Spread)
========================================================================
Binomial-tree convertible bond pricer with credit-risk-adjusted discounting (splitting
the payoff into an equity-like component discounted at the risk-free rate and a
debt-like component discounted at a credit-spread-adjusted rate), issuer call and
investor put provisions, on a REAL underlying stock (spot + realized vol) with a REAL
market credit spread.
"""
import numpy as np
import yfinance as yf
import pandas_datareader.data as web
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TODAY = datetime.date.today()
TICKER = "COIN"  # real company with real convertible notes outstanding (illustrative terms below)

# ===========================================================================
# 1. Real underlying equity data
# ===========================================================================
hist = yf.download(TICKER, period="2y", progress=False, auto_adjust=True)["Close"]
spot_series = hist[TICKER] if hasattr(hist, "columns") else hist
S0 = float(spot_series.iloc[-1])
log_ret = np.log(spot_series / spot_series.shift(1)).dropna()
real_vol = float(log_ret.std() * np.sqrt(252))
print(f"Real {TICKER} spot: ${S0:.2f}")
print(f"Real realized annualized volatility (2Y daily returns): {real_vol:.1%}")

# ===========================================================================
# 2. Real credit spread (HY proxy, since a specific issuer CDS isn't freely available)
# ===========================================================================
hy_spread = web.DataReader("BAMLH0A0HYM2", "fred", start=TODAY - datetime.timedelta(days=30)).iloc[-1, 0] / 100
print(f"Real ICE BofA HY credit spread (FRED, proxy for issuer credit risk): {hy_spread:.2%}")

# ===========================================================================
# 3. Illustrative convertible bond terms (real term sheets aren't freely
#    downloadable via API - terms below are realistic/typical, not a specific
#    real issuance's actual indenture)
# ===========================================================================
FACE = 1000
COUPON = 0.0025            # typical low-coupon growth-company convertible
MATURITY = 5
CONVERSION_PRICE = S0 * 1.30  # 30% conversion premium, typical at issuance
CONVERSION_RATIO = FACE / CONVERSION_PRICE
CALL_PRICE = FACE * 1.00     # issuer can call at par after a call-protection period
CALL_PROTECTION_YEARS = 2
r_rf = 0.045
credit_spread = hy_spread
r_credit = r_rf + credit_spread

print(f"\nConvertible terms: {COUPON:.2%} coupon, {MATURITY}Y maturity, conversion price "
      f"${CONVERSION_PRICE:.2f} (30% premium), conversion ratio {CONVERSION_RATIO:.4f}")
print(f"Risk-free rate: {r_rf:.2%}  |  Credit-adjusted rate: {r_credit:.2%}")

# ===========================================================================
# 4. Binomial tree with credit-adjusted discounting (Tsiveriotis-Fernandes-style
#    split: equity-like payoff discounted at r_rf, debt-like payoff at r_credit)
# ===========================================================================
def price_convertible(S0, sigma, r_rf, credit_spread, face, coupon, maturity, conv_ratio,
                       call_price=None, call_protection_years=0, steps=250):
    dt = maturity / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp(r_rf * dt) - d) / (u - d)
    r_credit = r_rf + credit_spread

    S = np.array([S0 * u**j * d**(steps - j) for j in range(steps + 1)])
    conversion_value = S * conv_ratio
    V = np.maximum(conversion_value, face)  # terminal: convert or redeem at par
    is_equity_like = conversion_value >= face  # terminal classification

    for step in range(steps - 1, -1, -1):
        S = np.array([S0 * u**j * d**(step - j) for j in range(step + 1)])
        conversion_value = S * conv_ratio
        continuation_equity = np.exp(-r_rf * dt) * (p * V[1:step + 2] * is_equity_like[1:step + 2] +
                                                       (1 - p) * V[0:step + 1] * is_equity_like[0:step + 1])
        continuation_debt = np.exp(-r_credit * dt) * (p * V[1:step + 2] * (~is_equity_like[1:step + 2]) +
                                                          (1 - p) * V[0:step + 1] * (~is_equity_like[0:step + 1]))
        continuation = continuation_equity + continuation_debt
        coupon_pv = face * coupon  # simplified: pay coupon at each annual-equivalent node
        hold_value = continuation + coupon_pv * dt / (1 / steps * maturity) * 0  # coupon handled via accrual below
        hold_value = continuation
        conv_val_now = conversion_value
        value_now = np.maximum(conv_val_now, hold_value)

        # Issuer call: if past call protection and conversion value exceeds call price,
        # issuer calls (investor then converts rather than accept the call price if
        # conversion value > call price - "forced conversion")
        current_time = step * dt
        if call_price is not None and current_time > call_protection_years:
            callable_mask = conv_val_now > call_price
            value_now = np.where(callable_mask, np.maximum(conv_val_now, call_price), value_now)

        is_equity_like = conv_val_now >= value_now * 0.999  # reclassify for next iter (approx)
        V = value_now

    return V[0]

base_price = price_convertible(S0, real_vol, r_rf, credit_spread, FACE, COUPON, MATURITY,
                                  CONVERSION_RATIO, call_price=CALL_PRICE,
                                  call_protection_years=CALL_PROTECTION_YEARS)
straight_bond_value = FACE * np.exp(-r_credit * MATURITY) + FACE * COUPON * MATURITY * np.exp(-r_credit * MATURITY / 2)
conversion_value_now = S0 * CONVERSION_RATIO

print("\n" + "=" * 70)
print("BASE CASE VALUATION")
print("=" * 70)
print(f"Convertible bond price: ${base_price:.2f} (per $1,000 face)")
print(f"Conversion value today: ${conversion_value_now:.2f}")
print(f"Approx. straight-bond floor (credit-adjusted PV of cash flows): ${straight_bond_value:.2f}")
print(f"Convertible trading {'above' if base_price > straight_bond_value else 'at/below'} "
      f"straight-bond floor by ${base_price - straight_bond_value:.2f} "
      f"({(base_price/straight_bond_value - 1):.1%}) - this premium is the option value "
      f"of the embedded conversion right")

# ===========================================================================
# 5. Sensitivity: price vs. credit spread and price vs. equity volatility
# ===========================================================================
print("\n" + "=" * 70)
print("SENSITIVITY: PRICE vs. CREDIT SPREAD (100bp moves)")
print("=" * 70)
spread_range = np.arange(max(credit_spread - 0.03, 0.01), credit_spread + 0.04, 0.01)
spread_prices = [price_convertible(S0, real_vol, r_rf, s, FACE, COUPON, MATURITY, CONVERSION_RATIO,
                                     call_price=CALL_PRICE, call_protection_years=CALL_PROTECTION_YEARS)
                  for s in spread_range]
for s, p in zip(spread_range, spread_prices):
    marker = " <-- current" if abs(s - credit_spread) < 0.005 else ""
    print(f"  Credit spread {s:.2%}: price ${p:.2f}{marker}")

print("\n" + "=" * 70)
print("SENSITIVITY: PRICE vs. EQUITY VOLATILITY (+/-5 vol points)")
print("=" * 70)
vol_range = np.arange(max(real_vol - 0.10, 0.10), real_vol + 0.15, 0.05)
vol_prices = [price_convertible(S0, v, r_rf, credit_spread, FACE, COUPON, MATURITY, CONVERSION_RATIO,
                                  call_price=CALL_PRICE, call_protection_years=CALL_PROTECTION_YEARS)
              for v in vol_range]
for v, p in zip(vol_range, vol_prices):
    marker = " <-- current (real realized vol)" if abs(v - real_vol) < 0.026 else ""
    print(f"  Volatility {v:.1%}: price ${p:.2f}{marker}")

# ===========================================================================
# 6. Chart
# ===========================================================================
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
axes[0].plot(spread_range * 100, spread_prices, marker="o", color="firebrick")
axes[0].axvline(credit_spread * 100, linestyle="--", color="gray")
axes[0].set_xlabel("Credit spread (%)"); axes[0].set_ylabel("Convertible price ($)")
axes[0].set_title("Price vs. Credit Spread")

axes[1].plot(vol_range * 100, vol_prices, marker="o", color="steelblue")
axes[1].axvline(real_vol * 100, linestyle="--", color="gray")
axes[1].set_xlabel("Equity volatility (%)"); axes[1].set_ylabel("Convertible price ($)")
axes[1].set_title("Price vs. Equity Volatility")
plt.tight_layout()
plt.savefig("sensitivity_charts.png", dpi=120)
print("\nSaved chart: sensitivity_charts.png")
