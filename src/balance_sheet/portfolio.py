"""Portfolio container and synthetic balance-sheet generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.balance_sheet.instruments import Position
from src.config import add_months


@dataclass
class Portfolio:
    """Thin portfolio wrapper around a list of positions."""

    positions: list[Position]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "position_id": position.position_id,
                    "product_type": position.product_type,
                    "balance_side": position.balance_side,
                    "notional": position.notional,
                    "currency": position.currency,
                    "start_date": position.start_date,
                    "maturity_date": position.maturity_date,
                    "rate_type": position.rate_type,
                    "coupon_rate": position.coupon_rate,
                    "spread": position.spread,
                    "repricing_freq_months": position.repricing_freq_months,
                    "liquidity_category": position.liquidity_category,
                    "behavioral_category": position.behavioral_category,
                    "hqla_level": position.hqla_level,
                    "asf_factor": position.asf_factor,
                    "rsf_factor": position.rsf_factor,
                    "encumbered": position.encumbered,
                    "stress_spread_addon": position.stress_spread_addon,
                }
                for position in self.positions
            ]
        )

    def total_assets(self) -> float:
        return sum(position.notional for position in self.positions if position.is_asset)

    def total_liabilities(self) -> float:
        return sum(position.notional for position in self.positions if position.is_liability)

    def total_equity(self) -> float:
        return sum(position.notional for position in self.positions if position.is_equity)


def build_synthetic_portfolio(as_of_date: date) -> Portfolio:
    """Create a synthetic banking-book balance sheet for v1 analytics."""

    positions = [
        Position(
            position_id="A1",
            product_type="fixed_mortgages",
            balance_side="asset",
            notional=250.0,
            currency="EUR",
            start_date=add_months(as_of_date, -18),
            maturity_date=add_months(as_of_date, 72),
            rate_type="fixed",
            coupon_rate=0.032,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="loan_book",
            behavioral_category="amortizing",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.85,
        ),
        Position(
            position_id="A2",
            product_type="fixed_mortgages",
            balance_side="asset",
            notional=180.0,
            currency="EUR",
            start_date=add_months(as_of_date, -30),
            maturity_date=add_months(as_of_date, 120),
            rate_type="fixed",
            coupon_rate=0.036,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="loan_book",
            behavioral_category="amortizing",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.85,
        ),
        Position(
            position_id="A3",
            product_type="floating_corporate_loans",
            balance_side="asset",
            notional=220.0,
            currency="EUR",
            start_date=add_months(as_of_date, -12),
            maturity_date=add_months(as_of_date, 48),
            rate_type="floating",
            coupon_rate=0.022,
            spread=0.015,
            repricing_freq_months=3,
            liquidity_category="loan_book",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.5,
        ),
        Position(
            position_id="A4",
            product_type="sovereign_bonds",
            balance_side="asset",
            notional=140.0,
            currency="EUR",
            start_date=add_months(as_of_date, -6),
            maturity_date=add_months(as_of_date, 36),
            rate_type="fixed",
            coupon_rate=0.024,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="securities",
            behavioral_category="contractual",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.05,
        ),
        Position(
            position_id="A5",
            product_type="reserves/cash",
            balance_side="asset",
            notional=90.0,
            currency="EUR",
            start_date=add_months(as_of_date, -1),
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
            notional=420.0,
            currency="EUR",
            start_date=add_months(as_of_date, -36),
            maturity_date=add_months(as_of_date, 240),
            rate_type="nonrate",
            coupon_rate=0.002,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="retail_nmd",
            hqla_level="none",
            asf_factor=0.9,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L2",
            product_type="retail_nmd",
            balance_side="liability",
            notional=110.0,
            currency="EUR",
            start_date=add_months(as_of_date, -12),
            maturity_date=add_months(as_of_date, 180),
            rate_type="nonrate",
            coupon_rate=0.004,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="retail_nmd_less_stable",
            hqla_level="none",
            asf_factor=0.8,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L3",
            product_type="term_deposits",
            balance_side="liability",
            notional=190.0,
            currency="EUR",
            start_date=add_months(as_of_date, -6),
            maturity_date=add_months(as_of_date, 12),
            rate_type="fixed",
            coupon_rate=0.028,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.95,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L4",
            product_type="interbank_borrowing",
            balance_side="liability",
            notional=85.0,
            currency="EUR",
            start_date=add_months(as_of_date, -3),
            maturity_date=add_months(as_of_date, 6),
            rate_type="floating",
            coupon_rate=0.027,
            spread=0.004,
            repricing_freq_months=1,
            liquidity_category="wholesale",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.5,
            rsf_factor=0.0,
        ),
        Position(
            position_id="E1",
            product_type="equity",
            balance_side="equity",
            notional=75.0,
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
    return Portfolio(positions=positions)
