"""Utility helpers for formatting numeric values in the in-game log."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NumberFormat:
    thousands: bool = False
    abbreviate: bool = False
    decimals: int = 0
    floor_damage: bool = True


def fmt_damage(x: float, nf: NumberFormat) -> str:
    if nf.floor_damage:
        return fmt_int(int(x), nf)
    value = round(x, nf.decimals)
    if nf.decimals > 0:
        text = f"{value:.{nf.decimals}f}".rstrip("0").rstrip(".")
        return text
    return fmt_int(int(value), nf)


def fmt_int(v: int, nf: NumberFormat) -> str:
    if nf.abbreviate:
        if v >= 1_000_000:
            return f"{v / 1_000_000:.1f}m".rstrip("0").rstrip(".")
        if v >= 1_000:
            return f"{v / 1_000:.1f}k".rstrip("0").rstrip(".")
    if nf.thousands:
        return f"{v:,}"
    return str(v)
