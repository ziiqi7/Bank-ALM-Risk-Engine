"""Stress execution across IRRBB and liquidity metrics."""

from __future__ import annotations

import pandas as pd

from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig
from src.irrbb.eve import calculate_eve_sensitivity
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import RateShock
from src.liquidity.cash_gap import calculate_cash_gap
from src.liquidity.lcr import calculate_lcr
from src.liquidity.nsfr import calculate_nsfr
from src.stress.scenarios import StressScenario


def run_stress_tests(
    portfolio: Portfolio,
    config: EngineConfig,
    scenarios: dict[str, StressScenario],
) -> pd.DataFrame:
    """Run a small integrated stress pack."""

    rows = []
    for scenario_name, scenario in scenarios.items():
        rate_shock = RateShock(
            name=f"{scenario_name}_parallel",
            kind="parallel",
            parallel_bps=scenario.parallel_rate_bps,
            description=f"{scenario_name} stress parallel shock",
        )
        nii_result = calculate_12m_nii_sensitivity(
            portfolio,
            config,
            rate_shock,
            funding_spread_addons=scenario.funding_spread_addons,
        )
        eve_result = calculate_eve_sensitivity(portfolio, config, rate_shock)
        lcr_result = calculate_lcr(
            portfolio,
            config,
            deposit_multiplier=scenario.deposit_outflow_multiplier,
            wholesale_multiplier=scenario.wholesale_outflow_multiplier,
            inflow_multiplier=scenario.inflow_multiplier,
            extra_haircut=scenario.hqla_haircut_addon,
        )
        nsfr_result = calculate_nsfr(
            portfolio,
            config,
            deposit_multiplier=scenario.deposit_outflow_multiplier,
            wholesale_multiplier=scenario.wholesale_outflow_multiplier,
        )
        cash_gap_result = calculate_cash_gap(
            portfolio,
            config,
            deposit_multiplier=scenario.deposit_outflow_multiplier,
            inflow_multiplier=scenario.inflow_multiplier,
        )
        rows.append(
            {
                "scenario": scenario_name,
                "delta_nii_12m": nii_result.total_delta_nii,
                "delta_eve": eve_result.delta_eve,
                "lcr": lcr_result.ratio,
                "nsfr": nsfr_result.ratio,
                "min_cumulative_cash_gap": float(cash_gap_result.ladder["cumulative_gap"].min()),
            }
        )

    return pd.DataFrame(rows)
