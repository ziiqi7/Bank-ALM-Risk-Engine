# bank-alm-risk-engine

`bank-alm-risk-engine` is a Python portfolio project for simplified banking-book ALM analysis. It is designed to be small enough to discuss in an interview, but structured enough to show how IRRBB, liquidity, stress testing, and treasury management actions can live in one coherent codebase.

## Project Motivation

Many ALM examples stop at passive measurement. This repository goes one step further:

- build a synthetic balance sheet
- load a stable CSV balance sheet or generate a constrained random one
- calculate IRRBB and liquidity metrics
- apply stress scenarios
- simulate deterministic treasury and management actions
- recompute the post-action risk profile

The result is not a production bank platform. It is a transparent research and portfolio implementation intended to demonstrate architecture, methodology choices, and trade-offs.

## What This Project Demonstrates

- A unified balance-sheet position schema reused across IRRBB, liquidity, stress, and treasury overlays
- Shared cashflow-based IRRBB design for both NII and EVE
- Clear separation between metric calculation and management action overlays
- Scenario-driven treasury funding cost feedback into stressed NII
- A practical example of how liquidity support can improve survival and LCR while worsening NII
- A codebase that stays readable without introducing unnecessary frameworks

## Current Scope

Included:

- Synthetic balance-sheet generation
- CSV-driven portfolio loading
- Constrained random portfolio generation
- Batch portfolio distribution analysis
- Repricing gap reporting
- 12M NII sensitivity
- EVE sensitivity
- Standard rate shocks
- Simplified LCR
- Simplified NSFR
- Contractual and behavioral cash-gap ladder
- Idiosyncratic, market-wide, and combined stress scenarios
- Rule-based management actions
- Simplified treasury overlay and contingency funding actions
- Post-action metric recomputation
- YAML-based assumptions
- Basic reporting tables and charts

Explicitly out of scope:

- Trading book functionality
- Derivative pricing or hedge valuation
- Full term-structure modeling
- Stochastic simulation or Monte Carlo
- Database integration
- Web dashboards, APIs, or deployment tooling
- Production-grade regulatory implementation

## Repository Layout

```text
bank-alm-risk-engine/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── assumptions/
│   │   └── base_assumptions.yaml
│   └── portfolios/
│       ├── base_portfolio.csv
│       ├── demo_balanced.csv
│       ├── demo_liquidity_tight.csv
│       └── demo_irrbb_heavy.csv
├── docs/
│   └── methodology.md
├── outputs/
│   ├── distributions/
│   └── reports/
├── scripts/
│   ├── example_pipeline.py
│   ├── generate_and_run.py
│   ├── generate_demo_cases.py
│   ├── generate_report.py
│   ├── run_demo_cases.py
│   └── run_distribution.py
├── src/
│   ├── config.py
│   ├── analysis/
│   ├── balance_sheet/
│   ├── data/
│   ├── irrbb/
│   ├── liquidity/
│   ├── reporting/
│   ├── stress/
│   └── treasury/
└── tests/
    ├── test_distribution.py
    ├── test_eve.py
    ├── test_lcr.py
    ├── test_nii.py
    ├── test_portfolio_inputs.py
    └── test_treasury.py
```

## Data Model

The core position schema lives in `src/balance_sheet/instruments.py`. Each position includes:

- `position_id`
- `product_type`
- `balance_side`
- `notional`
- `currency`
- `start_date`
- `maturity_date`
- `rate_type`
- `coupon_rate`
- `spread`
- `repricing_freq_months`
- `liquidity_category`
- `behavioral_category`
- `hqla_level`
- `asf_factor`
- `rsf_factor`
- `encumbered`
- `stress_spread_addon`

`contractual_rate` and `base_rate` are exposed as derived properties on the position object and are used by the shared cashflow-based IRRBB logic. Portfolios can now be loaded directly from CSV using this same schema.

The supported banking-book product set includes:

- Fixed mortgages
- Floating corporate loans
- Sovereign bonds
- Reserves/cash
- Retail NMDs
- Term deposits
- Interbank borrowing
- Equity

## Methodology Overview

### IRRBB

- Repricing gap buckets positions by next contractual or behavioral repricing horizon.
- 12M NII uses shared future cashflows over the next 12 months and shocks row-level applied rates where repricing occurs.
- Treasury funding costs can widen under stress through deterministic scenario-specific spread add-ons.
- EVE uses the same cashflow schedules with two modes:
  discount-only mode shocks discount rates only
  projected-cashflow mode keeps the same schedule but can also reprice floating cashflows

### Liquidity

- LCR uses unencumbered HQLA only.
- Repo cash proceeds are included in HQLA, but encumbered collateral is excluded from the numerator.
- NSFR uses position-level ASF and RSF factors.
- Cash-gap ladders support a simplified survival horizon view.

### Stress And Actions

- Stress scenarios apply runoff, haircut, inflow, and rate shocks.
- Management actions run in sequence and recompute stressed metrics after each step.
- Treasury overlays are modeled as balance-sheet transformations, not as abstract labels.

### Portfolio Inputs

- `data/portfolios/base_portfolio.csv` provides a stable example portfolio for repeatable runs.
- `data/portfolios/demo_balanced.csv` is the fixed balanced showcase case.
- `data/portfolios/demo_liquidity_tight.csv` is the fixed liquidity-stress showcase case.
- `data/portfolios/demo_irrbb_heavy.csv` is the fixed IRRBB-sensitive showcase case.
- A constrained random generator can create `balanced`, `irrbb_heavy`, and `liquidity_tight` portfolios with a deterministic seed.
- `scripts/generate_demo_cases.py` regenerates the three fixed demo-case CSVs from deterministic seeds.
- The current demo-case seeds are `41` for `balanced`, `36` for `liquidity_tight`, and `55` for `irrbb_heavy`.
- The legacy hard-coded synthetic builder is still available in code for backward compatibility, but the runnable workflow is now CSV-first.

### Distribution Analysis

- The project can run many constrained random portfolios and collect a distribution of outcomes by profile.
- This is an ensemble analysis over randomized balance-sheet shapes, not a Monte Carlo market simulation.
- It reuses the same IRRBB, liquidity, stress, and management-action engine for every generated portfolio.

## Design Boundaries

- Repo is modeled as secured funding with simple encumbrance exclusion, not a full collateral engine.
- Treasury funding cost feedback is deterministic and scenario-aware, not market-calibrated.
- The hedge placeholder is a labeled synthetic balance-sheet overlay, not an IRS or derivative valuation.
- EVE remains a simplified sensitivity view, even in projected-cashflow mode.

## Example Outputs

The example pipeline prints:

- Portfolio summary
- Repricing gap table
- NII sensitivity grid
- EVE sensitivity grid
- EVE mode comparison
- EVE attribution by product type
- LCR and NSFR summaries
- Cash-gap ladder
- Stress summary
- Combined-stress pre-action vs post-action comparison
- Management action summary

It also writes:

- `docs/repricing_gap.png`
- `docs/cash_gap.png`
- a generated PDF report under `outputs/reports/`

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the example pipeline:

```bash
python scripts/example_pipeline.py
```

The script bootstraps the repository root onto `sys.path` automatically, so it can also be run from outside the project directory by pointing Python at the script path directly.

Run the engine on the stable base CSV explicitly:

```bash
python scripts/example_pipeline.py --portfolio data/portfolios/base_portfolio.csv
```

Run the fixed demo cases:

```bash
python scripts/example_pipeline.py --portfolio data/portfolios/demo_balanced.csv
python scripts/example_pipeline.py --portfolio data/portfolios/demo_liquidity_tight.csv
python scripts/example_pipeline.py --portfolio data/portfolios/demo_irrbb_heavy.csv
```

Regenerate the fixed demo-case CSVs:

```bash
python scripts/generate_demo_cases.py
```

Run all three fixed demo cases in sequence:

```bash
python scripts/run_demo_cases.py
```

Generate PDF report:

```bash
python scripts/generate_report.py
```

Generate a constrained random portfolio and run the engine:

```bash
python scripts/generate_and_run.py --profile liquidity_tight --seed 42
```

Run batch distribution analysis:

```bash
python scripts/run_distribution.py --profile balanced --runs 50 --seed-start 1
```

Run the tests:

```bash
pytest
```

## Interview-Ready Talking Points

- Why a shared cashflow engine matters for keeping NII and EVE structurally consistent
- Why fixed demo-case CSVs make walkthroughs repeatable without depending on ad hoc random draws
- Why LCR should exclude encumbered HQLA after repo
- How treasury actions improve liquidity metrics while often worsening stressed NII
- Why EVE is presented as a sensitivity view rather than a full valuation engine
- How scenario-dependent funding spreads add realism without introducing heavy market infrastructure
- How profile-driven ensembles help study distribution of balance-sheet outcomes without claiming to model stochastic markets

## Known Limitations

- No amortization engine
- No stochastic rates or spreads
- No Monte Carlo market simulation; distribution analysis varies constrained balance-sheet inputs rather than market paths
- No production Basel treatment or legal-entity granularity
- No derivative pricing or full hedge effectiveness modeling
- No optimization layer for action selection

## Potential Future Extensions

- Multi-currency aggregation
- Richer behavioral deposit segmentation
- Planned asset-growth pipeline positions for action simulation
- More granular EVE decomposition and reporting exports
- Optional optimization of management action sequence under user-defined constraints
