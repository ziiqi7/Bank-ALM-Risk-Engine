"""Summary tables and lightweight chart helpers."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def summary_table(metrics: dict[str, float]) -> pd.DataFrame:
    """Turn a metric dictionary into a tidy summary table."""

    return pd.DataFrame(
        [{"metric": metric_name, "value": metric_value} for metric_name, metric_value in metrics.items()]
    )


def comparison_table(pre_metrics: pd.DataFrame, post_metrics: pd.DataFrame) -> pd.DataFrame:
    """Build a pre-action vs post-action comparison table."""

    table = pre_metrics.rename(columns={"value": "pre_action"}).merge(
        post_metrics.rename(columns={"value": "post_action"}),
        on="metric",
    )
    table["delta_improvement"] = table["post_action"] - table["pre_action"]
    return table


def action_log_table(action_log: pd.DataFrame) -> pd.DataFrame:
    """Return a lightly formatted action log table."""

    if action_log.empty:
        return pd.DataFrame(columns=["step", "action_name", "amount", "trigger", "comment"])
    preferred_order = [
        "step",
        "action_name",
        "amount",
        "trigger",
        "funding_stress_spread_used",
        "delta_nii_before",
        "delta_nii_after",
        "delta_nii_change",
        "delta_eve_before",
        "delta_eve_after",
        "lcr_before",
        "lcr_after",
        "nsfr_before",
        "nsfr_after",
        "survival_before_days",
        "survival_after_days",
        "comment",
    ]
    existing_columns = [column for column in preferred_order if column in action_log.columns]
    remaining_columns = [column for column in action_log.columns if column not in existing_columns]
    return action_log[[*existing_columns, *remaining_columns]].copy()


def attribution_table(portfolio_frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate a simple notional attribution by product type and balance side."""

    return (
        portfolio_frame.groupby(["product_type", "balance_side"], as_index=False)["notional"]
        .sum()
        .sort_values(["balance_side", "notional"], ascending=[True, False])
        .reset_index(drop=True)
    )


def eve_attribution_table(eve_breakdown: pd.DataFrame, group_column: str = "product_type") -> pd.DataFrame:
    """Aggregate EVE sensitivity by product type or another available segment."""

    return (
        eve_breakdown.groupby(group_column, as_index=False)[["base_pv", "shocked_pv", "delta_eve"]]
        .sum()
        .sort_values("delta_eve")
        .reset_index(drop=True)
    )


def save_bar_chart(
    table: pd.DataFrame,
    category_column: str,
    value_column: str,
    title: str,
    output_path: str | Path,
) -> Path:
    """Save a simple bar chart for a bucketed metric table."""

    chart_path = Path(output_path)
    chart_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 4))
    plt.bar(table[category_column], table[value_column], color="#1f77b4")
    plt.title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(chart_path, dpi=160)
    plt.close()
    return chart_path
