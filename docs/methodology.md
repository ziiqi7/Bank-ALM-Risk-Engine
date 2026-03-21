# Methodology Notes

This repository implements a simplified banking-book ALM risk engine for portfolio and research use. The calculations are intentionally compact and transparent rather than regulatory-production complete.

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

- No derivative valuation, hedge pricing, or optimization solver.
- No term structure model, no stochastic spread process, and no full valuation engine for EVE.
- No production Basel calibration or full regulatory cap logic.
- No database, API, or dashboard layer.
