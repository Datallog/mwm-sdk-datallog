import base64
import contextlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse


DEFAULT_AUTHORIZATION = "Token " + ("ab" * 20)
DEFAULT_X_API_KEY = base64.b64encode(b"123456789012345678901234567890").decode("ascii")
DEFAULT_PROFILE = {
    "username": "mock-user",
    "email": "mock@datallog.test",
}


class MockDatallogBackend:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        authorization: str = DEFAULT_AUTHORIZATION,
        x_api_key: str = DEFAULT_X_API_KEY,
        profile: Optional[Dict[str, str]] = None,
        auto_authorize: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.authorization = authorization
        self.x_api_key = x_api_key
        self.profile = profile or dict(DEFAULT_PROFILE)
        self.auto_authorize = auto_authorize
        self._server = ThreadingHTTPServer((host, port), self._build_handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def backend_url(self) -> str:
        return self.base_url

    @property
    def web_url(self) -> str:
        return self.base_url

    def start(self) -> "MockDatallogBackend":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def manual_code(self, state: str) -> str:
        payload = {
            "state": state,
            "authorization": self.authorization,
            "X-Api-Key": self.x_api_key,
            "username": self.profile.get("username", ""),
            "email": self.profile.get("email", ""),
        }
        return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")

    def _build_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                parsed = urlparse(self.path)

                if parsed.path == "/sdk/authorize":
                    params = parse_qs(parsed.query)
                    redirect_uri = params.get("redirect_uri", [""])[0]
                    state = params.get("state", [""])[0]

                    if outer.auto_authorize and redirect_uri and state:
                        query = urlencode(
                            {
                                "status": "success",
                                "state": state,
                                "authorization": outer.authorization,
                                "X-Api-Key": outer.x_api_key,
                                "username": outer.profile.get("username", ""),
                                "email": outer.profile.get("email", ""),
                            }
                        )
                        self.send_response(302)
                        self.send_header("Location", f"{redirect_uri}?{query}")
                        self.end_headers()
                        return

                    payload = {"ok": True, "manual_code": outer.manual_code(state)}
                    self._send_json(200, payload)
                    return

                if parsed.path == "/sdk/login-result":
                    self._send_json(200, {"ok": True})
                    return

                self.send_response(404)
                self.end_headers()

            def do_POST(self):  # noqa: N802
                parsed = urlparse(self.path)

                if parsed.path != "/api/sdk/verify-token":
                    self.send_response(404)
                    self.end_headers()
                    return

                if (
                    self.headers.get("Authorization") != outer.authorization
                    or self.headers.get("x-api-key") != outer.x_api_key
                ):
                    self._send_json(401, {"detail": "Invalid token"})
                    return

                self._send_json(200, dict(outer.profile))

            def log_message(self, format, *args):  # noqa: A003
                return

            def _send_json(self, status: int, payload: Dict[str, object]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        return Handler


@contextlib.contextmanager
def running_mock_backend(**kwargs):
    backend = MockDatallogBackend(**kwargs).start()
    try:
        yield backend
    finally:
        backend.stop()


if __name__ == "__main__":
    import time

    with running_mock_backend() as backend:
        print(f"Mock Datallog backend running at {backend.base_url}")
        print(f"Set DATALLOG_SDK_BACKEND_URL={backend.backend_url}")
        print(f"Set DATALLOG_SDK_WEB_URL={backend.web_url}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
