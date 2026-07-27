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
from subcommands import repair as repair_module


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


class RepairPullDeprecationTests(unittest.TestCase):
    """`datallog repair pull` no longer has its own pull mechanics: it prints a
    deprecation notice and delegates entirely to `pull.py`'s `_execute_pull`,
    which `datallog pull` also uses. See test_pull.py for coverage of the
    actual file-writing/prompt/zip-slip behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)
        _write_project_ini(self.project_path, "myproj")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _patch_env(self, token={"Authorization": "t"}):
        return patch.multiple(
            repair_module,
            get_project_base_dir=MagicMock(return_value=self.project_path),
            retrieve_token=MagicMock(return_value=token),
        )

    def test_pull_requires_project_folder(self) -> None:
        with patch.object(
            repair_module,
            "get_project_base_dir",
            side_effect=InvalidProjectError("no project.ini"),
        ):
            with self.assertRaises(DatallogError) as ctx:
                repair_module._repair_pull(Namespace())
        self.assertIn("project folder", ctx.exception.message)

    def test_pull_requires_authentication(self) -> None:
        with self._patch_env(token=None):
            with self.assertRaises(LoginRequiredError):
                repair_module._repair_pull(Namespace())

    def test_pull_prints_deprecation_notice_and_delegates_to_execute_pull(self) -> None:
        execute = MagicMock()
        printed = []

        with self._patch_env(), patch.object(
            repair_module, "_execute_pull", execute
        ), patch(
            "builtins.print",
            side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a)),
        ):
            repair_module._repair_pull(Namespace(force=True))

        output = "\n".join(printed)
        self.assertIn("DEPRECATED", output)
        self.assertIn("datallog pull", output)
        execute.assert_called_once_with(
            {"Authorization": "t"}, self.project_path, "myproj", True
        )

    def test_pull_defaults_force_to_false_when_absent(self) -> None:
        execute = MagicMock()

        with self._patch_env(), patch.object(repair_module, "_execute_pull", execute):
            repair_module._repair_pull(Namespace())

        execute.assert_called_once_with(
            {"Authorization": "t"}, self.project_path, "myproj", False
        )


class RepairDiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)
        _write_project_ini(self.project_path, "myproj")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _patch_env(self):
        return patch.multiple(
            repair_module,
            get_project_base_dir=MagicMock(return_value=self.project_path),
            retrieve_token=MagicMock(return_value={"Authorization": "t"}),
        )

    def test_diff_filters_by_app(self) -> None:
        patches = [
            {"app_name": "app_a", "patch": [], "patch_explanation": "exp a"},
            {"app_name": "app_b", "patch": [], "patch_explanation": "exp b"},
        ]
        get = MagicMock(return_value=_resp(json_data={"data": patches}))
        printed = []

        with self._patch_env(), patch.object(
            repair_module.requests, "get", get
        ), patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
            repair_module._repair_diff(Namespace(app="app_b"))

        output = "\n".join(printed)
        self.assertIn("app_b", output)
        self.assertNotIn("app_a", output)

    def test_diff_requires_project_folder(self) -> None:
        with patch.object(
            repair_module,
            "get_project_base_dir",
            side_effect=InvalidProjectError("no project.ini"),
        ):
            with self.assertRaises(DatallogError):
                repair_module._repair_diff(Namespace(app=None))


if __name__ == "__main__":
    unittest.main()
