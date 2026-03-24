from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socket import socket
from threading import Event, Thread
from time import sleep
from typing import Dict, Optional
from urllib.parse import parse_qs, quote, urlparse
import secrets
import webbrowser

import requests

from errors import DatallogError, InvalidLoginTokenError
from logger import Logger
from spinner import Spinner
from token_manager import encode_token, retrieve_token, save_token, save_user_info
from variables import datallog_api_url, datallog_web_url

logger = Logger(__name__)

authorize_page_url = f"{datallog_web_url}/sdk/authorize"
verify_token_url = f"{datallog_api_url}/api/sdk/verify-token"


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


def _find_callback_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _build_authorize_url(port: int, state: str) -> str:
    callback_url = f"http://127.0.0.1:{port}/callback"
    return (
        f"{authorize_page_url}?redirect_uri={quote(callback_url, safe='')}"
        f"&state={quote(state, safe='')}"
    )


def _make_callback_handler(callback_state: Dict[str, Optional[str]], event: Event):
    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return

            params = parse_qs(parsed.query)
            status = params.get("status", ["error"])[0]
            state = params.get("state", [""])[0]

            if state != callback_state["expected_state"]:
                callback_state["error"] = "Invalid callback state received from browser."
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Invalid login response.</h1></body></html>")
                event.set()
                return

            if status != "success":
                callback_state["error"] = params.get("message", ["Login authorization failed."])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Login failed.</h1><p>You can close this window.</p></body></html>")
                event.set()
                return

            callback_state["authorization"] = params.get("authorization", [""])[0]
            callback_state["x_api_key"] = params.get("x_api_key", [""])[0]
            callback_state["email"] = params.get("email", [""])[0]
            callback_state["username"] = params.get("username", [""])[0]

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>SDK login completed.</h1><p>You can close this window and return to the terminal.</p></body></html>"
            )
            event.set()

        def log_message(self, format, *args):  # noqa: A003
            return

    return CallbackHandler


def login(args: Namespace) -> None:
    force = getattr(args, "force_login", False)

    if not force and not _should_continue_login():
        return

    state = secrets.token_urlsafe(24)
    port = _find_callback_port()
    callback_state: Dict[str, Optional[str]] = {
        "expected_state": state,
        "authorization": None,
        "x_api_key": None,
        "email": None,
        "username": None,
        "error": None,
    }
    event = Event()

    server = ThreadingHTTPServer(("127.0.0.1", port), _make_callback_handler(callback_state, event))
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    authorize_url = _build_authorize_url(port, state)
    print("Open the following URL to authorize the SDK login:")
    print(authorize_url)
    webbrowser.open(authorize_url)

    spinner = Spinner("Waiting for browser authorization...")
    spinner.start()  # type: ignore

    try:
        if not event.wait(timeout=300):
            spinner.fail("Login authorization timed out")  # type: ignore
            raise DatallogError("Login authorization timed out. Please try again.")

        if callback_state["error"]:
            spinner.fail("Login authorization failed")  # type: ignore
            raise DatallogError(callback_state["error"] or "Login authorization failed.")

        authorization = callback_state["authorization"] or ""
        x_api_key = callback_state["x_api_key"] or ""
        if not authorization or not x_api_key:
            spinner.fail("Login authorization failed")  # type: ignore
            raise InvalidLoginTokenError("Invalid login response. Missing credentials.")

        headers = {
            "Authorization": authorization,
            "x-api-key": x_api_key,
        }

        response = requests.post(
            verify_token_url,
            headers=headers,
        )

        if response.status_code != 200:
            spinner.fail("Token verification failed")  # type: ignore
            response_data = _response_json(response)
            error_message = (
                response_data.get("detail")
                or response_data.get("message")
                or response_data.get("error")
                or response.text
                or "Invalid token. Please check your token."
            )
            raise InvalidLoginTokenError(str(error_message))

        data = _response_json(response)
        project_path = getattr(args, "project_path", None)
        save_token(encode_token(authorization, x_api_key), project_path)
        save_user_info(
            {
                "email": data.get("email") or callback_state["email"] or "",
                "username": data.get("username") or callback_state["username"] or "",
            },
            project_path,
        )
        spinner.succeed(f"Logged in as {_format_account(data)}")  # type: ignore
    finally:
        sleep(0.2)
        server.shutdown()
        server.server_close()
