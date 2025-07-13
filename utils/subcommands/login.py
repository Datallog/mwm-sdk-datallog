from argparse import Namespace
from logger import Logger
import webbrowser
from errors import InvalidLoginToken
from token_manager import decode_token, save_token

logger = Logger(__name__)

login_page_url = "https://mwm.datallog.com/preferences/settings"


def login(args: Namespace) -> None:
    webbrowser.open(login_page_url)

    print("Please copy the token from page:")
    print(login_page_url)
    token = input("Enter your token: ").strip()
    if not token:
        InvalidLoginToken("Token cannot be empty.")
        return
    token_parsed = token.strip()
    decode_token(token_parsed)

    save_token(token_parsed)
