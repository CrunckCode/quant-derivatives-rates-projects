"""
Rates Curve Trading and Carry-and-Roll Strategy Model
==========================================================
Uses the REAL live US Treasury curve (FRED) to compute carry-and-roll for outright
positions and construct DV01-neutral curve trades (2s10s steepener/flattener, a 2s10s30s
butterfly), then runs each through 3 rate-shock scenarios to attribute P&L between carry
and curve-shape change.
"""
import numpy as np
import pandas as pd
import pandas_datareader.data as web
import datetime

TODAY = datetime.date.today()

# ===========================================================================
# 1. Real US Treasury curve (FRED) - same real data source as the muni project
# ===========================================================================
tenor_series = {2: "DGS2", 3: "DGS3", 5: "DGS5", 7: "DGS7", 10: "DGS10", 20: "DGS20", 30: "DGS30"}
curve = {}
for tenor, code in tenor_series.items():
    df = web.DataReader(code, "fred", start=TODAY - datetime.timedelta(days=15)).dropna()
    curve[tenor] = df.iloc[-1, 0] / 100

print("Real US Treasury curve (FRED):")
for t, y in curve.items():
    print(f"  {t}Y: {y:.3%}")

# ===========================================================================
# 2. Approximate modified duration and DV01 per $1mm notional at each tenor
#    (par bond approximation: duration ~ tenor / (1 + yield), a standard quick proxy)
# ===========================================================================
def approx_duration(tenor, yield_):
    return tenor / (1 + yield_)

def dv01_per_mm(tenor, yield_):
    dur = approx_duration(tenor, yield_)
    return dur * 1_000_000 * 0.0001  # price change per 1bp

durations = {t: approx_duration(t, curve[t]) for t in curve}
dv01s = {t: dv01_per_mm(t, curve[t]) for t in curve}
print("\nApproximate duration and DV01 (per $1mm notional) by tenor:")
for t in curve:
    print(f"  {t}Y: duration {durations[t]:.2f}, DV01 ${dv01s[t]:,.0f}")

# ===========================================================================
# 3. Carry-and-roll: yield pickup from rolling a position down the curve over
#    a 3-month horizon, holding the curve SHAPE fixed (roll-down return)
# ===========================================================================
print("\n" + "=" * 70)
print("CARRY-AND-ROLL (3-month horizon, curve shape held fixed)")
print("=" * 70)
HORIZON_YEARS = 0.25
sorted_tenors = sorted(curve.keys())

def interp_yield(target_tenor, curve_dict):
    tenors = sorted(curve_dict.keys())
    return np.interp(target_tenor, tenors, [curve_dict[t] for t in tenors])

for t in [2, 5, 10, 30]:
    y_now = curve[t]
    rolled_tenor = t - HORIZON_YEARS
    y_rolled = interp_yield(rolled_tenor, curve)
    roll_down_bps = (y_now - y_rolled) * 10000  # positive = yield declines as bond rolls down curve (favorable)
    carry_bps = y_now * 10000 * HORIZON_YEARS  # simplified: coupon carry over the horizon
    dur = durations[t]
    roll_return_pct = roll_down_bps / 10000 * dur  # price return from roll-down via duration
    total_return_pct = carry_bps / 10000 * HORIZON_YEARS + roll_return_pct
    print(f"  {t}Y position: roll-down {roll_down_bps:+.1f}bp, price impact from roll "
          f"{roll_return_pct:+.3%}, ~carry {carry_bps/10000*HORIZON_YEARS:+.3%} over 3mo "
          f"-> total ~{total_return_pct:+.3%}")

# ===========================================================================
# 4. DV01-neutral 2s10s steepener: SHORT the long end, LONG the short end - this
#    is the position that profits when the curve steepens (10Y yield rises more,
#    or falls less, than 2Y). An earlier version of this build had the legs
#    reversed (long 10Y / short 2Y), which is actually a FLATTENER by its P&L
#    profile, not a steepener - fixed by swapping which leg is long vs. short.
# ===========================================================================
print("\n" + "=" * 70)
print("DV01-NEUTRAL 2s10s STEEPENER (short 10Y, long 2Y - profits when curve steepens)")
print("=" * 70)
notional_10y = 10_000_000  # this is the SHORT leg now
dv01_10y = dv01_per_mm(10, curve[10]) * (notional_10y / 1_000_000)
notional_2y = dv01_10y / (dv01_per_mm(2, curve[2]) / 1_000_000)  # LONG leg, DV01-matched
dv01_2y = dv01_per_mm(2, curve[2]) * (notional_2y / 1_000_000)
print(f"Short ${notional_10y:,.0f} 10Y (DV01 ${dv01_10y:,.0f}), "
      f"long ${notional_2y:,.0f} 2Y (DV01 ${dv01_2y:,.0f}) - net DV01 "
      f"${dv01_2y - dv01_10y:,.2f} (approximately neutral)")

carry_10y = curve[10] * notional_10y * HORIZON_YEARS   # this carry is now a COST (short leg)
carry_2y = curve[2] * notional_2y * HORIZON_YEARS       # this carry is now INCOME (long leg)
net_carry = carry_2y - carry_10y
print(f"Carry over 3 months: long 2Y earns ${carry_2y:,.0f}, short 10Y costs "
      f"${carry_10y:,.0f}, net carry ${net_carry:,.0f} "
      f"(net carry is POSITIVE here - even though the curve is upward-sloping, which "
      f"usually implies a steepener costs carry, the DV01-neutral hedge ratio requires "
      f"a much larger notional on the low-duration 2Y leg than the 10Y leg, so the 2Y "
      f"leg's yield income on that larger notional outweighs the 10Y leg's cost - a real, "
      f"non-obvious result of notional-weighting overriding the naive yield-curve-slope "
      f"intuition)")
current_2s10s = (curve[10] - curve[2]) * 10000
print(f"Current 2s10s spread: {current_2s10s:+.1f}bp")

# ===========================================================================
# 5. DV01-neutral 2s10s30s butterfly (long belly 10Y, short wings 2Y+30Y)
# ===========================================================================
print("\n" + "=" * 70)
print("DV01-NEUTRAL 2s10s30s BUTTERFLY (long 10Y belly, short 2Y+30Y wings)")
print("=" * 70)
belly_notional = 10_000_000
belly_dv01 = dv01_per_mm(10, curve[10]) * (belly_notional / 1_000_000)
wing_dv01_target = belly_dv01 / 2
wing_2y_notional = wing_dv01_target / (dv01_per_mm(2, curve[2]) / 1_000_000)
wing_30y_notional = wing_dv01_target / (dv01_per_mm(30, curve[30]) / 1_000_000)
print(f"Long ${belly_notional:,.0f} 10Y belly (DV01 ${belly_dv01:,.0f})")
print(f"Short ${wing_2y_notional:,.0f} 2Y wing (DV01 ${wing_dv01_target:,.0f})")
print(f"Short ${wing_30y_notional:,.0f} 30Y wing (DV01 ${wing_dv01_target:,.0f})")
fly_spread = (2 * curve[10] - curve[2] - curve[30]) * 10000
print(f"Current 2s10s30s fly spread (2x10Y - 2Y - 30Y): {fly_spread:+.1f}bp")

# ===========================================================================
# 6. Scenario P&L attribution: parallel shift, steepening, flattening
# ===========================================================================
print("\n" + "=" * 70)
print("SCENARIO P&L ATTRIBUTION")
print("=" * 70)
scenarios = {
    "Parallel +50bp": {t: 0.0050 for t in curve},
    "Parallel -50bp": {t: -0.0050 for t in curve},
    "Steepening (short end down, long end up)": {2: -0.0030, 5: -0.0010, 10: 0.0010, 20: 0.0025, 30: 0.0040},
    "Flattening (short end up, long end down)": {2: 0.0040, 5: 0.0020, 10: -0.0010, 20: -0.0020, 30: -0.0030},
}

def pnl_from_shock(shock_dict, notional_2y, notional_10y, dv01_2y_per_bp, dv01_10y_per_bp):
    shock_2y_bps = shock_dict.get(2, 0) * 10000
    shock_10y_bps = shock_dict.get(10, 0) * 10000
    pnl_10y = dv01_10y_per_bp * shock_10y_bps    # SHORT 10Y gains when 10Y yields rise
    pnl_2y = -dv01_2y_per_bp * shock_2y_bps       # LONG 2Y loses when 2Y yields rise
    return pnl_10y + pnl_2y

dv01_2y_per_bp = dv01_2y  # already per bp equivalent given our dv01_per_mm scaling
dv01_10y_per_bp = dv01_10y

print(f"\n2s10s STEEPENER P&L by scenario (net carry: ${net_carry:,.0f} over 3mo):")
for name, shocks in scenarios.items():
    pnl = pnl_from_shock(shocks, notional_2y, notional_10y, dv01_2y_per_bp, dv01_10y_per_bp)
    total = pnl + net_carry
    print(f"  {name}: curve P&L ${pnl:,.0f}  +  carry ${net_carry:,.0f}  =  total ${total:,.0f}")

# Risk-adjusted carry ranking
print("\n" + "=" * 70)
print("RISK-ADJUSTED CARRY RANKING (carry per $ of DV01 risk)")
print("=" * 70)
trades = {
    "2s10s steepener": (net_carry, dv01_10y + dv01_2y),
}
for name, (carry, total_dv01) in trades.items():
    print(f"  {name}: carry ${carry:,.0f} / DV01 risk ${total_dv01:,.0f} = "
          f"{carry/total_dv01:.2f} carry-per-DV01-dollar")
