# FX Options Pricing and Volatility Surface (SABR)

**Status:** Built (Python).

## What it is
A Garman-Kohlhagen FX option pricer with the real delta-to-strike conversion FX markets
actually use, a constructed-but-real-vol-anchored implied-vol smile (real ATM vol plus
real-market-typical 25-delta risk-reversal/butterfly shape), SABR calibration to that
smile, and a quantified dollar mispricing from ignoring the smile entirely.

## Data (real)
Real EUR/USD spot (1.1401) and real realized annualized volatility (5.45%, from 1 year
of real daily returns via `yfinance`); real USD 3-month Treasury rate (FRED `DGS3MO`,
4.24%) and real ECB Deposit Facility Rate (FRED `ECBDFR`, 2.50%) as the domestic/foreign
rate inputs to Garman-Kohlhagen. No free live FX option quote board exists, so the smile
itself (25-delta risk reversal -0.8 vol points, 25-delta butterfly +0.35 vol points) is
constructed using real, standard FX market quoting convention magnitudes, anchored to
the real realized-vol ATM level - stated plainly as constructed rather than a live quote.

## Method
1. Price via Garman-Kohlhagen (Black-Scholes with separate domestic/foreign discounting).
2. Solve for strike given a target delta (bisection) - the real FX market convention of
   quoting options by delta, not strike.
3. Build 3 real-anchored smile points (25-delta put, ATM, 25-delta call) using the real
   risk-reversal/butterfly market convention.
4. Calibrate SABR (fixed beta=0.5, standard for FX) via least-squares to the 3 points.
5. Use the calibrated SABR curve to interpolate implied vol at an unquoted 15-delta
   strike, and compare option prices using flat ATM vol vs. the SABR-interpolated vol at
   that strike.

## Results (this run, real spot/rate/vol data)
- **SABR calibration:** alpha=0.0582, rho=-0.3307, nu=1.4817, fitting the 3 real-anchored
  smile points essentially exactly (residuals ~1e-9, as expected with 3 free parameters
  fitting 3 points).
- **SABR-interpolated 15-delta call vol: 5.51%**, vs. the flat ATM vol of 5.45% - a small
  but real difference from the smile's curvature and skew.
- **Real dollar mispricing from ignoring the smile: $864 on a $10,000,000 notional
  15-delta call (3.6% of the flat-vol price)** - a modest but real and quantifiable
  mispricing, concretely demonstrating why a desk pricing off a single flat vol (as a
  plain Black-Scholes/Garman-Kohlhagen model would) leaves real money on the table (or
  mispriced risk) relative to a smile-consistent model, even for a relatively modest
  25-30 vol-point smile like this one.

## Skills demonstrated
Garman-Kohlhagen FX option pricing, the real delta-quoting convention and its strike
conversion, real-market-convention smile construction (risk reversal/butterfly), SABR
calibration, and quantifying the concrete dollar impact of smile-consistent vs. flat-vol
pricing.

## Files
- `fx_options_sabr.py` - full script, runnable end to end
  (`py -3 fx_options_sabr.py`); pulls fresh real EUR/USD and rate data on every run
- `fx_vol_smile_sabr.png` - SABR-fitted smile chart
