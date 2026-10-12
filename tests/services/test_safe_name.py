import pytest
from sync_app.services.checks import find_problems, safe_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("обычное имя.jpg", "обычное имя.jpg"),
        ("11:00 съёмка", "11-00 съёмка"),
        ("a\tb   c", "a b c"),
        ("что? где*.txt", "что_ где_.txt"),
        ("папка ", "папка"),
        ("конец.", "конец"),
        ("???", "___"),
        ("", "_"),
    ],
)
def test_safe_name(name: str, expected: str) -> None:
    assert safe_name(name) == expected


def test_long_name_is_cut_but_extension_is_kept() -> None:
    result = safe_name("я" * 200 + ".jpg")

    assert result.endswith(".jpg") and len(result.encode()) <= 255
    assert find_problems(result, 1) == []


def test_different_long_names_stay_different() -> None:
    a = safe_name("я" * 300 + "a.docx")
    b = safe_name("я" * 300 + "b.docx")

    assert a != b and len(a.encode()) <= 255 and a.endswith(".docx")
