from argparse import Namespace
from pathlib import Path

from logger import Logger
from errors import DatallogError
from get_project_base_dir import get_project_base_dir
from parser_project_ini import parse_project_ini

logger = Logger(__name__)

CUSTOM_RUNTIME = "custom"

CUSTOM_DOCKERFILE_BOILERPLATE = """# Define your custom base image
FROM python:3.10-slim

# Install system dependencies if needed (e.g for slim based images)
# RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt /project/requirements.txt
RUN pip install --no-cache-dir -r /project/requirements.txt

COPY . /project
WORKDIR /project
"""


def _available_runtimes():
    runtimes_dir = Path(__file__).parent.parent.parent / "runtimes"
    if not runtimes_dir.exists():
        return []
    return sorted(
        entry.name
        for entry in runtimes_dir.iterdir()
        if entry.is_file() and entry.name.startswith("python-")
    )


def set_runtime(args: Namespace) -> None:
    """
    Thin editor: validates the runtime and writes it to project.ini.

    It does NOT touch the local env cache — reconciliation happens lazily on the
    next `datallog run`/`install`/`push`, and the backend syncs on the next push.
    """
    runtime = (args.runtime or "").strip()
    if not runtime:
        raise DatallogError(
            "You must provide a runtime, e.g. `datallog set-runtime python-3.12` "
            "or `datallog set-runtime custom`."
        )

    available = _available_runtimes()
    if runtime != CUSTOM_RUNTIME and runtime not in available:
        choices = ", ".join(available + [CUSTOM_RUNTIME])
        raise DatallogError(f"Unknown runtime '{runtime}'. Available: {choices}.")

    project_path = get_project_base_dir()
    project_ini_path = project_path / "project.ini"
    config = parse_project_ini(project_ini_path)

    previous = config.get("project", "runtime", fallback=None)
    if previous == runtime:
        print(f"Runtime is already '{runtime}'. Nothing to do.")
        return

    config.set("project", "runtime", runtime)
    with open(project_ini_path, "w") as f:
        config.write(f)

    if runtime == CUSTOM_RUNTIME:
        dockerfile_path = project_path / "datallog.Dockerfile"
        if not dockerfile_path.exists():
            dockerfile_path.write_text(CUSTOM_DOCKERFILE_BOILERPLATE)
            logger.info(f"Created boilerplate {dockerfile_path.name}")

    logger.info(f"Runtime changed from '{previous}' to '{runtime}'.")
    print(f"\033[92mRuntime set to '{runtime}'.\033[0m")
    print(
        "Run `datallog run <automation>` to rebuild locally, "
        "or `datallog push` to deploy the new base image."
    )
