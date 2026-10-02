# Rates Curve Trading and Carry-and-Roll Strategy Model

**Status:** Built (Python).

## What it is
Carry-and-roll analysis and DV01-neutral curve trade construction (2s10s steepener,
2s10s30s butterfly) on the real live US Treasury curve, with scenario-based P&L
attribution separating carry from curve-shape change.

## Data (real)
Real US Treasury yields across 7 tenors (FRED `DGS2` through `DGS30`), pulled live: 2Y
4.87%, 5Y 5.03%, 10Y 5.18%, 20Y 5.53%, 30Y 5.47% (as of 2026-09-26).

## Method
1. Approximate modified duration/DV01 per tenor from a standard quick par-bond proxy
   (duration ~ tenor / (1 + yield)).
2. **Carry-and-roll:** compute the yield pickup from rolling each outright position down
   the curve over a 3-month horizon (holding the curve shape fixed), translating the
   roll-down yield change into a price return via duration.
3. **2s10s steepener:** short the 10Y, long a DV01-matched notional of 2Y - the position
   that profits when the curve steepens (10Y yield rises more, or falls less, than 2Y).
4. **2s10s30s butterfly:** long the 10Y belly, short DV01-matched 2Y and 30Y wings.
5. Run both trades through 4 rate scenarios (parallel +50bp, parallel -50bp, steepening,
   flattening) and attribute total P&L into curve-shape P&L plus carry.

## A caught-and-fixed trade-construction error
An initial build had the steepener's legs reversed (long 10Y / short 2Y) - its own P&L
results immediately exposed the bug: that position **lost money when the curve
steepened and made money when it flattened**, meaning it was actually a flattener wearing
a steepener's label. Fixed by swapping which leg is long vs. short (short 10Y, long 2Y),
after which the P&L correctly flipped: profits under steepening, losses under flattening.
Catching this from the position's own P&L behavior, rather than trusting the label, is
itself the more important skill than getting the construction right on the first attempt.

## Results (this run, real Treasury curve)
- **Current 2s10s spread: +31.0bp** (real, positive - curve is not inverted at this pair
  of tenors right now).
- **2s10s30s butterfly spread: +2.0bp** (real).
- **Net carry on the DV01-neutral steepener: +$477,456 over 3 months** - and this is the
  standout finding: even though the curve is upward-sloping (2Y at 4.87% below 10Y at
  5.18%, which naively should mean a steepener that's short the higher-yielding 10Y and
  long the lower-yielding 2Y *costs* carry), **the DV01-neutral hedge ratio requires far
  more notional on the low-duration 2Y leg** ($49.9M vs. $10M on the 10Y leg), so the 2Y
  leg's yield income on that much larger notional actually outweighs the 10Y leg's
  funding cost. This is a genuinely useful, non-obvious real-world insight: **naive
  "curve slope tells you the carry sign" intuition can be wrong once you account for
  DV01-neutral notional weighting** - exactly the kind of nuance a rates strategist needs
  to get right before sizing a real trade.
- **Scenario P&L:** the steepener earns $857,756 total (curve P&L + carry) under the
  steepening scenario, and is roughly breakeven ($2,080) under the flattening scenario
  specifically because the large positive carry offsets most of the curve-shape loss -
  a real risk/reward asymmetry worth being able to explain (this trade has positive carry
  cushioning the "wrong way" scenario, not just upside in the "right way" scenario).

## Skills demonstrated
Real Treasury curve carry-and-roll methodology, DV01-neutral curve trade construction,
scenario-based P&L attribution, and - importantly - diagnosing a real trade-construction
error from its own P&L behavior and correcting both the mechanics and a related, initially
wrong intuition about carry direction.

## Files
- `rates_curve_trading.py` - full script, runnable end to end
  (`py -3 rates_curve_trading.py`); pulls the fresh real Treasury curve from FRED on every
  run
