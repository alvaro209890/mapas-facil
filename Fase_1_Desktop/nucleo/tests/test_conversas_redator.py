# M6 / F1-17 — redator de CPF e chaves (antes do INSERT).

from __future__ import annotations

from mapasfacil_nucleo.conversas.redator import redigir, truncar


def test_redige_cpf_formatado_e_cru():
    assert "[CPF removido]" in redigir("CPF 123.456.789-00 do dono")
    assert "123.456.789-00" not in redigir("CPF 123.456.789-00 do dono")
    assert "[CPF removido]" in redigir("documento 12345678900")


def test_redige_api_key_authkey_bearer_plak_sk():
    texto = (
        "api_key=PLAK11beb31d00294d84a41c2efdf5836a61 "
        "authkey=541085de-9a2e-454e-bdba-eb3d57a2f492 "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc "
        "sk-ed926829c15545b5bd318b5e66a9a164"
    )
    saida = redigir(texto)
    assert "PLAK11beb" not in saida
    assert "541085de" not in saida
    assert "eyJhbGci" not in saida
    assert "ed926829" not in saida
    assert "api_key=***" in saida
    assert "authkey=***" in saida
    assert "Bearer ***" in saida
    assert "sk-***" in saida


def test_redigir_idempotente():
    uma = redigir("CPF 111.222.333-44")
    assert redigir(uma) == uma


def test_truncar():
    assert truncar("abc", 10) == "abc"
    assert truncar("abcdefghij", 5) == "abcd…"
    assert truncar("", 5) == ""
