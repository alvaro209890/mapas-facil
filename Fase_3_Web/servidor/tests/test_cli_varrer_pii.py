"""W12-20 — `varrer-pii`: CPF no banco/eventos/logs vira alerta, sem imprimir o valor.

Dois cuidados que o teste trava:

1. **validação de verdade** — `123.456.789-00` tem a máscara certa e o verificador errado: se a
   varredura acusar isso, o alerta perde credibilidade e alguém desliga o timer;
2. **o alerta não repete o CPF** — o arquivo de alerta diz onde, nunca o quê.
"""

from __future__ import annotations

import json

import pytest

from mapasfacil_servidor import __main__ as cli
from mapasfacil_servidor import pii

CPF_VALIDO = "111.444.777-35"
CPF_VALIDO_2 = "529.982.247-25"
CPF_INVALIDO = "123.456.789-00"


def _ambiente(monkeypatch, tmp_path):
    raiz = tmp_path / "raiz"
    (raiz / "logs").mkdir(parents=True)
    (raiz / "dados" / "projetos" / "p1").mkdir(parents=True)
    segredos = raiz / "segredos" / "servidor.env"
    segredos.parent.mkdir()
    segredos.write_text(
        "MAPASFACIL_PROVEDOR_CHAVE=chave-de-teste\n"
        "MAPASFACIL_SEMA_AUTHKEY=sema-de-teste\n"
        "MAPASFACIL_PLANET_API_KEY=planet-de-teste\n",
        encoding="utf-8",
    )
    segredos.chmod(0o600)
    monkeypatch.setenv("MF_RAIZ", str(raiz))
    monkeypatch.setenv("MF_SEGREDOS", str(segredos))
    return raiz


# --- validação ------------------------------------------------------------------


@pytest.mark.parametrize("texto", [CPF_VALIDO, CPF_VALIDO_2, "11144477735", "52998224725"])
def test_cpf_valido_passa(texto: str) -> None:
    assert pii.cpf_valido(texto)


@pytest.mark.parametrize(
    "texto",
    [CPF_INVALIDO, "000.000.000-00", "111.111.111-11", "123", "1114447773", "1114447773500"],
)
def test_cpf_invalido_nao_passa(texto: str) -> None:
    assert not pii.cpf_valido(texto)


def test_mascara_e_digitos_crus_sao_o_mesmo_cpf() -> None:
    assert pii.digitos(CPF_VALIDO) == pii.digitos("11144477735")


def test_varredura_acha_com_mascara_e_sem() -> None:
    texto = f"titular: {CPF_VALIDO}\noutro: 52998224725\nlimpo: nada aqui"
    achados = pii.varrer_texto(texto, "memoria")
    assert [a.linha for a in achados] == [1, 2]


def test_ignora_numero_grande_em_volta() -> None:
    """Coordenada ou matrícula com 11 dígitos no meio não é CPF."""
    assert not pii.varrer_texto("car=1234567890123456 area=1114447773501", "x")


# --- CLI ponta a ponta ----------------------------------------------------------


def test_ambiente_limpo_sai_zero(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)
    (raiz / "logs" / "servidor.log").write_text('{"nivel":"info","msg":"deploy ok"}\n', encoding="utf-8")
    assert cli.main(["varrer-pii"]) == 0
    assert "nenhum CPF" in capsys.readouterr().out


def test_cpf_no_evento_alerta_e_nao_imprime_valor(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)
    eventos = raiz / "dados" / "projetos" / "p1" / "eventos.ndjson"
    eventos.write_text(
        json.dumps({"evento": "job.log", "dados": {"texto": f"recibo de {CPF_VALIDO}"}}) + "\n",
        encoding="utf-8",
    )
    codigo = cli.main(["varrer-pii"])
    saida = capsys.readouterr()
    assert codigo == 1, "achado tem de falhar o comando (o timer registra a falha)"
    assert "eventos.ndjson:1" in saida.err

    alertas = raiz / "logs" / "alertas.log"
    conteudo = alertas.read_text(encoding="utf-8")
    assert "SV-PII" in conteudo
    assert pii.digitos(CPF_VALIDO) not in conteudo, "o alerta não pode conter o CPF"
    assert pii.digitos(CPF_VALIDO) not in saida.out + saida.err, "nem a saída do comando"


def test_cpf_no_log_tambem_pega(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)
    (raiz / "logs" / "servidor.log").write_text(
        f'{{"msg":"cliente {CPF_VALIDO_2} importado"}}\n', encoding="utf-8"
    )
    assert cli.main(["varrer-pii"]) == 1
    assert "servidor.log:1" in capsys.readouterr().err


def test_cpf_invalido_no_log_nao_alerta(monkeypatch, tmp_path, capsys):
    raiz = _ambiente(monkeypatch, tmp_path)
    (raiz / "logs" / "servidor.log").write_text(f"cpf de teste {CPF_INVALIDO}\n", encoding="utf-8")
    assert cli.main(["varrer-pii"]) == 0
