from argparse import Namespace

from token_manager import delete_token
from logger import Logger

logger = Logger(__name__)

def logout(args: Namespace) -> None:
    # retrieve_token() falls back to the global credential, so wiping only one of
    # the two would leave the user logged in.
    project_path = getattr(args, "project_path", None)
    if project_path:
        delete_token(project_path)
    delete_token()
    print("Logged out successfully.")
    logger.info("You have been logged out successfully.")
