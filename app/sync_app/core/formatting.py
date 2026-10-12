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


def describe_error(error: BaseException) -> str:
    """Описывает исключение понятным текстом, даже если у него пустое сообщение.

    Args:
        error: Исключение.

    Returns:
        Строка вида `RequestTimeoutError (ReadTimeout)` или `Тип: сообщение`.
    """
    message = str(error).strip().splitlines()[0] if str(error).strip() else ""
    cause = error.__cause__
    cause_name = f" ({type(cause).__name__})" if cause is not None else ""
    return (
        f"{type(error).__name__}{cause_name}: {message}"
        if message
        else (f"{type(error).__name__}{cause_name}")
    )
