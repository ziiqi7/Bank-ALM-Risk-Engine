"""Rate shock definitions for simplified IRRBB analytics."""

from __future__ import annotations

from dataclasses import dataclass

from src.config import EngineConfig


@dataclass(frozen=True)
class RateShock:
    """Yield-curve shock definition."""

    name: str
    kind: str
    parallel_bps: float = 0.0
    short_bps: float = 0.0
    long_bps: float = 0.0
    description: str = ""


def build_standard_rate_shocks(config: EngineConfig) -> dict[str, RateShock]:
    """Build standard IRRBB shocks from configuration."""

    shocks = config.standard_shocks
    return {
        "parallel_up": RateShock(
            name="parallel_up",
            kind="parallel",
            parallel_bps=shocks.parallel_up_bps,
            description="Parallel upward shift of the curve.",
        ),
        "parallel_down": RateShock(
            name="parallel_down",
            kind="parallel",
            parallel_bps=shocks.parallel_down_bps,
            description="Parallel downward shift of the curve.",
        ),
        "short_up": RateShock(
            name="short_up",
            kind="short",
            short_bps=shocks.short_up_bps,
            description="Front-end upward shock with decaying long-end impact.",
        ),
        "short_down": RateShock(
            name="short_down",
            kind="short",
            short_bps=shocks.short_down_bps,
            description="Front-end downward shock with decaying long-end impact.",
        ),
        "steepener": RateShock(
            name="steepener",
            kind="curve",
            short_bps=shocks.steepener_short_bps,
            long_bps=shocks.steepener_long_bps,
            description="Short rates down, long rates up.",
        ),
        "flattener": RateShock(
            name="flattener",
            kind="curve",
            short_bps=shocks.flattener_short_bps,
            long_bps=shocks.flattener_long_bps,
            description="Short rates up, long rates down.",
        ),
    }


def rate_shift_decimal(shock: RateShock, term_years: float) -> float:
    """Return the scenario rate shift in decimal form for a tenor."""

    tenor = max(term_years, 0.0)

    if shock.kind == "parallel":
        return shock.parallel_bps / 10_000.0

    if shock.kind == "short":
        short_weight = max(0.15, 1.0 - min(tenor, 5.0) / 5.0)
        return (shock.short_bps * short_weight) / 10_000.0

    short_anchor = 1.0
    long_anchor = 10.0
    if tenor <= short_anchor:
        return shock.short_bps / 10_000.0
    if tenor >= long_anchor:
        return shock.long_bps / 10_000.0

    mix = (tenor - short_anchor) / (long_anchor - short_anchor)
    interpolated_bps = shock.short_bps + mix * (shock.long_bps - shock.short_bps)
    return interpolated_bps / 10_000.0
