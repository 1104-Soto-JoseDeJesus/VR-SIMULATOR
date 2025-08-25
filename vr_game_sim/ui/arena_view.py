from __future__ import annotations

import asyncio
from typing import Dict, Iterable, Tuple, Any


class ArenaView:
    """Minimal view helper to animate lane results in parallel.

    The simulator exposes ``last_round_buffer`` which contains tuples of
    ``(attacker_pos, defender_pos, attacker_remaining, defender_remaining)``.
    This view can flash all affected lane icons concurrently using
    :func:`asyncio.gather`.
    """

    def __init__(self) -> None:
        # Mapping of grid positions to UI icon objects.  Icons are expected to
        # provide a ``flash`` method for visual feedback.
        self.lane_icons: Dict[Tuple[int, int], Any] = {}

    async def _flash_icon(self, pos: Tuple[int, int]) -> None:
        icon = self.lane_icons.get(pos)
        if icon and hasattr(icon, "flash"):
            icon.flash()
        await asyncio.sleep(0)

    async def flash_lanes(
        self,
        results: Iterable[Tuple[Tuple[int, int], Tuple[int, int], float, float]],
    ) -> None:
        """Animate all lane icons based on a round result buffer."""

        tasks = []
        for pos1, pos2, *_ in results:
            tasks.append(self._flash_icon(pos1))
            tasks.append(self._flash_icon(pos2))
        if tasks:
            await asyncio.gather(*tasks)
