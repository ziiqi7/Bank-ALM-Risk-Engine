"""Tests for treasury transformations and management actions."""

import pytest

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months, load_config
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import build_standard_rate_shocks
from src.liquidity.lcr import calculate_lcr
from src.stress.management_actions import run_management_action_plan
from src.stress.scenarios import StressScenario
from src.treasury.money_market import raise_interbank_funding
from src.treasury.securities import repo_level1_hqla


def test_raise_interbank_funding_adds_cash_and_liability() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    portfolio = Portfolio(positions=[])

    updated = raise_interbank_funding(
        portfolio,
        config.as_of_date,
        amount=50.0,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.009,
        stress_spread_addon=0.010,
    )

    assert len(updated.positions) == 2
    assert updated.positions[0].product_type == "reserves/cash"
    assert updated.positions[0].balance_side == "asset"
    assert updated.positions[0].notional == pytest.approx(50.0)
    assert updated.positions[1].product_type == "interbank_borrowing"
    assert updated.positions[1].balance_side == "liability"
    assert updated.positions[1].notional == pytest.approx(50.0)


def test_management_actions_issue_term_funding_when_nsfr_is_weak() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="fixed_mortgages",
                balance_side="asset",
                notional=300.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 60),
                rate_type="fixed",
                coupon_rate=0.03,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="loan_book",
                behavioral_category="contractual",
                hqla_level="none",
                asf_factor=0.0,
                rsf_factor=0.85,
            ),
            Position(
                position_id="A2",
                product_type="reserves/cash",
                balance_side="asset",
                notional=100.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 1),
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
                notional=50.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 120),
                rate_type="nonrate",
                coupon_rate=0.001,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="deposit",
                behavioral_category="retail_nmd",
                hqla_level="none",
                asf_factor=0.9,
                rsf_factor=0.0,
            ),
            Position(
                position_id="E1",
                product_type="equity",
                balance_side="equity",
                notional=50.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 360),
                rate_type="nonrate",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="capital",
                behavioral_category="permanent",
                hqla_level="none",
                asf_factor=1.0,
                rsf_factor=0.0,
            ),
        ]
    )

    mild_scenario = StressScenario(
        name="mild",
        deposit_outflow_multiplier=1.0,
        wholesale_outflow_multiplier=1.0,
        inflow_multiplier=1.0,
        hqla_haircut_addon=0.0,
        parallel_rate_bps=0.0,
    )

    result = run_management_action_plan(portfolio, config, mild_scenario)

    assert "issue_term_funding" in set(result.action_log["action_name"])
    pre_nsfr = float(result.pre_action_metrics.loc[result.pre_action_metrics["metric"] == "nsfr", "value"].iloc[0])
    post_nsfr = float(result.post_action_metrics.loc[result.post_action_metrics["metric"] == "nsfr", "value"].iloc[0])
    assert post_nsfr > pre_nsfr


def test_repo_encumbers_hqla_without_double_counting_lcr_numerator() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="sovereign_bonds",
                balance_side="asset",
                notional=100.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 24),
                rate_type="fixed",
                coupon_rate=0.02,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="securities",
                behavioral_category="contractual",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.05,
            ),
            Position(
                position_id="L1",
                product_type="retail_nmd",
                balance_side="liability",
                notional=100.0,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 120),
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

    updated_portfolio, proceeds = repo_level1_hqla(
        portfolio,
        as_of_date,
        proceeds_amount=98.0,
        advance_rate=0.98,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.004,
        stress_spread_addon=0.003,
    )
    lcr_result = calculate_lcr(updated_portfolio, config)

    assert proceeds == pytest.approx(98.0)
    assert any(position.encumbered for position in updated_portfolio.positions)
    assert lcr_result.hqla == pytest.approx(98.0)
    assert lcr_result.hqla != pytest.approx(198.0)


def test_stressed_unsecured_funding_worsens_nii_more_than_repo_funding() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    shock = build_standard_rate_shocks(config)["parallel_up"]

    interbank_portfolio = raise_interbank_funding(
        Portfolio(positions=[]),
        as_of_date,
        amount=50.0,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.009,
        stress_spread_addon=0.010,
    )

    repo_base_portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="sovereign_bonds",
                balance_side="asset",
                notional=51.0204081633,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 24),
                rate_type="fixed",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="securities",
                behavioral_category="contractual",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.05,
            )
        ]
    )
    repo_portfolio, _ = repo_level1_hqla(
        repo_base_portfolio,
        as_of_date,
        proceeds_amount=50.0,
        advance_rate=0.98,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.004,
        stress_spread_addon=0.003,
    )

    interbank_result = calculate_12m_nii_sensitivity(interbank_portfolio, config, shock)
    repo_result = calculate_12m_nii_sensitivity(repo_portfolio, config, shock)

    assert interbank_result.delta_nii < repo_result.delta_nii


def test_scenario_dependent_funding_spreads_make_combined_stress_more_expensive() -> None:
    config = load_config("data/assumptions/base_assumptions.yaml")
    as_of_date = config.as_of_date
    shock = build_standard_rate_shocks(config)["parallel_up"]

    interbank_portfolio = raise_interbank_funding(
        Portfolio(positions=[]),
        as_of_date,
        amount=50.0,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.009,
        stress_spread_addon=config.management_actions.interbank_stress_spread_addon,
    )

    repo_base_portfolio = Portfolio(
        positions=[
            Position(
                position_id="A1",
                product_type="sovereign_bonds",
                balance_side="asset",
                notional=51.0204081633,
                currency="EUR",
                start_date=as_of_date,
                maturity_date=add_months(as_of_date, 24),
                rate_type="fixed",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="securities",
                behavioral_category="contractual",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.05,
            )
        ]
    )
    repo_portfolio, _ = repo_level1_hqla(
        repo_base_portfolio,
        as_of_date,
        proceeds_amount=50.0,
        advance_rate=0.98,
        term_months=3,
        base_rate=0.022,
        funding_spread=0.004,
        stress_spread_addon=config.management_actions.repo_stress_spread_addon,
    )

    mild_addons = {"interbank_borrowing": 0.003, "repo_funding": 0.001}
    combined_addons = {"interbank_borrowing": 0.015, "repo_funding": 0.006}

    interbank_mild = calculate_12m_nii_sensitivity(
        interbank_portfolio,
        config,
        shock,
        funding_spread_addons=mild_addons,
    )
    interbank_combined = calculate_12m_nii_sensitivity(
        interbank_portfolio,
        config,
        shock,
        funding_spread_addons=combined_addons,
    )
    repo_combined = calculate_12m_nii_sensitivity(
        repo_portfolio,
        config,
        shock,
        funding_spread_addons=combined_addons,
    )

    assert interbank_combined.delta_nii < interbank_mild.delta_nii
    assert repo_combined.delta_nii > interbank_combined.delta_nii
