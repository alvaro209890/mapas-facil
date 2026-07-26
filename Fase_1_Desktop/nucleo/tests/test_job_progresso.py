"""A9 — emissão de `job.progresso` nas 10 etapas de `mapa.gerar` (F1-01)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.progresso import ETAPAS, IDS_ETAPAS, RastreadorProgresso, pct_ao_concluir
from mapasfacil_nucleo.protocolo import Emissor, Roteador, envelope_req
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import eventos_e_resposta, montar_workspace_minimo


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    montar_workspace_minimo(tmp_path)
    return tmp_path


@pytest.fixture
def mapspec_local(repo_root: Path) -> dict:
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    spec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    spec["saidas"] = ["pdf"]
    spec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_2026_teste",
        "caminhos_relativos": True,
        "materializar_camadas_em": "SHP",
    }
    return spec


# --------------------------------------------------------------------------- contrato


def test_dez_etapas_com_pesos_que_somam_cem() -> None:
    assert len(ETAPAS) == 10
    assert sum(e.peso for e in ETAPAS) == 100
    assert IDS_ETAPAS == (
        "validando_spec",
        "resolvendo_camadas_locais",
        "baixando_externas",
        "calculando_quantitativos",
        "gerando_tabela",
        "preparando_template",
        "aplicando_layout",
        "salvando_mxd",
        "exportando_pdf",
        "validando_saida",
    )
    assert pct_ao_concluir("validando_spec") == 3
    assert pct_ao_concluir("validando_saida") == 100


def test_rastreador_emite_pct_acumulado_monotonico() -> None:
    emitidos: list[tuple[str, dict]] = []
    rastreador = RastreadorProgresso(lambda evento, dados: emitidos.append((evento, dados)))
    for etapa in IDS_ETAPAS:
        rastreador.concluir(etapa)

    assert [e for e, _ in emitidos] == ["job.progresso"] * 10
    pcts = [d["pct"] for _, d in emitidos]
    assert pcts == [3, 10, 30, 40, 45, 55, 70, 75, 90, 100]
    assert pcts == sorted(pcts)


def test_rastreador_sem_emissor_e_no_op() -> None:
    rastreador = RastreadorProgresso()
    rastreador.concluir("validando_spec")
    assert rastreador.pct == 3
    assert rastreador.etapas_concluidas == 1


def test_item_fica_dentro_da_faixa_da_etapa() -> None:
    emitidos: list[dict] = []
    rastreador = RastreadorProgresso(lambda _evento, dados: emitidos.append(dados))
    rastreador.concluir("validando_spec")
    for i, camada in enumerate(("atp", "avn", "auas"), start=1):
        rastreador.item("resolvendo_camadas_locais", camada, indice=i, total=3)

    faixa = [d for d in emitidos if d["etapa"] == "resolvendo_camadas_locais"]
    assert [d["item"] for d in faixa] == ["atp", "avn", "auas"]
    assert all(3 < d["pct"] <= 10 for d in faixa)
    assert faixa[-1]["pct"] == 10  # o último item conclui a etapa
    assert rastreador.etapas_concluidas == 2


def test_etapa_nao_anda_para_tras() -> None:
    rastreador = RastreadorProgresso()
    rastreador.concluir("exportando_pdf")
    with pytest.raises(ValueError):
        rastreador.concluir("validando_spec")
    with pytest.raises(ValueError):
        rastreador.concluir("exportando_pdf")


def test_etapa_fora_do_contrato_e_recusada() -> None:
    rastreador = RastreadorProgresso()
    with pytest.raises(ValueError):
        rastreador.concluir("inventando_etapa")
    with pytest.raises(ValueError):
        rastreador.item("validando_spec", "atp", indice=1, total=1)


def test_concluir_se_pendente_nao_duplica_evento() -> None:
    emitidos: list[dict] = []
    rastreador = RastreadorProgresso(lambda _evento, dados: emitidos.append(dados))
    rastreador.concluir("validando_spec")
    assert rastreador.concluir_se_pendente("validando_spec") is None
    assert len(emitidos) == 1


# --------------------------------------------------------------------------- protocolo


def test_emissor_monta_envelope_evt() -> None:
    recebidos: list[dict] = []
    emissor = Emissor("01ABC", recebidos.append)
    envelope = emissor.emitir("job.progresso", {"etapa": "validando_spec", "pct": 3})

    assert envelope == recebidos[0]
    assert envelope["v"] == 1
    assert envelope["id"] == "01ABC"
    assert envelope["tipo"] == "evt"
    assert envelope["evento"] == "job.progresso"
    assert envelope["dados"] == {"etapa": "validando_spec", "pct": 3}


def test_emissor_sem_sink_nao_explode() -> None:
    assert Emissor("01ABC").emitir("aviso", {"codigo": "NU-000"})["tipo"] == "evt"


def test_roteador_passa_emissor_para_handler_com_eventos() -> None:
    roteador = Roteador()

    def _handler(params: dict, emissor: Emissor) -> dict:
        emissor.emitir("job.progresso", {"etapa": "validando_spec", "pct": 3})
        return {"ok": True}

    roteador.registrar("teste.evt", _handler, com_eventos=True)
    recebidos: list[dict] = []
    resposta = roteador.despachar(
        envelope_req("teste.evt", {}, id_req="01ABC"),
        recebidos.append,
    )

    assert resposta["ok"] is True
    assert recebidos[0]["id"] == "01ABC"
    assert recebidos[0]["evento"] == "job.progresso"


def test_registrar_sem_eventos_sobrescreve_handler_com_eventos() -> None:
    roteador = Roteador()
    roteador.registrar("x", lambda _p, _e: {"a": 1}, com_eventos=True)
    roteador.registrar("x", lambda _p: {"a": 2})
    assert roteador.despachar(envelope_req("x"))["resultado"] == {"a": 2}


def test_mapa_gerar_esta_registrado_com_eventos() -> None:
    roteador = criar_roteador()
    assert "mapa.gerar" in roteador._com_eventos  # noqa: SLF001 — contrato interno


# --------------------------------------------------------------------------- ponta a ponta


def test_mapa_gerar_emite_as_dez_etapas_em_ordem(projeto: Path, mapspec_local: dict) -> None:
    workspace_servico.abrir(str(projeto))
    processar_linha(json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)})))

    req = envelope_req("mapa.gerar", {"mapspec": mapspec_local}, id_req="01JOBTESTE")
    eventos, resposta = eventos_e_resposta(processar_linha(json.dumps(req)))
    assert resposta["ok"] is True, resposta

    progresso = [e for e in eventos if e["evento"] == "job.progresso"]
    assert len(progresso) >= 10

    for evento in progresso:
        assert evento["v"] == 1
        assert evento["tipo"] == "evt"
        assert evento["id"] == "01JOBTESTE"  # mesmo id da requisição
        assert set(evento["dados"]) <= {"etapa", "pct", "item", "job_id"}
        assert evento["dados"]["etapa"] in IDS_ETAPAS
        assert isinstance(evento["dados"]["pct"], int)

    pcts = [e["dados"]["pct"] for e in progresso]
    assert pcts == sorted(pcts), "pct andou para trás"
    assert pcts[0] == 3 and pcts[-1] == 100

    # As 10 etapas aparecem, na ordem do contrato, e cada uma fecha na sua fatia.
    ordem = [e["dados"]["etapa"] for e in progresso]
    assert [etapa for etapa in IDS_ETAPAS if etapa in ordem] == list(dict.fromkeys(ordem))
    for etapa in IDS_ETAPAS:
        fechamento = [
            e["dados"]["pct"] for e in progresso if e["dados"]["etapa"] == etapa
        ]
        assert fechamento, f"etapa ausente: {etapa}"
        assert max(fechamento) == pct_ao_concluir(etapa)


def test_mapa_gerar_reporta_item_das_camadas_locais(projeto: Path, mapspec_local: dict) -> None:
    workspace_servico.abrir(str(projeto))
    processar_linha(json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)})))

    req = envelope_req("mapa.gerar", {"mapspec": mapspec_local})
    eventos, resposta = eventos_e_resposta(processar_linha(json.dumps(req)))
    assert resposta["ok"] is True, resposta

    itens = [
        e["dados"]
        for e in eventos
        if e["evento"] == "job.progresso" and "item" in e["dados"]
    ]
    assert itens, "nenhum item de camada reportado"
    assert {d["etapa"] for d in itens} == {"resolvendo_camadas_locais"}
    ids_mapspec = {c["id"] for c in mapspec_local["camadas"]}
    assert {d["item"] for d in itens} <= ids_mapspec


def test_mapa_gerar_invalido_nao_emite_evento(projeto: Path) -> None:
    workspace_servico.abrir(str(projeto))
    processar_linha(json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)})))

    req = envelope_req("mapa.gerar", {"mapspec": {"contract_version": 2}})
    eventos, resposta = eventos_e_resposta(processar_linha(json.dumps(req)))
    assert resposta["ok"] is False
    assert eventos == []


def test_loop_ndjson_escreve_evento_antes_da_resposta(projeto: Path, mapspec_local: dict) -> None:
    """No stdio real o evento sai na hora, não no fim do job."""
    import io

    from mapasfacil_nucleo.__main__ import loop_ndjson

    workspace_servico.abrir(str(projeto))
    entrada = io.StringIO(
        json.dumps(envelope_req("workspace.abrir", {"caminho": str(projeto)}))
        + "\n"
        + json.dumps(envelope_req("mapa.gerar", {"mapspec": mapspec_local}))
        + "\n"
    )
    saida = io.StringIO()
    loop_ndjson(entrada, saida)

    mensagens = [json.loads(linha) for linha in saida.getvalue().splitlines() if linha.strip()]
    tipos = [m["tipo"] for m in mensagens]
    assert tipos[0] == "res"  # workspace.abrir
    assert "evt" in tipos
    assert tipos[-1] == "res"
    assert tipos.index("evt") < len(tipos) - 1
