from eval.progress import Progress, clock


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_clock_prints_minutes_and_hours():
    assert clock(0) == "0:00"
    assert clock(75) == "1:15"
    assert clock(3725) == "1:02:05"


def test_the_time_left_follows_the_pace_so_far():
    now = FakeClock()
    progress = Progress(4, now=now)
    assert progress.status() == "elapsed 0:00 | left ?"  # nothing done yet: no estimate

    now.t = 30
    progress.advance()
    assert progress.status() == "elapsed 0:30 | left ~1:30"  # 30 s per item, 3 to go


def test_skipped_work_does_not_count_towards_the_estimate():
    now = FakeClock()
    progress = Progress(300, now=now)  # three PDFs of 100 bytes
    progress.skip(100)  # already ingested, took no time
    now.t = 60
    progress.advance(100)
    assert progress.status() == "elapsed 1:00 | left ~1:00"  # one PDF of 100 bytes left, not two
