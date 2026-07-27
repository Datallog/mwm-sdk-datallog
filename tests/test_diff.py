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

from errors import DatallogError, InvalidProjectError
from subcommands import diff as diff_module


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


class DiffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)
        _write_project_ini(self.project_path, "myproj")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _patch_env(self):
        return patch.multiple(
            diff_module,
            get_project_base_dir=MagicMock(return_value=self.project_path),
            retrieve_token=MagicMock(return_value={"Authorization": "t"}),
        )

    def test_diff_filters_by_app(self) -> None:
        changes = [
            {"app_name": "app_a", "patch": [], "patch_explanation": "exp a"},
            {"app_name": "app_b", "patch": [], "patch_explanation": "exp b"},
        ]
        get = MagicMock(return_value=_resp(json_data={"data": changes}))
        printed = []

        with self._patch_env(), patch.object(
            diff_module.requests, "get", get
        ), patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
            diff_module._diff_command(Namespace(app="app_b"))

        output = "\n".join(printed)
        self.assertIn("app_b", output)
        self.assertNotIn("app_a", output)

    def test_diff_requires_project_folder(self) -> None:
        with patch.object(
            diff_module,
            "get_project_base_dir",
            side_effect=InvalidProjectError("no project.ini"),
        ):
            with self.assertRaises(DatallogError):
                diff_module._diff_command(Namespace(app=None))

    def test_diff_shows_changes_from_both_repair_and_agent_sources(self) -> None:
        """O backend já unifica Auto Reparo e agente de IA (o que for mais
        recente) num único endpoint — o CLI só precisa exibir o que vier,
        sem se importar com a origem."""
        changes = [
            {
                "app_name": "teste_erro", "applied_at": 1721000000,
                "patch": [{"path": "automations/teste_erro/teste_erro.py", "new_content": "print('fix')"}],
                "patch_explanation": "corrigido pelo agente",
            },
        ]
        get = MagicMock(return_value=_resp(json_data={"data": changes}))
        printed = []

        with self._patch_env(), patch.object(
            diff_module.requests, "get", get
        ), patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
            diff_module._diff_command(Namespace(app=None))

        output = "\n".join(printed)
        self.assertIn("teste_erro", output)
        self.assertIn("corrigido pelo agente", output)

    def test_diff_prints_message_when_nothing_to_show(self) -> None:
        get = MagicMock(return_value=_resp(json_data={"data": []}))
        printed = []

        with self._patch_env(), patch.object(
            diff_module.requests, "get", get
        ), patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(str(x) for x in a))):
            diff_module._diff_command(Namespace(app=None))

        output = "\n".join(printed)
        self.assertIn("No cloud changes", output)

    def test_diff_wraps_unexpected_errors_without_raising(self) -> None:
        with patch.object(
            diff_module, "_diff_command", side_effect=RuntimeError("boom"),
        ):
            diff_module.diff(Namespace(app=None))  # não deve levantar


if __name__ == "__main__":
    unittest.main()
