import configparser
import shutil
from argparse import Namespace
from pathlib import Path

from halo import Halo  # type: ignore

from errors import DatallogError, UnableToSaveConfigError
from get_user_path import get_user_path
from logger import Logger
from get_project_env import get_project_env
from validate_name import validate_name
from container import (
    container_check_if_image_exists,
    container_build,
    container_install_from_packages_list,
)
from install_local_python import (
    get_python_executable,
    create_local_env,
    install_local_python_packages,
)
from settings import load_settings
from parser_project_ini import parse_project_ini


logger = Logger(__name__)


def create_project_config(
    name: str, runtime: str, region: str, output_path: Path
) -> None:
    """
    Generates a project configuration file.

    This function uses the configparser library to create a .ini-style
    configuration file with a [project] section containing the provided
    details.

    Args:
        name (str): The name for the project (e.g., 'project-1').
        runtime (str): The runtime environment (e.g., 'python-3.10').
        region (str): The project region (e.g., 'us-east-1').
        output_path (str): The full path, including filename, where the
                           configuration file will be saved.
    """
    # Create a new ConfigParser object
    config = configparser.ConfigParser()

    # Define the section name
    section_name = "project"

    # Add the 'project' section to the configuration
    config[section_name] = {}

    # Set the key-value pairs within the 'project' section
    config[section_name]["name"] = name
    config[section_name]["runtime"] = runtime
    config[section_name]["region"] = region

    # Write the configuration to the specified output file
    try:
        with open(str(output_path), "w") as configfile:
            config.write(configfile)
    except IOError as e:
        raise UnableToSaveConfigError(
            f"Unable to save configuration file at {output_path}"
        ) from e


def create_project(args: Namespace) -> None:
    """
    Create a new project with the necessary files and directories.
    """
    spinner = None
    try:
        settings   = load_settings()
        current_path: Path = get_user_path()
        project_name = args.name.strip() if args.name.strip() else ''
        
        spinner = Halo(text="Creating project", spinner="dots") # type: ignore
        project_path = current_path
        project_ini_path = project_path / "project.ini"
        
        dirname = current_path.name
        if not project_ini_path.exists() and project_name:
            project_path = current_path / project_name
            project_ini_path = project_path / "project.ini"
        
        if project_ini_path.exists():
            project_ini = parse_project_ini(project_ini_path)

            logger.info("Parsed project.ini successfully.")

            runtime = project_ini.get("project", "runtime")
            region = project_ini.get("project", "region")
            logger.warning(
            f"Project '{project_name}' already exists. Skipping project.ini creation."
            )
            spinner.succeed("project configuration already exists, using existing config")  # type: ignore
        else:        
            if len(project_name) == 0:
                project_name = input(f"Enter the name of the new project or press enter to use ({dirname}): ").strip()
                if len(project_name) == 0:
                    project_name = dirname

            if not validate_name(project_name):
                raise DatallogError(
                    """Invalid project name. The name must follow these rules:
    - Must start with a letter (a-z, A-Z)
    - Can contain letters, digits (0-9), underscores (_), and hyphens (-)
    - Must be between 3 and 50 characters long."""
                )
            runtime = "python-3.10"
            region = "us-east-1"
            
            
            if project_name == dirname:
                project_path = current_path
            else:
                project_path = current_path / project_name
            project_path.mkdir(parents=True, exist_ok=True)
            project_ini_path = project_path / "project.ini"
            create_project_config(
                name=project_name,
                runtime=runtime,
                region=region,
                output_path=project_ini_path,
            )
            base_project_files = Path(__file__).parent.parent.parent / "project-base"
            spinner.text = "Copying base project files"  # type: ignore

            shutil.copytree(base_project_files, project_path, dirs_exist_ok=True)
    

        spinner.start()  # type: ignore


        python_version = runtime[(len("python-")) :].strip()

        spinner.succeed("project parameters loaded successfully")  # type: ignore
        spinner.start(text="Checking Docker image")  # type: ignore
        container_status = container_check_if_image_exists(settings, runtime)

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

        logger.info("Checking if packages are installed in Docker container")
        container_install_from_packages_list(
            settings=settings,
            requirements_file=project_path / "requirements.txt",
            runtime_image=runtime,
            env_dir=env_path,
            packages=["datallog"],
        )
        spinner.succeed("Packages installed in Docker container successfully")  # type: ignore

        spinner.start(text="Installing local Python environment. This may take a while...")  # type: ignore
        python_executable = get_python_executable(python_version)
        spinner.succeed("Python executable found")  # type: ignore

        spinner.start(text="Creating local Python environment")  # type: ignore
        venv_path = create_local_env(project_path, python_executable)

        spinner.succeed(text="Local Python environment created successfully")  # type: ignore

        install_local_python_packages(
            project_dir=project_path,
            python_executable=venv_path / "bin" / "python",
            packages=["datallog"],
        )
    except FileNotFoundError as e:
        raise DatallogError(f"Failed to create project: {e}")
    except IOError as e:
        raise DatallogError(f"Failed to write project file: {e}")
    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")