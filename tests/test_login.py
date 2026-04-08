import io
import pathlib
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from argparse import Namespace
from unittest.mock import patch

import requests


ROOT = pathlib.Path(__file__).resolve().parent.parent
UTILS_DIR = ROOT / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from subcommands import login as login_module
from token_manager import decode_token, retrieve_user_info
from tests.mock_backend import MockDatallogBackend


class DummySpinner:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.events = []

    def start(self) -> None:
        self.events.append(("start", self.text))

    def stop(self) -> None:
        self.events.append(("stop", self.text))

    def succeed(self, message: str) -> None:
        self.events.append(("succeed", message))

    def fail(self, message: str) -> None:
        self.events.append(("fail", message))


class LoginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_backend = MockDatallogBackend().start()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.mock_backend.stop()
        self.temp_dir.cleanup()

    def test_decode_manual_login_code_rejects_state_mismatch(self) -> None:
        code = self.mock_backend.manual_code("expected-state")

        with self.assertRaises(login_module.InvalidLoginTokenError):
            login_module._decode_manual_login_code(code, "different-state")

    def test_login_callback_flow_saves_token_and_user(self) -> None:
        args = Namespace(force_login=True, project_path=self.project_path)
        opened_urls = []

        def fake_open(url: str) -> bool:
            opened_urls.append(url)
            response = requests.get(url, allow_redirects=True, timeout=5)
            self.assertEqual(response.status_code, 200)
            return True

        with self._patched_login_environment(), patch.object(login_module.webbrowser, "open", side_effect=fake_open):
            login_module.login(args)

        self.assertEqual(len(opened_urls), 1)
        token = login_module.retrieve_token(self.project_path)
        self.assertIsNotNone(token)
        self.assertEqual(
            token,
            {
                "Authorization": self.mock_backend.authorization,
                "x-api-key": self.mock_backend.x_api_key,
            },
        )
        self.assertEqual(retrieve_user_info(self.project_path), self.mock_backend.profile)

    def test_login_accepts_manual_code_when_browser_callback_is_unavailable(self) -> None:
        manual_backend = MockDatallogBackend(auto_authorize=False).start()
        self.addCleanup(manual_backend.stop)
        args = Namespace(force_login=True, project_path=self.project_path)
        buffered_stdout = io.StringIO()

        def fake_input() -> str:
            while not buffered_stdout.getvalue():
                pass
            for line in buffered_stdout.getvalue().splitlines():
                if "/sdk/authorize?" in line:
                    response = requests.get(line.strip(), timeout=5)
                    self.assertEqual(response.status_code, 200)
                    query = parse_qs(urlparse(line).query)
                    return manual_backend.manual_code(query["state"][0])
            raise AssertionError("Authorize URL not printed")

        with self._patched_login_environment(manual_backend), patch.object(login_module.webbrowser, "open", return_value=False), patch("builtins.input", side_effect=fake_input), patch("sys.stdout", buffered_stdout):
            login_module.login(args)

        token = login_module.retrieve_token(self.project_path)
        self.assertEqual(
            token,
            {
                "Authorization": manual_backend.authorization,
                "x-api-key": manual_backend.x_api_key,
            },
        )
        self.assertEqual(retrieve_user_info(self.project_path), manual_backend.profile)

    def _patched_login_environment(self, backend: MockDatallogBackend | None = None):
        active_backend = backend or self.mock_backend
        return patch.multiple(
            login_module,
            Spinner=DummySpinner,
            authorize_page_url=f"{active_backend.web_url}/sdk/authorize",
            login_result_page_url=f"{active_backend.web_url}/sdk/login-result",
            verify_token_url=f"{active_backend.backend_url}/api/sdk/verify-token",
            sleep=lambda *_args, **_kwargs: None,
        )


class TokenEncodingTests(unittest.TestCase):
    def test_mock_backend_tokens_match_sdk_encoding_contract(self) -> None:
        backend = MockDatallogBackend()
        encoded = login_module.encode_token(backend.authorization, backend.x_api_key)

        self.assertEqual(
            decode_token(encoded),
            {
                "Authorization": backend.authorization,
                "x-api-key": backend.x_api_key,
            },
        )


if __name__ == "__main__":
    unittest.main()
