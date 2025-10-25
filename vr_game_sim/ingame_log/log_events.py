"""Canonical log event definitions for the in-game export."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

EventType = Literal[
    "BATTLE_START",
    "ROUND_START",
    "ROUND_END",
    "BATTLE_END",
    "BASIC_ATTACK",
    "COUNTER_ATTACK",
    "SKILL_CAST",
    "DOT_TICK",
    "HOT_TICK",
    "SHIELD_APPLIED",
    "SHIELD_ABSORB",
    "EFFECT_GAINED",
    "EFFECT_EXPIRED",
    "QUEUE_PRIMARY_RAGE",
    "RAGE_CLEARED",
    "KILLS_APPLIED",
]


@dataclass
class LogEvent:
    """Container describing a single in-game log entry."""

    type: EventType
    round: Optional[int] = None
    attacker_name: Optional[str] = None
    defender_name: Optional[str] = None
    skill_name: Optional[str] = None
    damage: Optional[float] = None
    absorbed: Optional[float] = None
    kills: Optional[int] = None
    target_name: Optional[str] = None
    winner: Optional[str] = None
    rounds_total: Optional[int] = None
    notes: dict[str, Any] = field(default_factory=dict)
