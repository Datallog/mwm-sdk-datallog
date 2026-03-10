from argparse import Namespace
from pathlib import Path
from logger import Logger
from spinner import Spinner
from errors import DatallogError
from install_local_python import (
    get_python_executable,
    create_local_env,
    install_local_packages_from_requirements,
    install_local_python_packages,
)
from get_project_base_dir import get_project_base_dir
from parser_project_ini import parse_project_ini
from container import (
    container_check_if_image_exists,
    container_build,
    container_install_from_packages_list,
    container_install_from_requirements,
)
from get_project_env import get_project_env
from errors import (
    DatallogError,
)
from get_user_path import get_user_path

from settings import load_settings

logger = Logger(__name__)

    
def install(args: Namespace) -> None:
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
        project_name = project_ini.get("project", "name")
        
        if runtime == "custom":
            python_version = "3.10"
        else:
            python_version = runtime[(len("python-")) :].strip()

        spinner.succeed("Project parameters loaded successfully")  # type: ignore

        is_custom_image = (runtime == "custom")
        runtime_image_for_server = runtime

        if is_custom_image:
            spinner.start(text="Building custom Docker image locally") # type: ignore
            import subprocess
            local_custom_image_name = f"local-custom-{project_name}"
            res = subprocess.run(
                ["docker", "build", "-t", local_custom_image_name, "-f", "datallog.Dockerfile", "."],
                cwd=str(project_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if res.returncode != 0:
                raise DatallogError(f"Failed to build custom image: {res.stderr.decode('utf-8')}")
            spinner.succeed("Custom Docker image built successfully") # type: ignore
            logger.info("Custom environment detected, local image built.")
            runtime_image_for_server = local_custom_image_name
        else:
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

        spinner.start(text="Installing packages in Docker container")  # type: ignore

        if args.packages:
            logger.info(f"Installing packages: {args.packages}")
            container_install_from_packages_list(
                settings=settings,
                requirements_file=project_path / "requirements.txt",
                runtime_image=runtime_image_for_server,
                env_dir=env_path,
                packages=args.packages,
                is_custom_image=is_custom_image,
            )
            spinner.succeed("Packages installed in Docker container successfully")  # type: ignore
        if args.requirements:
            requirements_path = get_user_path() / args.requirements
            logger.info(f"Installing packages from file: {args.requirements}")
            container_install_from_requirements(
                settings=settings,
                requirements_file=project_path / "requirements.txt",
                runtime_image=runtime_image_for_server,
                env_dir=env_path,
                new_requirements=Path(requirements_path).absolute(),
                is_custom_image=is_custom_image,
            )
            spinner.succeed(  # type: ignore
                "Packages installed from file in Docker container successfully"
            )

        spinner.succeed(message="Packages installed successfully")  # type: ignore

        spinner.start(text="Installing local Python environment. This may take a while...")  # type: ignore
        python_executable = get_python_executable(python_version)
        spinner.succeed("Python executable found")  # type: ignore

        spinner.start(text="Creating local Python environment")  # type: ignore
        venv_path = create_local_env(project_path, python_executable)

        spinner.succeed(message="Local Python environment created successfully")  # type: ignore
        spinner.start(text="Installing packages locally")

        if args.packages:
            install_local_python_packages(
                project_dir=project_path,
                python_executable=venv_path / "bin" / "python",
                packages=args.packages,
            )
        if args.requirements:
            requirements_path = get_user_path() / args.requirements
            install_local_packages_from_requirements(
                project_dir=project_path,
                python_executable=venv_path / "bin" / "python",
                requirements_file=Path(requirements_path).absolute(),
            )
        spinner.succeed(message="Packages installed successfully")


    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")