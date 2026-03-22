"""Constrained random portfolio generation for CSV-driven ALM workflows."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np

from src.balance_sheet.instruments import Position
from src.balance_sheet.portfolio import Portfolio, save_portfolio_to_csv
from src.config import add_months

GENERATION_PROFILES = ("balanced", "irrbb_heavy", "liquidity_tight")

_PROFILE_CONFIG = {
    "balanced": {
        "equity_ratio": (0.09, 0.115),
        "asset_ranges": {
            "fixed_mortgages": (0.39, 0.47),
            "floating_corporate_loans": (0.24, 0.31),
            "sovereign_bonds": (0.13, 0.19),
            "reserves/cash": (0.10, 0.15),
        },
        "liability_ranges": {
            "retail_nmd": (0.55, 0.65),
            "term_deposits": (0.19, 0.27),
            "interbank_borrowing": (0.10, 0.17),
        },
        "stable_deposit_share": (0.80, 0.88),
        "tranche_concentration": 34.0,
        "mortgage_tranche_weights": (0.08, 0.11, 0.15, 0.18, 0.17, 0.16, 0.15),
        "mortgage_tranche_months": (
            (24, 42),
            (42, 60),
            (60, 78),
            (78, 96),
            (96, 114),
            (114, 138),
            (138, 180),
        ),
        "loan_tranche_weights": (0.12, 0.15, 0.18, 0.19, 0.19, 0.17),
        "loan_tranche_months": (
            (9, 18),
            (15, 24),
            (24, 36),
            (30, 48),
            (42, 60),
            (54, 78),
        ),
        "loan_tranche_repricing": ((1, 3), (1, 3), (3, 6), (3, 6), (6,), (6,)),
        "bond_tranche_weights": (0.24, 0.22, 0.20, 0.18, 0.16),
        "bond_tranche_months": ((3, 9), (9, 18), (18, 30), (30, 42), (42, 60)),
        "reserve_tranche_weights": (0.55, 0.45),
        "reserve_tranche_days": ((1, 7), (7, 28)),
        "stable_nmd_tranche_weights": (0.54, 0.46),
        "less_stable_nmd_tranche_weights": (0.57, 0.43),
        "term_deposit_tranche_weights": (0.30, 0.27, 0.23, 0.20),
        "term_deposit_tranche_months": ((2, 5), (5, 9), (9, 14), (14, 20)),
        "interbank_tranche_weights": (0.34, 0.28, 0.22, 0.16),
        "interbank_tranche_months": ((1, 1), (1, 2), (2, 3), (3, 5)),
    },
    "irrbb_heavy": {
        "equity_ratio": (0.09, 0.11),
        "asset_ranges": {
            "fixed_mortgages": (0.45, 0.55),
            "floating_corporate_loans": (0.22, 0.29),
            "sovereign_bonds": (0.11, 0.17),
            "reserves/cash": (0.08, 0.13),
        },
        "liability_ranges": {
            "retail_nmd": (0.55, 0.66),
            "term_deposits": (0.18, 0.25),
            "interbank_borrowing": (0.10, 0.17),
        },
        "stable_deposit_share": (0.79, 0.86),
        "tranche_concentration": 32.0,
        "mortgage_tranche_weights": (0.05, 0.08, 0.11, 0.15, 0.18, 0.20, 0.23),
        "mortgage_tranche_months": (
            (36, 54),
            (54, 72),
            (72, 90),
            (90, 114),
            (114, 138),
            (138, 162),
            (162, 204),
        ),
        "loan_tranche_weights": (0.08, 0.12, 0.16, 0.20, 0.22, 0.22),
        "loan_tranche_months": (
            (15, 24),
            (24, 33),
            (33, 45),
            (45, 57),
            (57, 72),
            (72, 90),
        ),
        "loan_tranche_repricing": ((3,), (3,), (3, 6), (3, 6), (6,), (6,)),
        "bond_tranche_weights": (0.14, 0.18, 0.20, 0.23, 0.25),
        "bond_tranche_months": ((6, 15), (15, 27), (27, 39), (39, 54), (54, 72)),
        "reserve_tranche_weights": (0.48, 0.52),
        "reserve_tranche_days": ((1, 7), (7, 24)),
        "stable_nmd_tranche_weights": (0.52, 0.48),
        "less_stable_nmd_tranche_weights": (0.54, 0.46),
        "term_deposit_tranche_weights": (0.22, 0.25, 0.26, 0.27),
        "term_deposit_tranche_months": ((3, 6), (6, 10), (10, 16), (16, 24)),
        "interbank_tranche_weights": (0.31, 0.27, 0.23, 0.19),
        "interbank_tranche_months": ((1, 1), (1, 2), (2, 3), (3, 4)),
    },
    "liquidity_tight": {
        "equity_ratio": (0.085, 0.105),
        "asset_ranges": {
            "fixed_mortgages": (0.40, 0.49),
            "floating_corporate_loans": (0.24, 0.31),
            "sovereign_bonds": (0.09, 0.14),
            "reserves/cash": (0.07, 0.12),
        },
        "liability_ranges": {
            "retail_nmd": (0.48, 0.59),
            "term_deposits": (0.18, 0.25),
            "interbank_borrowing": (0.15, 0.23),
        },
        "stable_deposit_share": (0.75, 0.83),
        "tranche_concentration": 30.0,
        "mortgage_tranche_weights": (0.09, 0.12, 0.15, 0.17, 0.17, 0.16, 0.14),
        "mortgage_tranche_months": (
            (30, 48),
            (48, 66),
            (66, 84),
            (84, 102),
            (102, 126),
            (126, 150),
            (150, 186),
        ),
        "loan_tranche_weights": (0.16, 0.18, 0.18, 0.18, 0.16, 0.14),
        "loan_tranche_months": (
            (6, 15),
            (12, 21),
            (18, 30),
            (27, 39),
            (36, 51),
            (48, 66),
        ),
        "loan_tranche_repricing": ((1, 3), (1, 3), (3,), (3,), (3, 6), (6,)),
        "bond_tranche_weights": (0.30, 0.24, 0.19, 0.15, 0.12),
        "bond_tranche_months": ((3, 6), (6, 12), (12, 21), (21, 33), (33, 45)),
        "reserve_tranche_weights": (0.62, 0.38),
        "reserve_tranche_days": ((1, 5), (5, 18)),
        "stable_nmd_tranche_weights": (0.58, 0.42),
        "less_stable_nmd_tranche_weights": (0.62, 0.38),
        "term_deposit_tranche_weights": (0.36, 0.28, 0.21, 0.15),
        "term_deposit_tranche_months": ((1, 3), (3, 6), (6, 10), (10, 15)),
        "interbank_tranche_weights": (0.40, 0.30, 0.18, 0.12),
        "interbank_tranche_months": ((1, 1), (1, 2), (2, 3), (3, 4)),
    },
}


def _sample_fraction(rng: np.random.Generator, bounds: tuple[float, float]) -> float:
    """Draw a bounded fraction from a profile-specific range."""

    return float(rng.uniform(bounds[0], bounds[1]))


def _sample_constrained_weights(
    rng: np.random.Generator,
    bounds: dict[str, tuple[float, float]],
) -> dict[str, float]:
    """Sample weights that sum to one while respecting per-product ranges."""

    names = list(bounds)
    mins = np.array([bounds[name][0] for name in names], dtype=float)
    maxs = np.array([bounds[name][1] for name in names], dtype=float)
    slack = 1.0 - mins.sum()
    capacities = maxs - mins

    if slack < 0 or slack > capacities.sum():
        raise ValueError("Invalid profile bounds for constrained weight sampling.")

    for _ in range(5000):
        raw = rng.random(len(names))
        proposal = mins if float(raw.sum()) == 0.0 else mins + slack * (raw / raw.sum())
        if np.all(proposal <= maxs + 1e-9):
            return {name: float(weight) for name, weight in zip(names, proposal)}

    raise RuntimeError("Unable to sample constrained weights within profile bounds.")


def _allocate_amounts(total: float, weights: dict[str, float]) -> dict[str, float]:
    """Allocate a total amount across weights while preserving an exact sum."""

    names = list(weights)
    amounts: dict[str, float] = {}
    running_total = 0.0
    for name in names[:-1]:
        amount = round(total * weights[name], 3)
        amounts[name] = amount
        running_total += amount
    amounts[names[-1]] = round(total - running_total, 3)
    return amounts


def _allocate_from_vector(total: float, weights: list[float]) -> list[float]:
    """Allocate a total amount across an ordered weight vector."""

    running_total = 0.0
    amounts: list[float] = []
    for weight in weights[:-1]:
        amount = round(total * weight, 3)
        amounts.append(amount)
        running_total += amount
    amounts.append(round(total - running_total, 3))
    return amounts


def _sample_months(rng: np.random.Generator, bounds: tuple[int, int]) -> int:
    """Draw an integer month count within inclusive bounds."""

    low, high = bounds
    return int(rng.integers(low, high + 1))


def _sample_days(rng: np.random.Generator, bounds: tuple[int, int]) -> int:
    """Draw an integer day count within inclusive bounds."""

    low, high = bounds
    return int(rng.integers(low, high + 1))


def _sample_choice(rng: np.random.Generator, values: tuple[int, ...]) -> int:
    """Sample a discrete configuration choice."""

    return int(values[int(rng.integers(0, len(values)))])


def _sample_tranche_weights(
    rng: np.random.Generator,
    base_weights: tuple[float, ...],
    concentration: float,
) -> list[float]:
    """Sample smooth tranche weights around a base profile shape."""

    alpha = np.maximum(np.array(base_weights, dtype=float) * concentration, 1.5)
    weights = rng.dirichlet(alpha)
    return [float(weight) for weight in weights]


def _sample_coupon(rng: np.random.Generator, base_range: tuple[float, float], shift: float = 0.0) -> float:
    """Sample a coupon rate with an optional tranche-specific shift."""

    low, high = base_range
    adjusted_low = max(low + shift, 0.0)
    adjusted_high = max(high + shift, adjusted_low + 1e-6)
    return round(_sample_fraction(rng, (adjusted_low, adjusted_high)), 4)


def _centered_shift(index: int, total_count: int, step: float) -> float:
    """Return a symmetric tranche shift around the portfolio midpoint."""

    midpoint = (total_count - 1) / 2
    return (index - midpoint) * step


def _append_fixed_tranches(
    positions: list[Position],
    id_factory,
    *,
    as_of_date: date,
    product_type: str,
    balance_side: str,
    total_amount: float,
    tranche_weights: tuple[float, ...],
    month_bounds: tuple[tuple[int, int], ...],
    start_back_bounds: tuple[int, int],
    coupon_bounds: tuple[float, float],
    coupon_step: float,
    liquidity_category: str,
    behavioral_category: str,
    hqla_level: str,
    asf_factor: float,
    rsf_factor: float,
    rng: np.random.Generator,
    concentration: float,
) -> None:
    """Append fixed-rate tranches for one product class."""

    sampled_weights = _sample_tranche_weights(rng, tranche_weights, concentration)
    tranche_amounts = _allocate_from_vector(total_amount, sampled_weights)
    total_count = len(tranche_amounts)

    for index, (amount, maturity_bounds) in enumerate(zip(tranche_amounts, month_bounds, strict=True)):
        positions.append(
            Position(
                position_id=id_factory(),
                product_type=product_type,
                balance_side=balance_side,
                notional=amount,
                currency="EUR",
                start_date=add_months(as_of_date, -_sample_months(rng, start_back_bounds)),
                maturity_date=add_months(as_of_date, _sample_months(rng, maturity_bounds)),
                rate_type="fixed",
                coupon_rate=_sample_coupon(rng, coupon_bounds, _centered_shift(index, total_count, coupon_step)),
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category=liquidity_category,
                behavioral_category=behavioral_category,
                hqla_level=hqla_level,
                asf_factor=asf_factor,
                rsf_factor=rsf_factor,
            )
        )


def _append_floating_tranches(
    positions: list[Position],
    id_factory,
    *,
    as_of_date: date,
    product_type: str,
    balance_side: str,
    total_amount: float,
    tranche_weights: tuple[float, ...],
    month_bounds: tuple[tuple[int, int], ...],
    repricing_choices: tuple[tuple[int, ...], ...],
    start_back_bounds: tuple[int, int],
    coupon_bounds: tuple[float, float],
    coupon_step: float,
    spread_bounds: tuple[float, float],
    spread_step: float,
    liquidity_category: str,
    behavioral_category: str,
    hqla_level: str,
    asf_factor: float,
    rsf_factor: float,
    rng: np.random.Generator,
    concentration: float,
) -> None:
    """Append floating-rate tranches for one product class."""

    sampled_weights = _sample_tranche_weights(rng, tranche_weights, concentration)
    tranche_amounts = _allocate_from_vector(total_amount, sampled_weights)
    total_count = len(tranche_amounts)

    for index, (amount, maturity_bounds, repricing_bucket) in enumerate(
        zip(tranche_amounts, month_bounds, repricing_choices, strict=True)
    ):
        positions.append(
            Position(
                position_id=id_factory(),
                product_type=product_type,
                balance_side=balance_side,
                notional=amount,
                currency="EUR",
                start_date=add_months(as_of_date, -_sample_months(rng, start_back_bounds)),
                maturity_date=add_months(as_of_date, _sample_months(rng, maturity_bounds)),
                rate_type="floating",
                coupon_rate=_sample_coupon(rng, coupon_bounds, _centered_shift(index, total_count, coupon_step)),
                spread=round(
                    _sample_fraction(
                        rng,
                        (
                            max(spread_bounds[0] + _centered_shift(index, total_count, spread_step), 0.0),
                            max(
                                spread_bounds[1] + _centered_shift(index, total_count, spread_step),
                                spread_bounds[0] + 0.0001,
                            ),
                        ),
                    ),
                    4,
                ),
                repricing_freq_months=_sample_choice(rng, repricing_bucket),
                liquidity_category=liquidity_category,
                behavioral_category=behavioral_category,
                hqla_level=hqla_level,
                asf_factor=asf_factor,
                rsf_factor=rsf_factor,
            )
        )


def _build_positions(
    as_of_date: date,
    asset_amounts: dict[str, float],
    liability_amounts: dict[str, float],
    equity_amount: float,
    profile_config: dict[str, object],
    rng: np.random.Generator,
) -> list[Position]:
    """Build a medium-granularity multi-tranche position set for one portfolio."""

    positions: list[Position] = []
    asset_counter = 1
    liability_counter = 1

    def next_asset_id() -> str:
        nonlocal asset_counter
        value = f"A{asset_counter}"
        asset_counter += 1
        return value

    def next_liability_id() -> str:
        nonlocal liability_counter
        value = f"L{liability_counter}"
        liability_counter += 1
        return value

    concentration = float(profile_config["tranche_concentration"])

    _append_fixed_tranches(
        positions,
        next_asset_id,
        as_of_date=as_of_date,
        product_type="fixed_mortgages",
        balance_side="asset",
        total_amount=asset_amounts["fixed_mortgages"],
        tranche_weights=profile_config["mortgage_tranche_weights"],
        month_bounds=profile_config["mortgage_tranche_months"],
        start_back_bounds=(12, 60),
        coupon_bounds=(0.028, 0.041),
        coupon_step=0.0005,
        liquidity_category="loan_book",
        behavioral_category="amortizing",
        hqla_level="none",
        asf_factor=0.0,
        rsf_factor=0.85,
        rng=rng,
        concentration=concentration,
    )

    _append_floating_tranches(
        positions,
        next_asset_id,
        as_of_date=as_of_date,
        product_type="floating_corporate_loans",
        balance_side="asset",
        total_amount=asset_amounts["floating_corporate_loans"],
        tranche_weights=profile_config["loan_tranche_weights"],
        month_bounds=profile_config["loan_tranche_months"],
        repricing_choices=profile_config["loan_tranche_repricing"],
        start_back_bounds=(6, 30),
        coupon_bounds=(0.017, 0.028),
        coupon_step=0.00025,
        spread_bounds=(0.011, 0.019),
        spread_step=0.0002,
        liquidity_category="loan_book",
        behavioral_category="contractual",
        hqla_level="none",
        asf_factor=0.0,
        rsf_factor=0.5,
        rng=rng,
        concentration=concentration,
    )

    _append_fixed_tranches(
        positions,
        next_asset_id,
        as_of_date=as_of_date,
        product_type="sovereign_bonds",
        balance_side="asset",
        total_amount=asset_amounts["sovereign_bonds"],
        tranche_weights=profile_config["bond_tranche_weights"],
        month_bounds=profile_config["bond_tranche_months"],
        start_back_bounds=(2, 18),
        coupon_bounds=(0.017, 0.031),
        coupon_step=0.00035,
        liquidity_category="securities",
        behavioral_category="contractual",
        hqla_level="level1",
        asf_factor=0.0,
        rsf_factor=0.05,
        rng=rng,
        concentration=concentration,
    )

    reserve_weights = _sample_tranche_weights(rng, profile_config["reserve_tranche_weights"], concentration)
    reserve_amounts = _allocate_from_vector(asset_amounts["reserves/cash"], reserve_weights)
    for amount, day_bounds in zip(reserve_amounts, profile_config["reserve_tranche_days"], strict=True):
        reserve_days = _sample_days(rng, day_bounds)
        positions.append(
            Position(
                position_id=next_asset_id(),
                product_type="reserves/cash",
                balance_side="asset",
                notional=amount,
                currency="EUR",
                start_date=as_of_date - timedelta(days=min(reserve_days, 7)),
                maturity_date=as_of_date + timedelta(days=reserve_days),
                rate_type="nonrate",
                coupon_rate=0.0,
                spread=0.0,
                repricing_freq_months=1,
                liquidity_category="cash",
                behavioral_category="overnight",
                hqla_level="level1",
                asf_factor=0.0,
                rsf_factor=0.0,
            )
        )

    retail_total = liability_amounts["retail_nmd"]
    stable_share = _sample_fraction(rng, profile_config["stable_deposit_share"])
    stable_retail = round(retail_total * stable_share, 3)
    less_stable_retail = round(retail_total - stable_retail, 3)

    stable_weights = _sample_tranche_weights(rng, profile_config["stable_nmd_tranche_weights"], concentration)
    stable_amounts = _allocate_from_vector(stable_retail, stable_weights)
    for amount in stable_amounts:
        positions.append(
            Position(
                position_id=next_liability_id(),
                product_type="retail_nmd",
                balance_side="liability",
                notional=amount,
                currency="EUR",
                start_date=add_months(as_of_date, -_sample_months(rng, (24, 84))),
                maturity_date=add_months(as_of_date, _sample_months(rng, (180, 300))),
                rate_type="nonrate",
                coupon_rate=round(_sample_fraction(rng, (0.001, 0.0035)), 4),
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="deposit",
                behavioral_category="retail_nmd",
                hqla_level="none",
                asf_factor=0.9,
                rsf_factor=0.0,
            )
        )

    less_stable_weights = _sample_tranche_weights(rng, profile_config["less_stable_nmd_tranche_weights"], concentration)
    less_stable_amounts = _allocate_from_vector(less_stable_retail, less_stable_weights)
    for amount in less_stable_amounts:
        positions.append(
            Position(
                position_id=next_liability_id(),
                product_type="retail_nmd",
                balance_side="liability",
                notional=amount,
                currency="EUR",
                start_date=add_months(as_of_date, -_sample_months(rng, (12, 48))),
                maturity_date=add_months(as_of_date, _sample_months(rng, (120, 220))),
                rate_type="nonrate",
                coupon_rate=round(_sample_fraction(rng, (0.0025, 0.0055)), 4),
                spread=0.0,
                repricing_freq_months=None,
                liquidity_category="deposit",
                behavioral_category="retail_nmd_less_stable",
                hqla_level="none",
                asf_factor=0.8,
                rsf_factor=0.0,
            )
        )

    _append_fixed_tranches(
        positions,
        next_liability_id,
        as_of_date=as_of_date,
        product_type="term_deposits",
        balance_side="liability",
        total_amount=liability_amounts["term_deposits"],
        tranche_weights=profile_config["term_deposit_tranche_weights"],
        month_bounds=profile_config["term_deposit_tranche_months"],
        start_back_bounds=(2, 12),
        coupon_bounds=(0.022, 0.036),
        coupon_step=0.00025,
        liquidity_category="deposit",
        behavioral_category="contractual",
        hqla_level="none",
        asf_factor=0.95,
        rsf_factor=0.0,
        rng=rng,
        concentration=concentration,
    )

    _append_floating_tranches(
        positions,
        next_liability_id,
        as_of_date=as_of_date,
        product_type="interbank_borrowing",
        balance_side="liability",
        total_amount=liability_amounts["interbank_borrowing"],
        tranche_weights=profile_config["interbank_tranche_weights"],
        month_bounds=profile_config["interbank_tranche_months"],
        repricing_choices=((1,), (1,), (1,), (1,)),
        start_back_bounds=(1, 6),
        coupon_bounds=(0.021, 0.029),
        coupon_step=0.0002,
        spread_bounds=(0.003, 0.008),
        spread_step=0.00015,
        liquidity_category="wholesale",
        behavioral_category="contractual",
        hqla_level="none",
        asf_factor=0.5,
        rsf_factor=0.0,
        rng=rng,
        concentration=concentration,
    )

    positions.append(
        Position(
            position_id="E1",
            product_type="equity",
            balance_side="equity",
            notional=equity_amount,
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
        )
    )

    return positions


def generate_random_portfolio(
    as_of_date: date,
    profile: str = "balanced",
    seed: int | None = None,
) -> Portfolio:
    """Generate a constrained, internally consistent banking-book portfolio.

    Portfolio totals are expressed in EUR millions and constrained to a total
    asset size between 5 and 8 billion.
    """

    if profile not in _PROFILE_CONFIG:
        raise ValueError(f"Unsupported profile '{profile}'. Expected one of {GENERATION_PROFILES}.")

    profile_config = _PROFILE_CONFIG[profile]
    rng = np.random.default_rng(seed)

    total_assets = float(rng.integers(5000, 8001))
    equity_ratio = _sample_fraction(rng, profile_config["equity_ratio"])
    equity_amount = round(total_assets * equity_ratio, 3)
    total_liabilities = round(total_assets - equity_amount, 3)

    asset_weights = _sample_constrained_weights(rng, profile_config["asset_ranges"])
    liability_weights = _sample_constrained_weights(rng, profile_config["liability_ranges"])

    asset_amounts = _allocate_amounts(total_assets, asset_weights)
    liability_amounts = _allocate_amounts(total_liabilities, liability_weights)

    positions = _build_positions(
        as_of_date=as_of_date,
        asset_amounts=asset_amounts,
        liability_amounts=liability_amounts,
        equity_amount=equity_amount,
        profile_config=profile_config,
        rng=rng,
    )
    return Portfolio(positions=positions)


def generate_random_portfolio_csv(
    as_of_date: date,
    output_path: str | Path,
    profile: str = "balanced",
    seed: int | None = None,
) -> Portfolio:
    """Generate a constrained random portfolio and persist it to CSV."""

    portfolio = generate_random_portfolio(as_of_date=as_of_date, profile=profile, seed=seed)
    save_portfolio_to_csv(portfolio, output_path)
    return portfolio
