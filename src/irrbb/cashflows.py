"""Shared cashflow generation for simplified IRRBB analytics.

The goal of this module is structural consistency rather than product-complete
valuation. It produces transparent, deterministic future cashflow schedules
that both NII and EVE can reuse.

Simplifications:
- Bullet principal repayment for contractual fixed and floating instruments
- No amortization schedules
- Floating-rate coupons reset on repricing dates and keep the current coupon
  between resets
- For floating-rate products, coupon period = repricing period. This is an
  explicit v1 simplification that avoids introducing a separate forecasting
  curve or reset schedule engine.
- Retail NMDs are represented with behavioral pseudo-cashflows:
  a fast-decaying non-core portion and a longer-dated core portion
- Cash / reserves are treated as very short-dated positions
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.balance_sheet.instruments import Position
from src.config import EngineConfig, add_months, year_fraction
from src.irrbb.shocks import rate_shift_decimal


def _build_periods(
    start_date: date,
    maturity_date: date,
    step_months: int,
) -> list[tuple[date, date]]:
    """Build future accrual periods from a start date to maturity."""

    periods: list[tuple[date, date]] = []
    period_start = start_date

    while period_start < maturity_date:
        period_end = add_months(period_start, step_months)
        if period_end > maturity_date:
            period_end = maturity_date
        periods.append((period_start, period_end))
        period_start = period_end

    return periods


def _cashflow_row(
    position: Position,
    cashflow_date: date,
    principal: float,
    interest: float,
    is_repricing_event: bool,
    accrual_start_date: date,
    accrual_years: float,
    balance: float,
    base_rate: float,
    segment: str,
) -> dict[str, object]:
    """Create one standardized cashflow row."""

    total_cashflow = principal + interest
    return {
        "date": cashflow_date,
        "principal": principal,
        "interest": interest,
        "total_cashflow": total_cashflow,
        "is_repricing_event": is_repricing_event,
        "accrual_start_date": accrual_start_date,
        "accrual_years": accrual_years,
        "balance": balance,
        "applied_rate": base_rate,
        "base_rate": position.base_rate,
        "funding_spread": position.spread,
        "stress_spread_addon": position.stress_spread_addon,
        "rate_type": position.rate_type,
        "repricing_freq_months": position.repricing_freq_months,
        "product_type": position.product_type,
        "segment": segment,
    }


def _generate_contractual_cashflows(
    position: Position,
    as_of_date: date,
    payment_frequency_months: int,
    repricing_events: bool,
) -> list[dict[str, object]]:
    """Generate simple bullet cashflows for fixed or floating instruments.

    For floating-rate products we intentionally use ``payment_frequency_months``
    equal to the repricing frequency. That means each coupon row represents one
    reset interval and carries its own ``applied_rate`` field for downstream
    shocked projections.
    """

    rows: list[dict[str, object]] = []
    for period_start, period_end in _build_periods(
        start_date=position.start_date,
        maturity_date=position.maturity_date,
        step_months=payment_frequency_months,
    ):
        if period_end <= as_of_date:
            continue

        accrual = year_fraction(period_start, period_end)
        interest = position.notional * position.contractual_rate * accrual
        principal = position.notional if period_end == position.maturity_date else 0.0
        rows.append(
            _cashflow_row(
                position=position,
                cashflow_date=period_end,
                principal=principal,
                interest=interest,
                is_repricing_event=repricing_events and period_start > as_of_date,
                accrual_start_date=period_start,
                accrual_years=accrual,
                balance=position.notional,
                base_rate=position.contractual_rate,
                segment="contractual",
            )
        )

    return rows


def _generate_retail_nmd_cashflows(
    position: Position,
    as_of_date: date,
    assumptions: EngineConfig,
) -> list[dict[str, object]]:
    """Generate behavioral pseudo cashflows for retail non-maturity deposits."""

    rows: list[dict[str, object]] = []
    stable_share = assumptions.behavioral.non_maturity_deposit_stable_share
    core_balance = position.notional * stable_share
    non_core_balance = position.notional - core_balance
    non_core_horizon_months = max(assumptions.behavioral.cash_repricing_months * 3, 1)
    core_horizon_months = max(int(round(assumptions.behavioral.retail_nmd_duration_years * 12)), 1)

    monthly_rate = position.contractual_rate

    outstanding_non_core = non_core_balance
    for month_number in range(1, non_core_horizon_months + 1):
        period_start = add_months(as_of_date, month_number - 1)
        period_end = add_months(as_of_date, month_number)
        principal = outstanding_non_core / (non_core_horizon_months - month_number + 1)
        accrual = year_fraction(period_start, period_end)
        interest = outstanding_non_core * monthly_rate * accrual
        rows.append(
            _cashflow_row(
                position=position,
                cashflow_date=period_end,
                principal=principal,
                interest=interest,
                is_repricing_event=True,
                accrual_start_date=period_start,
                accrual_years=accrual,
                balance=outstanding_non_core,
                base_rate=monthly_rate,
                segment="non_core",
            )
        )
        outstanding_non_core -= principal

    for month_number in range(1, core_horizon_months + 1):
        period_start = add_months(as_of_date, month_number - 1)
        period_end = add_months(as_of_date, month_number)
        accrual = year_fraction(period_start, period_end)
        principal = core_balance if month_number == core_horizon_months else 0.0
        rows.append(
            _cashflow_row(
                position=position,
                cashflow_date=period_end,
                principal=principal,
                interest=core_balance * monthly_rate * accrual,
                is_repricing_event=True,
                accrual_start_date=period_start,
                accrual_years=accrual,
                balance=core_balance,
                base_rate=monthly_rate,
                segment="core",
            )
        )

    return rows


def _generate_cash_reserve_cashflows(
    position: Position,
    as_of_date: date,
    assumptions: EngineConfig,
) -> list[dict[str, object]]:
    """Generate short-dated cash or reserve cashflows."""

    effective_end_date = min(
        position.maturity_date,
        add_months(as_of_date, assumptions.behavioral.cash_repricing_months),
    )
    if effective_end_date <= as_of_date:
        return []

    accrual = year_fraction(as_of_date, effective_end_date)
    return [
        _cashflow_row(
            position=position,
            cashflow_date=effective_end_date,
            principal=position.notional,
            interest=position.notional * position.contractual_rate * accrual,
            is_repricing_event=False,
            accrual_start_date=as_of_date,
            accrual_years=accrual,
            balance=position.notional,
            base_rate=position.contractual_rate,
            segment="cash",
        )
    ]


def generate_cashflows(
    position: Position,
    as_of_date: date,
    assumptions: EngineConfig,
) -> pd.DataFrame:
    """Generate future cashflows for one position.

    Required output columns:
    - ``date``
    - ``principal``
    - ``interest``
    - ``total_cashflow``
    - ``is_repricing_event``
    - ``applied_rate``
    - ``rate_type``
    - ``repricing_freq_months``
    - ``product_type``

    Additional columns are included to make downstream NII and EVE logic
    explicit and reusable.
    """

    if position.is_equity:
        return pd.DataFrame(
            columns=[
                "date",
                "principal",
                "interest",
                "total_cashflow",
                "is_repricing_event",
                "accrual_start_date",
                "accrual_years",
                "balance",
                "applied_rate",
                "base_rate",
                "funding_spread",
                "stress_spread_addon",
                "rate_type",
                "repricing_freq_months",
                "product_type",
                "segment",
            ]
        )

    if position.product_type == "retail_nmd":
        rows = _generate_retail_nmd_cashflows(position, as_of_date, assumptions)
    elif position.product_type in {"reserves/cash", "cash", "reserves"}:
        rows = _generate_cash_reserve_cashflows(position, as_of_date, assumptions)
    elif position.rate_type == "floating":
        rows = _generate_contractual_cashflows(
            position=position,
            as_of_date=as_of_date,
            payment_frequency_months=position.repricing_freq_months or 3,
            repricing_events=True,
        )
    else:
        rows = _generate_contractual_cashflows(
            position=position,
            as_of_date=as_of_date,
            payment_frequency_months=12,
            repricing_events=False,
        )

    cashflows = pd.DataFrame(rows)
    if cashflows.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "principal",
                "interest",
                "total_cashflow",
                "is_repricing_event",
                "accrual_start_date",
                "accrual_years",
                "balance",
                "applied_rate",
                "base_rate",
                "funding_spread",
                "stress_spread_addon",
                "rate_type",
                "repricing_freq_months",
                "product_type",
                "segment",
            ]
        )

    return cashflows.sort_values("date").reset_index(drop=True)


def calculate_shocked_applied_rate(
    product_type: str,
    rate_type: str,
    cashflow: pd.Series,
    as_of_date: date,
    assumptions: EngineConfig,
    shock,
    shock_retail_nmd: bool,
    funding_spread_addons: dict[str, float] | None = None,
) -> float:
    """Return a row-level shocked applied rate.

    Simplified treatment:
    - Fixed-rate contractual rows keep their original applied rate.
    - Floating-rate rows only move once the row is marked as a repricing event.
    - Retail NMD rows can optionally reprice using the configured deposit beta.
    - Treasury funding products can also pick up a deterministic stress spread
      add-on to represent wholesale funding pressure.
    """

    applied_rate = float(cashflow["applied_rate"])
    default_stress_spread_addon = float(cashflow.get("stress_spread_addon", 0.0))
    stress_spread_addon = (
        funding_spread_addons.get(product_type, default_stress_spread_addon)
        if funding_spread_addons is not None
        else default_stress_spread_addon
    )

    if product_type == "retail_nmd":
        if not shock_retail_nmd:
            return applied_rate
        term_years = max(year_fraction(as_of_date, cashflow["date"]), 1.0 / 12.0)
        deposit_beta = assumptions.behavioral.retail_nmd_beta
        return applied_rate + rate_shift_decimal(shock, term_years) * deposit_beta

    stressed_rate = applied_rate
    if product_type in {"interbank_borrowing", "repo_funding", "term_funding"}:
        stressed_rate += stress_spread_addon

    if rate_type != "floating" or not bool(cashflow["is_repricing_event"]):
        return stressed_rate

    term_years = max(year_fraction(as_of_date, cashflow["date"]), 1.0 / 12.0)
    return stressed_rate + rate_shift_decimal(shock, term_years)
