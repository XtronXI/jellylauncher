class JellyLauncherError(Exception):
    """Base exception for expected JellyLauncher errors."""


class MigrationError(JellyLauncherError):
    """A migration step failed."""


class ProcessError(JellyLauncherError):
    """A Jellyfin process operation failed."""


class ConfigError(JellyLauncherError):
    """The JellyLauncher configuration is invalid."""
