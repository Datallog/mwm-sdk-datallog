from argparse import Namespace

from token_manager import retrieve_token, delete_token
from logger import Logger
from errors import NotLoggedInError
logger = Logger(__name__)

def logout(args: Namespace) -> None:
    token = retrieve_token()
    if not token:
        raise NotLoggedInError("You are not logged in.")

    delete_token()
    logger.info("You have been logged out successfully.")
