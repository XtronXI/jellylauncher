# JellyLauncher

A lightweight Python launcher and migration utility for Jellyfin.

JellyLauncher handles the process of stopping Jellyfin, migrating Jellyfin data, and starting Jellyfin again while providing a clean terminal interface.

## Features

- Rich terminal UI for migration progress
- Jellyfin version detection
- Cross-platform support for Linux and Windows
- Jellyfin process management
- Linux `systemctl` integration
- Linux Jellyfin log output through `journalctl`
- Graceful Windows Jellyfin shutdown using `CTRL_BREAK_EVENT`
- Configurable Jellyfin executable and data paths
- Optional verbose migration output
- Migration stages with success/failure status
- Elapsed migration time

## Requirements

- Python 3.8 or newer
- Jellyfin Server
- Linux:
  - `systemd`
  - `sudo`
- Windows:
  - Windows console
  - Jellyfin Server

Python dependencies are listed in `requirements.txt`.

## Installation

Clone the repository:

```bash
git clone <REPOSITORY_URL>
cd JellyLauncher
````

Create a virtual environment:

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Install the dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

JellyLauncher uses a local `config.json` file.

A template is provided:

```text
config.example.json
```

Copy it to:

```text
config.json
```

and edit the values for your Jellyfin installation.

**Do not commit `config.json`.** It may contain private information such as your Jellyfin API key.

## Usage

Run JellyLauncher with:

```bash
python launcher.py
```

For verbose migration information:

```bash
python launcher.py --verbose
```

### Keyboard controls

During the Jellyfin stage:

| Key | Action        |
| --- | ------------- |
| `S` | Stop Jellyfin |

## Platform behavior

### Linux

JellyLauncher uses the system Jellyfin service:

```text
systemctl start jellyfin
systemctl stop jellyfin
```

Jellyfin output is read from `journalctl` and displayed using Rich formatting.

### Windows

JellyLauncher starts Jellyfin as a child process and places it in its own Windows process group.

Pressing `S` sends a `CTRL_BREAK_EVENT` to the Jellyfin process group, allowing Jellyfin to perform its normal shutdown handling.

## Migration

The migration process currently consists of several stages, including:

* GUID migration
* Metadata migration
* Database migration
* XML migration
* `.mblink` path updates

JellyLauncher stops Jellyfin before modifying its data and starts it again after migration.

### Jellyfin compatibility

Database and other internal Jellyfin structures can change between Jellyfin releases.

JellyLauncher should therefore only be considered compatible with Jellyfin versions that have been explicitly tested.

Do not assume that a future Jellyfin release is automatically supported.

**Back up your Jellyfin data before performing a migration.**

## Project structure

```text
JellyLauncher/
├── launcher.py
├── migrate.py
├── config.example.json
├── requirements.txt
├── README.md
├── .gitignore
└── modules/
    ├── __init__.py
    ├── process.py
    └── ui.py
```

## Development

Create a virtual environment and install the dependencies as described above.

Run JellyLauncher directly:

```bash
python launcher.py
```

Before making changes to migration logic, test against a copy or backup of your Jellyfin data.

## License

Add your chosen license here.

For example:

```text
MIT License
```

See `LICENSE` for the full license text.
