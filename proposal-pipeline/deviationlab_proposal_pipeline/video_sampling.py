"""Timestamp scheduling for the short-video workflow described in the appendix."""

from __future__ import annotations


def uniform_sample_times(duration_seconds: float, sample_count: int = 6) -> list[float]:
    """Return evenly spaced sample starts without adding the clip endpoint.

    A 30-second clip sampled six times yields 0, 5, 10, 15, 20, and 25 seconds,
    matching the technical appendix.
    """
    if duration_seconds <= 0 or duration_seconds > 60:
        raise ValueError("duration_seconds must be greater than 0 and at most 60")
    if sample_count < 1 or sample_count > 12:
        raise ValueError("sample_count must be between 1 and 12")
    step = duration_seconds / sample_count
    return [round(index * step, 6) for index in range(sample_count)]
