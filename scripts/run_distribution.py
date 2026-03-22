"""Run batch distribution analysis over constrained random portfolios."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import pandas as pd


def _bootstrap_project_root() -> Path:
    """Add the repository root to ``sys.path`` from this script's location."""

    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    os.environ.setdefault("MPLCONFIGDIR", str(project_root / ".mpl-cache"))
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from src.analysis.aggregation import action_frequency_by_profile, save_distribution_charts, summarize_ensemble_results
from src.analysis.ensemble import run_portfolio_ensemble
from src.config import load_config
from src.data.generator import GENERATION_PROFILES


def parse_args() -> argparse.Namespace:
    """Parse distribution-run CLI arguments."""

    parser = argparse.ArgumentParser(description="Run batch ALM distribution analysis by profile.")
    parser.add_argument("--profile", default="balanced", choices=GENERATION_PROFILES)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        default="outputs/distributions",
        help="Directory for run-level CSVs, summary CSVs, and charts.",
    )
    return parser.parse_args()


def _print_title(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_table(table: pd.DataFrame) -> None:
    print(table.to_string(index=False, float_format=lambda value: f"{value:,.3f}"))


def main() -> None:
    args = parse_args()
    config = load_config(PROJECT_ROOT / "data" / "assumptions" / "base_assumptions.yaml")

    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    run_level_path = output_dir / f"{args.profile}_run_level_results.csv"
    summary_path = output_dir / f"{args.profile}_profile_summary.csv"
    action_path = output_dir / f"{args.profile}_action_frequency.csv"

    results = run_portfolio_ensemble(
        config=config,
        profile=args.profile,
        runs=args.runs,
        seed_start=args.seed_start,
        output_path=run_level_path,
    )
    summary = summarize_ensemble_results(results)
    action_summary = action_frequency_by_profile(results)
    charts = save_distribution_charts(results, output_dir)

    summary.to_csv(summary_path, index=False)
    action_summary.to_csv(action_path, index=False)

    compact_metrics = summary[
        [
            "profile",
            "delta_nii_parallel_up_mean",
            "delta_eve_parallel_up_mean",
            "stressed_lcr_mean",
            "post_action_lcr_mean",
            "post_action_delta_nii_mean",
        ]
    ]

    _print_title("Distribution Run")
    print(f"profile: {args.profile}")
    print(f"runs: {args.runs}")
    print(f"seed_start: {args.seed_start}")

    _print_title("Profile Summary")
    _print_table(compact_metrics)

    _print_title("Action Frequency")
    _print_table(action_summary)

    _print_title("Outputs")
    print(run_level_path)
    print(summary_path)
    print(action_path)
    for chart_path in charts.values():
        print(chart_path)


if __name__ == "__main__":
    main()
