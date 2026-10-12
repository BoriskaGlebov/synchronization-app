from sync_app.services.checks import find_problems


def test_clean_name_has_no_problems() -> None:
    assert find_problems("2022/05/IMG 1.jpg", 10) == []


def test_empty_file_is_reported() -> None:
    assert any("пустой" in p for p in find_problems("a.jpg", 0))


def test_forbidden_characters_are_reported() -> None:
    assert any("недопустимые" in p for p in find_problems("a/12:30?.jpg", 1))


def test_trailing_space_and_dot_are_reported() -> None:
    assert find_problems("папка /a.jpg", 1)
    assert find_problems("a.", 1)


def test_too_long_name_is_reported() -> None:
    assert any("длиннее" in p for p in find_problems("я" * 200 + ".jpg", 1))
