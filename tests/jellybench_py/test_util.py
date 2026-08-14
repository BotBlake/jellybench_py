import pytest
from jellybench_py.util import format_time


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (1, "1s"),
        (59, "59s"),
        (60, "1m"),
        (61, "1m 1s"),
        (3599, "59m 59s"),
        # no more seconds for >= 1h
        (3600, "1h"),
        (3601, "1h"),
        (3660, "1h 1m"),
        (3661, "1h 1m"),
    ],
)
def test_format_time(seconds: int, expected: str) -> None:
    result = format_time(seconds)
    assert result == expected
