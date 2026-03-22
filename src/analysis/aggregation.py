"""Aggregate batch ensemble results into profile-level summaries and simple charts."""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SUMMARY_METRICS = [
    "delta_nii_parallel_up",
    "delta_eve_parallel_up",
    "stressed_lcr",
    "stressed_survival_horizon_days",
    "post_action_lcr",
    "post_action_delta_nii",
]


def summarize_ensemble_results(results: pd.DataFrame) -> pd.DataFrame:
    """Create profile-level summary statistics for key ensemble metrics."""

    rows: list[dict[str, float | str]] = []
    for profile, group in results.groupby("profile"):
        row: dict[str, float | str] = {"profile": profile}
        for metric in SUMMARY_METRICS:
            values = group[metric].astype(float)
            row[f"{metric}_mean"] = float(values.mean())
            row[f"{metric}_median"] = float(values.median())
            row[f"{metric}_min"] = float(values.min())
            row[f"{metric}_max"] = float(values.max())
            row[f"{metric}_p10"] = float(values.quantile(0.10))
            row[f"{metric}_p90"] = float(values.quantile(0.90))
        rows.append(row)
    return pd.DataFrame(rows)


def action_frequency_by_profile(results: pd.DataFrame) -> pd.DataFrame:
    """Compute management-action usage rates by profile."""

    grouped = results.groupby("profile", as_index=False).agg(
        repo_usage_rate=("used_repo", "mean"),
        interbank_usage_rate=("used_interbank", "mean"),
        term_funding_usage_rate=("used_term_funding", "mean"),
        hedge_usage_rate=("used_hedge", "mean"),
        mean_action_count=("action_count", "mean"),
    )
    return grouped


def _save_histogram(
    results: pd.DataFrame,
    metric: str,
    title: str,
    output_path: str | Path,
) -> Path:
    """Save a simple per-profile histogram for one ensemble metric."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 4.5))
    for profile, group in results.groupby("profile"):
        plt.hist(group[metric], bins=12, alpha=0.55, label=profile)
    plt.title(title)
    plt.xlabel(metric)
    plt.ylabel("Run count")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(output, dpi=160)
    plt.close()
    return output


def save_action_frequency_chart(action_summary: pd.DataFrame, output_path: str | Path) -> Path:
    """Save a simple grouped bar chart of action usage rates."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    rate_columns = [
        "repo_usage_rate",
        "interbank_usage_rate",
        "term_funding_usage_rate",
        "hedge_usage_rate",
    ]
    labels = ["Repo", "Interbank", "Term Funding", "Hedge"]

    x_positions = range(len(action_summary))
    width = 0.18

    plt.figure(figsize=(8.5, 4.5))
    for index, column in enumerate(rate_columns):
        offsets = [x + (index - 1.5) * width for x in x_positions]
        plt.bar(offsets, action_summary[column], width=width, label=labels[index])

    plt.xticks(list(x_positions), list(action_summary["profile"]))
    plt.ylim(0.0, 1.0)
    plt.ylabel("Usage rate")
    plt.title("Management Action Frequency by Profile")
    plt.legend(frameon=False, ncol=2)
    plt.tight_layout()
    plt.savefig(output, dpi=160)
    plt.close()
    return output


def save_distribution_charts(results: pd.DataFrame, output_dir: str | Path) -> dict[str, Path]:
    """Save the required distribution charts for ensemble results."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    action_summary = action_frequency_by_profile(results)
    return {
        "lcr_distribution": _save_histogram(
            results,
            metric="stressed_lcr",
            title="Stressed LCR Distribution",
            output_path=directory / "lcr_distribution.png",
        ),
        "delta_eve_distribution": _save_histogram(
            results,
            metric="delta_eve_parallel_up",
            title="Parallel-Up EVE Sensitivity Distribution",
            output_path=directory / "delta_eve_distribution.png",
        ),
        "action_frequency": save_action_frequency_chart(
            action_summary,
            output_path=directory / "action_frequency.png",
        ),
    }
