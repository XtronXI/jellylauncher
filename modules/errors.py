# Error Handling, small but necessary to be here.

class JellyLauncherError(Exception): pass
class MigrationError(JellyLauncherError): pass
class ProcessError(JellyLauncherError): pass
class ConfigError(JellyLauncherError): pass
