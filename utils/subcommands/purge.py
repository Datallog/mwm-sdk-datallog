from argparse import Namespace
from pathlib import Path
import shutil
import sys


def purge(args: Namespace) -> None:
    """
    Deletes the local cache and logs for the current deployment after user confirmation.
    """

    base_path = Path.cwd()

    paths_to_purge = {
        "project-envs": base_path / ".." / "project-envs",
        "deploy-envs": base_path / ".." / "deploy-envs",
        "datallog.log": base_path / ".." / "datallog.log",
        "selenium-drivers": base_path / ".." / "selenium-drivers",
    }

    existing_paths = {
        name: path for name, path in paths_to_purge.items() if path.exists()
    }

    if not existing_paths:
        print("Nothing to purge.")
        return

    print("The following items will be permanently deleted:")
    for name in existing_paths:
        print(f" - {name}")

    try:
        confirm = input("Are you sure you want to proceed? (Y/N): ")
    except KeyboardInterrupt:
        print("\nPurge cancelled.")
        sys.exit(0)

    if confirm.lower() == "y":
        for name, path in existing_paths.items():
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                    print(f"Deleted directory: {name}")
                elif path.is_file():
                    path.unlink()
                    print(f"Deleted file: {name}")
            except OSError as e:
                print(f"Error deleting {name}: {e}", file=sys.stderr)
        print("Purge complete.")
    else:
        print("Purge cancelled.")
