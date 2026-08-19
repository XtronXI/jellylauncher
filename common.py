import argparse, hashlib, json, platform, re, uuid
import xml.etree.ElementTree as ET
from pathlib import Path, PureWindowsPath, PurePosixPath
from modules.errors import ConfigError

class Context:
    def __init__(self):
        self.os = None
        self.config = None
        self.verbose = False
        self.data_dir = None
        self.server_executable = None
        self.paths = None
        self.runtime = None
        self.container = None
        self.container_engine = None
        self.service = None
        self.case_sensitive = True
        self.server_url = None
        self.api_key = None
        self.headers = None
        self.jellyfin_version = None
        self.jellyfin_process = None
        self.note = None

def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigError("config.json must contain a JSON object.")

    required = {
        "server_url": str,
        "api_key": str,
        "linux": dict,
        "windows": dict,
        "paths": dict,
    }

    for key, expected_type in required.items():
        if key not in config:
            raise ConfigError(f"Missing required configuration key: {key}")
        if not isinstance(config[key], expected_type):
            raise ConfigError(f"Configuration key '{key}' must be {expected_type.__name__}.")

    for source, destination in config["paths"].items():
        if not isinstance(source, str):
            raise ConfigError("Configuration key 'paths' contains a non-string source path.")
        if not isinstance(destination, str):
            raise ConfigError("Configuration key 'paths' contains a non-string destination path.")

    for os_name in ("linux", "windows"):
        os_config = config[os_name]
        required_os = {"data_dir": str, "server_executable": str}
        for key, expected_type in required_os.items():
            if key not in os_config:
                raise ConfigError(f"Missing required configuration key: {os_name}.{key}")
            if not isinstance(os_config[key], expected_type):
                raise ConfigError(f"Configuration key '{os_name}.{key}' must be {expected_type.__name__}.")

def initialize():
    context = Context()

    try:
        with open("config.json", "r", encoding="utf-8") as f:
            context.config = json.load(f)
    except FileNotFoundError:
        raise ConfigError("config.json was not found.")
    except json.JSONDecodeError as error:
        raise ConfigError(f"config.json contains invalid JSON: {error}") from error

    validate_config(context.config)
    system = platform.system()

    if system == "Linux":
        context.os = "linux"
        context.paths = context.config["paths"]
    elif system == "Windows":
        context.os = "windows"
        context.paths = {v: k for k, v in context.config["paths"].items()}
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    os_config = context.config[context.os]
    context.data_dir = Path(os_config["data_dir"])
    context.server_executable = Path(os_config["server_executable"])
    context.runtime = os_config["runtime"]
    context.container = os_config.get("container")
    context.container_engine = os_config.get("container_engine")
    context.service = os_config.get("service")
    context.server_url = context.config["server_url"]
    context.api_key = context.config["api_key"]
    context.case_sensitive = _read_case_sensitive(context.data_dir)
    context.headers = {"X-Emby-Token": context.api_key}
    return context

def parse_args():
    parser = argparse.ArgumentParser(prog="jellylauncher", description="Migrate and launch Jellyfin.")
    parser.add_argument("--verbose", action="store_true", help="Show detailed migration information")
    parser.add_argument("--stop", action="store_true", help="Stop Jellyfin and exit.")
    return parser.parse_args()

def _read_case_sensitive(data_dir):
    config_file = Path(data_dir) / "config" / "system.xml"
    if not config_file.exists():
        return True
    try:
        tree = ET.parse(config_file)
        node = tree.getroot().find("EnableCaseSensitiveItemIds")
        if node is not None and node.text is not None:
            return node.text.strip().lower() == "true"
    except ET.ParseError:
        pass
    return True

# ---------------------------------- Path Translation ----------------------------------

def translate(path, context):
    path = str(path)
    if (
        path.startswith("/")
        or (len(path) > 2 and path[1:3] == ":\\")
        or (len(path) > 2 and path[1:3] == ":/")
    ):
        if context.os == "linux":
            path = path.replace("\\", "/")
        else:
            path = path.replace("/", "\\")
    normalized = path.replace("\\", "/")

    for source, target in context.paths.items():
        source_normalized = source.replace("\\", "/")
        if not normalized.startswith(source_normalized):
            continue
        relative = normalized[len(source_normalized):].lstrip("/")
        if context.os == "linux":
            return str(PurePosixPath(target, *relative.split("/")))
        return str(PureWindowsPath(target, *relative.split("/")))

    return path

def translate_reverse(path, context):
    path = str(path)
    normalized = path.replace("\\", "/")

    for source, target in context.paths.items():
        target_normalized = target.replace("\\", "/")
        if not normalized.startswith(target_normalized):
            continue
        relative = normalized[len(target_normalized):].lstrip("/")
        if context.os == "linux":
            return str(PureWindowsPath(source, *relative.split("/")))
        return str(PurePosixPath(source, *relative.split("/")))

    return path

# ------------------------------------ GUID Replication ------------------------------------

def jellyfin_guid(item_type, path, program_data_path, case_sensitive=True):
    key = str(path)
    program_data_path = str(program_data_path)
    if key.startswith(program_data_path):
        key = key[len(program_data_path):].lstrip("/\\").replace("/", "\\")
    if not case_sensitive:
        key = key.lower()
    return uuid.UUID(bytes_le=hashlib.md5((item_type + key).encode("utf-16le")).digest())

def normalize_guid(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii")
        except UnicodeDecodeError:
            return None
    value = str(value).strip()
    try:
        return str(uuid.UUID(value)).upper()
    except (ValueError, AttributeError):
        return None

_GUID_DASHED = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_GUID_NODASH = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
_GUID_ANY = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])"
)
_METADATA_LIBRARY = re.compile(
    r"(?:linux_library|windows_library|library)"
    r"(?P<sep1>[\\/])"
    r"[0-9a-f]{2}"
    r"(?P<sep2>[\\/])"
    r"(?P<body>[0-9a-f]{32})",
    re.IGNORECASE,
)

def normalize_metadata_path(text):
    if not isinstance(text, str):
        return text
    def repl(match):
        return "library" + match.group("sep1") + match.group("body")[:2] + match.group("sep2") + match.group("body")
    return _METADATA_LIBRARY.sub(repl, text)

def guid_tokens(text):
    if not isinstance(text, str):
        return
    for token in _GUID_DASHED.findall(text):
        yield str(uuid.UUID(token)).upper()
    for token in _GUID_NODASH.findall(text):
        yield str(uuid.UUID(token)).upper()

def rewrite_guids_in_text(text, mapping):
    if not isinstance(text, str):
        return text

    def repl(match):
        token = match.group(0)
        canonical = str(uuid.UUID(token)).upper()
        replacement = mapping.get(canonical)
        if replacement is None:
            return token
        result = replacement if "-" in token else replacement.replace("-", "")
        return result.lower() if token.islower() else result

    if mapping:
        text = _GUID_ANY.sub(repl, text)
    return normalize_metadata_path(text)
