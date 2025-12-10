from argparse import Namespace
from pathlib import Path
from logger import Logger
from spinner import Spinner 
from errors import DatallogError
from uninstall_local_python import (
    get_python_executable,
    create_local_env,
    uninstall_local_packages_from_requirements,
    uninstall_local_python_packages,
    
)
from get_project_base_dir import get_project_base_dir
from parser_project_ini import parse_project_ini
from container import (
    container_check_if_image_exists,
    container_build,
    container_uninstall_from_packages_list,
    container_uninstall_from_requirements,
)
from get_project_env import get_project_env
from errors import (
    DatallogError,
)
from get_user_path import get_user_path
from settings import load_settings

logger = Logger(__name__)

    
def uninstall(args: Namespace) -> None:
    spinner = None
    try:
        settings = load_settings()
        spinner = Spinner("Loading project...")
        spinner.start()  # type: ignore
        project_path = get_project_base_dir()
        logger.info(f"Project Base Directory: {project_path}")
        logger.info("Parsing application name...")

        project_ini = parse_project_ini(project_path / "project.ini")

        logger.info("Parsed project.ini successfully.")
        logger.info("Checking if Docker image exists...")

        runtime = project_ini.get("project", "runtime")
        python_version = runtime[(len("python-")) :].strip()

        spinner.succeed("Project parameters loaded successfully")  # type: ignore
        spinner.start(text="Checking Docker image")  # type: ignore
        container_status = container_check_if_image_exists(settings=settings, runtime_image=runtime)

        if container_status != "Yes":
            if container_status == "Outdated":
                spinner.fail("Docker image is outdated")  # type: ignore
            else:
                spinner.fail("Docker image does not exist")  # type: ignore

            spinner.start(text="Building Docker image")  # type: ignore
            logger.warning("Docker image does not exist. Building the image...")
            container_build(settings, runtime)
            spinner.succeed("Docker image built successfully")  # type: ignore
            logger.info("Docker image built successfully.")
        else:
            spinner.succeed("Runtime Docker image exists")  # type: ignore
            logger.info("Docker image exists.")

        env_path = get_project_env(project_path)
        logger.info(f"Environment Path: {env_path}")

        spinner.start(text="Uninstalling packages in Docker container")  # type: ignore

        if args.packages:
            logger.info(f"Uninstalling packages: {args.packages}")
            container_uninstall_from_packages_list(
                settings=settings,
                requirements_file=project_path / "requirements.txt",
                runtime_image=runtime,
                env_dir=env_path,
                packages=args.packages,
            )
            spinner.succeed("Packages Uninstalled in Docker container successfully")  # type: ignore
        if args.requirements:
            logger.info(f"Uninstalling packages from file: {args.requirements}")
            requirements_path = get_user_path() / args.requirements
            container_uninstall_from_requirements(
                settings=settings,
                requirements_file=project_path / "requirements.txt",
                runtime_image=runtime,
                env_dir=env_path,
                new_requirements=Path(requirements_path).absolute(),
            )
            spinner.succeed(  # type: ignore
                "Packages Uninstalled from file in Docker container successfully"
            )

        spinner.succeed("Packages Uninstalled successfully")  # type: ignore

        spinner.start(text="Installing local Python environment. This may take a while...")  # type: ignore
        python_executable = get_python_executable(python_version)
        spinner.succeed("Python executable found")  # type: ignore

        spinner.start(text="Creating local Python environment")  # type: ignore
        venv_path = create_local_env(project_path, python_executable)

        spinner.succeed(message="Local Python environment created successfully")  # type: ignore
        spinner.start(text="Uninstalling packages locally")


        if args.packages:
            uninstall_local_python_packages(
                project_dir=project_path,
                python_executable=venv_path / "bin" / "python",
                packages=args.packages,
            )
        if args.requirements:
            requirements_path = get_user_path() / args.requirements
            uninstall_local_packages_from_requirements(
                project_dir=project_path,
                python_executable=venv_path / "bin" / "python",
                requirements_file=Path(requirements_path).absolute(),
            )

        spinner.succeed(message="Packages uninstalled successfully")

    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")