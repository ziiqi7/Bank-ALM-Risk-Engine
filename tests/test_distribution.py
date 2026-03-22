"""Tests for batch ensemble and aggregation helpers."""

from __future__ import annotations

from src.analysis.aggregation import action_frequency_by_profile, summarize_ensemble_results
from src.analysis.ensemble import run_portfolio_ensemble
from src.config import load_config


def test_run_portfolio_ensemble_returns_expected_number_of_rows() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")

    results = run_portfolio_ensemble(
        config=config,
        profile="balanced",
        runs=3,
        seed_start=11,
    )

    assert len(results) == 3
    assert list(results["seed"]) == [11, 12, 13]
    assert set(results["profile"]) == {"balanced"}


def test_aggregation_outputs_expected_summary_columns() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    results = run_portfolio_ensemble(
        config=config,
        profile="liquidity_tight",
        runs=2,
        seed_start=21,
    )

    summary = summarize_ensemble_results(results)
    action_summary = action_frequency_by_profile(results)

    assert "delta_nii_parallel_up_mean" in summary.columns
    assert "delta_eve_parallel_up_p90" in summary.columns
    assert "stressed_lcr_median" in summary.columns
    assert "post_action_delta_nii_max" in summary.columns
    assert "repo_usage_rate" in action_summary.columns
    assert "interbank_usage_rate" in action_summary.columns
    assert "term_funding_usage_rate" in action_summary.columns
    assert "hedge_usage_rate" in action_summary.columns
