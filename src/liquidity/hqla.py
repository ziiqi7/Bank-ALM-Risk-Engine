"""HQLA stock calculations."""

from __future__ import annotations

import pandas as pd

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig


def hqla_adjusted_amount(position: Position, config: EngineConfig, extra_haircut: float = 0.0) -> float:
    """Apply a simple HQLA haircut schedule.

    Simplification: encumbered collateral remains on balance sheet but is
    excluded from the freely available HQLA numerator.
    """

    if not position.is_asset or position.encumbered:
        return 0.0

    base_haircut = config.liquidity.hqla_haircuts.get(position.hqla_level, 1.0)
    effective_haircut = min(max(base_haircut + extra_haircut, 0.0), 1.0)
    return position.notional * (1.0 - effective_haircut)


def calculate_hqla_stock(
    portfolio: Portfolio,
    config: EngineConfig,
    extra_haircut: float = 0.0,
) -> tuple[float, pd.DataFrame]:
    """Return total HQLA stock and a position-level breakdown."""

    rows = []
    for position in portfolio.positions:
        adjusted_amount = hqla_adjusted_amount(position, config, extra_haircut=extra_haircut)
        rows.append(
            {
                "position_id": position.position_id,
                "product_type": position.product_type,
                "hqla_level": position.hqla_level,
                "encumbered": position.encumbered,
                "adjusted_hqla": adjusted_amount,
            }
        )
    breakdown = pd.DataFrame(rows)
    return float(breakdown["adjusted_hqla"].sum()), breakdown
