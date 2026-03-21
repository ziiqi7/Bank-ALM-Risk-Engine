"""Instrument-level balance-sheet schema."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.config import BehavioralAssumptions, year_fraction


@dataclass(frozen=True)
class Position:
    """Unified balance-sheet position schema for the simplified ALM engine."""

    position_id: str
    product_type: str
    balance_side: str
    notional: float
    currency: str
    start_date: date
    maturity_date: date
    rate_type: str
    coupon_rate: float
    spread: float
    repricing_freq_months: int | None
    liquidity_category: str
    behavioral_category: str
    hqla_level: str
    asf_factor: float
    rsf_factor: float
    encumbered: bool = False
    stress_spread_addon: float = 0.0

    @property
    def is_asset(self) -> bool:
        return self.balance_side.lower() == "asset"

    @property
    def is_liability(self) -> bool:
        return self.balance_side.lower() == "liability"

    @property
    def is_equity(self) -> bool:
        return self.balance_side.lower() == "equity"

    @property
    def contractual_rate(self) -> float:
        return self.coupon_rate + self.spread

    @property
    def base_rate(self) -> float:
        """Return the base contractual rate component."""

        return self.coupon_rate

    def signed_notional(self) -> float:
        if self.is_asset:
            return self.notional
        if self.is_liability:
            return -self.notional
        return 0.0

    def years_to_maturity(self, as_of_date: date) -> float:
        return year_fraction(as_of_date, self.maturity_date)

    def months_to_maturity(self, as_of_date: date) -> int:
        return max(int(round(self.years_to_maturity(as_of_date) * 12)), 0)

    def effective_repricing_months(
        self,
        as_of_date: date,
        behavioral: BehavioralAssumptions,
    ) -> int:
        """Estimate the next behavioral or contractual repricing horizon."""

        maturity_months = max(self.months_to_maturity(as_of_date), 1)

        if self.rate_type == "floating":
            return min(self.repricing_freq_months or 1, maturity_months)

        if self.rate_type == "fixed":
            return maturity_months

        if self.product_type == "retail_nmd":
            return behavioral.retail_nmd_repricing_months

        if self.product_type in {"reserves/cash", "cash", "reserves"}:
            return behavioral.cash_repricing_months

        return maturity_months
