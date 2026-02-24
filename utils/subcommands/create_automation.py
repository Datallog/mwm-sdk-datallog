from argparse import Namespace
from pathlib import Path
from get_project_base_dir import get_project_base_dir

from logger import Logger
from errors import DatallogError
from validate_name import validate_name

logger = Logger(__name__)


def create_automation(args: Namespace) -> None:
    """
    Create a new automation in a project
    """
    spinner = None
    try:
        automation_name = args.automation_name.strip() if args.automation_name else ""
        if len(automation_name) == 0:
            automation_name = input("Enter the name of the new automation: ").strip()
            if len(automation_name) == 0:
                raise DatallogError("Automation name cannot be empty.")

        if not validate_name(automation_name):
            raise DatallogError(
                """Invalid automation name. The name must follow these rules:
    - Must start with a letter (a-z, A-Z)
    - Can contain letters, digits (0-9), underscores (_)
    - Must be between 3 and 50 characters long."""
            )
        project_path = get_project_base_dir()
        automation_path = project_path / "automations" / automation_name
        logger.info(f"Creating automation at: {automation_path}")
        if automation_path.exists():
            raise DatallogError(
                f"Automation '{automation_name}' already exists at {automation_path}."
            )
        automation_path.mkdir(parents=True, exist_ok=True)

        base_automation_template = (
            Path(__file__).parent.parent.parent / "base-automation" / "template.py"
        )
        with open(base_automation_template, "r") as template_file:
            template_content = template_file.read()
            template_content = template_content.replace("{{automation_name}}", automation_name)

        with open(automation_path / f"{automation_name}.py", "w") as automation_file:
            automation_file.write(template_content)
        with open(automation_path / "seed.json", "w") as seed_file:
            seed_file.write("{}")
    except FileNotFoundError as e:
        raise DatallogError(f"Failed to create automation: {e}")
    except IOError as e:
        raise DatallogError(f"Failed to write automation file: {e}")
    except DatallogError as e:
        if spinner:
            spinner.fail(f"Error: {e}")  # type: ignore
        else:
            logger.error(f"Error: {e}")
            print(f"\033[91m{e.message}\033[0m")
