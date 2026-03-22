"""Run ensembles of constrained random portfolios through the existing ALM engine."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.balance_sheet.portfolio import Portfolio, save_portfolio_to_csv
from src.config import EngineConfig
from src.data.generator import generate_random_portfolio
from src.irrbb.eve import calculate_eve_sensitivity
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import build_standard_rate_shocks
from src.liquidity.lcr import calculate_lcr
from src.liquidity.nsfr import calculate_nsfr
from src.stress.management_actions import evaluate_stressed_metrics, run_management_action_plan
from src.stress.scenarios import build_stress_scenarios


def _usage_flag(action_log: pd.DataFrame, action_name: str) -> int:
    """Return 1 when the action log contains the requested action."""

    if action_log.empty:
        return 0
    return int(action_name in set(action_log["action_name"]))


def _portfolio_share(portfolio_frame: pd.DataFrame, product_type: str, total_assets: float) -> float:
    """Compute a notional share against total assets."""

    if total_assets <= 0.0:
        return 0.0
    amount = float(portfolio_frame.loc[portfolio_frame["product_type"] == product_type, "notional"].sum())
    return amount / total_assets


def collect_run_metrics(
    portfolio: Portfolio,
    config: EngineConfig,
    profile: str,
    seed: int,
    run_id: str,
) -> dict[str, float | int | str]:
    """Collect a single tidy row of ensemble metrics for one portfolio run."""

    portfolio_frame = portfolio.to_frame()
    total_assets = portfolio.total_assets()
    total_liabilities = portfolio.total_liabilities()
    total_equity = portfolio.total_equity()

    shocks = build_standard_rate_shocks(config)
    scenarios = build_stress_scenarios(config)
    combined_scenario = scenarios["combined"]

    base_lcr = calculate_lcr(portfolio, config)
    base_nsfr = calculate_nsfr(portfolio, config)
    nii_parallel_up = calculate_12m_nii_sensitivity(portfolio, config, shocks["parallel_up"])
    eve_parallel_up = calculate_eve_sensitivity(portfolio, config, shocks["parallel_up"])
    stressed_metrics, _ = evaluate_stressed_metrics(portfolio, config, combined_scenario)
    action_result = run_management_action_plan(portfolio, config, combined_scenario)
    action_log = action_result.action_log

    return {
        "run_id": run_id,
        "profile": profile,
        "seed": seed,
        "total_assets": total_assets,
        "mortgage_share": _portfolio_share(portfolio_frame, "fixed_mortgages", total_assets),
        "hqla_share": float(
            portfolio_frame.loc[portfolio_frame["hqla_level"] == "level1", "notional"].sum()
        )
        / total_assets,
        "interbank_share": _portfolio_share(portfolio_frame, "interbank_borrowing", total_assets),
        "equity_ratio": 0.0 if total_assets <= 0.0 else total_equity / total_assets,
        "base_lcr": base_lcr.ratio,
        "base_nsfr": base_nsfr.ratio,
        "delta_nii_parallel_up": nii_parallel_up.total_delta_nii,
        "delta_eve_parallel_up": eve_parallel_up.delta_eve,
        "stressed_lcr": stressed_metrics.lcr,
        "stressed_nsfr": stressed_metrics.nsfr,
        "stressed_min_cumulative_cash_gap": stressed_metrics.min_cumulative_cash_gap,
        "stressed_survival_horizon_days": stressed_metrics.survival_horizon_days,
        "action_count": int(len(action_log)),
        "used_repo": _usage_flag(action_log, "repo_level1_hqla"),
        "used_interbank": _usage_flag(action_log, "raise_interbank_funding"),
        "used_term_funding": _usage_flag(action_log, "issue_term_funding"),
        "used_hedge": int(
            any("hedge_placeholder" in action_name for action_name in action_log.get("action_name", pd.Series()))
        ),
        "post_action_lcr": float(
            action_result.post_action_metrics.loc[action_result.post_action_metrics["metric"] == "lcr", "value"].iloc[0]
        ),
        "post_action_survival_horizon_days": float(
            action_result.post_action_metrics.loc[
                action_result.post_action_metrics["metric"] == "survival_horizon_days", "value"
            ].iloc[0]
        ),
        "post_action_delta_nii": float(
            action_result.post_action_metrics.loc[
                action_result.post_action_metrics["metric"] == "total_delta_nii", "value"
            ].iloc[0]
        ),
        "post_action_delta_eve": float(
            action_result.post_action_metrics.loc[
                action_result.post_action_metrics["metric"] == "total_delta_eve", "value"
            ].iloc[0]
        ),
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
    }


def run_portfolio_ensemble(
    config: EngineConfig,
    profile: str,
    runs: int,
    seed_start: int = 1,
    seeds: list[int] | None = None,
    output_path: str | Path | None = None,
    portfolio_output_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Run many generated portfolios and collect tidy run-level metrics."""

    seed_values = seeds if seeds is not None else list(range(seed_start, seed_start + runs))
    rows: list[dict[str, float | int | str]] = []

    portfolio_dir = Path(portfolio_output_dir) if portfolio_output_dir is not None else None
    if portfolio_dir is not None:
        portfolio_dir.mkdir(parents=True, exist_ok=True)

    for index, seed in enumerate(seed_values, start=1):
        portfolio = generate_random_portfolio(config.as_of_date, profile=profile, seed=seed)
        run_id = f"{profile}_{seed}"
        if portfolio_dir is not None:
            save_portfolio_to_csv(portfolio, portfolio_dir / f"{run_id}.csv")
        rows.append(collect_run_metrics(portfolio=portfolio, config=config, profile=profile, seed=seed, run_id=run_id))

    results = pd.DataFrame(rows)
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output, index=False)
    return results
