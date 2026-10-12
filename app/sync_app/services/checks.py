import re
from pathlib import PurePosixPath

FORBIDDEN_CHARS = re.compile(r'[<>:"\\|?*\x00-\x1f]')
MAX_NAME_BYTES = 255


def find_problems(path: str, size: int) -> list[str]:
    """Находит причины, по которым файл может не записаться на сетевой диск.

    Args:
        path: Путь файла относительно папки назначения.
        size: Размер файла в байтах.

    Returns:
        Список причин, пустой, если проблем не видно.
    """
    problems: list[str] = []
    if size == 0:
        problems.append("пустой файл (размер 0)")
    for part in PurePosixPath(path).parts:
        forbidden = sorted(set(FORBIDDEN_CHARS.findall(part)))
        if forbidden:
            problems.append(f"недопустимые символы {forbidden!r} в «{part}»")
        if part != part.strip() or part.endswith("."):
            problems.append(f"пробел или точка на краю имени «{part}»")
        if len(part.encode()) > MAX_NAME_BYTES:
            problems.append(f"имя длиннее {MAX_NAME_BYTES} байт: «{part[:40]}…»")
    return problems


def safe_name(name: str) -> str:
    """Делает имя файла или папки допустимым для сетевых дисков (SMB, Windows).

    Недопустимые символы заменяются: `:` на `-`, остальные на `_`, табы и повторные
    пробелы схлопываются, пробелы и точки по краям убираются, длинное имя обрезается
    до 255 байт с сохранением расширения.

    Args:
        name: Имя одного элемента пути.

    Returns:
        Безопасное имя, не пустое.
    """
    cleaned = re.sub(r"\s+", " ", name.replace(":", "-"))
    cleaned = FORBIDDEN_CHARS.sub("_", cleaned).strip(" .") or "_"
    while len(cleaned.encode()) > MAX_NAME_BYTES:
        stem, dot, extension = cleaned.rpartition(".")
        cleaned = stem[:-1] + dot + extension if dot and len(extension) < 10 else cleaned[:-1]
    return cleaned
