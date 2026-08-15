from common import *
from modules import process, migrate, ui
import time, threading

def main():
    args = parse_args()
    context=initialize()
    context.verbose = args.verbose
    context.jellyfin_version = process.get_version(context)
    steps = []

    if context.os == "linux":
        threading.Thread(
            target=process._refresh_sudo,
            daemon=True,
        ).start()
    if args.stop:
        ui.begin(["Stopping Jellyfin"], title="JELLYFIN")
        try:
            ui.start("Stopping Jellyfin")
            process.stop(context)
            ui.success("Stopping Jellyfin")
            ui.complete()
        except Exception as error:
            ui.end()
            ui.show_error(context, error)
            return

        ui.end()
        return

    ui.show_header()
    ui.show_status(context)

    steps.append("Stopping Jellyfin")
    if context.data_dir.exists():
        steps += [
            "Migrating GUIDs",
            "Migrating metadata",
            "Migrating database",
            "Migrating XML",
            "Updating .mblink paths",
        ]
    else:
        steps.append("Skipping migration as Data doesn't exist!")

    ui.begin(steps)
    try:
        ui.start("Stopping Jellyfin")
        process.stop(context)
        ui.success("Stopping Jellyfin")
        if context.data_dir.exists():
            migrate.guids(context)
            migrate.metadata(context)
            migrate.database(context)
            migrate.xml(context)
            migrate.mblink(context)
            time.sleep(1)
        ui.complete()
        ui.end()
        ui.jellyfin_rule()
        process.start(context)            
        process.start_logs(context)
        threading.Thread(
            target=ui._key_listener,
            daemon=True,
        ).start()
        while True:
            if ui.stop_requested():
                process.stop(context)
                break
            time.sleep(0.1)
    except Exception as error:
        ui.end()
        ui.show_error(context, error)
        if context.verbose:
            raise
        return

if __name__ == "__main__":
    main()
