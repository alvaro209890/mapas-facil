import pytest

from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_exec import registrar_tools_exec


def test_python_exec_fail_closed_por_padrao():
    registro = RegistroFerramentas()
    registrar_tools_exec(registro)

    assert "python_exec" in registro.nomes_tools()

    # Tentativa normal de rodar código
    res = registro.executar("python_exec", {"codigo": "print('teste')"}, {})
    assert res["ok"] is False
    assert res["codigo"] == "SEC-001"
    assert "fail-closed" in res["mensagem"].lower() or "isolamento" in res["mensagem"].lower()


def test_python_exec_recusa_mesmo_com_flags_de_permissao():
    registro = RegistroFerramentas()
    registrar_tools_exec(registro)

    # Tentativa de burlar com flags
    res = registro.executar(
        "python_exec",
        {"codigo": "import os; print(os.name)", "permitir": True, "forcar": True, "sandbox": True},
        {},
    )
    assert res["ok"] is False
    assert res["codigo"] == "SEC-001"
    assert "isolamento" in res["mensagem"].lower()
