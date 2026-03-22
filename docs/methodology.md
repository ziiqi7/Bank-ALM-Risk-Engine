# Methodology Notes

This repository implements a simplified banking-book ALM risk engine for portfolio and research use. The calculations are intentionally compact and transparent rather than regulatory-production complete.

## Portfolio Inputs

- The preferred workflow is CSV-driven: portfolio rows map directly into the shared `Position` schema.
- `data/portfolios/base_portfolio.csv` is the stable reference dataset for repeatable examples.
- `data/portfolios/demo_balanced.csv` is the fixed balanced showcase case selected from the `balanced` generator profile.
- `data/portfolios/demo_liquidity_tight.csv` is the fixed liquidity-stress showcase case selected from the `liquidity_tight` profile.
- `data/portfolios/demo_irrbb_heavy.csv` is the fixed IRRBB-sensitive showcase case selected from the `irrbb_heavy` profile.
- A constrained random generator can produce seeded portfolios for `balanced`, `irrbb_heavy`, and `liquidity_tight` profiles.
- `scripts/generate_demo_cases.py` regenerates those three demo-case CSVs from deterministic seeds so walkthroughs stay stable over time.
- The current fixed demo seeds are `balanced=41`, `liquidity_tight=36`, and `irrbb_heavy=55`, chosen from a small deterministic search to match the intended narratives.
- The legacy hard-coded synthetic builder remains in the codebase for backward compatibility, but it is no longer the primary runnable workflow.

## Batch Distribution Analysis

- The analysis layer can run many generated portfolios and collect run-level outcomes into a tidy results table.
- Aggregation is profile-based and reports summary statistics such as mean, median, min, max, p10, and p90.
- Action usage rates are summarized separately so the user can see how often repo, unsecured funding, term funding, or the hedge placeholder are triggered.
- This is not Monte Carlo market simulation. The randomness is in constrained balance-sheet composition, while rate shocks and stress scenarios remain deterministic.

## IRRBB

- Repricing gap assigns each rate-sensitive position to a next-repricing bucket.
- 12M NII sensitivity uses the shared cashflow engine and evaluates interest cashflows falling within the next 12 months.
- Floating-rate rows can reprice at row level, while fixed-rate contractual cashflows remain unchanged over the horizon in the simplified setup.
- Treasury funding costs in NII use deterministic scenario overlays so repo, unsecured interbank, and term funding can widen by different amounts under stress.
- EVE has two simplified modes:
  discount-only mode shocks discount rates while leaving projected cashflows unchanged; projected-cashflow mode keeps the same schedule but can also reprice floating cashflows.
- Both EVE modes remain sensitivity views rather than full valuation models.
- Standard shocks include parallel up/down, short up/down, steepener, and flattener.

## Liquidity

- LCR uses haircut-adjusted HQLA divided by net 30-day outflows, with a simplified inflow cap.
- NSFR uses position-level ASF and RSF factors defined directly on the portfolio schema.
- Cash-gap ladders combine contractual maturities with two behavioral overlays:
  retail NMD stability split and fixed-mortgage prepayment assumptions.

## Stress Testing

- Idiosyncratic, market-wide, and combined stresses apply rate, runoff, haircut, and inflow multipliers.
- The stress runner summarizes NII, EVE, LCR, NSFR, and the minimum cumulative cash gap.

## Management Actions

- A deterministic action engine can rerun stressed metrics after each balance-sheet action.
- The action sequence is:
  use HQLA buffer, repo level-1 HQLA, raise interbank funding, issue term funding, reduce planned loan growth if present, and add a lightweight hedge placeholder if EVE remains outside tolerance.
- Triggers are rule-based and use YAML-backed thresholds for LCR, NSFR, survival horizon, and EVE tolerance.

## Treasury Overlay

- Liquidation converts level-1 securities into reserves/cash one-for-one.
- Repo adds secured funding plus cash proceeds. The collateral remains on balance sheet, but the encumbered slice is excluded from freely available HQLA in LCR. This is a simple eligibility exclusion rather than a full collateral engine.
- Interbank funding adds a short-dated floating-rate liability and matching cash proceeds.
- Term funding adds a longer-dated fixed-rate liability and matching cash proceeds.
- The hedge placeholder is not derivative valuation. It is a clearly labeled synthetic position used only to show how treasury actions could alter EVE directionally.

## Deliberate Simplifications

- Portfolio generation is constrained and profile-based rather than market-calibrated or institution-specific.
- No derivative valuation, hedge pricing, or optimization solver.
- No term structure model, no stochastic spread process, and no full valuation engine for EVE.
- No production Basel calibration or full regulatory cap logic.
- No database, API, or dashboard layer.
