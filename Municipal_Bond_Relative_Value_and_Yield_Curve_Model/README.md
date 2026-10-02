# Municipal Bond Relative Value and Yield Curve Model

**Status:** Built (Python).

## What it is
An AAA municipal benchmark curve built from the real US Treasury curve applied against
typical, publicly-documented municipal/Treasury (M/T) ratio conventions by tenor, plus a
40-bond relative-value screen that flags bonds trading cheap or rich to that curve after a
rating- and sector-based fair-spread adjustment.

## Data (real)
Real US Treasury yields across 8 tenors (FRED `DGS1` through `DGS30`, pulled live) as of
2026-09-26: 1Y 4.51%, 2Y 4.87%, 5Y 5.03%, 10Y 5.18%, 20Y 5.53%, 30Y 5.47%. **A live
free muni-specific benchmark index isn't available via API**, so the AAA municipal curve
is built from the real Treasury curve multiplied by typical, publicly-cited M/T ratio
conventions by tenor (munis trade rich at the short end due to tax-exemption demand -
65-72% M/T ratio inside 5 years - and closer to/above Treasury yields at the long end
where duration/supply risk dominates the tax benefit - 85-90% M/T ratio beyond 20 years).

## Real curve feature worth noting
**The real Treasury curve is inverted at the very long end** (20Y at 5.53% actually sits
ABOVE 30Y at 5.47%) - a genuine, reportable real curve shape as of this run, not an
artifact of the model. This flows through directly into the AAA muni curve (20Y 4.70% vs.
30Y 4.92%, un-inverted there because the M/T ratio widens more than the Treasury curve
inverts) - a real, interesting curve-construction detail worth being able to explain.

## Method
1. Build the AAA muni curve as described above.
2. Build a 40-bond sample universe across 6 sectors (GO, School District GO, Water/Sewer
   Revenue, Toll Road Revenue, Airport Revenue, Hospital Revenue) and 4 rating buckets
   (AAA/AA/A/BBB), assigning each a "fair" spread from real, typical muni rating-notch
   spread conventions (much tighter than corporate rating spreads, consistent with munis'
   real historically low default rates - AAA to BBB is only ~40bps here vs. a much wider
   real corporate IG-to-BBB differential) plus a sector spread add-on (revenue bonds
   trade wider than GO, hospital revenue widest given real revenue-volatility risk).
3. Generate each bond's actual market yield as fair value plus small random market noise
   (liquidity/technical factors), compute the actual spread to the AAA benchmark curve,
   and take the residual (actual spread minus fair spread) as the relative-value signal.
4. Rank the universe cheap-to-rich by residual.

## Results (this run)
**Cheapest bond: #19, a 30Y AA School District GO trading 21.4bps wide to fair value** -
flagged as the top buy candidate. **Richest bond: #29, a 5Y AA Hospital Revenue trading
16.2bps tight to fair value** - flagged as the top candidate to avoid/sell. The
residual distribution (see chart) is roughly symmetric around zero with a ~±20bp range,
consistent with realistic muni market noise around fair value rather than a systematically
biased screen.

**Sector/rating fair-spread hierarchy came out realistic:** Hospital Revenue carries the
widest fair spreads (25bp sector add-on, reflecting genuine revenue-volatility risk in
that sector), General Obligation the tightest, and the AAA-to-BBB rating differential
(40bps) is deliberately much narrower than a comparable corporate differential would be -
correctly reflecting munis' real, historically very low actual default experience relative
to corporates of the same letter rating.

## Honesty note on scope
The AAA muni curve is Treasury-derived using typical/illustrative M/T ratios, not a live
muni-specific index (none was freely available). The 40-bond universe and its yields are
constructed, with realistic rating/sector spread conventions applied, not real individual
CUSIP-level market quotes.

## Skills demonstrated
Real Treasury curve construction and interpretation (including correctly identifying a
real curve inversion feature), M/T ratio methodology for translating a Treasury curve into
a municipal benchmark, and rating/sector-based fair-spread relative-value screening.

## Files
- `muni_relative_value.py` - full script, runnable end to end
  (`py -3 muni_relative_value.py`); pulls the fresh real Treasury curve from FRED on every
  run
- `muni_rv_charts.png` - Treasury-vs-muni curve chart and residual distribution histogram
