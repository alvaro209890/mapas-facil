# F1-07 — cliente de visão. `urlopen` injetável (mesmo padrão de
# `agente/deepseek.py` + `tests/test_agente_vcr.py`) — sem rede, exercita o
# cliente real, não só o double.

from __future__ import annotations

import io
import json

import pytest

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.visao.provedor import (
    DeepSeekVisaoProvedor,
    ProvedorVisaoFalha,
    ProvedorVisaoFixo,
    modelo_visao_configurado,
)
from mapasfacil_nucleo.erros import ErroNucleo

CHAVE_TESTE = "sk-visao-nao-pode-vazar-8f7e6d"


class _RespostaFake:
    def __init__(self, corpo: bytes) -> None:
        self._buf = io.BytesIO(corpo)

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def close(self) -> None:
        self._buf.close()


def _urlopen_ok(req, timeout=None):  # noqa: ANN001, ARG001
    corpo = json.loads(req.data.decode())
    assert corpo["messages"][0]["content"][0]["type"] == "text"
    assert corpo["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    assert req.headers.get("Authorization") == f"Bearer {CHAVE_TESTE}"
    assert CHAVE_TESTE not in req.data.decode()  # a chave vai só no header, não no corpo
    resposta = {"choices": [{"message": {"content": '{"mapa_da_serie":"dinamica"}'}}]}
    return _RespostaFake(json.dumps(resposta).encode())


def test_deepseek_visao_monta_payload_multimodal_e_parseia_resposta() -> None:
    provedor = DeepSeekVisaoProvedor(CHAVE_TESTE, urlopen=_urlopen_ok)
    texto = provedor.analisar(imagem_base64="QUJD", mime="image/png", prompt="descreva")
    assert texto == '{"mapa_da_serie":"dinamica"}'


def test_deepseek_visao_resposta_nao_json_e_ia060() -> None:
    def urlopen_ruim(req, timeout=None):  # noqa: ANN001, ARG001
        return _RespostaFake(b"nao e json")

    provedor = DeepSeekVisaoProvedor(CHAVE_TESTE, urlopen=urlopen_ruim)
    with pytest.raises(ErroNucleo) as exc:
        provedor.analisar(imagem_base64="QUJD", mime="image/png", prompt="x")
    assert exc.value.codigo == limites.CODIGO_VISAO_INDISPONIVEL


def test_deepseek_visao_http_error_e_ia060() -> None:
    import urllib.error

    def urlopen_falha(req, timeout=None):  # noqa: ANN001, ARG001
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, io.BytesIO(b"nope"))

    provedor = DeepSeekVisaoProvedor(CHAVE_TESTE, urlopen=urlopen_falha)
    with pytest.raises(ErroNucleo) as exc:
        provedor.analisar(imagem_base64="QUJD", mime="image/png", prompt="x")
    assert exc.value.codigo == limites.CODIGO_VISAO_INDISPONIVEL
    assert CHAVE_TESTE not in json.dumps(exc.value.para_dict())


def test_modelo_visao_configuravel_por_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAPASFACIL_MODELO_VISAO", raising=False)
    assert modelo_visao_configurado() == "deepseek-vl"
    monkeypatch.setenv("MAPASFACIL_MODELO_VISAO", "modelo-futuro-confirmado")
    assert modelo_visao_configurado() == "modelo-futuro-confirmado"


def test_provedor_fixo_devolve_respostas_em_sequencia() -> None:
    fixo = ProvedorVisaoFixo(["a", "b"])
    assert fixo.analisar(imagem_base64="x", mime="image/png", prompt="p1") == "a"
    assert fixo.analisar(imagem_base64="x", mime="image/png", prompt="p2") == "b"
    assert fixo.analisar(imagem_base64="x", mime="image/png", prompt="p3") == "b"  # repete a última
    assert len(fixo.chamadas) == 3
    assert fixo.chamadas[0]["prompt"] == "p1"


def test_provedor_falha_levanta_erro_tipado() -> None:
    falha = ProvedorVisaoFalha()
    with pytest.raises(ErroNucleo) as exc:
        falha.analisar(imagem_base64="x", mime="image/png", prompt="p")
    assert exc.value.codigo == limites.CODIGO_VISAO_INDISPONIVEL
