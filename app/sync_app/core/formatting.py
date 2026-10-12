def human_size(size: int) -> str:
    """Переводит размер в байтах в читаемую строку.

    Args:
        size: Размер в байтах.

    Returns:
        Строка вида `1.5 ГБ`.
    """
    value = float(size)
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "Б" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} ТБ"
