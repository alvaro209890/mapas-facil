import json
import pytest

from mapasfacil_nucleo.agente.registro import DefinicaoTool, RegistroFerramentas
from mapasfacil_nucleo.erros import ErroNucleo


def test_registro_e_execucao_basica():
    registro = RegistroFerramentas()

    def handler_eco(args, ctx):
        return {"eco": args.get("msg", ""), "ctx_id": ctx.get("id")}

    def_eco = DefinicaoTool(
        nome="ecoar_mensagem",
        descricao="Ecoa a mensagem enviada",
        categoria="util",
        parametros={
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
            "additionalProperties": False,
        },
        handler=handler_eco,
    )
    registro.registrar(def_eco)

    assert "ecoar_mensagem" in registro.nomes_tools()
    assert registro.obter("ecoar_mensagem") is not None

    # Execução com dicionário
    res = registro.executar("ecoar_mensagem", {"msg": "olá"}, {"id": "123"})
    assert res["ok"] is True
    assert res["eco"] == "olá"
    assert res["ctx_id"] == "123"

    # Execução com string JSON
    res_str = registro.executar("ecoar_mensagem", '{"msg": "tudo bem"}', {})
    assert res_str["ok"] is True
    assert res_str["eco"] == "tudo bem"


def test_schemas_openai_e_categoria():
    registro = RegistroFerramentas()

    @registro.ferramenta(
        nome="geo_teste",
        descricao="Teste geo",
        categoria="geo",
        parametros={"type": "object", "properties": {"a": {"type": "number"}}, "required": ["a"]},
    )
    def handler_geo(args, ctx):
        return {"resultado": args.get("a", 0) * 2}

    @registro.ferramenta(
        nome="pdf_teste",
        descricao="Teste pdf",
        categoria="pdf",
        parametros={"type": "object", "properties": {}},
    )
    def handler_pdf(args, ctx):
        return {"status": "ok"}

    schemas = registro.schemas_openai()
    assert len(schemas) == 2
    nomes = [s["function"]["name"] for s in schemas]
    assert "geo_teste" in nomes
    assert "pdf_teste" in nomes

    # Filtrar por categoria
    schemas_geo = registro.schemas_openai(categoria="geo")
    assert len(schemas_geo) == 1
    assert schemas_geo[0]["function"]["name"] == "geo_teste"
    assert schemas_geo[0]["function"]["parameters"]["required"] == ["a"]


def test_tool_inexistente_com_sugestao():
    registro = RegistroFerramentas()

    @registro.ferramenta(nome="workspace_listar", descricao="Lista arquivos", categoria="workspace")
    def handler_ws(args, ctx):
        return {"arquivos": []}

    res = registro.executar("workspace_lista", {}, {})
    assert res["ok"] is False
    assert res["codigo"] == "IA-020"
    assert res["sugestao"] == "workspace_listar"


def test_tratamento_de_erros_e_excecoes():
    registro = RegistroFerramentas()

    @registro.ferramenta(nome="falha_nucleo", descricao="Lança ErroNucleo", categoria="teste")
    def handler_err(args, ctx):
        raise ErroNucleo("NU-123", "Erro de teste", {"extra": 1})

    @registro.ferramenta(nome="falha_geral", descricao="Lança RuntimeError", categoria="teste")
    def handler_boom(args, ctx):
        raise RuntimeError("Falha inesperada")

    res_nucleo = registro.executar("falha_nucleo", {}, {})
    assert res_nucleo["ok"] is False
    assert res_nucleo["codigo"] == "NU-123"
    assert "Erro de teste" in res_nucleo["mensagem"]

    res_geral = registro.executar("falha_geral", {}, {})
    assert res_geral["ok"] is False
    assert res_geral["codigo"] == "NU-999"
    assert "Falha inesperada" in res_geral["mensagem"]


def test_json_invalido_nos_argumentos():
    registro = RegistroFerramentas()
    registro.registrar(DefinicaoTool(nome="dummy", descricao="", categoria="", handler=lambda a, c: {}))
    res = registro.executar("dummy", "{invalid-json", {})
    assert res["ok"] is False
    assert res["codigo"] == "NU-001"
