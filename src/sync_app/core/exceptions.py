class SyncError(Exception):
    """Базовое исключение приложения."""


class YandexAuthError(SyncError):
    """Яндекс Диск отклонил токен."""


class RemoteFolderNotFoundError(SyncError):
    """Папка на Яндекс Диске не найдена."""


class LocalFolderNotFoundError(SyncError):
    """Локальная папка синхронизации не найдена."""
