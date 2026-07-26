# F1-17 §Privacidade / AP-09 — redator de CPF e chaves (anel 1).

from __future__ import annotations

import pytest

from mapasfacil_nucleo.conversas.redator import (
    MARCA_CHAVE,
    MARCA_CPF,
    redigir,
    redigir_com_marcas,
    tem_segredo,
)


@pytest.mark.parametrize(
    "entrada",
    [
        "CPF 123.456.789-00 do proprietário",
        "cpf 12345678900",
        "documento: 123.456.789-00.",
        "123456789-00",
    ],
)
def test_cpf_em_qualquer_pontuacao_sai(entrada: str):
    saida = redigir(entrada)
    assert MARCA_CPF in saida
    assert "123456789" not in saida.replace(".", "").replace("-", "")


def test_numero_comprido_nao_e_confundido_com_cpf():
    # Código de recibo do CAR e coordenada não podem ser picados no meio.
    assert redigir("recibo MT-5107925-1234567890123456") == (
        "recibo MT-5107925-1234567890123456"
    )
    assert redigir("area 3823.9033 ha em 8123456.78 N") == "area 3823.9033 ha em 8123456.78 N"


@pytest.mark.parametrize(
    "entrada",
    [
        "api_key=PLAKabcdef1234567890",
        "authkey: 9f8e7d6c5b4a3f2e1d0c",
        'apikey="segredo-do-cliente"',
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc",
        "usa a chave sk-abcdefghijklmnopqrstuvwxyz",
        "token=abc123def456",
    ],
)
def test_chave_de_api_sai(entrada: str):
    saida = redigir(entrada)
    assert MARCA_CHAVE in saida
    for pedaco in ("PLAKabcdef", "9f8e7d6c", "segredo-do-cliente", "eyJhbGci", "sk-abcdef"):
        assert pedaco not in saida


def test_nome_do_campo_permanece_para_o_usuario_entender():
    assert redigir("api_key=PLAKabc12345678") == f"api_key={MARCA_CHAVE}"


def test_marcas_dizem_o_que_saiu_sem_repetir():
    limpo, marcas = redigir_com_marcas("CPF 111.222.333-44 e api_key=PLAKabc12345678 e 555.666.777-88")
    assert marcas == ["cpf", "api_key"]
    assert limpo.count(MARCA_CPF) == 2


def test_texto_limpo_passa_intacto():
    texto = "Preciso do mapa de dinâmica de uso do solo da Fazenda Harmonia, escala 1:75.000."
    assert redigir(texto) == texto
    assert tem_segredo(texto) is False


def test_none_entra_none_sai():
    assert redigir(None) is None
    assert redigir_com_marcas(None) == (None, [])
    assert tem_segredo(None) is False
