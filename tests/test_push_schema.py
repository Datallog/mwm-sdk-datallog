"""O `push` manda a declaração de tabelas ANTES de promover o build.

A ordem é o ponto deste arquivo, e ela não é estética. `notify-user-push` é o
que PROMOVE o build: a partir dele a automação nova está no ar e pode rodar.
A automação precisa da tabela ANTES disso — se o DDL saísse depois, ou junto,
o primeiro `insert` dela cairia num 404 "tabela nao existe". Está escrito no
docstring da `DataSchemaView`, do outro lado.

A segunda decisão que estes testes travam é o que acontece quando o manifesto
NÃO aplica: o push PARA, e o build não é promovido. Ver
`FalhaNoManifestoTests`.
"""
import json
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

from subcommands import push as push_module


URL = "https://backend.test"

MANIFESTO_DO_BUILD = [
    {"name": "leads", "fields": [
        {"name": "company", "type": "Text", "index": False},
        {"name": "stage", "type": "Text", "index": True},
    ]},
]

RELATORIO = {
    "schema": "org_760",
    "tables": [{"table": "leads", "created": True, "added_columns": [],
                "undeclared_columns": []}],
}


def _resp(status_code=200, json_data=None, ok=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = (200 <= status_code < 300) if ok is None else ok
    resp.json.return_value = {} if json_data is None else json_data
    resp.text = ""
    return resp


class ManifestoDoBuildTests(unittest.TestCase):
    """O corpo que sai do `build.json`, sem driblar o `push` inteiro."""

    def setUp(self):
        self.token = {"Authorization": "Token abc", "x-api-key": "k"}
        self.spinner = MagicMock()

    def _aplica(self, build_data, resposta):
        with patch.object(push_module, "datallog_url", URL), \
             patch.object(push_module, "requests") as req:
            req.post.return_value = resposta
            ok = push_module._aplica_o_manifesto(build_data, self.token, self.spinner)
        return ok, req

    def test_manda_o_manifesto_na_rota_e_com_o_token_do_projeto(self):
        ok, req = self._aplica(
            {"tables": MANIFESTO_DO_BUILD, "manifest_version": 1}, _resp(200, RELATORIO))

        self.assertTrue(ok)
        req.post.assert_called_once()
        url = req.post.call_args.args[0]
        self.assertEqual(url, f"{URL}/platform-api/data/schema")
        # O MESMO dict de headers do resto do push. A rota resolve a conta pelo
        # token, e nunca por nada do corpo — e por isso o token e o corpo todo
        # do isolamento aqui.
        self.assertIs(req.post.call_args.kwargs["headers"], self.token)

    def test_o_corpo_e_o_manifesto_que_o_backend_espera(self):
        _, req = self._aplica(
            {"tables": MANIFESTO_DO_BUILD, "manifest_version": 1}, _resp(200, RELATORIO))

        corpo = req.post.call_args.kwargs["json"]
        self.assertEqual(corpo, {"version": 1, "tables": MANIFESTO_DO_BUILD})
        # Dado puro: o CLI nao constroi objeto nenhum, ele repassa o que veio do
        # `build.json` de dentro da imagem.
        self.assertEqual(json.loads(json.dumps(corpo)), corpo)

    def test_sem_manifest_version_o_corpo_sai_SEM_a_chave(self):
        """Versão ausente é o SDK da imagem sendo mais velho que este CLI.

        Mandar um `version` chutado seria afirmar um formato que o SDK não
        afirmou. Omitir deixa o backend assumir a versão dele
        (`valida_manifesto` faz isso de propósito), e se os dois formatos
        divergirem de verdade a resposta é um 400 com mensagem — não um DDL
        torto aplicado a partir de um palpite do CLI.
        """
        _, req = self._aplica({"tables": MANIFESTO_DO_BUILD}, _resp(200, RELATORIO))
        self.assertEqual(req.post.call_args.kwargs["json"], {"tables": MANIFESTO_DO_BUILD})

    def test_projeto_sem_tabela_nao_chama_a_rota(self):
        # Um POST de manifesto vazio seria 400 "manifesto sem tables", e todo
        # projeto que nao usa o motor de dados falharia no push.
        for build_data in ({"tables": []}, {}, {"automations": ["a"]}):
            with self.subTest(build=build_data):
                ok, req = self._aplica(build_data, _resp(200, RELATORIO))
                self.assertTrue(ok)
                req.post.assert_not_called()

    def test_devolve_False_quando_o_backend_recusa(self):
        ok, _ = self._aplica(
            {"tables": MANIFESTO_DO_BUILD},
            _resp(400, {"message": "nome de coluna invalido: 'Sub-segmento'"}))
        self.assertFalse(ok)

    def test_devolve_False_quando_a_rede_cai(self):
        # `requests` levantando nao pode virar traceback nu no terminal do
        # cliente, e muito menos deixar o push seguir para a promocao.
        with patch.object(push_module, "datallog_url", URL), \
             patch.object(push_module, "requests") as req:
            req.post.side_effect = OSError("conexao recusada")
            req.exceptions.RequestException = Exception
            ok = push_module._aplica_o_manifesto(
                {"tables": MANIFESTO_DO_BUILD}, self.token, self.spinner)
        self.assertFalse(ok)

    def test_resposta_200_que_nao_e_json_nao_estoura(self):
        resposta = _resp(200)
        resposta.json.side_effect = json.decoder.JSONDecodeError("x", "y", 0)
        ok, _ = self._aplica({"tables": MANIFESTO_DO_BUILD}, resposta)
        # 200 e 200: o DDL foi aplicado. Nao conseguir imprimir o relatorio nao
        # e motivo para abortar o push e deixar o build velho no ar.
        self.assertTrue(ok)


def _projeto(tmp):
    caminho = pathlib.Path(tmp)
    (caminho / "project.ini").write_text(
        "[project]\nname = myproj\nruntime = python-3.12\nregion = us-east-1\n"
        "last_pushed_by = dono@datallog.test\n"
    )
    (caminho / "requirements.txt").write_text("requests\n")
    return caminho


class _PushCompleto:
    """O arreio do `push` inteiro, com a rede dublada. Não é um TestCase.

    Mixin e não classe-base de teste de propósito: herdar de um `TestCase` faria
    o `unittest` recolher os testes da base outra vez em cada subclasse, e a
    contagem passaria a mentir sobre o que foi medido.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.projeto = _projeto(self.tmp.name)
        self.token = {"Authorization": "Token abc", "x-api-key": "k"}

    def tearDown(self):
        self.tmp.cleanup()

    def _roda(self, build_data, resposta_do_schema=None):
        """Roda `push()` inteiro e devolve a lista de URLs que receberam POST."""
        ecr = _resp(200, {
            "credentials": {}, "registry_url": "reg.test",
            "repository_uri": "reg.test/myproj",
            "docker_username": "u", "docker_password": "p",
        })
        notify = _resp(200, {"build_id": None})
        schema = resposta_do_schema or _resp(200, RELATORIO)

        def post(url, *a, **kw):
            if url.endswith("/platform-api/data/schema"):
                return schema
            if url.endswith("/notify-user-push"):
                return notify
            raise AssertionError(f"POST inesperado: {url}")

        req = MagicMock()
        req.get.return_value = ecr
        req.post.side_effect = post

        processo = MagicMock(returncode=0, stdout=b"", stderr=b"")

        with patch.multiple(
            push_module,
            datallog_url=URL,
            requests=req,
            load_settings=MagicMock(return_value=MagicMock()),
            get_project_base_dir=MagicMock(return_value=self.projeto),
            retrieve_token=MagicMock(return_value=self.token),
            get_project_env=MagicMock(return_value=self.projeto / "env"),
            container_check_if_image_exists=MagicMock(return_value="Yes"),
            Spinner=MagicMock(),
        ), patch("subprocess.run", return_value=processo), \
             patch("container.container_generate_build", return_value=build_data):
            push_module.push(Namespace(force=False))

        return [c.args[0] for c in req.post.call_args_list], req

class OrdemDoPushTests(_PushCompleto, unittest.TestCase):
    """Não testa `_aplica_o_manifesto` — testa que o `push` o chama, e QUANDO."""

    def test_o_schema_vem_ANTES_do_notify_que_promove_o_build(self):
        """A afirmação central: DDL primeiro, promoção depois.

        `notify-user-push` é o que promove o build. Invertida a ordem, a
        automação nova entra no ar no mesmo instante em que a tabela é criada —
        e `CREATE TABLE` numa tabela com índice não é instantâneo. A janela
        entre as duas é um `insert` em 404.
        """
        urls, _ = self._roda({"automations": ["coleta"], "tables": MANIFESTO_DO_BUILD,
                              "manifest_version": 1})

        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[0].endswith("/platform-api/data/schema"), urls)
        self.assertTrue(urls[1].endswith("/notify-user-push"), urls)

    def test_projeto_sem_tabela_promove_normalmente(self):
        urls, _ = self._roda({"automations": ["coleta"], "tables": []})
        self.assertEqual(len(urls), 1)
        self.assertTrue(urls[0].endswith("/notify-user-push"))


class FalhaNoManifestoTests(_PushCompleto, unittest.TestCase):
    """Manifesto que não aplica PARA o push. O build NÃO é promovido.

    É a decisão, e o raciocínio é o mesmo que ordena as duas chamadas: uma
    automação que precisa de uma tabela que não existe falha no primeiro
    `insert`. Promover o build depois de o DDL falhar entrega exatamente esse
    estado — só que em produção, no horário do cron do cliente, e o erro
    aparece num log de execução em vez de no terminal de quem deu o push.

    Não promover não piora nada: o build anterior continua no ar, que é o
    estado que o cliente já tinha. A imagem já subiu para o registry, então
    repetir o push depois de consertar a declaração custa só as camadas que
    mudaram.

    E o erro é acionável: as recusas desta rota são 400 com mensagem — nome de
    coluna fora da lista branca, troca de tipo numa coluna com dado dentro,
    nome de tabela ocupado. Todas são coisa que o cliente conserta no código
    dele.

    O arquivo já tinha esse precedente antes desta mudança: o 409 de
    `unsynced_repairs` também aborta o push sem promover.
    """

    def test_o_notify_NAO_e_chamado_quando_o_manifesto_e_recusado(self):
        urls, _ = self._roda(
            {"automations": ["coleta"], "tables": MANIFESTO_DO_BUILD},
            _resp(400, {"message": "nome de coluna invalido: 'Sub-segmento'"}))

        self.assertEqual(len(urls), 1)
        self.assertTrue(urls[0].endswith("/platform-api/data/schema"))
        self.assertNotIn("/notify-user-push", " ".join(urls))

    def test_tambem_para_quando_a_rota_do_schema_da_500(self):
        urls, _ = self._roda(
            {"automations": ["coleta"], "tables": MANIFESTO_DO_BUILD},
            _resp(500, {"message": "nao foi possivel aplicar a declaracao de tabelas"}))
        self.assertEqual(len(urls), 1)


if __name__ == "__main__":
    unittest.main()
