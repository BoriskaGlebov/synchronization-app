class SyncError(Exception):
    """Базовое исключение приложения."""


class LocalFolderNotFoundError(SyncError):
    """Локальная папка синхронизации не найдена."""


class AuthRequiredError(SyncError):
    """Нет действующего токена, нужно выполнить `sync-app auth`."""
