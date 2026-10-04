"""Progress lines for the long eval steps: elapsed time and an estimate of the time left."""

import time

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600


def clock(seconds: float) -> str:
    """75 -> '1:15', 3725 -> '1:02:05'."""
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, SECONDS_PER_HOUR)
    minutes, seconds = divmod(rest, SECONDS_PER_MINUTE)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


class Progress:
    """Work done out of a total (questions, or bytes of PDF). The time left assumes the rest goes at the same pace."""

    def __init__(self, total: float, now=time.perf_counter):
        self.total = total
        self.done = 0.0
        self.now = now
        self.started = now()

    def advance(self, amount: float = 1.0) -> None:
        self.done += amount

    def skip(self, amount: float) -> None:
        """Work that took no time (a PDF that is already ingested): it would make the estimate too optimistic."""
        self.total -= amount

    def status(self) -> str:
        elapsed = self.now() - self.started
        if self.done <= 0:
            return f"elapsed {clock(elapsed)} | left ?"
        left = elapsed / self.done * max(0.0, self.total - self.done)
        return f"elapsed {clock(elapsed)} | left ~{clock(left)}"
