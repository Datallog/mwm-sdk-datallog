from argparse import Namespace
from logger import Logger
from errors import InvalidLoginTokenError
from token_manager import encode_token, save_token
import requests
from variables import datallog_url
from time import sleep
from halo import Halo  # type: ignore

logger = Logger(__name__)

login_page_url = "https://mwm.datallog.com/preferences/settings"


def login(args: Namespace) -> None:
    print("Please copy the X-Api-Key and Authorization from page:")
    print(login_page_url)

    authorization = input("Enter your Authorization token: ").strip()
    if not authorization:
        raise InvalidLoginTokenError("Authorization token cannot be empty.")

    authorization_parts = authorization.split()
    if len(authorization_parts) != 2 or authorization_parts[0].lower() != "token":
        raise InvalidLoginTokenError("Invalid Authorization token format.")

    x_api_key = input("Enter your X-Api-Key: ").strip()
    if not x_api_key:
        raise InvalidLoginTokenError("X-Api-Key cannot be empty.")

    headers = {
        "Authorization": authorization,
        "x-api-key": x_api_key,
    }
    spinner = Halo(text="Verifying token", spinner="dots") # type: ignore
    spinner.start()  # type: ignore
    for _ in range(60):
        response = requests.post(
            f"{datallog_url}/api/sdk/verify-token",
            headers=headers,
        )

        if response.status_code == 200:
            save_token(encode_token(authorization, x_api_key))
            spinner.succeed("Token verified successfully")  # type: ignore
            break
        if (
            response.status_code == 403
            and response.json().get("message") == "Forbidden"
        ):
            sleep(1)
        else:
            spinner.fail("Token verification failed") # type: ignore
            raise InvalidLoginTokenError(f"Invalid token. Please check your token.")
    else:
        spinner.fail("Token verification timed out") # type: ignore
        raise InvalidLoginTokenError(f"Invalid token. Please check your token.")
