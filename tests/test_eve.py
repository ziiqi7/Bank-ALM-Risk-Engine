"""Tests for floating cashflows and configurable EVE shock design."""

import pytest

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months, load_config
from src.irrbb.cashflows import generate_cashflows
from src.irrbb.eve import calculate_eve_sensitivity
from src.irrbb.shocks import build_standard_rate_shocks


def test_generate_cashflows_adds_row_level_floating_rate_fields() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    position = Position(
        position_id="A1",
        product_type="floating_corporate_loans",
        balance_side="asset",
        notional=100.0,
        currency="EUR",
        start_date=as_of_date,
        maturity_date=add_months(as_of_date, 12),
        rate_type="floating",
        coupon_rate=0.02,
        spread=0.0,
        repricing_freq_months=3,
        liquidity_category="loan_book",
        behavioral_category="contractual",
        hqla_level="none",
        asf_factor=0.0,
        rsf_factor=0.5,
    )

    cashflows = generate_cashflows(position, as_of_date, config)

    assert list(cashflows["date"]) == [
        add_months(as_of_date, 3),
        add_months(as_of_date, 6),
        add_months(as_of_date, 9),
        add_months(as_of_date, 12),
    ]
    assert list(cashflows["is_repricing_event"]) == [False, True, True, True]
    assert list(cashflows["applied_rate"]) == pytest.approx([0.02, 0.02, 0.02, 0.02])
    assert list(cashflows["rate_type"].unique()) == ["floating"]
    assert list(cashflows["repricing_freq_months"].unique()) == [3]
    assert list(cashflows["product_type"].unique()) == ["floating_corporate_loans"]


def test_eve_projected_cashflow_mode_only_changes_floating_projection() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    shock = build_standard_rate_shocks(config)["parallel_up"]
    portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="floating_corporate_loans",
                balance_side="asset",
                notional=100.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 12),
                rate_type="floating",
                coupon_rate=0.02,
                spread=0.0,
                repricing_freq_months=3,
                liquidity_category="loan_book",
                behavioral_category="contractual",
                hqla_level="none",
                asf_factor=0.0,
                rsf_factor=0.5,
            )
        ]
    )

    discount_only = calculate_eve_sensitivity(portfolio, config, shock)
    projected = calculate_eve_sensitivity(
        portfolio,
        config,
        shock,
        shock_projected_cashflows=True,
    )

    assert projected.base_eve == pytest.approx(discount_only.base_eve)
    assert projected.shocked_eve > discount_only.shocked_eve
    assert projected.delta_eve > discount_only.delta_eve
