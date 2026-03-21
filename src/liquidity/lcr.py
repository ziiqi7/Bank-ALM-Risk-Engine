"""Simplified LCR calculations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig
from src.liquidity.hqla import calculate_hqla_stock


@dataclass(frozen=True)
class LcrResult:
    """Container for LCR results."""

    hqla: float
    outflows: float
    inflows: float
    net_outflows: float
    ratio: float
    breakdown: pd.DataFrame


def _outflow_rate(position: Position, config: EngineConfig) -> float:
    rates = config.liquidity.outflow_rates
    if position.product_type == "retail_nmd":
        if position.behavioral_category == "retail_nmd_less_stable":
            return rates["less_stable_retail_nmd"]
        return rates["stable_retail_nmd"]
    if position.product_type in {"term_deposits", "term_funding"}:
        return rates["term_deposits"]
    if position.product_type in {"interbank_borrowing", "repo_funding"}:
        return rates["interbank_borrowing"]
    return 0.0


def _inflow_rate(position: Position, config: EngineConfig) -> float:
    return config.liquidity.inflow_rates.get(position.product_type, 0.0)


def calculate_lcr(
    portfolio: Portfolio,
    config: EngineConfig,
    deposit_multiplier: float = 1.0,
    wholesale_multiplier: float = 1.0,
    inflow_multiplier: float = 1.0,
    extra_haircut: float = 0.0,
) -> LcrResult:
    """Compute a simplified liquidity coverage ratio.

    The numerator uses unencumbered HQLA only. Repo proceeds held as cash are
    still eligible, while encumbered collateral is excluded.
    """

    hqla, _ = calculate_hqla_stock(portfolio, config, extra_haircut=extra_haircut)
    rows = []

    for position in portfolio.positions:
        outflow = 0.0
        inflow = 0.0

        if position.is_liability:
            within_30d = position.months_to_maturity(config.as_of_date) <= 1
            multiplier = wholesale_multiplier if position.liquidity_category == "wholesale" else deposit_multiplier
            if position.product_type == "retail_nmd" or within_30d:
                outflow = position.notional * _outflow_rate(position, config) * multiplier
        elif position.is_asset and position.months_to_maturity(config.as_of_date) <= 1:
            inflow = position.notional * _inflow_rate(position, config) * inflow_multiplier

        rows.append(
            {
                "position_id": position.position_id,
                "product_type": position.product_type,
                "outflow": outflow,
                "inflow": inflow,
            }
        )

    breakdown = pd.DataFrame(rows)
    total_outflows = float(breakdown["outflow"].sum())
    raw_inflows = float(breakdown["inflow"].sum())
    capped_inflows = min(raw_inflows, total_outflows * config.liquidity.inflow_cap_pct)
    net_outflows = max(total_outflows - capped_inflows, 1e-9)
    ratio = hqla / net_outflows if net_outflows > 0.0 else float("inf")

    return LcrResult(
        hqla=hqla,
        outflows=total_outflows,
        inflows=capped_inflows,
        net_outflows=net_outflows,
        ratio=ratio,
        breakdown=breakdown,
    )
