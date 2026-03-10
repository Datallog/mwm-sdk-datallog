from argparse import Namespace
import json
import os
import subprocess
from get_project_base_dir import get_project_base_dir
from get_project_env import Path, get_project_env
from parser_project_ini import parse_project_ini
from container import (
    container_build,
    container_install_packages,
    container_check_if_image_exists,
)
from errors import InvalidAutomationError
from worker_server import WorkerServer
from spinner import Spinner

from settings import load_settings

def parse_automation(automation_name: str) -> str:
    automation_name = automation_name.strip()
    if automation_name.endswith("/"):
        automation_name = automation_name[:-1]
    if automation_name.startswith("./"):
        automation_name = automation_name[2:]
    if automation_name.endswith(".py"):
        automation_name = automation_name[:-3]
    if automation_name.startswith("automations/"):
        automation_name = automation_name[5:]

    if not automation_name:
        raise InvalidAutomationError("Automation name cannot be empty.")
    automation_name_parts = automation_name.split("/")
    if len(automation_name_parts) > 1:
        automation_name = automation_name_parts[-1]

    return automation_name


def run(args: Namespace) -> None:
    spinner = None
    try:
        settings = load_settings()
        project_path = get_project_base_dir()

        processed_automation_name = parse_automation(args.automation_name)

        app_path = (
            project_path / "automations" / processed_automation_name / f"{processed_automation_name}.py"
        )
        if not app_path.exists():
            raise InvalidAutomationError(
                f"Automation file '{app_path}' does not exist. Please check the automation name."
            )

        spinner = Spinner("Loading project...")

        project_ini = parse_project_ini(project_path / "project.ini")

        runtime: str = project_ini.get("project", "runtime")
        project_name: str = project_ini.get("project", "name")

        spinner.succeed("Project parameters loaded successfully")  # type: ignore

        is_custom_image = (runtime == "custom")
        runtime_image_for_server = runtime

        if is_custom_image:
            spinner.start(text="Building custom Docker image") # type: ignore
            dockerfile_path = project_path / "datallog.Dockerfile"
            if not dockerfile_path.exists():
                raise InvalidAutomationError("Missing datallog.Dockerfile for custom runtime. Please create one.")
            
            local_custom_image_name = f"local-custom-{project_name}"
            res = subprocess.run(
                ["docker", "build", "-t", local_custom_image_name, "-f", "datallog.Dockerfile", "."],
                cwd=str(project_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if res.returncode != 0:
                raise InvalidAutomationError(f"Failed to build custom image: {res.stderr.decode('utf-8')}")
            spinner.succeed("Custom Docker image built successfully") # type: ignore
            runtime_image_for_server = local_custom_image_name
        else:
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

        env_path = get_project_env(project_path)
        spinner.start(text="Checking if packages are installed in Docker container")  # type: ignore
        container_install_packages(
            settings=settings,
            requirements_file=project_path / "requirements.txt",
            runtime_image=runtime_image_for_server,
            env_dir=env_path,
            is_custom_image=is_custom_image,
        )
        spinner.succeed("Packages installed in Docker container successfully")  # type: ignore

        seed_content = None
        try:
            if args.seed is not None:
                seed_content = json.loads(args.seed)
            else:
                seed_file = args.seed_file.strip() if args.seed_file else ""
                if not seed_file:
                    seed_file = project_path / "automations" / processed_automation_name / "seed.json"
                if not os.path.exists(seed_file):
                    raise InvalidAutomationError(
                        f"Seed file '{seed_file}' does not exist. Please provide a valid seed file."
                    )
                with open(seed_file, "r") as seed_file:
                    seed_content = json.load(seed_file)
        except json.JSONDecodeError as e:
            raise InvalidAutomationError(
                f"Invalid seed content, please provide a valid JSON: {e}"
            )
        log_to_dir = None
        if args.log_to_dir:
            try:
                log_to_dir = Path(args.log_to_dir)
                if not log_to_dir.exists():
                    log_to_dir.mkdir(parents=True, exist_ok=True)
                if not log_to_dir.is_dir():
                    raise InvalidAutomationError(f"{log_to_dir} is not a directory.")
                
            except Exception as e:
                raise InvalidAutomationError(f"Error creating log directory: {e}")
    
        server = WorkerServer(
            settings=settings,
            runtime_image=runtime_image_for_server,
            project_dir=project_path,
            env_dir=env_path,
            automation_name=processed_automation_name,
            parallelism=args.parallelism,
            seed=seed_content,
            log_to_dir=log_to_dir.absolute() if log_to_dir else None,
            is_custom_image=is_custom_image,
        )
        server.serve_forever()
    except InvalidAutomationError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            print(f"\033[91mError: {e}\033[0m")
