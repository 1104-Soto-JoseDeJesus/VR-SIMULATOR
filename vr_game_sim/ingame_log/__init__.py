"""In-game log rendering integration."""

from .html_renderer import HtmlRenderer
from .log_adapter import LogAdapter
from .log_events import LogEvent, EventType
from .number_format import NumberFormat, fmt_damage, fmt_int

__all__ = [
    "HtmlRenderer",
    "LogAdapter",
    "LogEvent",
    "EventType",
    "NumberFormat",
    "fmt_damage",
    "fmt_int",
]
