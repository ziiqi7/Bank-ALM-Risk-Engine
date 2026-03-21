"""Unit tests for simplified NII sensitivity."""

import pytest

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months, load_config, year_fraction
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import build_standard_rate_shocks


def test_12m_nii_parallel_up_matches_expected_simple_case() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    config_as_of = config.as_of_date
    portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="floating_corporate_loans",
                balance_side="asset",
                notional=100.0,
                currency="EUR",
                start_date=config_as_of,
                maturity_date=add_months(config_as_of, 24),
                rate_type="floating",
                coupon_rate=0.02,
                spread=0.0,
                repricing_freq_months=3,
                liquidity_category="loan_book",
                behavioral_category="contractual",
                hqla_level="none",
                asf_factor=0.0,
                rsf_factor=0.5,
            ),
            Position(
                position_id="L1",
                product_type="retail_nmd",
                balance_side="liability",
                notional=80.0,
                currency="EUR",
                start_date=config_as_of,
                maturity_date=add_months(config_as_of, 120),
                rate_type="nonrate",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="deposit",
                behavioral_category="retail_nmd",
                hqla_level="none",
                asf_factor=0.9,
                rsf_factor=0.0,
            ),
        ]
    )

    result = calculate_12m_nii_sensitivity(
        portfolio,
        config,
        build_standard_rate_shocks(config)["parallel_up"],
    )

    expected_asset_delta = 100.0 * 0.02 * (
        year_fraction(add_months(config_as_of, 3), add_months(config_as_of, 6))
        + year_fraction(add_months(config_as_of, 6), add_months(config_as_of, 9))
        + year_fraction(add_months(config_as_of, 9), add_months(config_as_of, 12))
    )
    expected_core_liability_delta = -(
        80.0
        * config.behavioral.non_maturity_deposit_stable_share
        * 0.02
        * config.behavioral.retail_nmd_beta
    )
    expected_non_core_liability_delta = -0.02 * config.behavioral.retail_nmd_beta * (
        12.0 * year_fraction(config_as_of, add_months(config_as_of, 1))
        + 8.0 * year_fraction(add_months(config_as_of, 1), add_months(config_as_of, 2))
        + 4.0 * year_fraction(add_months(config_as_of, 2), add_months(config_as_of, 3))
    )
    expected_liability_delta = expected_core_liability_delta + expected_non_core_liability_delta

    assert result.base_nii == pytest.approx(2.0)
    assert result.shocked_nii == pytest.approx(2.0 + expected_asset_delta + expected_liability_delta)
    assert result.delta_nii == pytest.approx(expected_asset_delta + expected_liability_delta)
