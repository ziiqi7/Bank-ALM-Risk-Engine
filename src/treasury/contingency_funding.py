"""Capacity and shortfall helpers for contingency funding decisions."""

from __future__ import annotations

from dataclasses import dataclass

from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig
from src.treasury.securities import level1_security_capacity


@dataclass(frozen=True)
class FundingNeed:
    """Simple summary of stressed liquidity and funding needs."""

    lcr_shortfall: float
    cash_shortfall: float
    nsfr_shortfall: float


def calculate_funding_need(metrics: dict[str, float], config: EngineConfig) -> FundingNeed:
    """Translate stressed metrics into simple action sizing needs."""

    lcr_shortfall = max(metrics["lcr_threshold_amount"] - metrics["hqla"], 0.0)
    cash_shortfall = max(-metrics["min_cumulative_cash_gap"], 0.0)
    nsfr_shortfall = max(metrics["nsfr_threshold_amount"] - metrics["available_stable_funding"], 0.0)
    return FundingNeed(
        lcr_shortfall=lcr_shortfall,
        cash_shortfall=cash_shortfall,
        nsfr_shortfall=nsfr_shortfall,
    )


def available_contingency_capacity(portfolio: Portfolio, config: EngineConfig) -> dict[str, float]:
    """Return simple treasury action capacities."""

    return {
        "securities_liquidation": min(
            config.management_actions.securities_liquidation_capacity,
            level1_security_capacity(portfolio),
        ),
        "repo_proceeds": min(
            config.management_actions.repo_capacity,
            level1_security_capacity(portfolio) * config.management_actions.repo_advance_rate,
        ),
        "interbank": config.management_actions.interbank_capacity,
        "term_funding": config.management_actions.term_funding_capacity,
        "loan_growth_reduction": config.management_actions.loan_growth_reduction_capacity,
        "hedge": config.management_actions.hedge_capacity,
    }
