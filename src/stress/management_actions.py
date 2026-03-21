"""Rule-based management actions and post-action metric recomputation."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig
from src.irrbb.eve import calculate_eve_sensitivity
from src.irrbb.nii import calculate_12m_nii_sensitivity
from src.irrbb.shocks import RateShock
from src.liquidity.cash_gap import CashGapResult, calculate_cash_gap
from src.liquidity.lcr import LcrResult, calculate_lcr
from src.liquidity.nsfr import NsfrResult, calculate_nsfr
from src.stress.scenarios import StressScenario
from src.treasury.contingency_funding import available_contingency_capacity, calculate_funding_need
from src.treasury.money_market import add_hedge_placeholder, issue_term_funding, raise_interbank_funding
from src.treasury.securities import liquidate_level1_securities, repo_level1_hqla


@dataclass(frozen=True)
class StressedMetrics:
    """Compact stressed metric snapshot used before and after actions."""

    total_delta_nii: float
    total_delta_eve: float
    lcr: float
    nsfr: float
    hqla: float
    net_outflows: float
    available_stable_funding: float
    required_stable_funding: float
    survival_horizon_days: int
    min_cumulative_cash_gap: float


@dataclass(frozen=True)
class ManagementActionResult:
    """Result bundle for stressed pre/post-action analysis."""

    pre_action_metrics: pd.DataFrame
    post_action_metrics: pd.DataFrame
    comparison: pd.DataFrame
    action_log: pd.DataFrame
    updated_portfolio: Portfolio
    pre_detail: dict[str, object]
    post_detail: dict[str, object]


def _build_rate_shock(scenario: StressScenario) -> RateShock:
    """Convert a stress scenario into a parallel rate shock."""

    return RateShock(
        name=f"{scenario.name}_parallel",
        kind="parallel",
        parallel_bps=scenario.parallel_rate_bps,
        description=f"{scenario.name} management action stress shock",
    )


def evaluate_stressed_metrics(
    portfolio: Portfolio,
    config: EngineConfig,
    scenario: StressScenario,
) -> tuple[StressedMetrics, dict[str, object]]:
    """Run the integrated stressed metric set for one portfolio."""

    rate_shock = _build_rate_shock(scenario)
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
    metrics = StressedMetrics(
        total_delta_nii=nii_result.total_delta_nii,
        total_delta_eve=eve_result.delta_eve,
        lcr=lcr_result.ratio,
        nsfr=nsfr_result.ratio,
        hqla=lcr_result.hqla,
        net_outflows=lcr_result.net_outflows,
        available_stable_funding=nsfr_result.available_stable_funding,
        required_stable_funding=nsfr_result.required_stable_funding,
        survival_horizon_days=cash_gap_result.survival_horizon_days,
        min_cumulative_cash_gap=cash_gap_result.min_cumulative_gap,
    )
    details = {
        "nii": nii_result,
        "eve": eve_result,
        "lcr": lcr_result,
        "nsfr": nsfr_result,
        "cash_gap": cash_gap_result,
    }
    return metrics, details


def metrics_to_frame(metrics: StressedMetrics) -> pd.DataFrame:
    """Convert a metric snapshot into a tidy table."""

    return pd.DataFrame(
        [
            {"metric": "total_delta_nii", "value": metrics.total_delta_nii},
            {"metric": "total_delta_eve", "value": metrics.total_delta_eve},
            {"metric": "lcr", "value": metrics.lcr},
            {"metric": "nsfr", "value": metrics.nsfr},
            {"metric": "survival_horizon_days", "value": float(metrics.survival_horizon_days)},
            {"metric": "min_cumulative_cash_gap", "value": metrics.min_cumulative_cash_gap},
        ]
    )


def _record_action(
    action_rows: list[dict[str, object]],
    step: int,
    action_name: str,
    amount: float,
    trigger: str,
    metrics_before: StressedMetrics,
    metrics_after: StressedMetrics,
    comment: str,
    funding_cost_used: float | None = None,
) -> None:
    """Append one action-log row."""

    action_rows.append(
        {
            "step": step,
            "action_name": action_name,
            "amount": amount,
            "trigger": trigger,
            "delta_nii_before": metrics_before.total_delta_nii,
            "delta_nii_after": metrics_after.total_delta_nii,
            "delta_nii_change": metrics_after.total_delta_nii - metrics_before.total_delta_nii,
            "funding_stress_spread_used": funding_cost_used,
            "lcr_before": metrics_before.lcr,
            "lcr_after": metrics_after.lcr,
            "nsfr_before": metrics_before.nsfr,
            "nsfr_after": metrics_after.nsfr,
            "survival_before_days": metrics_before.survival_horizon_days,
            "survival_after_days": metrics_after.survival_horizon_days,
            "delta_eve_before": metrics_before.total_delta_eve,
            "delta_eve_after": metrics_after.total_delta_eve,
            "comment": comment,
        }
    )


def _scenario_funding_cost(
    action_name: str,
    config: EngineConfig,
    scenario: StressScenario,
) -> float | None:
    """Return the scenario-specific funding spread used by an action."""

    scenario_addons = scenario.funding_spread_addons or {}
    defaults = config.management_actions
    mapping = {
        "repo_level1_hqla": ("repo_funding", defaults.repo_stress_spread_addon),
        "raise_interbank_funding": ("interbank_borrowing", defaults.interbank_stress_spread_addon),
        "issue_term_funding": ("term_funding", defaults.term_funding_stress_spread_addon),
    }
    if action_name not in mapping:
        return None
    product_type, default_value = mapping[action_name]
    return scenario_addons.get(product_type, default_value)


def _reduce_planned_loan_growth(portfolio: Portfolio, amount: float) -> tuple[Portfolio, float]:
    """Remove planned growth assets if they exist.

    This action is available for future scenario extensions. The base synthetic
    portfolio does not currently include planned growth positions, so the
    realized amount will often be zero.
    """

    if amount <= 0.0:
        return portfolio, 0.0

    remaining = amount
    reduced = 0.0
    positions: list[Position] = []
    for position in portfolio.positions:
        if remaining <= 0.0 or position.product_type != "planned_loan_growth":
            positions.append(position)
            continue

        reduction = min(position.notional, remaining)
        reduced += reduction
        remaining -= reduction
        if position.notional > reduction:
            positions.append(replace(position, notional=position.notional - reduction))

    return Portfolio(positions=positions), reduced


def run_management_action_plan(
    portfolio: Portfolio,
    config: EngineConfig,
    scenario: StressScenario,
) -> ManagementActionResult:
    """Run stressed metrics, apply deterministic actions, and recompute.

    Action sequence:
    1. Liquidate part of level-1 securities into reserves/cash
    2. Repo level-1 HQLA up to capacity
    3. Raise unsecured interbank funding
    4. Issue longer-dated term funding if NSFR remains weak
    5. Reduce planned loan growth if such assets exist
    6. Add a simple hedge placeholder if EVE remains outside tolerance
    """

    pre_metrics, pre_detail = evaluate_stressed_metrics(portfolio, config, scenario)
    current_portfolio = portfolio
    current_metrics = pre_metrics
    current_detail = pre_detail
    action_rows: list[dict[str, object]] = []
    step = 1

    thresholds = config.management_actions
    capacities = available_contingency_capacity(current_portfolio, config)

    if current_metrics.lcr < thresholds.lcr_threshold or (
        current_metrics.survival_horizon_days < thresholds.survival_horizon_days_threshold
    ):
        raw_need = {
            "hqla": current_metrics.hqla,
            "lcr_threshold_amount": thresholds.lcr_threshold * current_metrics.net_outflows,
            "min_cumulative_cash_gap": current_metrics.min_cumulative_cash_gap,
            "available_stable_funding": current_metrics.available_stable_funding,
            "nsfr_threshold_amount": thresholds.nsfr_threshold * current_metrics.required_stable_funding,
        }
        funding_need = calculate_funding_need(raw_need, config)

        liquidation_amount = min(capacities["securities_liquidation"], funding_need.cash_shortfall)
        if liquidation_amount > 0.0:
            updated_portfolio, actual = liquidate_level1_securities(
                current_portfolio,
                config.as_of_date,
                liquidation_amount,
            )
            if actual > 0.0:
                next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
                _record_action(
                    action_rows,
                    step,
                    "use_hqla_buffer",
                    actual,
                    "cash_gap",
                    current_metrics,
                    next_metrics,
                    "Liquidate eligible level-1 securities into reserves/cash.",
                    funding_cost_used=_scenario_funding_cost("use_hqla_buffer", config, scenario),
                )
                current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail
                step += 1

        capacities = available_contingency_capacity(current_portfolio, config)
        raw_need = {
            "hqla": current_metrics.hqla,
            "lcr_threshold_amount": thresholds.lcr_threshold * current_metrics.net_outflows,
            "min_cumulative_cash_gap": current_metrics.min_cumulative_cash_gap,
            "available_stable_funding": current_metrics.available_stable_funding,
            "nsfr_threshold_amount": thresholds.nsfr_threshold * current_metrics.required_stable_funding,
        }
        funding_need = calculate_funding_need(raw_need, config)

        repo_amount = min(capacities["repo_proceeds"], max(funding_need.lcr_shortfall, funding_need.cash_shortfall))
        if repo_amount > 0.0:
            updated_portfolio, actual = repo_level1_hqla(
                current_portfolio,
                config.as_of_date,
                repo_amount,
                thresholds.repo_advance_rate,
                thresholds.repo_term_months,
                thresholds.repo_base_rate,
                thresholds.repo_spread,
                thresholds.repo_stress_spread_addon,
            )
            if actual > 0.0:
                next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
                _record_action(
                    action_rows,
                    step,
                    "repo_level1_hqla",
                    actual,
                    "liquidity",
                    current_metrics,
                    next_metrics,
                    "Raise secured funding against level-1 HQLA.",
                    funding_cost_used=_scenario_funding_cost("repo_level1_hqla", config, scenario),
                )
                current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail
                step += 1

        if current_metrics.lcr < thresholds.lcr_threshold or (
            current_metrics.survival_horizon_days < thresholds.survival_horizon_days_threshold
        ):
            raw_need = {
                "hqla": current_metrics.hqla,
                "lcr_threshold_amount": thresholds.lcr_threshold * current_metrics.net_outflows,
                "min_cumulative_cash_gap": current_metrics.min_cumulative_cash_gap,
                "available_stable_funding": current_metrics.available_stable_funding,
                "nsfr_threshold_amount": thresholds.nsfr_threshold * current_metrics.required_stable_funding,
            }
            funding_need = calculate_funding_need(raw_need, config)
            interbank_amount = min(
                thresholds.interbank_capacity,
                max(funding_need.lcr_shortfall, funding_need.cash_shortfall, 0.0),
            )
            if interbank_amount > 0.0:
                updated_portfolio = raise_interbank_funding(
                    current_portfolio,
                    config.as_of_date,
                    interbank_amount,
                    thresholds.interbank_term_months,
                    thresholds.interbank_base_rate,
                    thresholds.interbank_spread,
                    thresholds.interbank_stress_spread_addon,
                )
                next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
                _record_action(
                    action_rows,
                    step,
                    "raise_interbank_funding",
                    interbank_amount,
                    "liquidity",
                    current_metrics,
                    next_metrics,
                    "Raise unsecured money-market funding and hold proceeds in reserves.",
                    funding_cost_used=_scenario_funding_cost("raise_interbank_funding", config, scenario),
                )
                current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail
                step += 1

    if current_metrics.nsfr < thresholds.nsfr_threshold:
        nsfr_gap = max(
            thresholds.nsfr_threshold * current_metrics.required_stable_funding - current_metrics.available_stable_funding,
            0.0,
        )
        term_amount = min(thresholds.term_funding_capacity, nsfr_gap)
        if term_amount > 0.0:
            updated_portfolio = issue_term_funding(
                current_portfolio,
                config.as_of_date,
                term_amount,
                thresholds.term_funding_term_months,
                thresholds.term_funding_base_rate,
                thresholds.term_funding_spread,
                thresholds.term_funding_stress_spread_addon,
            )
            next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
            _record_action(
                action_rows,
                step,
                "issue_term_funding",
                term_amount,
                "nsfr",
                current_metrics,
                next_metrics,
                "Add longer-dated fixed funding to improve stable funding.",
                funding_cost_used=_scenario_funding_cost("issue_term_funding", config, scenario),
            )
            current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail
            step += 1

    if current_metrics.survival_horizon_days < thresholds.survival_horizon_days_threshold:
        reduction_amount = min(thresholds.loan_growth_reduction_capacity, max(-current_metrics.min_cumulative_cash_gap, 0.0))
        updated_portfolio, actual = _reduce_planned_loan_growth(current_portfolio, reduction_amount)
        if actual > 0.0:
            next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
            _record_action(
                action_rows,
                step,
                "reduce_loan_growth",
                actual,
                "cash_gap",
                current_metrics,
                next_metrics,
                "Remove planned asset expansion from the stressed balance sheet.",
                funding_cost_used=_scenario_funding_cost("reduce_loan_growth", config, scenario),
            )
            current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail
            step += 1

    if abs(current_metrics.total_delta_eve) > thresholds.eve_tolerance:
        hedge_amount = min(thresholds.hedge_capacity, abs(current_metrics.total_delta_eve) - thresholds.eve_tolerance)
        direction = "pay_fixed" if current_metrics.total_delta_eve < 0 else "receive_fixed"
        if hedge_amount > 0.0:
            updated_portfolio = add_hedge_placeholder(
                current_portfolio,
                config.as_of_date,
                hedge_amount,
                direction,
                thresholds.hedge_term_months,
                thresholds.hedge_fixed_rate,
            )
            next_metrics, next_detail = evaluate_stressed_metrics(updated_portfolio, config, scenario)
            _record_action(
                action_rows,
                step,
                f"{direction}_hedge_placeholder",
                hedge_amount,
                "eve",
                current_metrics,
                next_metrics,
                "Add a simplified hedge placeholder rather than pricing a derivative.",
                funding_cost_used=_scenario_funding_cost(f"{direction}_hedge_placeholder", config, scenario),
            )
            current_portfolio, current_metrics, current_detail = updated_portfolio, next_metrics, next_detail

    post_metrics = metrics_to_frame(current_metrics)
    comparison = (
        metrics_to_frame(pre_metrics)
        .rename(columns={"value": "pre_action"})
        .merge(post_metrics.rename(columns={"value": "post_action"}), on="metric")
    )
    comparison["delta_improvement"] = comparison["post_action"] - comparison["pre_action"]

    return ManagementActionResult(
        pre_action_metrics=metrics_to_frame(pre_metrics),
        post_action_metrics=post_metrics,
        comparison=comparison,
        action_log=pd.DataFrame(action_rows),
        updated_portfolio=current_portfolio,
        pre_detail=pre_detail,
        post_detail=current_detail,
    )
