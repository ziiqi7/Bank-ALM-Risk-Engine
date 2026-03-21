"""Configuration loading and shared time helpers."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


def parse_date(value: str | date) -> date:
    """Parse ISO date strings into ``date`` objects."""

    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def add_months(base_date: date, months: int) -> date:
    """Add calendar months without external dependencies."""

    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def year_fraction(start_date: date, end_date: date) -> float:
    """Return a simple ACT/365 year fraction."""

    return max((end_date - start_date).days, 0) / 365.0


@dataclass(frozen=True)
class StandardShockConfig:
    """Standardized rate shock magnitudes in basis points."""

    parallel_up_bps: float
    parallel_down_bps: float
    short_up_bps: float
    short_down_bps: float
    steepener_short_bps: float
    steepener_long_bps: float
    flattener_short_bps: float
    flattener_long_bps: float


@dataclass(frozen=True)
class BehavioralAssumptions:
    """Behavioral overlays used in simplified IRRBB and liquidity views."""

    retail_nmd_repricing_months: int
    retail_nmd_duration_years: float
    retail_nmd_beta: float
    non_maturity_deposit_stable_share: float
    term_deposit_early_withdrawal_pct: float
    fixed_mortgage_prepayment_pct: float
    cash_repricing_months: int


@dataclass(frozen=True)
class LiquidityAssumptions:
    """Liquidity assumptions for simplified LCR and NSFR views."""

    hqla_haircuts: dict[str, float]
    outflow_rates: dict[str, float]
    inflow_rates: dict[str, float]
    inflow_cap_pct: float


@dataclass(frozen=True)
class StressScenarioConfig:
    """Scenario-level stress overlays."""

    name: str
    deposit_outflow_multiplier: float
    wholesale_outflow_multiplier: float
    inflow_multiplier: float
    hqla_haircut_addon: float
    parallel_rate_bps: float
    funding_spread_addons: dict[str, float] | None = None


@dataclass(frozen=True)
class ManagementActionConfig:
    """Thresholds and capacities for deterministic management actions."""

    lcr_threshold: float
    survival_horizon_days_threshold: int
    nsfr_threshold: float
    eve_tolerance: float
    securities_liquidation_capacity: float
    repo_capacity: float
    repo_advance_rate: float
    repo_term_months: int
    repo_base_rate: float
    repo_spread: float
    repo_stress_spread_addon: float
    interbank_capacity: float
    interbank_term_months: int
    interbank_base_rate: float
    interbank_spread: float
    interbank_stress_spread_addon: float
    term_funding_capacity: float
    term_funding_term_months: int
    term_funding_base_rate: float
    term_funding_spread: float
    term_funding_stress_spread_addon: float
    loan_growth_reduction_capacity: float
    hedge_capacity: float
    hedge_term_months: int
    hedge_fixed_rate: float


@dataclass(frozen=True)
class EngineConfig:
    """Application configuration loaded from YAML assumptions."""

    as_of_date: date
    repricing_buckets_months: list[int]
    cash_gap_buckets_days: list[int]
    base_discount_rate: float
    standard_shocks: StandardShockConfig
    behavioral: BehavioralAssumptions
    liquidity: LiquidityAssumptions
    stress_scenarios: dict[str, StressScenarioConfig]
    management_actions: ManagementActionConfig


def load_config(path: str | Path) -> EngineConfig:
    """Load YAML assumptions into typed configuration."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)

    stress_scenarios = {
        name: StressScenarioConfig(name=name, **scenario_data)
        for name, scenario_data in raw["stress_scenarios"].items()
    }

    return EngineConfig(
        as_of_date=parse_date(raw["as_of_date"]),
        repricing_buckets_months=list(raw["repricing_buckets_months"]),
        cash_gap_buckets_days=list(raw["cash_gap_buckets_days"]),
        base_discount_rate=float(raw["base_discount_rate"]),
        standard_shocks=StandardShockConfig(**raw["standard_shocks"]),
        behavioral=BehavioralAssumptions(**raw["behavioral_assumptions"]),
        liquidity=LiquidityAssumptions(**raw["liquidity_assumptions"]),
        stress_scenarios=stress_scenarios,
        management_actions=ManagementActionConfig(**raw["management_actions"]),
    )
