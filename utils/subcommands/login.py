from argparse import Namespace
from logger import Logger
from errors import DatallogError, InvalidLoginTokenError
from token_manager import encode_token, retrieve_token, save_token
import requests
from variables import datallog_url
from time import sleep
from spinner import Spinner

logger = Logger(__name__)

login_page_url = f"{datallog_url}/preferences/settings"
verify_token_url = f"{datallog_url}/api/sdk/verify-token"


def _response_json(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


def _format_account(response_data: dict) -> str:
    username = response_data.get("username")
    email = response_data.get("email")

    if username and email:
        return f"{username} ({email})"
    if username:
        return str(username)
    if email:
        return str(email)
    return "Unknown account"


def _should_continue_login() -> bool:
    try:
        current_token = retrieve_token()
    except InvalidLoginTokenError:
        print("Saved login is invalid. Please log in again.")
        return True

    if not current_token:
        return True

    response = requests.post(
        verify_token_url,
        headers=current_token,
    )

    if response.status_code == 200:
        print(f"Current logged in account: {_format_account(_response_json(response))}")
        confirm = input("Do you want to switch accounts? (Y/N): ").strip()
        if confirm.lower() != "y":
            print("Login cancelled.")
            return False
        return True

    if response.status_code in (401, 403):
        print("Saved login is no longer valid. Please log in again.")
        return True

    raise DatallogError("Unable to verify the current login. Please try again.")


def login(args: Namespace) -> None:
    if not _should_continue_login():
        return

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
    spinner = Spinner("Verifying token...")
    spinner.start()  # type: ignore
    for _ in range(60):
        response = requests.post(
            verify_token_url,
            headers=headers,
        )

        if response.status_code == 200:
            save_token(encode_token(authorization, x_api_key))
            spinner.succeed(
                f"Logged in as {_format_account(_response_json(response))}"
            )  # type: ignore
            break
        if (
            response.status_code == 403
            and _response_json(response).get("message") == "Forbidden"
        ):
            sleep(1)
        else:
            spinner.fail("Token verification failed") # type: ignore
            raise InvalidLoginTokenError(f"Invalid token. Please check your token.")
    else:
        spinner.fail("Token verification timed out") # type: ignore
        raise InvalidLoginTokenError(f"Invalid token. Please check your token.")
