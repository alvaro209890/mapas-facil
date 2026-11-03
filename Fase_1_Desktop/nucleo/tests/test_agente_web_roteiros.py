# W5-17 — os 7 roteiros de conversa da web, como cassetes (sem rede, com FakeProvedor).
#
# Cada teste afirma a **sequência de tools** e o **estado final**, exatamente como o plano
# W-05 §Roteiros de conversa. Cassete é roteiro de teste, não gravação de provedor real:
# os sete rodam no CI sem chave e sem 9Router.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo.agente.orquestrador import (
    configurar_provedor,
    esquecer_conversa,
    executar_turno,
    mapspec_da_conversa,
)
from mapasfacil_nucleo.agente.vcr import carregar_cassete, provedor_de_cassete
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm

ROTEIROS = (
    "web_dinamica",
    "web_estilo",
    "web_folha",
    "web_qual_folha",
    "web_hard",
    "web_voltar",
    "web_pergunta",
)


@pytest.fixture
def amb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta_chats = tmp_path / "chats"
    pasta_chats.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta_chats))
    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    conversas_servico.configurar_diretorio(pasta_chats)

    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))

    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=str(tmp_path))["conversation_id"]
    repo.fechar()

    yield {"cid": cid, "pasta": tmp_path, "chats": pasta_chats}

    configurar_provedor(None)
    conversas_servico.configurar_diretorio(None)
    workspace_servico.fechar()


def _turno(
    amb: dict[str, Any], roteiro: str, mensagem: str, *, versao: int | None = None
) -> dict[str, Any]:
    """Roda um turno. `versao` imita o que o servidor faz ao despachar o job.

    Em produção quem define a pasta da versão é o servidor, via
    `MAPASFACIL_VERSAO_SAIDA`, antes de pedir a geração — sem isso duas gerações
    caem na mesma `Mapas/v001` e a segunda sobrescreve a primeira.
    """
    if versao is not None:
        os.environ["MAPASFACIL_VERSAO_SAIDA"] = str(versao)
    else:
        os.environ.pop("MAPASFACIL_VERSAO_SAIDA", None)
    configurar_provedor(provedor_de_cassete(roteiro))
    return executar_turno(conversation_id=amb["cid"], mensagem=mensagem)


def test_cassetes_existem_e_tem_o_formato_da_casa():
    for nome in ROTEIROS:
        dados = carregar_cassete(nome)
        assert dados["passos"], nome
        for passo in dados["passos"]:
            assert passo.get("finish_reason"), nome
            for chamada in passo.get("tool_calls") or []:
                assert chamada["function"]["name"], nome
                json.loads(chamada["function"]["arguments"] or "{}")


# ------------------------------------------------------------------ web_dinamica


def test_web_dinamica_monta_pela_galeria_e_gera(amb):
    resultado = _turno(amb, "web_dinamica", "faz a dinâmica 2026", versao=1)
    assert resultado["tools_usadas"][:5] == [
        "estado_do_projeto",
        "ler_recibo_car",
        "usar_modelo_da_galeria",
        "validar_mapspec",
        "gerar_mapa",
    ]
    mapspec = mapspec_da_conversa(amb["cid"])
    assert mapspec is not None
    assert mapspec["folha"]["formato"] == "A4"
    assert {"pdf", "xlsx"} <= set(mapspec.get("saidas") or [])
    assert resultado.get("texto")
    esquecer_conversa(amb["cid"])


# -------------------------------------------------------------------- web_estilo


def test_web_estilo_edita_camada_e_tira_a_tabela(amb):
    _turno(amb, "web_dinamica", "faz a dinâmica 2026", versao=1)
    antes = mapspec_da_conversa(amb["cid"])
    resultado = _turno(amb, "web_estilo", "clareia a vegetação e tira a tabela", versao=2)
    assert resultado["tools_usadas"] == ["editar_camada", "alternar_elemento", "gerar_mapa"]
    depois = mapspec_da_conversa(amb["cid"])
    assert depois["elementos_layout"]["tabela"] is False
    # duas edições no mesmo turno = duas versões novas (editar_camada, alternar_elemento)
    assert depois["versao"] == antes["versao"] + 2
    assert depois["parent_id"] is not None
    esquecer_conversa(amb["cid"])


# --------------------------------------------------------------------- web_folha


def test_web_folha_vira_a3_paisagem(amb):
    _turno(amb, "web_dinamica", "faz a dinâmica 2026", versao=1)
    antes = mapspec_da_conversa(amb["cid"])
    resultado = _turno(amb, "web_folha", "passa pra A3 paisagem", versao=2)
    assert resultado["tools_usadas"] == ["definir_folha", "gerar_mapa"]
    depois = mapspec_da_conversa(amb["cid"])
    assert depois["folha"]["formato"] == "A3"
    assert depois["folha"]["orientacao"] == "paisagem"
    # A3 cabe mais área: a escala só pode ficar igual ou menor (mais detalhe)
    assert _escala(depois) <= _escala(antes)
    esquecer_conversa(amb["cid"])


def _escala(mapspec: dict[str, Any]) -> float:
    bruto = mapspec.get("escala")
    if isinstance(bruto, (int, float)):
        return float(bruto)
    if isinstance(bruto, str) and bruto.isdigit():
        return float(bruto)
    return 10**9  # "auto": não compara


# ----------------------------------------------------------------- web_qual_folha


def test_web_qual_folha_responde_sem_gerar_versao(amb):
    _turno(amb, "web_dinamica", "faz a dinâmica 2026", versao=1)
    antes = mapspec_da_conversa(amb["cid"])
    resultado = _turno(amb, "web_qual_folha", "qual folha fica melhor?")
    assert resultado["tools_usadas"] == ["sugerir_enquadramento"]
    assert "gerar_mapa" not in resultado["tools_usadas"]
    depois = mapspec_da_conversa(amb["cid"])
    assert depois["versao"] == antes["versao"]
    assert "1:" in resultado["texto"]
    esquecer_conversa(amb["cid"])


# ---------------------------------------------------------------------- web_hard


def test_web_hard_o_nucleo_ainda_nao_produz_check_obrigatorio_falho(amb):
    """Mede o estado real: hoje nenhum fixture sintético derruba um check HARD.

    O roteiro do plano (W-05 §web_hard) parte de um HARD falhando — AUAS fora da ATP e
    recibo divergente, que é o **H17** ("áreas × recibo do CAR"), check que ainda **não
    existe** no núcleo (entra no W7/W9). Até lá o roteiro roda, chama `explicar_validacao`
    e responde o que o relatório diz — este teste afirma exatamente isso e falha no dia em
    que um HARD começar a falhar, para alguém revisar a promessa da IA.
    """
    resultado = _turno(amb, "web_hard", "recorta só a classe que eu te falei", versao=1)
    assert resultado["tools_usadas"] == [
        "usar_modelo_da_galeria",
        "editar_camada",
        "gerar_mapa",
        "explicar_validacao",
    ]
    assert "explicar_validacao" in resultado["tools_usadas"]

    relatorios = sorted((amb["pasta"] / "Mapas" / "v001").glob("*_validacao.json"))
    assert relatorios, "a geração não deixou relatório de validação"
    relatorio = json.loads(relatorios[-1].read_text(encoding="utf-8"))
    hard = relatorio["checks"]["hard"]
    falhas = [c for c in hard if not c.get("ok")]
    assert falhas == [], (
        "apareceu um HARD falhando: revise o roteiro web_hard para afirmar que a IA "
        f"explica o check em vez de dizer pronto — falhas: {falhas}"
    )
    esquecer_conversa(amb["cid"])


# -------------------------------------------------------------------- web_voltar


def test_web_voltar_restaura_em_versao_nova(amb):
    _turno(amb, "web_dinamica", "faz a dinâmica 2026", versao=1)  # v1, A4
    _turno(amb, "web_folha", "passa pra A3 paisagem", versao=2)  # v2, A3
    v1 = json.loads(
        (amb["pasta"] / "Mapas" / "v001" / "mapspec.json").read_text(encoding="utf-8")
    )["mapspec"]

    resultado = _turno(amb, "web_voltar", "volta pra versão 1", versao=3)
    assert resultado["tools_usadas"] == ["listar_versoes", "restaurar_versao"]

    atual = mapspec_da_conversa(amb["cid"])
    assert atual["versao"] == 3
    assert atual["folha"]["formato"] == "A4"           # conteúdo da v1
    assert atual["parent_id"] == v1["id"]              # aponta para a origem
    # nada foi apagado: v001 e v002 continuam no disco
    assert (amb["pasta"] / "Mapas" / "v001" / "mapspec.json").is_file()
    assert (amb["pasta"] / "Mapas" / "v002" / "mapspec.json").is_file()
    esquecer_conversa(amb["cid"])


# ------------------------------------------------------------------ web_pergunta


def test_web_pergunta_emite_pergunta_e_nao_gera_versao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta_chats = tmp_path / "chats_p"
    pasta_chats.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta_chats))
    monkeypatch.setenv("MAPASFACIL_MODO", "servidor")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    conversas_servico.configurar_diretorio(pasta_chats)

    # nomes que não casam com nenhum papel conhecido: o perímetro fica ambíguo
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "Poligono_1.shp", nome="A", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "Area_2.shp", nome="B", lado_m=1200)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    repo = RepositorioConversas(pasta_chats)
    cid = repo.criar_conversa(workspace=str(tmp_path))["conversation_id"]
    repo.fechar()

    try:
        configurar_provedor(provedor_de_cassete("web_pergunta"))
        resultado = executar_turno(conversation_id=cid, mensagem="faz um mapa")
        assert resultado["tools_usadas"] == ["criar_mapa"]
        assert mapspec_da_conversa(cid) is None
        assert resultado["mapspec_versao"] is None
        # nenhum MapSpec vivo foi gravado: a pergunta veio antes de existir mapa
        assert not (pasta_chats / "mapspecs" / f"{cid}.json").exists()
        texto = resultado["texto"].lower()
        assert "perímetro" in texto or "perimetro" in texto
    finally:
        configurar_provedor(None)
        conversas_servico.configurar_diretorio(None)
        workspace_servico.fechar()
