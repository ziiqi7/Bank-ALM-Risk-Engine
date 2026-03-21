"""Repricing gap reporting."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio
from src.config import EngineConfig


def _bucket_label(edges: Iterable[int], months: int) -> str:
    lower_bound = 0
    for edge in edges:
        if months <= edge:
            if lower_bound == 0:
                return f"0-{edge}m"
            return f"{lower_bound + 1}-{edge}m"
        lower_bound = edge
    return f">{lower_bound}m"


def compute_repricing_gap(portfolio: Portfolio, config: EngineConfig) -> pd.DataFrame:
    """Aggregate a basic repricing gap table."""

    rows: list[dict[str, float | str]] = []
    for position in portfolio.positions:
        if position.is_equity:
            continue

        repricing_months = position.effective_repricing_months(
            as_of_date=config.as_of_date,
            behavioral=config.behavioral,
        )
        bucket = _bucket_label(config.repricing_buckets_months, repricing_months)
        rows.append(
            {
                "bucket": bucket,
                "asset_amount": position.notional if position.is_asset else 0.0,
                "liability_amount": position.notional if position.is_liability else 0.0,
            }
        )

    gap_table = (
        pd.DataFrame(rows)
        .groupby("bucket", sort=False)[["asset_amount", "liability_amount"]]
        .sum()
        .reset_index()
    )
    gap_table["gap"] = gap_table["asset_amount"] - gap_table["liability_amount"]
    gap_table["cumulative_gap"] = gap_table["gap"].cumsum()
    return gap_table
