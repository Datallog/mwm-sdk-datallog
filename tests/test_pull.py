import pathlib
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch


ROOT = pathlib.Path(__file__).resolve().parent.parent
UTILS_DIR = ROOT / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from errors import DatallogError, InvalidProjectError, LoginRequiredError
from subcommands import pull as pull_module


def _resp(status_code=200, json_data=None, ok=True):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = ok
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = ""
    return resp


def _write_project_ini(path: pathlib.Path, name: str) -> None:
    (path / "project.ini").write_text(
        f"[project]\nname = {name}\nruntime = python-3.12\nregion = us-east-1\n"
    )


class PullAuthAndProjectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)
        _write_project_ini(self.project_path, "myproj")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_requires_project_folder(self) -> None:
        with patch.object(
            pull_module,
            "get_project_base_dir",
            side_effect=InvalidProjectError("no project.ini"),
        ):
            with self.assertRaises(DatallogError) as ctx:
                pull_module._get_auth_and_project()
        self.assertIn("project folder", ctx.exception.message)

    def test_requires_authentication(self) -> None:
        with patch.multiple(
            pull_module,
            get_project_base_dir=MagicMock(return_value=self.project_path),
            retrieve_token=MagicMock(return_value=None),
        ):
            with self.assertRaises(LoginRequiredError):
                pull_module._get_auth_and_project()


class PullExecuteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)
        _write_project_ini(self.project_path, "myproj")
        self.token = {"Authorization": "t"}

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _patch_env(self):
        return patch.multiple(
            pull_module,
            get_project_base_dir=MagicMock(return_value=self.project_path),
            retrieve_token=MagicMock(return_value=self.token),
        )

    def test_writes_all_files_with_force_no_prompt(self) -> None:
        files = {
            "automations/app_a/app_a.py": "print('a')",
            "requirements.txt": "datallog\n",
        }
        get = MagicMock(return_value=_resp(json_data={"files": files}))
        post = MagicMock(return_value=_resp())

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch.object(
            pull_module.requests, "post", post
        ), patch("builtins.input") as mock_input:
            pull_module.pull(Namespace(force=True))

        mock_input.assert_not_called()
        self.assertEqual(
            (self.project_path / "automations/app_a/app_a.py").read_text(), "print('a')"
        )
        self.assertEqual((self.project_path / "requirements.txt").read_text(), "datallog\n")

    def test_prompts_before_overwriting_and_respects_decline(self) -> None:
        (self.project_path / "requirements.txt").write_text("old\n")
        files = {"requirements.txt": "new\n"}
        get = MagicMock(return_value=_resp(json_data={"files": files}))

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch(
            "builtins.input", return_value="n"
        ) as mock_input:
            pull_module.pull(Namespace(force=False))

        mock_input.assert_called_once()
        self.assertEqual((self.project_path / "requirements.txt").read_text(), "old\n")

    def test_overwrites_when_user_confirms(self) -> None:
        (self.project_path / "requirements.txt").write_text("old\n")
        files = {"requirements.txt": "new\n"}
        get = MagicMock(return_value=_resp(json_data={"files": files}))

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch(
            "builtins.input", return_value="y"
        ):
            pull_module.pull(Namespace(force=False))

        self.assertEqual((self.project_path / "requirements.txt").read_text(), "new\n")

    def test_no_prompt_when_no_local_files_would_be_overwritten(self) -> None:
        files = {"requirements.txt": "new\n"}
        get = MagicMock(return_value=_resp(json_data={"files": files}))

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch(
            "builtins.input"
        ) as mock_input:
            pull_module.pull(Namespace(force=False))

        mock_input.assert_not_called()
        self.assertEqual((self.project_path / "requirements.txt").read_text(), "new\n")

    def test_skips_zip_slip_path(self) -> None:
        files = {
            "../evil.py": "boom",
            "requirements.txt": "ok\n",
        }
        get = MagicMock(return_value=_resp(json_data={"files": files}))

        with self._patch_env(), patch.object(pull_module.requests, "get", get):
            pull_module.pull(Namespace(force=True))

        self.assertFalse((self.project_path.parent / "evil.py").exists())
        self.assertEqual((self.project_path / "requirements.txt").read_text(), "ok\n")

    def test_no_files_prints_message_and_writes_nothing(self) -> None:
        get = MagicMock(return_value=_resp(json_data={"files": {}}))
        printed = []

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch(
            "builtins.print",
            side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        ):
            pull_module.pull(Namespace(force=True))

        self.assertTrue(any("Nothing to pull" in line for line in printed))

    def test_reconciles_pulled_automations_after_writing(self) -> None:
        files = {
            "automations/app_a/app_a.py": "print('a')",
            "automations/app_b/app_b.py": "print('b')",
            "requirements.txt": "datallog\n",
        }
        get = MagicMock(return_value=_resp(json_data={"files": files}))
        post = MagicMock(return_value=_resp())

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch.object(
            pull_module.requests, "post", post
        ):
            pull_module.pull(Namespace(force=True))

        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["project_name"], "myproj")
        self.assertEqual(sorted(kwargs["json"]["app_names"]), ["app_a", "app_b"])

    def test_does_not_reconcile_when_nothing_to_pull(self) -> None:
        get = MagicMock(return_value=_resp(json_data={"files": {}}))
        post = MagicMock(return_value=_resp())

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch.object(
            pull_module.requests, "post", post
        ):
            pull_module.pull(Namespace(force=True))

        post.assert_not_called()

    def test_project_not_found_prints_error(self) -> None:
        get = MagicMock(return_value=_resp(status_code=404, ok=False, json_data={"error": "no project"}))
        printed = []

        with self._patch_env(), patch.object(pull_module.requests, "get", get), patch(
            "builtins.print",
            side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        ):
            pull_module.pull(Namespace(force=True))

        self.assertTrue(any("no project" in line for line in printed))


if __name__ == "__main__":
    unittest.main()
