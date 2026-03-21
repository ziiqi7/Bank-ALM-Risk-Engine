"""12-month NII sensitivity built on shared position cashflows.

Floating-rate handling remains intentionally simple: coupon period equals
repricing period, so each floating row already represents one reset interval.
Shocks therefore work at the row level by replacing the row's ``applied_rate``
when a repricing event is reached. Treasury funding rows can also receive a
deterministic stress spread add-on, which makes unsecured funding costs widen
more than secured repo under stress.
"""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig, add_months
from src.irrbb.cashflows import calculate_shocked_applied_rate, generate_cashflows
from src.irrbb.shocks import RateShock


@dataclass(frozen=True)
class NiiSensitivityResult:
    """Container for NII sensitivity outputs."""

    shock_name: str
    base_nii: float
    shocked_nii: float
    delta_nii: float
    breakdown: pd.DataFrame

    @property
    def total_delta_nii(self) -> float:
        """Backward-compatible alias used by existing reporting code."""

        return self.delta_nii


def _build_nii_cashflow_view(
    position: Position,
    cashflows: pd.DataFrame,
    config: EngineConfig,
    shock: RateShock,
    funding_spread_addons: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Add explicit base and shocked row-level rates and interest amounts.

    Simplified treatment preserved:
    - fixed-rate rows do not reprice within the horizon
    - floating rows only move on repricing-event rows
    - retail NMD rows use the configured deposit beta
    """

    view = cashflows.copy()
    shocked_applied_rates = []
    for _, cashflow in view.iterrows():
        shocked_applied_rates.append(
            calculate_shocked_applied_rate(
                product_type=position.product_type,
                rate_type=position.rate_type,
                cashflow=cashflow,
                as_of_date=config.as_of_date,
                assumptions=config,
                shock=shock,
                shock_retail_nmd=True,
                funding_spread_addons=funding_spread_addons,
            )
        )

    view["base_applied_rate"] = view["applied_rate"].astype(float)
    view["shocked_applied_rate"] = pd.Series(shocked_applied_rates, index=view.index, dtype=float)
    view["stressed_funding_addon"] = view["shocked_applied_rate"] - view["base_applied_rate"]
    view["base_interest"] = view["balance"] * view["base_applied_rate"] * view["accrual_years"]
    view["shocked_interest"] = view["balance"] * view["shocked_applied_rate"] * view["accrual_years"]
    view["delta_interest"] = view["shocked_interest"] - view["base_interest"]
    return view


def calculate_12m_nii_sensitivity(
    portfolio: Portfolio,
    config: EngineConfig,
    shock: RateShock,
    funding_spread_addons: dict[str, float] | None = None,
) -> NiiSensitivityResult:
    """Estimate 12M NII from the next-12-month shared cashflows.

    Base NII is the signed sum of contractual or behavioral interest cashflows
    over the next 12 months. Shocked NII keeps the schedule unchanged but
    recalculates row-level interest as:

    ``balance * shocked_applied_rate * accrual_years``
    """

    breakdown_rows: list[dict[str, float | str]] = []
    base_nii = 0.0
    shocked_nii = 0.0
    horizon_end = add_months(config.as_of_date, 12)

    for position in portfolio.positions:
        if position.is_equity:
            continue

        sign = 1.0 if position.is_asset else -1.0
        cashflows = generate_cashflows(position, config.as_of_date, config)
        next_12m_cashflows = cashflows[cashflows["date"] <= horizon_end].copy()

        if next_12m_cashflows.empty:
            breakdown_rows.append(
                {
                    "position_id": position.position_id,
                    "product_type": position.product_type,
                    "balance_side": position.balance_side,
                    "base_nii": 0.0,
                    "shocked_nii": 0.0,
                    "delta_nii": 0.0,
                    "repricing_cashflows": 0,
                }
            )
            continue

        nii_cashflows = _build_nii_cashflow_view(
            position,
            next_12m_cashflows,
            config,
            shock,
            funding_spread_addons=funding_spread_addons,
        )
        base_position_nii = sign * float(nii_cashflows["base_interest"].sum())
        shocked_position_nii = sign * float(nii_cashflows["shocked_interest"].sum())
        delta_position_nii = shocked_position_nii - base_position_nii
        base_nii += base_position_nii
        shocked_nii += shocked_position_nii

        breakdown_rows.append(
            {
                "position_id": position.position_id,
                "product_type": position.product_type,
                "balance_side": position.balance_side,
                "base_nii": base_position_nii,
                "shocked_nii": shocked_position_nii,
                "delta_nii": delta_position_nii,
                "repricing_cashflows": int(nii_cashflows["is_repricing_event"].sum()),
                "avg_base_applied_rate": float(nii_cashflows["base_applied_rate"].mean()),
                "avg_shocked_applied_rate": float(nii_cashflows["shocked_applied_rate"].mean()),
                "avg_funding_spread": float(nii_cashflows["funding_spread"].mean()),
                "avg_stress_spread_addon": float(nii_cashflows["stress_spread_addon"].mean()),
            }
        )

    breakdown = pd.DataFrame(breakdown_rows)
    return NiiSensitivityResult(
        shock_name=shock.name,
        base_nii=base_nii,
        shocked_nii=shocked_nii,
        delta_nii=shocked_nii - base_nii,
        breakdown=breakdown,
    )


def run_nii_sensitivity_grid(
    portfolio: Portfolio,
    config: EngineConfig,
    shocks: dict[str, RateShock],
    funding_spread_addons: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Run a compact NII summary for multiple shocks."""

    rows = []
    for shock_name, shock in shocks.items():
        result = calculate_12m_nii_sensitivity(
            portfolio,
            config,
            shock,
            funding_spread_addons=funding_spread_addons,
        )
        rows.append(
            {
                "shock": shock_name,
                "base_nii_12m": result.base_nii,
                "shocked_nii_12m": result.shocked_nii,
                "delta_nii_12m": result.delta_nii,
            }
        )
    return pd.DataFrame(rows)
