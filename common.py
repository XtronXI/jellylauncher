import hashlib, json, platform, re, uuid, shutil, argparse
import xml.etree.ElementTree as ET
from pathlib import Path, PureWindowsPath, PurePosixPath
from modules import ui, process

class Context:
    def __init__(self):
        self.os = None
        self.config = None
        self.verbose = False
        self.data_dir = None
        self.db_path = None
        self.server_executable = None
        self.paths = None
        self.case_sensitive = True
        self.server_url = None
        self.api_key = None
        self.headers = None
        self.jellyfin_version = None
        self.jellyfin_process = None


def initialize():
    context = Context()

    # Detect OS
    system = platform.system()

    if system == "Linux":
        context.os = "linux"
    elif system == "Windows":
        context.os = "windows"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")

    # Load config
    with open("config.json", "r", encoding="utf-8") as f:
        context.config = json.load(f)

    os_config = context.config[context.os]

    context.data_dir = Path(os_config["data_dir"])
    context.server_executable = Path(os_config["server_executable"])
    context.db_path = Path(os_config["db_path"])
    context.paths = os_config["paths"]

    context.server_url = context.config["server_url"]
    context.api_key = context.config["api_key"]
    context.case_sensitive = _read_case_sensitive(context.data_dir)

    context.headers = {
        "X-Emby-Token": context.api_key
    }
    return context

def parse_args():
    parser = argparse.ArgumentParser(
        description="JellyLauncher"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed migration information",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop Jellyfin and exit.",
    )

    return parser.parse_args()

def _read_case_sensitive(data_dir):
    """Read EnableCaseSensitiveItemIds from Jellyfin's system.xml (default: True)."""
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
    """
    Convert a path that is already in the current OS's form back to the form
    used by the other OS (the inverse of translate).

    Used to recompute the GUID an item had on the other OS so metadata
    folders stored under the old name can be found and renamed.
    """
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


def jellyfin_guid(item_type, path, program_data_path, case_sensitive=True):
    """
    Replicates Jellyfin's LibraryManager.GetNewItemIdInternal():
    - hashes the raw path with its native separators (backslashes on
      Windows, forward slashes on Linux) unless it sits under the
      program-data path, in which case the prefix is stripped and
      separators normalized to backslashes to keep it portable,
    - lowercases the key unless case-sensitive IDs are enabled,
    - md5s (type + key) in UTF-16LE as a .NET Guid.
    """
    key = str(path)
    program_data_path = str(program_data_path)

    if key.startswith(program_data_path):
        key = key[len(program_data_path):]
        key = key.lstrip("/\\")
        key = key.replace("/", "\\")

    if not case_sensitive:
        key = key.lower()

    key = item_type + key

    digest = hashlib.md5(
        key.encode("utf-16le")
    ).digest()

    return uuid.UUID(bytes_le=digest)


def normalize_guid(value):
    """Return a canonical uppercase-dashed GUID string if value looks like a GUID."""
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


_GUID_DASHED = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_GUID_NODASH = re.compile(
    r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])"
)
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
    """
    Repair stored metadata paths so they always point at the active 'library'
    tree and use a {prefix}/{guid} folder layout where the 2-char prefix is
    the GUID's own first two characters.

    A blanket GUID-token rewrite (see rewrite_guids_in_text) changes the
    folder name inside a path but leaves the 2-char prefix stale, producing
    e.g. metadata\\library\\c1\\7eb4897b...\\poster.jpg. This normalizes it
    to metadata\\library\\7e\\7eb4897b...\\poster.jpg.
    """
    if not isinstance(text, str):
        return text

    def repl(match):
        sep1 = match.group("sep1")
        sep2 = match.group("sep2")
        body = match.group("body")
        return "library" + sep1 + body[:2] + sep2 + body

    return _METADATA_LIBRARY.sub(repl, text)


def guid_tokens(text):
    """Yield canonical uppercase-dashed GUIDs contained in a string."""
    if not isinstance(text, str):
        return

    for token in _GUID_DASHED.findall(text):
        yield str(uuid.UUID(token)).upper()

    for token in _GUID_NODASH.findall(text):
        yield str(uuid.UUID(token)).upper()


def rewrite_guids_in_text(text, mapping):
    """
    Replace every GUID token found in `text` that is a key of `mapping`
    (canonical uppercase-dashed) with its mapped value, preserving the
    original token's style (dashed vs no-dash, case).

    Also normalizes any Jellyfin metadata-library paths embedded in the text
    so their {prefix}/{guid} folders stay consistent after the rewrite.

    Handles plain GUID cells, comma-separated lists (ExtraIds) and
    N-format GUIDs embedded in JSON (BaseItems.Data).
    """
    if not isinstance(text, str):
        return text

    def repl(match):
        token = match.group(0)
        canonical = str(uuid.UUID(token)).upper()
        replacement = mapping.get(canonical)

        if replacement is None:
            return token

        if "-" in token:
            result = replacement
        else:
            result = replacement.replace("-", "")

        if token.islower():
            return result.lower()

        return result

    if mapping:
        text = _GUID_ANY.sub(repl, text)

    return normalize_metadata_path(text)
