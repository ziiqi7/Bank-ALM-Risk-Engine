"""Portfolio container, CSV loading, and synthetic balance-sheet generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.balance_sheet.instruments import Position
from src.config import add_months, parse_date

PORTFOLIO_COLUMNS = [
    "position_id",
    "product_type",
    "balance_side",
    "notional",
    "currency",
    "start_date",
    "maturity_date",
    "rate_type",
    "coupon_rate",
    "spread",
    "repricing_freq_months",
    "liquidity_category",
    "behavioral_category",
    "hqla_level",
    "asf_factor",
    "rsf_factor",
    "encumbered",
    "stress_spread_addon",
]


def _parse_optional_int(value: Any) -> int | None:
    """Convert optional CSV integer values into Python integers."""

    if value is None or pd.isna(value) or value == "":
        return None
    return int(float(value))


def _parse_bool(value: Any) -> bool:
    """Convert CSV booleans into Python ``bool`` values."""

    if isinstance(value, bool):
        return value
    if value is None or pd.isna(value) or value == "":
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def position_to_record(position: Position) -> dict[str, Any]:
    """Serialize a ``Position`` into a CSV-friendly record."""

    return {
        "position_id": position.position_id,
        "product_type": position.product_type,
        "balance_side": position.balance_side,
        "notional": position.notional,
        "currency": position.currency,
        "start_date": position.start_date.isoformat(),
        "maturity_date": position.maturity_date.isoformat(),
        "rate_type": position.rate_type,
        "coupon_rate": position.coupon_rate,
        "spread": position.spread,
        "repricing_freq_months": position.repricing_freq_months,
        "liquidity_category": position.liquidity_category,
        "behavioral_category": position.behavioral_category,
        "hqla_level": position.hqla_level,
        "asf_factor": position.asf_factor,
        "rsf_factor": position.rsf_factor,
        "encumbered": position.encumbered,
        "stress_spread_addon": position.stress_spread_addon,
    }


def position_from_record(record: dict[str, Any]) -> Position:
    """Build a ``Position`` from a CSV or DataFrame record."""

    missing_columns = [column for column in PORTFOLIO_COLUMNS if column not in record]
    if missing_columns:
        raise ValueError(f"Portfolio row is missing required columns: {missing_columns}")

    return Position(
        position_id=str(record["position_id"]),
        product_type=str(record["product_type"]),
        balance_side=str(record["balance_side"]),
        notional=float(record["notional"]),
        currency=str(record["currency"]),
        start_date=parse_date(record["start_date"]),
        maturity_date=parse_date(record["maturity_date"]),
        rate_type=str(record["rate_type"]),
        coupon_rate=float(record["coupon_rate"]),
        spread=float(record["spread"]),
        repricing_freq_months=_parse_optional_int(record["repricing_freq_months"]),
        liquidity_category=str(record["liquidity_category"]),
        behavioral_category=str(record["behavioral_category"]),
        hqla_level=str(record["hqla_level"]),
        asf_factor=float(record["asf_factor"]),
        rsf_factor=float(record["rsf_factor"]),
        encumbered=_parse_bool(record["encumbered"]),
        stress_spread_addon=float(record["stress_spread_addon"]),
    )


@dataclass
class Portfolio:
    """Thin portfolio wrapper around a list of positions."""

    positions: list[Position]

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> Portfolio:
        """Create a ``Portfolio`` from a tabular position dataset."""

        records = frame.to_dict(orient="records")
        return cls(positions=[position_from_record(record) for record in records])

    @classmethod
    def from_csv(cls, path: str | Path) -> Portfolio:
        """Load a portfolio from a CSV file using the unified position schema."""

        return load_portfolio_from_csv(path)

    def to_frame(self) -> pd.DataFrame:
        """Return the portfolio as a tidy DataFrame."""

        return pd.DataFrame([position_to_record(position) for position in self.positions], columns=PORTFOLIO_COLUMNS)

    def to_csv(self, path: str | Path) -> Path:
        """Write the portfolio to CSV in the project schema."""

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.to_frame().to_csv(output_path, index=False)
        return output_path

    def total_assets(self) -> float:
        return sum(position.notional for position in self.positions if position.is_asset)

    def total_liabilities(self) -> float:
        return sum(position.notional for position in self.positions if position.is_liability)

    def total_equity(self) -> float:
        return sum(position.notional for position in self.positions if position.is_equity)


def load_portfolio_from_csv(path: str | Path) -> Portfolio:
    """Load a portfolio CSV into ``Position`` objects."""

    portfolio_path = Path(path)
    frame = pd.read_csv(portfolio_path)
    missing_columns = [column for column in PORTFOLIO_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Portfolio CSV is missing required columns: {missing_columns}")
    return Portfolio.from_frame(frame[PORTFOLIO_COLUMNS])


def save_portfolio_to_csv(portfolio: Portfolio, path: str | Path) -> Path:
    """Persist a portfolio to CSV."""

    return portfolio.to_csv(path)


def _build_base_synthetic_positions(as_of_date: date) -> list[Position]:
    """Create the legacy hard-coded synthetic banking-book portfolio."""

    return [
        Position(
            position_id="A1",
            product_type="fixed_mortgages",
            balance_side="asset",
            notional=250.0,
            currency="EUR",
            start_date=add_months(as_of_date, -18),
            maturity_date=add_months(as_of_date, 72),
            rate_type="fixed",
            coupon_rate=0.032,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="loan_book",
            behavioral_category="amortizing",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.85,
        ),
        Position(
            position_id="A2",
            product_type="fixed_mortgages",
            balance_side="asset",
            notional=180.0,
            currency="EUR",
            start_date=add_months(as_of_date, -30),
            maturity_date=add_months(as_of_date, 120),
            rate_type="fixed",
            coupon_rate=0.036,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="loan_book",
            behavioral_category="amortizing",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.85,
        ),
        Position(
            position_id="A3",
            product_type="floating_corporate_loans",
            balance_side="asset",
            notional=220.0,
            currency="EUR",
            start_date=add_months(as_of_date, -12),
            maturity_date=add_months(as_of_date, 48),
            rate_type="floating",
            coupon_rate=0.022,
            spread=0.015,
            repricing_freq_months=3,
            liquidity_category="loan_book",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.0,
            rsf_factor=0.5,
        ),
        Position(
            position_id="A4",
            product_type="sovereign_bonds",
            balance_side="asset",
            notional=140.0,
            currency="EUR",
            start_date=add_months(as_of_date, -6),
            maturity_date=add_months(as_of_date, 36),
            rate_type="fixed",
            coupon_rate=0.024,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="securities",
            behavioral_category="contractual",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.05,
        ),
        Position(
            position_id="A5",
            product_type="reserves/cash",
            balance_side="asset",
            notional=90.0,
            currency="EUR",
            start_date=add_months(as_of_date, -1),
            maturity_date=add_months(as_of_date, 1),
            rate_type="nonrate",
            coupon_rate=0.0,
            spread=0.0,
            repricing_freq_months=1,
            liquidity_category="cash",
            behavioral_category="overnight",
            hqla_level="level1",
            asf_factor=0.0,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L1",
            product_type="retail_nmd",
            balance_side="liability",
            notional=420.0,
            currency="EUR",
            start_date=add_months(as_of_date, -36),
            maturity_date=add_months(as_of_date, 240),
            rate_type="nonrate",
            coupon_rate=0.002,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="retail_nmd",
            hqla_level="none",
            asf_factor=0.9,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L2",
            product_type="retail_nmd",
            balance_side="liability",
            notional=110.0,
            currency="EUR",
            start_date=add_months(as_of_date, -12),
            maturity_date=add_months(as_of_date, 180),
            rate_type="nonrate",
            coupon_rate=0.004,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="retail_nmd_less_stable",
            hqla_level="none",
            asf_factor=0.8,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L3",
            product_type="term_deposits",
            balance_side="liability",
            notional=190.0,
            currency="EUR",
            start_date=add_months(as_of_date, -6),
            maturity_date=add_months(as_of_date, 12),
            rate_type="fixed",
            coupon_rate=0.028,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="deposit",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.95,
            rsf_factor=0.0,
        ),
        Position(
            position_id="L4",
            product_type="interbank_borrowing",
            balance_side="liability",
            notional=85.0,
            currency="EUR",
            start_date=add_months(as_of_date, -3),
            maturity_date=add_months(as_of_date, 6),
            rate_type="floating",
            coupon_rate=0.027,
            spread=0.004,
            repricing_freq_months=1,
            liquidity_category="wholesale",
            behavioral_category="contractual",
            hqla_level="none",
            asf_factor=0.5,
            rsf_factor=0.0,
        ),
        Position(
            position_id="E1",
            product_type="equity",
            balance_side="equity",
            notional=75.0,
            currency="EUR",
            start_date=as_of_date,
            maturity_date=add_months(as_of_date, 360),
            rate_type="nonrate",
            coupon_rate=0.0,
            spread=0.0,
            repricing_freq_months=None,
            liquidity_category="capital",
            behavioral_category="permanent",
            hqla_level="none",
            asf_factor=1.0,
            rsf_factor=0.0,
        ),
    ]


def build_synthetic_portfolio(as_of_date: date) -> Portfolio:
    """Create the legacy hard-coded synthetic banking-book balance sheet."""

    return Portfolio(positions=_build_base_synthetic_positions(as_of_date))
