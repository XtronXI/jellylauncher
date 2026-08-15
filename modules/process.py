import platform, subprocess, requests, time, threading, signal
from modules import ui
from modules.errors import ProcessError

def is_running(context):
    try:
        response = requests.get(
            context.server_url + "/System/Info/Public",
            timeout=1
        )

        return response.ok

    except requests.RequestException:   
        return False

def stop(context):
    ui.start("Stopping Jellyfin")
    try:
        if is_running(context):
            if context.os == "windows":
                context.jellyfin_process.send_signal(signal.CTRL_BREAK_EVENT)
            elif context.os == "linux":
                subprocess.run(
                    ["sudo", "-n", "systemctl", "stop", "jellyfin"],
                    check=True,
                )
            timeout = 30
            start_time = time.monotonic()

            while is_running(context):
                if time.monotonic() - start_time > timeout:
                    raise ProcessError(
                        "Timed out waiting for Jellyfin to stop."
                    )

                time.sleep(1)
        ui.success("Stopping Jellyfin")
    except Exception as error:
        ui.fail("Stopping Jellyfin")
        raise ProcessError(
            f"Failed to stop Jellyfin: {error}"
        ) from error

def _read_jellyfin_output(context):
    for line in context.jellyfin_process.stdout:
        ui.jellyfin_log(line.rstrip())

def start(context, timeout=30):
    try:
        if context.os == "windows":
            context.jellyfin_process = subprocess.Popen([
                str(context.server_executable),
                "--datadir",
                str(context.data_dir)
                ],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )

        elif context.os == "linux":
            subprocess.run(
                ["sudo", "systemctl", "start", "jellyfin"]
            )
            start_time = time.monotonic()

        while not is_running(context):
            if time.monotonic() - start_time > timeout:
                raise ProcessError(
                    "Jellyfin failed to start within "
                    f"{timeout} seconds."
                )
            time.sleep(0.5)
    except Exception as error:
        raise ProcessError(
            f"Failed to start Jellyfin: {error}"
        ) from error

def start_logs(context):
    if context.os == "windows":
        return
    context.jellyfin_process = subprocess.Popen(
        [
            "journalctl",
            "-u", "jellyfin",
            "-f",
            "--no-pager",
            #"-n", "50",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threading.Thread(
        target=_read_jellyfin_output,
        args=(context,),
        daemon=True,
    ).start()

def get_version(context):
    result = subprocess.run(
        [str(context.server_executable), "--version"],
        capture_output=True,
        text=True,
    )

    output = result.stdout.strip() or result.stderr.strip()

    version = output.replace("Jellyfin.Server ", "")

    if version.endswith(".0"):
        version = version[:-2]

    return version

def _refresh_sudo():
    while True:
        time.sleep(300)  # 5 minutes

        result = subprocess.run(
            ["sudo", "-n", "-v"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if result.returncode != 0:
            break
