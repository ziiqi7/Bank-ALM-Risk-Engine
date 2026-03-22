"""Tests for CSV-driven portfolio loading and constrained generation."""

from __future__ import annotations

import pytest

from src.balance_sheet.portfolio import Portfolio, load_portfolio_from_csv
from src.config import load_config
from src.data.generator import generate_random_portfolio, generate_random_portfolio_csv


def test_load_portfolio_from_csv_returns_valid_portfolio() -> None:
    portfolio = load_portfolio_from_csv("data/portfolios/base_portfolio.csv")

    assert isinstance(portfolio, Portfolio)
    assert len(portfolio.positions) == 10
    assert portfolio.total_assets() == pytest.approx(6600.0)
    assert portfolio.total_liabilities() == pytest.approx(6037.5)
    assert portfolio.total_equity() == pytest.approx(562.5)


def test_generated_portfolio_csv_balances_assets_and_funding(tmp_path) -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    output_path = tmp_path / "generated_portfolio.csv"

    portfolio = generate_random_portfolio_csv(
        as_of_date=config.as_of_date,
        output_path=output_path,
        profile="balanced",
        seed=42,
    )

    reloaded = load_portfolio_from_csv(output_path)

    assert output_path.exists()
    assert portfolio.total_assets() == pytest.approx(portfolio.total_liabilities() + portfolio.total_equity())
    assert reloaded.total_assets() == pytest.approx(reloaded.total_liabilities() + reloaded.total_equity())
    assert 5000.0 <= reloaded.total_assets() <= 8000.0


def test_profiles_produce_different_liquidity_and_duration_shapes() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    balanced = generate_random_portfolio(config.as_of_date, profile="balanced", seed=7)
    liquidity_tight = generate_random_portfolio(config.as_of_date, profile="liquidity_tight", seed=7)
    irrbb_heavy = generate_random_portfolio(config.as_of_date, profile="irrbb_heavy", seed=7)

    balanced_frame = balanced.to_frame()
    liquidity_tight_frame = liquidity_tight.to_frame()
    irrbb_heavy_frame = irrbb_heavy.to_frame()

    balanced_hqla = balanced_frame.loc[balanced_frame["hqla_level"] == "level1", "notional"].sum()
    liquidity_tight_hqla = liquidity_tight_frame.loc[liquidity_tight_frame["hqla_level"] == "level1", "notional"].sum()
    balanced_interbank = balanced_frame.loc[
        balanced_frame["product_type"] == "interbank_borrowing", "notional"
    ].sum()
    liquidity_tight_interbank = liquidity_tight_frame.loc[
        liquidity_tight_frame["product_type"] == "interbank_borrowing", "notional"
    ].sum()
    balanced_mortgages = balanced_frame.loc[balanced_frame["product_type"] == "fixed_mortgages", "notional"].sum()
    irrbb_heavy_mortgages = irrbb_heavy_frame.loc[
        irrbb_heavy_frame["product_type"] == "fixed_mortgages", "notional"
    ].sum()

    assert liquidity_tight_hqla < balanced_hqla
    assert liquidity_tight_interbank > balanced_interbank
    assert irrbb_heavy_mortgages > balanced_mortgages


def test_generated_portfolio_contains_multiple_product_tranches() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    portfolio = generate_random_portfolio(config.as_of_date, profile="balanced", seed=13)
    frame = portfolio.to_frame()

    assert 30 <= len(frame) <= 40
    assert (frame["product_type"] == "fixed_mortgages").sum() == 7
    assert (frame["product_type"] == "floating_corporate_loans").sum() == 6
    assert (frame["product_type"] == "sovereign_bonds").sum() == 5
    assert (frame["product_type"] == "term_deposits").sum() == 4
    assert (frame["product_type"] == "interbank_borrowing").sum() == 4
    assert (frame["product_type"] == "retail_nmd").sum() == 4
    assert 1 <= (frame["product_type"] == "reserves/cash").sum() <= 2
