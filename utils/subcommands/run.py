from argparse import Namespace
import json
import os
from get_project_base_dir import get_project_base_dir
from get_project_env import Path, get_project_env
from parser_project_ini import parse_project_ini
from container import (
    container_build,
    container_install_packages,
    container_check_if_image_exists,
)
from errors import InvalidAppError
from worker_server import WorkerServer
from halo import Halo  # type: ignore

from settings import load_settings

def parse_app(app_name: str) -> str:
    app_name = app_name.strip()
    if app_name.endswith("/"):
        app_name = app_name[:-1]
    if app_name.startswith("./"):
        app_name = app_name[2:]
    if app_name.endswith(".py"):
        app_name = app_name[:-3]
    if app_name.startswith("apps/"):
        app_name = app_name[5:]

    if not app_name:
        raise InvalidAppError("App name cannot be empty.")
    app_name_parts = app_name.split("/")
    if len(app_name_parts) > 1:
        app_name = app_name_parts[-1]

    return app_name


def run(args: Namespace) -> None:
    spinner = None
    try:
        settings = load_settings()
        project_path = get_project_base_dir()

        processed_app_name = parse_app(args.app_name)

        app_path = (
            project_path / "apps" / processed_app_name / f"{processed_app_name}.py"
        )
        if not app_path.exists():
            raise InvalidAppError(
                f"Application file '{app_path}' does not exist. Please check the app name."
            )

        spinner = Halo(text="Loading project", spinner="dots")  # type: ignore

        project_ini = parse_project_ini(project_path / "project.ini")

        runtime: str = project_ini.get("project", "runtime")

        spinner.succeed("Project parameters loaded successfully")  # type: ignore

        spinner.start(text="Checking Docker image")  # type: ignore
        container_status = container_check_if_image_exists(settings, runtime)

        if container_status != "Yes":
            if container_status == "Outdated":
                print("Docker image is outdated. Building the image...")
                spinner.fail("Docker image is outdated")  # type: ignore
            else:
                print("Docker image does not exist. Building the image...")
                spinner.fail("Docker image does not exist")  # type: ignore
            spinner.start(text="Building Docker image")  # type: ignore
            container_build(settings, runtime)
            spinner.succeed("Docker image built successfully")  # type: ignore
        else:
            spinner.succeed("Runtime Docker image exists")  # type: ignore
            pass

        spinner.start(text="Checking if packages are installed in Docker container")  # type: ignore
        env_path = get_project_env(project_path)
        container_install_packages(
            settings=settings,
            requirements_file=project_path / "requirements.txt",
            runtime_image=runtime,
            env_dir=env_path,
        )

        spinner.succeed("Packages installed in Docker container successfully")  # type: ignore

        seed_content = None
        try:
            if args.seed is not None:
                seed_content = json.loads(args.seed)
            else:
                seed_file = args.seed_file.strip() if args.seed_file else ""
                if not seed_file:
                    seed_file = project_path / "apps" / processed_app_name / "seed.json"
                if not os.path.exists(seed_file):
                    raise InvalidAppError(
                        f"Seed file '{seed_file}' does not exist. Please provide a valid seed file."
                    )
                with open(seed_file, "r") as seed_file:
                    seed_content = json.load(seed_file)
        except json.JSONDecodeError as e:
            raise InvalidAppError(
                f"Invalid seed content, please provide a valid JSON: {e}"
            )
        log_to_dir = None
        if args.log_to_dir:
            try:
                log_to_dir = Path(args.log_to_dir)
                if not log_to_dir.exists():
                    log_to_dir.mkdir(parents=True, exist_ok=True)
                if not log_to_dir.is_dir():
                    raise InvalidAppError(f"{log_to_dir} is not a directory.")
                
            except Exception as e:
                raise InvalidAppError(f"Error creating log directory: {e}")
    
        server = WorkerServer(
            settings=settings,
            runtime_image=runtime,
            project_dir=project_path,
            env_dir=env_path,
            app_name=processed_app_name,
            parallelism=args.parallelism,
            seed=seed_content,
            log_to_dir=log_to_dir.absolute() if log_to_dir else None,
        )
        server.serve_forever()
    except InvalidAppError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            print(f"\033[91mError: {e}\033[0m")
