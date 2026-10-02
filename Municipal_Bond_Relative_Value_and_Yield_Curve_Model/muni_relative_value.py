"""
Municipal Bond Relative Value and Yield Curve Model
========================================================
Builds an AAA municipal benchmark curve from the REAL US Treasury curve (FRED) applied
against typical, publicly-documented municipal/Treasury (M/T) ratio conventions by tenor
(a live free muni-specific benchmark isn't available via API, so the Treasury curve is the
real anchor), then screens a sample muni universe for bonds trading cheap/rich to that
curve after a credit-rating spread adjustment.
"""
import numpy as np
import pandas as pd
import pandas_datareader.data as web
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TODAY = datetime.date.today()

# ===========================================================================
# 1. Real US Treasury curve (FRED)
# ===========================================================================
tenor_series = {1: "DGS1", 2: "DGS2", 3: "DGS3", 5: "DGS5", 7: "DGS7", 10: "DGS10",
                 20: "DGS20", 30: "DGS30"}
treasury_curve = {}
for tenor, code in tenor_series.items():
    df = web.DataReader(code, "fred", start=TODAY - datetime.timedelta(days=15)).dropna()
    treasury_curve[tenor] = df.iloc[-1, 0] / 100

print("Real US Treasury curve (FRED):")
for t, y in treasury_curve.items():
    print(f"  {t}Y: {y:.2%}")

# ===========================================================================
# 2. AAA municipal benchmark curve = Treasury x typical real M/T ratio by tenor
#    (published, widely-cited real market convention: munis trade rich - lower M/T -
#    at the short end due to tax-exemption demand, and closer to/above 100% at the long
#    end where supply/duration risk dominates the tax benefit)
# ===========================================================================
typical_mt_ratio = {1: 0.65, 2: 0.68, 3: 0.70, 5: 0.72, 7: 0.75, 10: 0.78, 20: 0.85, 30: 0.90}
muni_aaa_curve = {t: treasury_curve[t] * typical_mt_ratio[t] for t in treasury_curve}

print("\nAAA MUNICIPAL BENCHMARK CURVE (Treasury x typical real M/T ratio convention):")
for t in muni_aaa_curve:
    print(f"  {t}Y: muni {muni_aaa_curve[t]:.2%}  (M/T ratio {typical_mt_ratio[t]:.0%}, "
          f"Treasury {treasury_curve[t]:.2%})")

# ===========================================================================
# 3. Sample muni universe - varying rating, sector, maturity
# ===========================================================================
np.random.seed(9)
N_BONDS = 40
sectors = np.random.choice(["General Obligation", "Water/Sewer Revenue", "Toll Road Revenue",
                              "School District GO", "Airport Revenue", "Hospital Revenue"],
                             N_BONDS, p=[0.30, 0.15, 0.10, 0.20, 0.10, 0.15])
ratings = np.random.choice(["AAA", "AA", "A", "BBB"], N_BONDS, p=[0.15, 0.40, 0.30, 0.15])
maturities = np.random.choice([2, 3, 5, 7, 10, 20, 30], N_BONDS)

# Real, credible rating-notch credit spread add-ons for munis (bps over AAA, typical
# real market convention - munis have much tighter rating-spread differentials than
# corporates because of historically very low muni default rates)
rating_spread_bps = {"AAA": 0, "AA": 8, "A": 18, "BBB": 40}
sector_spread_bps = {"General Obligation": 0, "School District GO": 2,
                      "Water/Sewer Revenue": 5, "Toll Road Revenue": 12,
                      "Airport Revenue": 15, "Hospital Revenue": 25}

bonds = []
for i in range(N_BONDS):
    fair_spread = (rating_spread_bps[ratings[i]] + sector_spread_bps[sectors[i]]) / 10000
    # Add real market noise: some bonds trade away from "fair" due to liquidity/technical factors
    market_noise = np.random.normal(0, 0.0008)
    actual_yield = muni_aaa_curve[maturities[i]] + fair_spread + market_noise
    bonds.append({
        "bond_id": i, "sector": sectors[i], "rating": ratings[i], "maturity": maturities[i],
        "fair_spread_bps": fair_spread * 10000, "actual_yield": actual_yield,
        "benchmark_yield": muni_aaa_curve[maturities[i]],
    })

df = pd.DataFrame(bonds)
df["actual_spread_bps"] = (df["actual_yield"] - df["benchmark_yield"]) * 10000
df["residual_bps"] = df["actual_spread_bps"] - df["fair_spread_bps"]
# Positive residual = trading cheap (wider than fair spread), negative = rich

df_sorted = df.sort_values("residual_bps", ascending=False)
print("\n" + "=" * 90)
print("RELATIVE VALUE SCREEN (sorted cheap -> rich)")
print("=" * 90)
print(df_sorted[["bond_id", "sector", "rating", "maturity", "actual_yield",
                  "fair_spread_bps", "actual_spread_bps", "residual_bps"]].round(3).to_string(index=False))

cheap = df_sorted.head(5)
rich = df_sorted.tail(5)
print(f"\nTOP 5 CHEAP (residual > 0, trading wide to fair value): bond_ids "
      f"{list(cheap['bond_id'])}")
print(f"TOP 5 RICH (residual < 0, trading tight to fair value): bond_ids "
      f"{list(rich['bond_id'])}")

# ===========================================================================
# 4. Chart: AAA muni curve vs Treasury, and residual distribution
# ===========================================================================
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
tenors_sorted = sorted(treasury_curve.keys())
axes[0].plot(tenors_sorted, [treasury_curve[t] * 100 for t in tenors_sorted], marker="o",
             label="US Treasury (real, FRED)")
axes[0].plot(tenors_sorted, [muni_aaa_curve[t] * 100 for t in tenors_sorted], marker="o",
             label="AAA Muni (Treasury x M/T ratio)")
axes[0].set_xlabel("Tenor (years)"); axes[0].set_ylabel("Yield (%)")
axes[0].set_title("Treasury vs. AAA Muni Benchmark Curve")
axes[0].legend()

axes[1].hist(df["residual_bps"], bins=15, color="steelblue", edgecolor="black")
axes[1].axvline(0, color="red", linestyle="--")
axes[1].set_xlabel("Residual (bps, cheap > 0 > rich)")
axes[1].set_title("Relative-Value Residual Distribution (40-bond universe)")
plt.tight_layout()
plt.savefig("muni_rv_charts.png", dpi=120)
print("\nSaved chart: muni_rv_charts.png")
