"""Adapter that forwards canonical log events to the renderer."""

from __future__ import annotations

from typing import Optional

from .log_events import LogEvent


class LogAdapter:
    """Write-only adapter: forwards canonical :class:`LogEvent` objects."""

    def __init__(self, renderer: Optional["HtmlRenderer"]):
        self.renderer = renderer

    def push(self, event: LogEvent) -> None:
        if self.renderer is not None:
            self.renderer.add(event)

    def render_html(self) -> str:
        return self.renderer.render() if self.renderer is not None else ""
