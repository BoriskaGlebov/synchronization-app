import pytest
from sync_app.core.formatting import human_size


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 Б"),
        (1023, "1023 Б"),
        (1536, "1.5 КБ"),
        (5 * 1024**3, "5.0 ГБ"),
        (2 * 1024**4, "2.0 ТБ"),
    ],
)
def test_human_size(size: int, expected: str) -> None:
    assert human_size(size) == expected
