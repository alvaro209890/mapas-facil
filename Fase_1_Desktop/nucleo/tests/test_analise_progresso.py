from __future__ import annotations

from types import SimpleNamespace

import pytest

from mapasfacil_nucleo import __main__ as main_mod
from mapasfacil_nucleo.analise import executar as executar_mod
from mapasfacil_nucleo.analise.progresso import RastreadorProgressoSerie
from mapasfacil_nucleo.analise.serie import POR_ID
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import Emissor


def test_progresso_da_serie_e_real_monotonico_e_enriquece_artefatos():
    eventos: list[tuple[str, dict]] = []
    progresso = RastreadorProgressoSerie(
        lambda evento, dados: eventos.append((evento, dados)),
        job_id="job-serie",
        total_mapas=20,
    )
    receita = POR_ID["alertas_mapbiomas"]

    progresso.iniciar_identidade()
    progresso.concluir_identidade("Fazenda Teste")
    progresso.iniciar_camadas()
    progresso.camada("CAR_ATP", 1, 2)
    progresso.camada("ALERTAS_MAPBIOMAS", 2, 2)
    progresso.iniciar_mapa(receita, 1)

    mapa = progresso.rastreador_do_mapa(receita, 1)
    mapa.concluir("validando_spec")
    mapa.item(
        "resolvendo_camadas_locais",
        "perimetro",
        indice=1,
        total=1,
    )
    mapa.concluir("baixando_externas")
    mapa.artefato(
        "preview_png",
        caminho="Mapas/.preview/parcial_01.png",
        etapa="aplicando_layout",
    )

    progresso.concluir_mapa(receita, 1, ok=True, erro=None)
    progresso.iniciar_compilacao(20)
    progresso.artefato_compilado("Mapas/Analise_de_area.pdf", 20)
    progresso.concluir(
        gerados=20,
        total=20,
        relatorio="Mapas/analise_de_area_relatorio.json",
    )

    progresso_evt = [dados for evento, dados in eventos if evento == "job.progresso"]
    assert progresso_evt
    assert [e["pct"] for e in progresso_evt] == sorted(e["pct"] for e in progresso_evt)
    assert progresso_evt[-1]["pct"] == 100
    assert progresso_evt[-1]["serie"]["fase"] == "concluido"
    assert all(e["job_id"] == "job-serie" for e in progresso_evt)
    assert any(e["serie"]["fase"] == "camada" and e.get("item") == "CAR_ATP" for e in progresso_evt)
    assert any(
        e["serie"].get("mapa_id") == "alertas_mapbiomas"
        and "mapa 1 de 20" in e["serie"]["mensagem"]
        for e in progresso_evt
    )

    artefatos = [dados for evento, dados in eventos if evento == "job.artefato_parcial"]
    assert artefatos[0]["serie"]["mapa_id"] == "alertas_mapbiomas"
    assert artefatos[-1]["caminho"] == "Mapas/Analise_de_area.pdf"
    assert artefatos[-1]["serie"]["compilado"] is True


def test_handler_registra_job_emite_serie_e_libera(monkeypatch):
    eventos: list[dict] = []
    liberados: list[str] = []
    recebido: dict = {}

    monkeypatch.setattr(main_mod.sessao, "exigir_conectado", lambda _acao: None)
    monkeypatch.setattr(
        main_mod.workspace_servico,
        "estado_atual",
        lambda: SimpleNamespace(guard="guard-teste"),
    )
    monkeypatch.setattr(main_mod, "_fontes_idx_do_estado", lambda _estado: {"ATP": "SHP/ATP.shp"})
    monkeypatch.setattr(main_mod.jobs, "registrar", lambda: "job-analise")
    monkeypatch.setattr(main_mod.jobs, "liberar", liberados.append)

    def executar_fake(**kwargs):
        recebido.update(kwargs)
        kwargs["progresso"].iniciar_identidade()
        return {"resumo": {"total": 20, "gerados": 20}}

    monkeypatch.setattr(main_mod.analise_executar, "executar", executar_fake)

    resposta = main_mod._handler_analise_executar(
        {},
        Emissor("req-analise", eventos.append),
    )

    assert resposta["resumo"]["gerados"] == 20
    assert recebido["guard"] == "guard-teste"
    assert recebido["atp_rel"] == "SHP/ATP.shp"
    assert liberados == ["job-analise"]
    assert eventos[0]["evento"] == "job.progresso"
    assert eventos[0]["dados"]["job_id"] == "job-analise"
    assert eventos[0]["dados"]["serie"]["fase"] == "identidade"


def test_handler_rejeita_receita_desconhecida_antes_de_criar_job(monkeypatch):
    monkeypatch.setattr(main_mod.sessao, "exigir_conectado", lambda _acao: None)
    monkeypatch.setattr(
        main_mod.workspace_servico,
        "estado_atual",
        lambda: SimpleNamespace(guard="guard-teste"),
    )
    monkeypatch.setattr(main_mod, "_fontes_idx_do_estado", lambda _estado: {"ATP": "SHP/ATP.shp"})

    with pytest.raises(ErroNucleo) as exc:
        main_mod._handler_analise_executar(
            {"apenas": ["mapa_inexistente"]},
            Emissor("req-analise"),
        )
    assert exc.value.codigo == "NU-001"


def test_cancelamento_nao_vira_falha_isolada_de_mapa(monkeypatch):
    receita = SimpleNamespace(id="mapa", ordem=1, nome="Mapa")
    preparacao = SimpleNamespace(feicoes={}, fontes_idx={})
    monkeypatch.setattr(
        executar_mod.serie_mod,
        "montar_mapspec",
        lambda *_args, **_kwargs: {"camadas": []},
    )

    def cancelar(*_args, **_kwargs):
        raise ErroNucleo("NU-050", "cancelado")

    monkeypatch.setattr(executar_mod, "gerar_mapa", cancelar)
    with pytest.raises(ErroNucleo) as exc:
        executar_mod._gerar_um(
            receita,
            identidade=SimpleNamespace(),
            preparacao=preparacao,
            guard=SimpleNamespace(),
            epsg=31982,
            modelos=None,
        )
    assert exc.value.codigo == "NU-050"
