"""Tests for example pipeline presentation helpers."""

from __future__ import annotations

import pandas as pd

from scripts.example_pipeline import _build_action_views
from src.reporting.tables import action_log_table


def test_empty_action_log_returns_expected_columns_and_safe_compact_view() -> None:
    action_summary = action_log_table(pd.DataFrame())
    compact_action_view, no_actions_triggered = _build_action_views(action_summary)

    assert no_actions_triggered is True
    assert list(action_summary.columns) == [
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
    assert list(compact_action_view.columns) == [
        "step",
        "action_name",
        "amount",
        "funding_stress_spread_used",
        "delta_nii_change",
        "lcr_after",
        "survival_after_days",
    ]
    assert compact_action_view.empty
