from common import *
from modules import process, migrate, ui
from modules.errors import JellyLauncherError
import time, threading

def main():
    try:
        args = parse_args()
        context=initialize()
        context.verbose = args.verbose
        context.jellyfin_version = process.get_version(context)
        steps = []

        if args.stop:
            ui.begin(["Stopping Jellyfin"], title="JELLYFIN")
            process.stop(context)
            ui.complete()
            ui.end()
            return

        if context.os == "linux" and context.runtime == "service":
            threading.Thread(
                target=process._refresh_sudo,
                daemon=True,
            ).start()

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
        process.stop(context)
        if context.data_dir.exists():
            migrate.guids(context)
            migrate.metadata(context)
            migrate.database(context)
            migrate.xml(context)
            migrate.mblink(context)
            time.sleep(1)
        ui.complete()
        ui.end()
        if context.runtime == "manual":
            return
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
    except JellyLauncherError as error:
        ui.end()
        ui.show_error(error)
        return
    except Exception:
        ui.end()
        if context.verbose:
            raise
        ui.show_error(
            "An unexpected error occurred. "
            "Run with --verbose for details.",
        )
        return

if __name__ == "__main__":
    main()
