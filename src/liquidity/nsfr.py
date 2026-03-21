"""Simplified NSFR calculations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig


@dataclass(frozen=True)
class NsfrResult:
    """Container for NSFR results."""

    available_stable_funding: float
    required_stable_funding: float
    ratio: float
    breakdown: pd.DataFrame


def calculate_nsfr(
    portfolio: Portfolio,
    config: EngineConfig,
    deposit_multiplier: float = 1.0,
    wholesale_multiplier: float = 1.0,
) -> NsfrResult:
    """Compute a simplified net stable funding ratio."""

    rows = []
    available = 0.0
    required = 0.0

    for position in portfolio.positions:
        runoff_multiplier = 1.0
        if position.product_type == "retail_nmd":
            runoff_multiplier = 1.0 - min(
                config.liquidity.outflow_rates[
                    "less_stable_retail_nmd"
                    if position.behavioral_category == "retail_nmd_less_stable"
                    else "stable_retail_nmd"
                ]
                * deposit_multiplier,
                1.0,
            )
        elif position.product_type in {"term_deposits", "interbank_borrowing"}:
            runoff_multiplier = 1.0 - min(
                config.liquidity.outflow_rates[position.product_type] * wholesale_multiplier,
                1.0,
            )

        asf_amount = 0.0
        rsf_amount = 0.0
        if position.is_liability or position.is_equity:
            asf_amount = position.notional * position.asf_factor * runoff_multiplier
            available += asf_amount
        elif position.is_asset:
            rsf_amount = position.notional * position.rsf_factor
            required += rsf_amount

        rows.append(
            {
                "position_id": position.position_id,
                "product_type": position.product_type,
                "asf_amount": asf_amount,
                "rsf_amount": rsf_amount,
            }
        )

    breakdown = pd.DataFrame(rows)
    ratio = available / required if required > 0.0 else float("inf")
    return NsfrResult(
        available_stable_funding=available,
        required_stable_funding=required,
        ratio=ratio,
        breakdown=breakdown,
    )
