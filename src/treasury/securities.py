"""Security mobilization and repo transformations."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months


def _level1_security_positions(portfolio: Portfolio) -> list[Position]:
    """Return unencumbered level-1 securities eligible for liquidation or repo."""

    return [
        position
        for position in portfolio.positions
        if position.is_asset
        and position.hqla_level == "level1"
        and position.liquidity_category == "securities"
        and not position.encumbered
    ]


def level1_security_capacity(portfolio: Portfolio) -> float:
    """Return total eligible level-1 security notional."""

    return sum(position.notional for position in _level1_security_positions(portfolio))


def liquidate_level1_securities(
    portfolio: Portfolio,
    as_of_date,
    amount: float,
    currency: str = "EUR",
) -> tuple[Portfolio, float]:
    """Convert eligible level-1 securities into reserves/cash.

    Simplification: liquidation is modeled as a one-for-one balance-sheet
    transformation with no realized gain/loss.
    """

    if amount <= 0.0:
        return portfolio, 0.0

    remaining = amount
    new_positions: list[Position] = []
    mobilized = 0.0

    for position in portfolio.positions:
        if remaining <= 0.0 or position not in _level1_security_positions(portfolio):
            new_positions.append(position)
            continue

        use_amount = min(position.notional, remaining)
        if position.notional > use_amount:
            new_positions.append(replace(position, notional=position.notional - use_amount))

        mobilized += use_amount
        remaining -= use_amount

    if mobilized > 0.0:
        new_positions.append(
            Position(
                position_id=f"TA_SEC_LIQ_{len(portfolio.positions) + 1}",
                product_type="reserves/cash",
                balance_side="asset",
                notional=mobilized,
                currency=currency,
                start_date=as_of_date,
                maturity_date=as_of_date + timedelta(days=7),
                rate_type="nonrate",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=1,
                liquidity_category="cash",
                behavioral_category="hqla_mobilized",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.0,
            )
        )

    return Portfolio(positions=new_positions), mobilized


def repo_level1_hqla(
    portfolio: Portfolio,
    as_of_date,
    proceeds_amount: float,
    advance_rate: float,
    term_months: int,
    base_rate: float,
    funding_spread: float,
    stress_spread_addon: float,
    currency: str = "EUR",
) -> tuple[Portfolio, float]:
    """Raise secured funding against eligible level-1 securities.

    Simplification: repo is modeled as a new cash asset and a secured funding
    liability. The collateral remains on balance sheet but the encumbered slice
    is excluded from LCR HQLA eligibility. This is a lightweight eligibility
    exclusion rather than a full collateral management engine.
    """

    if proceeds_amount <= 0.0:
        return portfolio, 0.0

    eligible_capacity = level1_security_capacity(portfolio) * advance_rate
    actual_proceeds = min(proceeds_amount, eligible_capacity)
    if actual_proceeds <= 0.0:
        return portfolio, 0.0

    collateral_needed = actual_proceeds / advance_rate
    remaining_collateral = collateral_needed
    adjusted_positions: list[Position] = []
    eligible_positions = _level1_security_positions(portfolio)

    for position in portfolio.positions:
        if remaining_collateral <= 0.0 or position not in eligible_positions:
            adjusted_positions.append(position)
            continue

        encumber_amount = min(position.notional, remaining_collateral)
        remaining_collateral -= encumber_amount

        if position.notional > encumber_amount:
            adjusted_positions.append(replace(position, notional=position.notional - encumber_amount))

        adjusted_positions.append(
            replace(
                position,
                position_id=f"{position.position_id}_ENC",
                notional=encumber_amount,
                encumbered=True,
            )
        )

    new_positions = [
        Position(
            position_id=f"TA_REPO_CASH_{len(portfolio.positions) + 1}",
            product_type="reserves/cash",
            balance_side="asset",
            notional=actual_proceeds,
            currency=currency,
            start_date=as_of_date,
            maturity_date=as_of_date + timedelta(days=7),
            rate_type="nonrate",
            coupon_rate=0.0,
            spread=0.0,
            repricing_freq_months=1,
            liquidity_category="cash",
            behavioral_category="repo_proceeds",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.0,
        ),
        Position(
            position_id=f"TL_REPO_{len(portfolio.positions) + 1}",
            product_type="repo_funding",
            balance_side="liability",
            notional=actual_proceeds,
            currency=currency,
            start_date=as_of_date,
            maturity_date=add_months(as_of_date, term_months),
            rate_type="floating",
            coupon_rate=base_rate,
            spread=funding_spread,
            repricing_freq_months=1,
            liquidity_category="wholesale",
            behavioral_category="secured_funding",
            hqla_level="none",
            asf_factor=0.0 if term_months < 6 else 0.5,
            rsf_factor=0.0,
            stress_spread_addon=stress_spread_addon,
        ),
    ]
    return Portfolio(positions=[*adjusted_positions, *new_positions]), actual_proceeds
