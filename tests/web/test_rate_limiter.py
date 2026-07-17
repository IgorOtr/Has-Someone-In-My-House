"""Tests for web.rate_limiter: pure logic, no I/O, no real clock waits."""

import pytest

from web.rate_limiter import InMemoryRateLimiter


def test_allows_requests_up_to_the_limit():
    limiter = InMemoryRateLimiter(max_attempts=3, window_seconds=60)

    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is True


def test_blocks_requests_beyond_the_limit():
    limiter = InMemoryRateLimiter(max_attempts=3, window_seconds=60)
    for _ in range(3):
        limiter.is_allowed("client-a")

    assert limiter.is_allowed("client-a") is False


def test_tracks_each_key_independently():
    limiter = InMemoryRateLimiter(max_attempts=1, window_seconds=60)

    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-b") is True
    assert limiter.is_allowed("client-a") is False


def test_reset_clears_all_state():
    limiter = InMemoryRateLimiter(max_attempts=1, window_seconds=60)
    limiter.is_allowed("client-a")
    assert limiter.is_allowed("client-a") is False

    limiter.reset()

    assert limiter.is_allowed("client-a") is True


def test_old_attempts_fall_outside_the_window_and_are_forgotten(monkeypatch):
    import web.rate_limiter as module

    current_time = [1000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: current_time[0])

    limiter = InMemoryRateLimiter(max_attempts=2, window_seconds=10)
    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-a") is False

    current_time[0] += 11  # past the window

    assert limiter.is_allowed("client-a") is True


@pytest.mark.parametrize("max_attempts,window_seconds", [(0, 60), (-1, 60), (3, 0), (3, -1)])
def test_rejects_invalid_configuration(max_attempts, window_seconds):
    with pytest.raises(ValueError):
        InMemoryRateLimiter(max_attempts=max_attempts, window_seconds=window_seconds)
