from argparse import Namespace

from token_manager import delete_token
from logger import Logger

logger = Logger(__name__)

def logout(args: Namespace) -> None:
    delete_token()
    print("Logged out successfully.")
    logger.info("You have been logged out successfully.")
