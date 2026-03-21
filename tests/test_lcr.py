"""Unit tests for simplified LCR."""

import pytest

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months, load_config
from src.liquidity.lcr import calculate_lcr


def test_lcr_uses_hqla_over_net_outflows() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    config_as_of = config.as_of_date
    portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="reserves/cash",
                balance_side="asset",
                notional=120.0,
                currency="EUR",
                start_date=config_as_of,
                maturity_date=add_months(config_as_of, 1),
                rate_type="nonrate",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=1,
                liquidity_category="cash",
                behavioral_category="overnight",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.0,
            ),
            Position(
                position_id="L1",
                product_type="retail_nmd",
                balance_side="liability",
                notional=100.0,
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

    result = calculate_lcr(portfolio, config)

    assert result.hqla == pytest.approx(120.0)
    assert result.outflows == pytest.approx(5.0)
    assert result.net_outflows == pytest.approx(5.0)
    assert result.ratio == pytest.approx(24.0)
