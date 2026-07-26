"""A11 — cofre BYOK (`cofre.definir` / `existe` / `testar`)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.doctor import _chaves_configuradas
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import envelope_req
from tests.helpers_fixtures import eventos_e_resposta


@pytest.fixture(autouse=True)
def _backend_memoria():
    mem = cofre.BackendMemoria()
    cofre.configurar_backend(mem)
    os.environ["MF_COFRE_TESTAR_OFF"] = "1"
    yield mem
    cofre.configurar_backend(None)
    os.environ.pop("MF_COFRE_TESTAR_OFF", None)


def test_definir_existe_apagar() -> None:
    assert cofre.existe("deepseek_api_key") is False
    cofre.definir("deepseek_api_key", "sk-teste-1234567890")
    assert cofre.existe("deepseek_api_key") is True
    assert cofre.usar("deepseek_api_key") == "sk-teste-1234567890"
    cofre.apagar("deepseek_api_key")
    assert cofre.existe("deepseek_api_key") is False


def test_nome_desconhecido_erra() -> None:
    with pytest.raises(ErroNucleo) as exc:
        cofre.definir("chave_inventada", "x")
    assert exc.value.codigo == "NU-001"


def test_ndjson_definir_nunca_devolve_valor() -> None:
    segredo = "sk-segredo-nao-pode-vazar-12345"
    linha = json.dumps(
        envelope_req("cofre.definir", {"chave": "deepseek_api_key", "valor": segredo}),
        ensure_ascii=False,
    )
    saida = processar_linha(linha, criar_roteador())
    assert segredo not in saida
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is True
    assert res["resultado"]["ok"] is True
    assert res["resultado"]["existe"] is True
    assert "valor" not in res["resultado"]


def test_ndjson_existe_e_testar() -> None:
    cofre.definir("deepseek_api_key", "sk-abcdef123456")
    linha_e = json.dumps(
        envelope_req("cofre.existe", {"chave": "deepseek_api_key"}),
        ensure_ascii=False,
    )
    _e, res_e = eventos_e_resposta(processar_linha(linha_e, criar_roteador()))
    assert res_e["resultado"]["existe"] is True

    linha_t = json.dumps(
        envelope_req("cofre.testar", {"chave": "deepseek_api_key"}),
        ensure_ascii=False,
    )
    saida_t = processar_linha(linha_t, criar_roteador())
    assert "sk-abcdef" not in saida_t
    _e, res_t = eventos_e_resposta(saida_t)
    assert res_t["resultado"]["ok"] is True
    assert res_t["resultado"]["chave"] == "deepseek_api_key"


def test_ler_chave_deepseek_prefere_cofre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cofre.definir("deepseek_api_key", "sk-do-cofre-999")
    assert ler_chave_deepseek() == "sk-do-cofre-999"


def test_doctor_ve_cofre(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Isola do secrets.local.json real deste PC.
    monkeypatch.setattr(
        "mapasfacil_nucleo.doctor.raiz_repositorio",
        lambda: tmp_path,
    )
    assert _chaves_configuradas()["deepseek"] is False
    cofre.definir("deepseek_api_key", "sk-doctor-xyz")
    assert _chaves_configuradas()["deepseek"] is True


def test_testar_sema_so_existencia() -> None:
    cofre.definir("sema_authkey", "token-sema")
    out = cofre.testar("sema_authkey")
    assert out["ok"] is True
    assert out["modo"] == "existencia"
    assert "token-sema" not in json.dumps(out)
