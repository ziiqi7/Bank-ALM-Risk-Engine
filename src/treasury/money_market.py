"""Money-market and simple hedge placeholder transformations."""

from __future__ import annotations

from datetime import timedelta

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import add_months


def _append_positions(portfolio: Portfolio, new_positions: list[Position]) -> Portfolio:
    """Return a new portfolio with appended synthetic positions."""

    return Portfolio(positions=[*portfolio.positions, *new_positions])


def raise_interbank_funding(
    portfolio: Portfolio,
    as_of_date,
    amount: float,
    term_months: int,
    base_rate: float,
    funding_spread: float,
    stress_spread_addon: float,
    currency: str = "EUR",
) -> Portfolio:
    """Add cash proceeds and unsecured interbank funding.

    The transformation is modeled as:
    - an asset-side reserve/cash position for the proceeds
    - a floating liability representing unsecured money-market borrowing
    """

    if amount <= 0.0:
        return portfolio

    new_positions = [
        Position(
            position_id=f"TA_CASH_IB_{len(portfolio.positions) + 1}",
            product_type="reserves/cash",
            balance_side="asset",
            notional=amount,
            currency=currency,
            start_date=as_of_date,
            maturity_date=as_of_date + timedelta(days=7),
            rate_type="nonrate",
            coupon_rate=0.0,
            spread=0.0,
            repricing_freq_months=1,
            liquidity_category="cash",
            behavioral_category="contingency_buffer",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.0,
        ),
        Position(
            position_id=f"TL_IB_{len(portfolio.positions) + 1}",
            product_type="interbank_borrowing",
            balance_side="liability",
            notional=amount,
            currency=currency,
            start_date=as_of_date,
            maturity_date=add_months(as_of_date, term_months),
            rate_type="floating",
            coupon_rate=base_rate,
            spread=funding_spread,
            repricing_freq_months=1,
            liquidity_category="wholesale",
            behavioral_category="contingency_funding",
            hqla_level="none",
            asf_factor=0.5 if term_months >= 6 else 0.0,
            rsf_factor=0.0,
            stress_spread_addon=stress_spread_addon,
        ),
    ]
    return _append_positions(portfolio, new_positions)


def issue_term_funding(
    portfolio: Portfolio,
    as_of_date,
    amount: float,
    term_months: int,
    base_rate: float,
    funding_spread: float,
    stress_spread_addon: float,
    currency: str = "EUR",
) -> Portfolio:
    """Add cash proceeds and longer-dated fixed-rate term funding."""

    if amount <= 0.0:
        return portfolio

    new_positions = [
        Position(
            position_id=f"TA_CASH_TF_{len(portfolio.positions) + 1}",
            product_type="reserves/cash",
            balance_side="asset",
            notional=amount,
            currency=currency,
            start_date=as_of_date,
            maturity_date=as_of_date + timedelta(days=7),
            rate_type="nonrate",
            coupon_rate=0.0,
            spread=0.0,
            repricing_freq_months=1,
            liquidity_category="cash",
            behavioral_category="contingency_buffer",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.0,
        ),
        Position(
            position_id=f"TL_TF_{len(portfolio.positions) + 1}",
            product_type="term_funding",
            balance_side="liability",
            notional=amount,
            currency=currency,
            start_date=as_of_date,
            maturity_date=add_months(as_of_date, term_months),
            rate_type="fixed",
            coupon_rate=base_rate,
            spread=funding_spread,
            repricing_freq_months=None,
            liquidity_category="wholesale",
            behavioral_category="contingency_funding",
            hqla_level="none",
            asf_factor=1.0 if term_months >= 12 else 0.5,
            rsf_factor=0.0,
            stress_spread_addon=stress_spread_addon,
        ),
    ]
    return _append_positions(portfolio, new_positions)


def add_hedge_placeholder(
    portfolio: Portfolio,
    as_of_date,
    amount: float,
    direction: str,
    term_months: int,
    fixed_rate: float,
    currency: str = "EUR",
) -> Portfolio:
    """Add a lightweight hedge placeholder as a synthetic balance-sheet item.

    This is not derivative pricing. It is a transparent placeholder that nudges
    EVE sensitivity through an added fixed-rate position:
    - ``receive_fixed`` is modeled as an asset
    - ``pay_fixed`` is modeled as a liability
    """

    if amount <= 0.0:
        return portfolio

    if direction not in {"receive_fixed", "pay_fixed"}:
        raise ValueError("direction must be 'receive_fixed' or 'pay_fixed'")

    hedge_position = Position(
        position_id=f"TH_{direction}_{len(portfolio.positions) + 1}",
        product_type=f"{direction}_hedge_placeholder",
        balance_side="asset" if direction == "receive_fixed" else "liability",
        notional=amount,
        currency=currency,
        start_date=as_of_date,
        maturity_date=add_months(as_of_date, term_months),
        rate_type="fixed",
        coupon_rate=fixed_rate,
        spread=0.0,
        repricing_freq_months=None,
        liquidity_category="treasury_overlay",
        behavioral_category="hedge_placeholder",
        hqla_level="none",
        asf_factor=0.0 if direction == "receive_fixed" else 1.0,
        rsf_factor=0.0 if direction == "pay_fixed" else 0.0,
    )
    return _append_positions(portfolio, [hedge_position])
