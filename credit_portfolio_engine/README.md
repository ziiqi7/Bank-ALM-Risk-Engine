# Portfolio Credit Risk Engine

A modular Python project for migration-based portfolio credit risk modelling across loans, bonds, and off-balance-sheet exposures.

## Objective

This module extends the existing ALM repository with a more granular credit portfolio engine that is suitable for staged enhancement during CQF study.

The target end-state is a production-style research project with:

- unified exposure schema for loans, bonds, and off-balance-sheet items
- migration-based valuation under rating transitions
- synthetic portfolio generation for public demonstration
- independent and correlated Monte Carlo engines
- Gaussian copula / latent-factor architecture
- sector factors and obligor-level factor loading
- rating-threshold mapping from latent variables to migration states
- VaR / Expected Shortfall contribution analysis
- stress overlays on transition matrices, LGD, CCF, and curves

## Planned Build Sequence

### Phase 1 — foundation

- unified data schema
- synthetic portfolio loader / generator
- baseline transition-matrix engine
- instrument-specific valuation functions
- independent Monte Carlo simulation
- portfolio VaR / ES

### Phase 2 — portfolio dependence

- Gaussian copula engine
- one-factor latent variable mapping
- sector factor extension
- rating threshold calibration from transition matrices
- correlated migration simulation

### Phase 3 — analytics and attribution

- loss decomposition by instrument type / sector / rating bucket
- marginal and component contribution to VaR / ES
- scenario overlays and stress sweeps
- richer reporting and charts

## Package Layout

```text
credit_portfolio_engine/
├── README.md
├── requirements.txt
├── data/
│   └── synthetic/
├── notebooks/
├── scripts/
│   └── run_demo.py
└── src/
    ├── config.py
    ├── schema.py
    ├── synthetic_data.py
    ├── transitions.py
    ├── valuation.py
    ├── simulation.py
    ├── correlation.py
    ├── metrics.py
    └── stress.py
```

## Design Principles

- No company data in the public project
- Reproducible synthetic portfolios
- Clear separation between exposure modelling, transition generation, valuation, and risk aggregation
- Incremental path from simple independent simulation to richer portfolio-credit dependence modelling
- Architecture first, feature accumulation second

## Immediate Next Steps

1. build the shared exposure schema
2. generate a synthetic public portfolio
3. implement baseline independent Monte Carlo
4. add Gaussian copula with rating-threshold mapping
5. layer sector factors and attribution analytics
