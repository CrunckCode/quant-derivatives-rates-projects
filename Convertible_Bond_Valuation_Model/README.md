# Convertible Bond Valuation Model (Binomial Tree with Credit Spread)

**Status:** Built (Python).

## What it is
A binomial-tree convertible bond pricer using credit-risk-adjusted discounting
(Tsiveriotis-Fernandes-style: equity-like payoff paths discounted at the risk-free rate,
debt-like payoff paths discounted at a credit-spread-adjusted rate), with issuer call
provisions and call protection, on a real high-volatility underlying with a real market
credit spread.

## Data (real)
- **Underlying:** Coinbase (COIN) - real spot ($195.11) and real realized annualized
  volatility (78.2%, from 2 years of real daily returns via `yfinance`) - chosen
  deliberately as a real company with genuine convertible notes outstanding and real
  high volatility, so the vega/optionality dynamics are meaningfully large, not a toy
  low-vol example.
- **Credit spread:** real ICE BofA High Yield index (FRED `BAMLH0A0HYM2`, 2.80%) as a
  proxy for the issuer's credit spread (a specific single-name CDS/bond spread for COIN
  isn't freely available via API).
- **Bond terms** (coupon, maturity, conversion premium, call price/protection) are
  illustrative/typical for a growth-company convertible, not a specific real issuance's
  actual indenture, since real term sheets aren't freely downloadable.

## Method
1. Build a CRR binomial tree for the underlying at the real realized volatility.
2. At each node, classify the payoff as equity-like (conversion value >= hold value) or
   debt-like, and discount each classification's continuation value at its own rate
   (risk-free for equity-like, credit-adjusted for debt-like) - the actual mechanism that
   makes convertible pricing different from a plain option or a plain bond.
3. Apply issuer call: once past a 2-year call-protection period, if conversion value
   exceeds the call price, the issuer forces conversion (holder gets the greater of call
   price or conversion value, not the full option-adjusted holding value).
4. Run sensitivity to credit spread (+/-300bps around the real 2.80% level) and to equity
   volatility (+/-10 vol points around the real 78.2% realized level).

## Results (this run, real COIN/credit-spread data)
- **Convertible bond price: $1,049.39** (per $1,000 face) vs. **conversion value $769.23**
  and an **approximate credit-adjusted straight-bond floor of $704.61**.
- **The convertible trades 48.9% above its straight-bond floor** - this premium is
  entirely the option value of the embedded conversion right, and it's large specifically
  *because* COIN's real volatility (78.2%) is very high; the same structure on a low-vol
  utility-style issuer would show a much smaller premium.
- **Credit spread sensitivity:** price moves from $1,108 at a 1% spread down to $958 at a
  6% spread - a $150 (14%) price range across a 500bp spread move, showing meaningful but
  not overwhelming credit sensitivity (the equity optionality dominates the debt-like
  component's sensitivity to credit).
- **Volatility sensitivity:** price moves from $1,009 at 68.2% vol to $1,087 at 88.2% vol -
  monotonically increasing in vol as expected for any instrument with embedded optionality,
  confirming the model's vega sign is correct.

## Honesty note on scope
Bond terms (conversion premium, call schedule) are typical/illustrative rather than a
specific real issuance's actual terms, and the credit spread is an HY index-level proxy
rather than an issuer-specific CDS spread. The underlying equity data, its real volatility,
and the credit-spread level itself are real and live.

## Skills demonstrated
Binomial-tree convertible bond pricing with credit-risk-adjusted (split) discounting,
issuer call-provision modeling, and correctly-signed two-factor sensitivity analysis
(credit spread and equity volatility).

## Files
- `convertible_bond_model.py` - full script, runnable end to end
  (`py -3 convertible_bond_model.py`); pulls fresh COIN price history and FRED credit
  spread data on every run
- `sensitivity_charts.png` - price-vs-spread and price-vs-volatility charts
