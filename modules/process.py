import subprocess, threading, time
import requests
from modules import ui
from modules.errors import ProcessError

def is_running(context):
    try:
        requests.get(context.server_url + "/System/Info/Public", timeout=1)
        return True
    except requests.RequestException:
        return False

def stop(context):
    ui.start("Stopping Jellyfin")
    try:
        if is_running(context):
            response = requests.post(
                context.server_url + "/System/Shutdown",
                headers=context.headers,
                timeout=5,
            )
            response.raise_for_status()
            start_time = time.monotonic()
            while is_running(context):
                if time.monotonic() - start_time > 30:
                    raise ProcessError("Timed out waiting for Jellyfin to stop.")
                time.sleep(1)
        ui.success("Stopping Jellyfin")
    except Exception as error:
        ui.fail("Stopping Jellyfin")
        raise ProcessError(f"Failed to stop Jellyfin: {error}") from error

def _read_jellyfin_output(context):
    for line in context.jellyfin_process.stdout:
        ui.jellyfin_log(line.rstrip())

def _read_log_file(path):
    with path.open("r", encoding="utf-8", errors="replace") as file:
        file.seek(0, 2)
        while True:
            line = file.readline()
            if line:
                ui.jellyfin_log(line.rstrip())
            else:
                time.sleep(0.1)

def start(context, timeout=30):
    try:
        if context.runtime == "process":
            subprocess.Popen(
                [str(context.server_executable), "--datadir", str(context.data_dir)],
                **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if context.os == "windows" else {}),
            )
        elif context.runtime == "service":
            if context.os == "linux":
                subprocess.run(
                    ["sudo", "systemctl", "start", context.service],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                )
            elif context.os == "windows":
                subprocess.run(["sc", "start", context.service], check=True)
        elif context.runtime == "container":
            subprocess.run([context.container_engine, "start", context.container], check=True)

        start_time = time.monotonic()
        while not is_running(context):
            if time.monotonic() - start_time > timeout:
                raise ProcessError(f"Jellyfin failed to start within {timeout} seconds.")
            time.sleep(0.5)
    except Exception as error:
        raise ProcessError(f"Failed to start Jellyfin: {error}") from error

def start_logs(context):
    if context.runtime == "process":
        return
    elif context.runtime == "service":
        if context.os == "linux":
            context.jellyfin_process = subprocess.Popen(
                ["journalctl", "-u", context.service, "-f", "--no-pager"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            threading.Thread(target=_read_jellyfin_output, args=(context,), daemon=True).start()
        elif context.os == "windows":
            log_dir = context.data_dir / "log"
            log_file = max(log_dir.glob("*.log"), key=lambda path: path.stat().st_mtime)
            threading.Thread(target=_read_log_file, args=(log_file,), daemon=True).start()
    elif context.runtime == "container":
        context.jellyfin_process = subprocess.Popen(
            [context.container_engine, "logs", "-f", "--tail", "0", context.container],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        threading.Thread(target=_read_jellyfin_output, args=(context,), daemon=True).start()

def get_version(context):
    result = subprocess.run([str(context.server_executable), "--version"], capture_output=True, text=True)
    output = result.stdout.strip() or result.stderr.strip()
    version = output.replace("Jellyfin.Server ", "")
    if version.endswith(".0"):
        version = version[:-2]
    return version

def _refresh_sudo():
    while True:
        time.sleep(300)
        result = subprocess.run(["sudo", "-n", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode != 0:
            break
