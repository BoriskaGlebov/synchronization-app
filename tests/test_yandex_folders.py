from sync_app.clients.yandex import YandexDisk


def test_nested_folders_are_dropped() -> None:
    assert YandexDisk._top_level(["/A/B", "/A", "/C"]) == ["/A", "/C"]


def test_root_swallows_everything() -> None:
    assert YandexDisk._top_level(["/A", "/"]) == ["/"]


def test_similar_names_are_kept() -> None:
    assert YandexDisk._top_level(["/Фото", "/Фотокамера"]) == ["/Фото", "/Фотокамера"]
