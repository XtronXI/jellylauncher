from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich.rule import Rule
import re, shutil, time, itertools, threading, readchar


console=Console()
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
ascii_title = r"""
[0;94;40m  ██[0;37;40m [0;94;40m███[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██████[0;37;40m [0;94;40m██  ██[0;37;40m [0;94;40m██▌ █[0;37;40m [0;94;40m████[0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m███[0;37;40m [0;94;40m███[0;37;40m [0m
[0;94;40m  ██[0;37;40m [0;94;40m██ [0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██  ██[0;37;40m [0;94;40m███ █[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██ [0;37;40m [0;94;40m██▐▌[0m
[0;94;40m  ██[0;37;40m [0;94;40m██ [0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██  ██[0;37;40m [0;94;40m███▌█[0;37;40m [0;94;40m██  [0;37;40m [0;94;40m██[0;37;40m  [0;94;40m██[0;37;40m [0;94;40m██ [0;37;40m [0;94;40m██[0;37;40m [0;94;40m█[0m
[0;94;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m [0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;35;40m▄[0;37;40m [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;37;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m▐[0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;37;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m [0;37;40m [0;34;45m░░[0;37;40m [0;34;45m░[0m
[0;94;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m [0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;35;40m▀[0;34;45m░░░░░[0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░[0;37;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m  [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m [0;34;45m░░[0;37;40m [0;34;45m░░[0;94;40m  [0;37;40m [0;34;45m░░░░░░[0;37;40m [0;34;45m░░[0;94;40m [0;37;40m [0;34;45m░░[0;37;40m [0;34;45m░[0m
[0;94;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m     [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;37;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m ▐[0;34;45m▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;37;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒▒[0;37;40m [0;34;45m▒▒[0;37;40m [0;34;45m▒[0m
[0;94;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m [0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;37;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;37;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;34;45m▒[0;37;40m [0;34;45m▒▒[0;94;40m  [0;37;40m [0;34;45m▒▒[0;37;40m  [0;34;45m▒▒[0;37;40m [0;34;45m▒▒[0;94;40m [0;37;40m [0;34;45m▒▒[0;37;40m [0;34;45m▒[0m
[0;94;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m [0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;37;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓▓▓▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;34;45m▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;37;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m [0;37;40m [0;34;45m▓▓▓[0;37;40m [0m
[0;94;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m [0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;37;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;37;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;34;45m▓[0;37;40m [0;34;45m▓▓[0;94;40m  [0;37;40m [0;34;45m▓▓[0;37;40m  [0;34;45m▓▓[0;37;40m [0;34;45m▓▓[0;94;40m [0;37;40m [0;34;45m▓▓[0;34;40m▐[0;34;45m▓[0m
[0;94;40m  [0;34;40m██[0;37;40m [0;34;40m██[0;94;40m [0;37;40m [0;34;40m██[0;94;40m  [0;37;40m [0;34;40m██[0;94;40m  [0;37;40m [0;34;40m██[0;37;40m [0;34;40m▄██[0;37;40m [0;34;40m██[0;94;40m  [0;37;40m [0;34;40m██[0;37;40m  [0;34;40m██[0;37;40m [0;34;45m██[0;94;40m  [0;34;45m██[0;37;40m [0;34;45m██[0;94;40m  [0;34;45m█[0;37;40m [0;34;40m██[0;94;40m  [0;37;40m [0;34;40m██[0;37;40m  [0;34;40m██[0;37;40m [0;34;40m██[0;94;40m [0;37;40m [0;34;40m██[0;37;40m [0;34;40m█[0m
[0;34;40m████[0;37;40m [0;34;40m███[0;37;40m [0;34;40m████[0;37;40m [0;34;40m████[0;37;40m [0;34;40m█████▀[0;37;40m [0;34;40m████[0;37;40m [0;34;40m██[0;37;40m  [0;34;40m██[0;37;40m [0;34;45m██████[0;37;40m [0;34;45m██[0;94;40m  [0;34;45m█[0;37;40m [0;34;40m████[0;37;40m [0;34;40m██[0;37;40m  [0;34;40m██[0;37;40m [0;34;40m███[0;37;40m [0;34;40m██[0;37;40m [0;34;40m█[0m
"""
_details = {}
_current_step = None
_steps = []
_live = None
_start_time = None
_spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])
_current_spinner = "⠋"
_completed = False
_panel_title = ""
_stop_requested = threading.Event()

def jellyfin_rule():
    console.print("")
    console.print(Rule("JELLYFIN", style="bold cyan"))

def show_header():
    terminal_width = shutil.get_terminal_size().columns

    for line in ascii_title.splitlines():
        visible_line = ANSI_ESCAPE.sub("", line)

        if visible_line.strip():
            padding = max(
                0,
                (terminal_width - len(visible_line)) // 2
            )
            print(" " * padding + line)
        else:
            print()

    print()
    print("JellyLauncher v2.1.1  •  © 2026 XtronXI".center(terminal_width))
    print()

def show_status(context):
    table = Table.grid(padding=(0, 2))

    table.add_column(style="bold cyan", justify="right")
    table.add_column(style="white")

    table.add_row("Jellyfin Version", context.jellyfin_version)
    table.add_row("OS", context.os.upper())
    table.add_row("Data Directory", str(context.data_dir))
    table.add_row("Server", context.server_url)
    table.add_row(
        "Case Sensitive",
        "[green]Yes[/green]" if context.case_sensitive else "[yellow]No[/yellow]"
    )

    panel = Panel(
        table,
        title="[bold cyan] SYSTEM [/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
        expand=False,
    )

    console.print(panel, justify="center")

def show_error(error):
    console.print()
    console.print(
        Panel(
            f"[bold red]Error:[/bold red] {error}",
            border_style="red",
            padding=(1, 2),
            expand=False,
        ),
        justify="center",
    )


def start(name):
    global _current_step

    _current_step = name
    _details.setdefault(name, [])

    _set_step(name, "running")


def success(name):
    global _current_step

    _set_step(name, "success")
    _current_step = None


def fail(name):
    global _current_step

    _set_step(name, "failed")
    _current_step = None


def verbose(context, message):
    if not context.verbose or _current_step is None:
        return

    _details.setdefault(_current_step, []).append(message)
    _refresh()


def _set_step(name, status):
    for step in _steps:
        if step[0] == name:
            step[1] = status
            _refresh()
            return

    _steps.append([name, status])
    _refresh()

def _render():

    global _current_spinner
    symbols = {
        "pending": ("○", "dim"),
        "running": (_current_spinner, "yellow"),
        "success": ("✓", "green"),
        "failed": ("✗", "red"),
    }

    lines = []

    _current_spinner = next(_spinner)

    for name, status in _steps:
        symbol, symbol_style = symbols[status]

        line = Text()
        line.append(f"{symbol} ", style=symbol_style)
        line.append(
            name,
            style="dim" if status == "pending" else "white"
        )

        lines.append(line)

        for detail in _details.get(name, []):
            detail_line = Text()
            detail_line.append("    ")
            detail_line.append(detail, style="dim")
            lines.append(detail_line)

    elapsed = time.perf_counter() - _start_time
    lines.append(Text())
    lines.append(
        Text(
            f"Elapsed: {elapsed:.1f}s",
            style="dim",
            justify="centre"
        )
    )
    if _completed:
        lines.append(Text())
        lines.append(
            Text(
                "✓ SUCCESS",
                style="bold green",
                justify="center",
            )
        )

    return Panel(
        Group(*lines),
        title=_panel_title,
        border_style="cyan",
        padding=(1, 3),
        expand=False,
    )


def _refresh():
    if _live is not None:
        _live.update(
            Align.center(_render())
            )


def begin(steps, title="[bold cyan] MIGRATION [/bold cyan]"):
    global _live, _start_time, _completed, _panel_title

    _steps.clear()
    _details.clear()
    _completed = False
    _panel_title = title

    for name in steps:
        _steps.append([name, "pending"])

    _start_time = time.perf_counter()

    _live = Live(
        refresh_per_second=10,
        transient=False,
        get_renderable=lambda: Align.center(_render()),
    )

    _live.start()

def end():
    global _live

    if _live is not None:
        _live.stop()
        _live = None

def complete():
    global _completed

    _completed = True
    _refresh()

def jellyfin_log(message):
    console.print(message)

def _key_listener():
    s_key_pressed = False
    while True:
        key = readchar.readkey().lower()

        if not s_key_pressed and key == "s":
            _stop_requested.set()
            s_key_pressed = True

def stop_requested():
    return _stop_requested.is_set()
