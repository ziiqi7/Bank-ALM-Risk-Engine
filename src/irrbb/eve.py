"""EVE sensitivity built on the shared IRRBB cashflow engine.

Default behavior shocks discounting only. An optional projected-cashflow mode
can also shock row-level floating-rate coupons while keeping the same schedule.
That optional mode is still deliberately simple and does not introduce a term
structure or stochastic rate projection.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig, year_fraction
from src.irrbb.cashflows import calculate_shocked_applied_rate, generate_cashflows
from src.irrbb.shocks import RateShock, rate_shift_decimal


@dataclass(frozen=True)
class EveSensitivityResult:
    """Container for EVE sensitivity outputs."""

    shock_name: str
    base_eve: float
    shocked_eve: float
    delta_eve: float
    breakdown: pd.DataFrame


def _discount_factor(rate: float, years: float) -> float:
    """Return a simple annual discount factor."""

    bounded_rate = max(rate, -0.95)
    return 1.0 / ((1.0 + bounded_rate) ** years)


def _present_value_from_cashflows(
    cashflows: pd.DataFrame,
    config: EngineConfig,
    shock: RateShock | None = None,
    shock_projected_cashflows: bool = False,
) -> float:
    """Discount cashflows under base or shocked rates.

    By default this is a discount-only EVE view: projected cashflows stay the
    same and only discount factors move. When ``shock_projected_cashflows`` is
    enabled, floating-rate rows can use shocked ``applied_rate`` values before
    discounting. Fixed-rate cashflows stay unchanged.
    """

    pv = 0.0
    for _, cashflow in cashflows.iterrows():
        term_years = max(year_fraction(config.as_of_date, cashflow["date"]), 0.0)
        discount_rate = config.base_discount_rate
        projected_cashflow = float(cashflow["total_cashflow"])

        if shock is not None and shock_projected_cashflows:
            shocked_applied_rate = calculate_shocked_applied_rate(
                product_type=str(cashflow["product_type"]),
                rate_type=str(cashflow["rate_type"]),
                cashflow=cashflow,
                as_of_date=config.as_of_date,
                assumptions=config,
                shock=shock,
                shock_retail_nmd=False,
            )
            projected_interest = cashflow["balance"] * shocked_applied_rate * cashflow["accrual_years"]
            projected_cashflow = float(cashflow["principal"] + projected_interest)

        if shock is not None:
            discount_rate += rate_shift_decimal(shock, max(term_years, 1.0 / 12.0))
        pv += projected_cashflow * _discount_factor(discount_rate, term_years)
    return pv


def calculate_eve_sensitivity(
    portfolio: Portfolio,
    config: EngineConfig,
    shock: RateShock,
    shock_projected_cashflows: bool = False,
) -> EveSensitivityResult:
    """Estimate EVE by discounting shared future cashflows.

    Default mode shocks discounting only: the cashflow schedule and projected
    interest cashflows are unchanged. When ``shock_projected_cashflows=True``,
    the same schedule is kept but floating-rate rows can use shocked row-level
    applied rates. Retail NMDs remain unchanged in projected-cashflow mode for
    now, which is a deliberate simplification.
    """

    breakdown_rows: list[dict[str, float | str]] = []
    base_eve = 0.0
    shocked_eve = 0.0

    for position in portfolio.positions:
        if position.is_equity:
            continue

        cashflows = generate_cashflows(position, config.as_of_date, config)
        sign = 1.0 if position.is_asset else -1.0
        base_pv = sign * _present_value_from_cashflows(cashflows, config)
        shocked_pv = sign * _present_value_from_cashflows(
            cashflows,
            config,
            shock=shock,
            shock_projected_cashflows=shock_projected_cashflows,
        )
        base_eve += base_pv
        shocked_eve += shocked_pv
        breakdown_rows.append(
            {
                "position_id": position.position_id,
                "product_type": position.product_type,
                "cashflow_count": len(cashflows),
                "shock_projected_cashflows": shock_projected_cashflows,
                "base_pv": base_pv,
                "shocked_pv": shocked_pv,
                "delta_eve": shocked_pv - base_pv,
            }
        )

    breakdown = pd.DataFrame(breakdown_rows)
    return EveSensitivityResult(
        shock_name=shock.name,
        base_eve=base_eve,
        shocked_eve=shocked_eve,
        delta_eve=shocked_eve - base_eve,
        breakdown=breakdown,
    )


def run_eve_sensitivity_grid(
    portfolio: Portfolio,
    config: EngineConfig,
    shocks: dict[str, RateShock],
    shock_projected_cashflows: bool = False,
) -> pd.DataFrame:
    """Run a compact EVE summary for multiple shocks."""

    rows = []
    for shock_name, shock in shocks.items():
        result = calculate_eve_sensitivity(
            portfolio,
            config,
            shock,
            shock_projected_cashflows=shock_projected_cashflows,
        )
        rows.append({"shock": shock_name, "delta_eve": result.delta_eve})
    return pd.DataFrame(rows)
