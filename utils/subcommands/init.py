import configparser
import shutil
from argparse import Namespace
from pathlib import Path

from halo import Halo  # type: ignore

from errors import DatallogError, UnableToSaveConfigError
from get_user_path import get_user_path
from logger import Logger
from get_deploy_env import get_deploy_env
from validate_name import validate_name
from conteiner import (
    conteiner_check_if_image_exists,
    conteiner_build,
    conteiner_install_from_packages_list,
)
from install_local_python import (
    get_python_executable,
    create_local_env,
    install_local_python_packages,
)
from settings import load_settings
from parser_deploy_ini import parse_deploy_ini


logger = Logger(__name__)


def create_deploy_config(
    name: str, runtime: str, region: str, output_path: Path
) -> None:
    """
    Generates a deployment configuration file.

    This function uses the configparser library to create a .ini-style
    configuration file with a [deploy] section containing the provided
    details.

    Args:
        name (str): The name for the deployment (e.g., 'deploy-1').
        runtime (str): The runtime environment (e.g., 'python-3.10').
        region (str): The deployment region (e.g., 'us-east-1').
        output_path (str): The full path, including filename, where the
                           configuration file will be saved.
    """
    # Create a new ConfigParser object
    config = configparser.ConfigParser()

    # Define the section name
    section_name = "deploy"

    # Add the 'deploy' section to the configuration
    config[section_name] = {}

    # Set the key-value pairs within the 'deploy' section
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


def init(args: Namespace) -> None:
    """
    Create a new project (deploy) with the necessary files and directories.
    """
    spinner = None
    try:
        settings   = load_settings()
        project_name = args.name.strip() if args.name else ""
        deploy_path = get_user_path()
        dirname = args.name.strip() if args.name.strip() else deploy_path.name
        deploy_ini_path = deploy_path / "deploy.ini"
        spinner = Halo(text="Creating deploy", spinner="dots")

        if not deploy_ini_path.exists():
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
            create_deploy_config(
                name=project_name,
                runtime=runtime,
                region=region,
                output_path=deploy_path / "deploy.ini",
            )
            base_project_files = Path(__file__).parent.parent.parent / "deploy-base"
            spinner.text = "Copying base project files"  # type: ignore

            shutil.copytree(base_project_files, deploy_path, dirs_exist_ok=True)
        else:
            deploy_ini = parse_deploy_ini(deploy_path / "deploy.ini")

            logger.info("Parsed deploy.ini successfully.")
            
            runtime = deploy_ini.get("deploy", "runtime")
            region = deploy_ini.get("deploy", "region")
            logger.warning(
                f"Project '{project_name}' already exists. Skipping deploy.ini creation."
            )
            spinner.succeed("Deploy configuration already exists, using existing config")  # type: ignore

        spinner.start()  # type: ignore


        python_version = runtime[(len("python-")) :].strip()

        spinner.succeed("Deploy parameters loaded successfully")  # type: ignore
        spinner.start(text="Checking Docker image")  # type: ignore
        conteiner_status = conteiner_check_if_image_exists(settings, runtime)

        if conteiner_status != "Yes":
            if conteiner_status == "Outdated":
                spinner.fail("Docker image is outdated")  # type: ignore
            else:
                spinner.fail("Docker image does not exist")  # type: ignore

            spinner.start(text="Building Docker image")  # type: ignore
            logger.warning("Docker image does not exist. Building the image...")
            conteiner_build(settings, runtime)
            spinner.succeed("Docker image built successfully")  # type: ignore
            logger.info("Docker image built successfully.")
        else:
            spinner.succeed("Runtime Docker image exists")  # type: ignore
            logger.info("Docker image exists.")

        env_path = get_deploy_env(deploy_path)
        logger.info(f"Environment Path: {env_path}")

        spinner.start(text="Installing packages in Docker container")  # type: ignore

        logger.info("Checking if packages are installed in Docker container")
        conteiner_install_from_packages_list(
            settings=settings,
            requirements_file=deploy_path / "requirements.txt",
            runtime_image=runtime,
            env_dir=env_path,
            packages=["datallog"],
        )
        spinner.succeed("Packages installed in Docker container successfully")  # type: ignore

        spinner.start(text="Installing local Python environment. This may take a while...")  # type: ignore
        python_executable = get_python_executable(python_version)
        spinner.succeed("Python executable found")  # type: ignore

        spinner.start(text="Creating local Python environment")  # type: ignore
        venv_path = create_local_env(deploy_path, python_executable)

        spinner.succeed(text="Local Python environment created successfully")  # type: ignore

        install_local_python_packages(
            deploy_dir=deploy_path,
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