"""Generate deterministic demo-case portfolio CSVs for repeatable showcases."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd


def _bootstrap_project_root() -> Path:
    """Add the repository root to ``sys.path`` based on this script location."""

    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)
    os.environ.setdefault("MPLCONFIGDIR", str(project_root / ".mpl-cache"))
    return project_root


PROJECT_ROOT = _bootstrap_project_root()

from src.balance_sheet.portfolio import Portfolio, save_portfolio_to_csv
from src.config import load_config
from src.data.generator import generate_random_portfolio

DEMO_CASES = (
    {
        "name": "demo_balanced",
        "profile": "balanced",
        "seed": 41,
        "narrative": "Stable reference case that usually stays above action thresholds under combined stress.",
    },
    {
        "name": "demo_liquidity_tight",
        "profile": "liquidity_tight",
        "seed": 36,
        "narrative": "Liquidity-stress showcase with tighter buffers and more likely repo or interbank actions.",
    },
    {
        "name": "demo_irrbb_heavy",
        "profile": "irrbb_heavy",
        "seed": 55,
        "narrative": "IRRBB-sensitive showcase with stronger EVE sensitivity and a clearer hedge-style response.",
    },
)


def _portfolio_summary(portfolio: Portfolio) -> pd.DataFrame:
    """Return a compact balance-sheet composition summary."""

    frame = portfolio.to_frame()
    total_assets = portfolio.total_assets()
    mortgage_share = float(frame.loc[frame["product_type"] == "fixed_mortgages", "notional"].sum()) / total_assets
    hqla_share = float(frame.loc[frame["hqla_level"] == "level1", "notional"].sum()) / total_assets
    interbank_share = float(
        frame.loc[frame["product_type"] == "interbank_borrowing", "notional"].sum()
    ) / total_assets
    equity_ratio = portfolio.total_equity() / total_assets
    return pd.DataFrame(
        [
            {
                "total_assets": total_assets,
                "mortgage_share": mortgage_share,
                "hqla_share": hqla_share,
                "interbank_share": interbank_share,
                "equity_ratio": equity_ratio,
            }
        ]
    )


def _print_case_summary(case_name: str, profile: str, seed: int, output_path: Path, summary: pd.DataFrame) -> None:
    """Print one terminal-friendly demo-case summary."""

    print(f"\n=== {case_name} ===")
    print(f"profile: {profile}")
    print(f"seed: {seed}")
    print(f"output: {output_path}")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:,.3f}"))


def generate_demo_cases() -> list[Path]:
    """Generate the three fixed demo-case CSVs."""

    config = load_config(PROJECT_ROOT / "data" / "assumptions" / "base_assumptions.yaml")
    output_dir = PROJECT_ROOT / "data" / "portfolios"
    output_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for case in DEMO_CASES:
        portfolio = generate_random_portfolio(
            as_of_date=config.as_of_date,
            profile=case["profile"],
            seed=case["seed"],
        )
        output_path = output_dir / f"{case['name']}.csv"
        save_portfolio_to_csv(portfolio, output_path)
        written_paths.append(output_path)
        _print_case_summary(
            case_name=case["name"],
            profile=case["profile"],
            seed=case["seed"],
            output_path=output_path,
            summary=_portfolio_summary(portfolio),
        )
        print(case["narrative"])

    return written_paths


def main() -> None:
    print("Generating deterministic demo-case portfolios.")
    print("Seeds were selected from a small deterministic search to match each showcase narrative.")
    generate_demo_cases()


if __name__ == "__main__":
    main()
