"""Stress scenario definitions."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import EngineConfig


@dataclass(frozen=True)
class StressScenario:
    """Stress scenario parameters used across liquidity and IRRBB views."""

    name: str
    deposit_outflow_multiplier: float
    wholesale_outflow_multiplier: float
    inflow_multiplier: float
    hqla_haircut_addon: float
    parallel_rate_bps: float
    funding_spread_addons: dict[str, float] | None = None


def build_stress_scenarios(config: EngineConfig) -> dict[str, StressScenario]:
    """Convert configured stress assumptions into typed scenarios."""

    return {
        name: StressScenario(
            name=scenario.name,
            deposit_outflow_multiplier=scenario.deposit_outflow_multiplier,
            wholesale_outflow_multiplier=scenario.wholesale_outflow_multiplier,
            inflow_multiplier=scenario.inflow_multiplier,
            hqla_haircut_addon=scenario.hqla_haircut_addon,
            parallel_rate_bps=scenario.parallel_rate_bps,
            funding_spread_addons=scenario.funding_spread_addons,
        )
        for name, scenario in config.stress_scenarios.items()
    }
