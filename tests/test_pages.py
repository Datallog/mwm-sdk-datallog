import pathlib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


ROOT = pathlib.Path(__file__).resolve().parent.parent
UTILS_DIR = ROOT / "utils"
if str(UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(UTILS_DIR))

from subcommands import pages as pages_module


TOKEN = {"Authorization": "Token x", "x-api-key": "k"}


def _resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = ""
    return resp


class PublishPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _page(self, name: str, content: str) -> None:
        folder = self.project_path / "pages"
        folder.mkdir(exist_ok=True)
        (folder / name).write_text(content, encoding="utf-8")

    def test_no_pages_folder_publishes_nothing(self) -> None:
        with patch.object(pages_module.requests, "put") as put:
            self.assertEqual(pages_module.publish_pages(self.project_path, "crm", TOKEN), [])
        put.assert_not_called()

    def test_existing_page_keeps_the_title_set_in_the_panel(self) -> None:
        self._page("carteira.html", "<title>CRM · Datallog</title><p>oi</p>")
        with patch.object(pages_module.requests, "get",
                          return_value=_resp(200, {"title": "CRM Datallog"})), \
             patch.object(pages_module.requests, "put", return_value=_resp(200)) as put:
            published = pages_module.publish_pages(self.project_path, "crm", TOKEN)

        url = put.call_args.args[0]
        self.assertTrue(url.endswith("/platform-api/pages/crm/carteira"))
        self.assertEqual(put.call_args.kwargs["json"]["title"], "CRM Datallog")
        self.assertEqual(put.call_args.kwargs["json"]["html"], "<title>CRM · Datallog</title><p>oi</p>")
        self.assertEqual(put.call_args.kwargs["headers"], TOKEN)
        self.assertEqual(published, [{"slug": "carteira", "title": "CRM Datallog", "created": False}])

    def test_new_page_takes_the_title_tag(self) -> None:
        self._page("resultados.html", "<html><title> Resultados &amp; metas </title></html>")
        with patch.object(pages_module.requests, "get", return_value=_resp(404)), \
             patch.object(pages_module.requests, "put", return_value=_resp(201)) as put:
            published = pages_module.publish_pages(self.project_path, "crm", TOKEN)

        self.assertEqual(put.call_args.kwargs["json"]["title"], "Resultados & metas")
        self.assertTrue(published[0]["created"])

    def test_new_page_without_title_tag_uses_the_slug(self) -> None:
        self._page("painel.html", "<p>sem titulo</p>")
        with patch.object(pages_module.requests, "get", return_value=_resp(404)), \
             patch.object(pages_module.requests, "put", return_value=_resp(201)) as put:
            pages_module.publish_pages(self.project_path, "crm", TOKEN)
        self.assertEqual(put.call_args.kwargs["json"]["title"], "painel")

    def test_invalid_file_name_fails_before_any_request(self) -> None:
        self._page("Minha_Pagina.html", "<p>x</p>")
        with patch.object(pages_module.requests, "get") as get, \
             patch.object(pages_module.requests, "put") as put:
            with self.assertRaises(pages_module.PagePublishError) as ctx:
                pages_module.publish_pages(self.project_path, "crm", TOKEN)
        self.assertIn("Minha_Pagina.html", str(ctx.exception))
        get.assert_not_called()
        put.assert_not_called()

    def test_backend_refusal_carries_its_message(self) -> None:
        self._page("carteira.html", "<p>x</p>")
        with patch.object(pages_module.requests, "get", return_value=_resp(404)), \
             patch.object(pages_module.requests, "put",
                          return_value=_resp(400, {"message": "o conteudo da pagina passa de 2 MB"})):
            with self.assertRaises(pages_module.PagePublishError) as ctx:
                pages_module.publish_pages(self.project_path, "crm", TOKEN)
        self.assertIn("2 MB", str(ctx.exception))

    def test_ignores_files_that_are_not_html(self) -> None:
        self._page("carteira.html", "<p>x</p>")
        self._page("notas.md", "rascunho")
        with patch.object(pages_module.requests, "get", return_value=_resp(404)), \
             patch.object(pages_module.requests, "put", return_value=_resp(201)) as put:
            pages_module.publish_pages(self.project_path, "crm", TOKEN)
        self.assertEqual(put.call_count, 1)


class PushExitCodeTests(unittest.TestCase):
    """CI reads the exit code: a failed push that exits 0 shows a green deploy."""

    def test_failure_exits_non_zero(self) -> None:
        from argparse import Namespace
        from errors import LoginRequiredError
        from subcommands import push as push_module

        with patch.object(push_module, "load_settings", return_value={}), \
             patch.object(push_module, "get_project_base_dir",
                          side_effect=LoginRequiredError("You must be logged in to push a project.")):
            with self.assertRaises(SystemExit) as ctx:
                push_module.push(Namespace())
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
