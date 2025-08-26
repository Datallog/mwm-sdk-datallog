from argparse import Namespace
from pathlib import Path
from halo import Halo  # type: ignore

from get_project_base_dir import get_deploy_base_dir

from logger import Logger
from errors import DatallogError
from validate_name import validate_name

logger = Logger(__name__)



def create_app(args: Namespace) -> None:
    """
    Create a new app in a project
    """
    spinner = None
    try:
        app_name = args.app_name.strip() if args.app_name else ""
        if len(app_name) == 0:
            app_name = input("Enter the name of the new application: ").strip()
            if len(app_name) == 0:
                raise DatallogError("Application name cannot be empty.")

        if not validate_name(app_name):
            raise DatallogError(
                """Invalid application name. The name must follow these rules:
- Must start with a letter (a-z, A-Z)
- Can contain letters, digits (0-9), underscores (_), and hyphens (-)
- Must be between 3 and 50 characters long."""
            )
        deploy_path = get_deploy_base_dir()
        app_path = deploy_path / "apps" / app_name
        logger.info(f"Creating application at: {app_path}")
        if app_path.exists():
            raise DatallogError(
                f"Application '{app_name}' already exists at {app_path}."
            )
        app_path.mkdir(parents=True, exist_ok=True)
       
        base_app_template = Path(__file__).parent.parent.parent / "base-app" / "template.py"
        with open(base_app_template, "r") as template_file:
            template_content = template_file.read()
            template_content = template_content.replace("{{app_name}}", app_name)
    
        with open(app_path / f"{app_name}.py", "w") as app_file:
            app_file.write(template_content)
        with open(app_path / "seed.json", "w") as seed_file:
            seed_file.write("{}")
    except FileNotFoundError as e:
        raise DatallogError(f"Failed to create application: {e}")
    except IOError as e:
        raise DatallogError(f"Failed to write application file: {e}")
    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")
