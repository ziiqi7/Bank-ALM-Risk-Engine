"""Contractual and behavioral cash-gap ladder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig


@dataclass(frozen=True)
class CashGapResult:
    """Container for cash-gap ladder outputs."""

    ladder: pd.DataFrame
    details: pd.DataFrame
    survival_horizon_days: int
    min_cumulative_gap: float


def _bucket_label(edges: Iterable[int], days: int) -> str:
    lower_bound = 0
    for edge in edges:
        if days <= edge:
            if lower_bound == 0:
                return f"0-{edge}d"
            return f"{lower_bound + 1}-{edge}d"
        lower_bound = edge
    return f">{lower_bound}d"


def calculate_cash_gap(
    portfolio: Portfolio,
    config: EngineConfig,
    deposit_multiplier: float = 1.0,
    inflow_multiplier: float = 1.0,
) -> CashGapResult:
    """Build a simple contractual and behavioral cash-gap ladder."""

    detail_rows: list[dict[str, float | str]] = []
    stable_share = config.behavioral.non_maturity_deposit_stable_share

    for position in portfolio.positions:
        if position.is_equity:
            continue

        maturity_days = max((position.maturity_date - config.as_of_date).days, 1)

        if position.product_type == "retail_nmd":
            unstable_balance = position.notional * (1.0 - stable_share) * deposit_multiplier
            stable_balance = position.notional - unstable_balance
            detail_rows.append(
                {
                    "position_id": position.position_id,
                    "bucket": _bucket_label(config.cash_gap_buckets_days, 30),
                    "inflow": 0.0,
                    "outflow": unstable_balance,
                }
            )
            detail_rows.append(
                {
                    "position_id": position.position_id,
                    "bucket": _bucket_label(
                        config.cash_gap_buckets_days,
                        int(config.behavioral.retail_nmd_duration_years * 365),
                    ),
                    "inflow": 0.0,
                    "outflow": stable_balance,
                }
            )
            continue

        if position.product_type == "fixed_mortgages":
            prepaid_amount = position.notional * config.behavioral.fixed_mortgage_prepayment_pct * inflow_multiplier
            remaining_amount = position.notional - prepaid_amount
            detail_rows.append(
                {
                    "position_id": position.position_id,
                    "bucket": _bucket_label(config.cash_gap_buckets_days, 180),
                    "inflow": prepaid_amount,
                    "outflow": 0.0,
                }
            )
            detail_rows.append(
                {
                    "position_id": position.position_id,
                    "bucket": _bucket_label(config.cash_gap_buckets_days, maturity_days),
                    "inflow": remaining_amount,
                    "outflow": 0.0,
                }
            )
            continue

        detail_rows.append(
            {
                "position_id": position.position_id,
                "bucket": _bucket_label(config.cash_gap_buckets_days, maturity_days),
                "inflow": position.notional if position.is_asset else 0.0,
                "outflow": position.notional if position.is_liability else 0.0,
            }
        )

    details = pd.DataFrame(detail_rows)
    ladder = details.groupby("bucket", sort=False)[["inflow", "outflow"]].sum().reset_index()
    ordered_buckets = [_bucket_label(config.cash_gap_buckets_days, edge) for edge in config.cash_gap_buckets_days]
    ordered_buckets.append(f">{config.cash_gap_buckets_days[-1]}d")
    bucket_order = {bucket: index for index, bucket in enumerate(ordered_buckets)}
    ladder["bucket_order"] = ladder["bucket"].map(bucket_order).fillna(len(bucket_order)).astype(int)
    ladder = ladder.sort_values("bucket_order").drop(columns="bucket_order").reset_index(drop=True)
    ladder["net_gap"] = ladder["inflow"] - ladder["outflow"]
    ladder["cumulative_gap"] = ladder["net_gap"].cumsum()
    min_cumulative_gap = float(ladder["cumulative_gap"].min())

    survival_horizon_days = 0
    for bucket, cumulative_gap in zip(ladder["bucket"], ladder["cumulative_gap"], strict=False):
        if cumulative_gap < 0:
            break
        if bucket.startswith(">"):
            survival_horizon_days = config.cash_gap_buckets_days[-1]
        else:
            survival_horizon_days = int(bucket.split("-")[1].removesuffix("d"))

    return CashGapResult(
        ladder=ladder,
        details=details,
        survival_horizon_days=survival_horizon_days,
        min_cumulative_gap=min_cumulative_gap,
    )
