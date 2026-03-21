"""Example end-to-end pipeline for the simplified ALM risk engine."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import pandas as pd


def _bootstrap_project_root() -> Path:
    """Add the repository root to ``sys.path`` based on this script's location.

    This keeps the example runnable even when it is launched from a different
    working directory, for example:
    ``python /path/to/bank-alm-risk-engine/scripts/example_pipeline.py``.
    """

    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    os.environ.setdefault("MPLCONFIGDIR", str(project_root / ".mpl-cache"))
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from src.balance_sheet.portfolio import build_synthetic_portfolio
from src.config import load_config
from src.irrbb.eve import calculate_eve_sensitivity, run_eve_sensitivity_grid
from src.irrbb.nii import calculate_12m_nii_sensitivity, run_nii_sensitivity_grid
from src.irrbb.repricing import compute_repricing_gap
from src.irrbb.shocks import build_standard_rate_shocks
from src.liquidity.cash_gap import calculate_cash_gap
from src.liquidity.lcr import calculate_lcr
from src.liquidity.nsfr import calculate_nsfr
from src.reporting.tables import action_log_table, comparison_table, eve_attribution_table, save_bar_chart, summary_table
from src.stress.management_actions import run_management_action_plan
from src.stress.run_stress import run_stress_tests
from src.stress.scenarios import build_stress_scenarios


def _print_title(title: str) -> None:
    print(f"\n=== {title} ===")


def _print_table(table: pd.DataFrame) -> None:
    print(table.to_string(index=False, float_format=lambda value: f"{value:,.3f}"))


def main() -> None:
    project_root = PROJECT_ROOT
    config = load_config(project_root / "data" / "assumptions" / "base_assumptions.yaml")
    portfolio = build_synthetic_portfolio(config.as_of_date)

    shocks = build_standard_rate_shocks(config)
    scenarios = build_stress_scenarios(config)

    repricing_gap = compute_repricing_gap(portfolio, config)
    nii_parallel_up = calculate_12m_nii_sensitivity(portfolio, config, shocks["parallel_up"])
    eve_parallel_up = calculate_eve_sensitivity(portfolio, config, shocks["parallel_up"])
    eve_parallel_up_projected = calculate_eve_sensitivity(
        portfolio,
        config,
        shocks["parallel_up"],
        shock_projected_cashflows=True,
    )
    nii_grid = run_nii_sensitivity_grid(portfolio, config, shocks)
    eve_grid = run_eve_sensitivity_grid(portfolio, config, shocks)
    eve_mode_table = pd.DataFrame(
        [
            {"mode": "discount_only", "delta_eve": eve_parallel_up.delta_eve},
            {"mode": "projected_cashflow", "delta_eve": eve_parallel_up_projected.delta_eve},
        ]
    )
    eve_attribution = eve_attribution_table(eve_parallel_up.breakdown)
    lcr = calculate_lcr(portfolio, config)
    nsfr = calculate_nsfr(portfolio, config)
    cash_gap = calculate_cash_gap(portfolio, config)
    stress_table = run_stress_tests(portfolio, config, scenarios)
    combined_action_result = run_management_action_plan(portfolio, config, scenarios["combined"])
    action_comparison = comparison_table(
        combined_action_result.pre_action_metrics,
        combined_action_result.post_action_metrics,
    )

    headline = summary_table(
        {
            "total_assets": portfolio.total_assets(),
            "total_liabilities": portfolio.total_liabilities(),
            "total_equity": portfolio.total_equity(),
            "lcr": lcr.ratio,
            "nsfr": nsfr.ratio,
            "delta_nii_parallel_up": nii_parallel_up.total_delta_nii,
            "delta_eve_parallel_up": eve_parallel_up.delta_eve,
        }
    )

    charts_dir = project_root / "docs"
    save_bar_chart(repricing_gap, "bucket", "gap", "Repricing Gap", charts_dir / "repricing_gap.png")
    save_bar_chart(cash_gap.ladder, "bucket", "net_gap", "Cash Gap Ladder", charts_dir / "cash_gap.png")

    action_summary = action_log_table(combined_action_result.action_log)
    compact_action_view = action_summary[
        [
            "step",
            "action_name",
            "amount",
            "funding_stress_spread_used",
            "delta_nii_change",
            "lcr_after",
            "survival_after_days",
        ]
    ].copy()

    _print_title("Portfolio Summary")
    _print_table(headline)

    _print_title("Repricing Gap")
    _print_table(repricing_gap)

    _print_title("IRRBB - NII")
    _print_table(nii_grid)

    _print_title("IRRBB - EVE")
    _print_table(eve_grid)

    _print_title("EVE Mode Comparison")
    _print_table(eve_mode_table)

    _print_title("EVE Attribution (Discount-Only)")
    _print_table(eve_attribution)

    _print_title("Liquidity Summary")
    print(f"LCR: {lcr.ratio:.2f}")
    print(f"NSFR: {nsfr.ratio:.2f}")

    _print_title("Cash Gap Ladder")
    _print_table(cash_gap.ladder)

    _print_title("Stress Summary")
    _print_table(stress_table)

    _print_title("Management Actions - Pre vs Post")
    _print_table(action_comparison)

    _print_title("Management Actions - Cost View")
    _print_table(compact_action_view)

    _print_title("Management Actions - Full Log")
    _print_table(action_summary)


if __name__ == "__main__":
    main()
