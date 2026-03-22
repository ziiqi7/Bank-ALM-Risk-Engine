"""Run all fixed demo-case portfolios through the shared example pipeline."""

from __future__ import annotations

from pathlib import Path

from example_pipeline import PROJECT_ROOT, load_config, load_or_generate_portfolio, run_pipeline

DEMO_CASES = (
    ("balanced", "data/portfolios/demo_balanced.csv"),
    ("liquidity_tight", "data/portfolios/demo_liquidity_tight.csv"),
    ("irrbb_heavy", "data/portfolios/demo_irrbb_heavy.csv"),
)


def main() -> None:
    """Run the three fixed demo portfolios sequentially."""

    config = load_config(PROJECT_ROOT / "data" / "assumptions" / "base_assumptions.yaml")

    for case_name, portfolio_path in DEMO_CASES:
        print(f"\n=== DEMO CASE: {case_name} ===")
        portfolio, resolved_path = load_or_generate_portfolio(
            config=config,
            project_root=PROJECT_ROOT,
            portfolio_path=Path(portfolio_path),
            generate=False,
        )
        run_pipeline(
            portfolio=portfolio,
            config=config,
            project_root=PROJECT_ROOT,
            portfolio_source=resolved_path,
        )


if __name__ == "__main__":
    main()
