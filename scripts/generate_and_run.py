"""Generate a constrained random portfolio CSV and run the ALM pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from example_pipeline import PROJECT_ROOT, load_config, load_or_generate_portfolio, run_pipeline
from src.data.generator import GENERATION_PROFILES


def parse_args() -> argparse.Namespace:
    """Parse generation-first workflow arguments."""

    parser = argparse.ArgumentParser(description="Generate a constrained portfolio CSV and run the ALM engine.")
    parser.add_argument("--profile", default="balanced", choices=GENERATION_PROFILES)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--output",
        default="data/portfolios/generated_portfolio.csv",
        help="CSV path for the generated portfolio.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(PROJECT_ROOT / "data" / "assumptions" / "base_assumptions.yaml")
    portfolio, output_path = load_or_generate_portfolio(
        config=config,
        project_root=PROJECT_ROOT,
        portfolio_path=Path(args.output),
        generate=True,
        profile=args.profile,
        seed=args.seed,
        generated_output=args.output,
    )
    run_pipeline(portfolio=portfolio, config=config, project_root=PROJECT_ROOT, portfolio_source=output_path)


if __name__ == "__main__":
    main()
