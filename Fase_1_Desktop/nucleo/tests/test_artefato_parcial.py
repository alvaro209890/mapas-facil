# H1 — `job.artefato_parcial`: contrato, emissão no pipeline e caminho relativo.

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mapasfacil_nucleo.artefatos import (
    EVENTO,
    PASTA_PREVIEW,
    TIPOS,
    ArtefatoInvalido,
    montar_dados,
    normalizar_caminho,
)
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.progresso import IDS_ETAPAS, RastreadorProgresso
from mapasfacil_nucleo.protocolo import EVENTOS, Emissor
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm


# --------------------------------------------------------------------------- contrato


def test_evento_esta_no_vocabulario_do_protocolo():
    assert EVENTO in EVENTOS
    assert Emissor("01ABC").emitir(EVENTO, {"tipo": "pdf"})["evento"] == EVENTO


def test_evento_fora_do_contrato_e_erro_de_programacao():
    with pytest.raises(ValueError):
        Emissor("01ABC").emitir("job.inventado", {})


def test_os_quatro_tipos_do_plano():
    assert TIPOS == ("camada", "tabela_png", "preview_png", "pdf")


def test_tipo_e_etapa_sao_validados():
    with pytest.raises(ArtefatoInvalido):
        montar_dados("thumbnail", caminho="Mapas/x.png", etapa="gerando_tabela")
    with pytest.raises(ArtefatoInvalido):
        montar_dados("pdf", caminho="Mapas/x.pdf", etapa="etapa_inventada")


@pytest.mark.parametrize(
    "caminho",
    [
        "C:\\Users\\alvaro\\Harmonia\\Mapas\\x.pdf",
        "/home/alvaro/Harmonia/Mapas/x.pdf",
        "../fora/x.pdf",
    ],
)
def test_caminho_absoluto_ou_de_fuga_e_recusado(caminho: str):
    with pytest.raises(ArtefatoInvalido):
        montar_dados("pdf", caminho=caminho, etapa="exportando_pdf")


def test_caminho_windows_vira_posix_relativo():
    dados = montar_dados("camada", caminho="SHP\\AVN.shp", etapa="resolvendo_camadas_locais")
    assert dados["caminho"] == "SHP/AVN.shp"


def test_absoluto_dentro_da_raiz_e_relativizado(tmp_path: Path):
    alvo = tmp_path / "Mapas" / "Dinamica.pdf"
    assert normalizar_caminho(alvo, raiz=tmp_path) == "Mapas/Dinamica.pdf"
    with pytest.raises(ArtefatoInvalido):
        normalizar_caminho(Path("/etc/passwd"), raiz=tmp_path)


def test_campos_opcionais_so_entram_quando_existem():
    minimo = montar_dados("tabela_png", caminho="Mapas/recursos/t.png", etapa="gerando_tabela")
    assert set(minimo) == {"tipo", "caminho", "etapa"}
    completo = montar_dados(
        "camada",
        caminho="SHP/AVN.shp",
        etapa="resolvendo_camadas_locais",
        camada_id="avn",
        ordem=30,
        pct=10,
    )
    assert completo["camada_id"] == "avn" and completo["ordem"] == 30 and completo["pct"] == 10


def test_rastreador_emite_pelo_canal_de_eventos():
    emitidos: list[tuple[str, dict[str, Any]]] = []
    prog = RastreadorProgresso(lambda evento, dados: emitidos.append((evento, dados)))
    prog.concluir("validando_spec")
    prog.artefato("camada", caminho="SHP/ATP.shp", etapa="resolvendo_camadas_locais", com_pct=True)
    assert emitidos[0][0] == "job.progresso"
    assert emitidos[1][0] == EVENTO
    assert emitidos[1][1]["pct"] == 3  # pct corrente do job, não inventado


def test_rastreador_sem_canal_e_no_op():
    dados = RastreadorProgresso().artefato("pdf", caminho="Mapas/x.pdf", etapa="exportando_pdf")
    assert dados["tipo"] == "pdf"


# --------------------------------------------------------------------------- pipeline


@pytest.fixture
def projeto(tmp_path: Path) -> dict[str, Any]:
    escrever_shapefile_quadrado_utm(tmp_path / "Dados" / "ATP.shp", nome="Harmonia", lado_m=4000)
    escrever_shapefile_quadrado_utm(tmp_path / "Dados" / "AVN.shp", nome="AVN", lado_m=1500)
    from mapasfacil_nucleo.fsguard import WorkspaceGuard

    guard = WorkspaceGuard(tmp_path)
    fontes_idx = {
        "ATP": str(tmp_path / "Dados" / "ATP.shp"),
        "AVN": str(tmp_path / "Dados" / "AVN.shp"),
    }
    mapspec = {
        "contract_version": 2,
        "perfil": "harmonia",
        "id": "spec_h1",
        "versao": 1,
        "titulo": "Dinâmica 2026",
        "template": "dinamica_retrato",
        "saidas": ["pdf", "png"],
        "imovel": {
            "nome": "Fazenda Harmonia",
            "car": "MT102042/2017",
            "municipio": {"nome": "Vila Rica", "uf": "MT"},
            "geometria": "local.ATP",
        },
        "crs": "EPSG:31982",
        "escala": "auto",
        "camadas": [
            {
                "id": "perimetro",
                "nome_no_mxd": "Fazenda Harmonia",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            },
            {
                "id": "avn",
                "nome_no_mxd": "Área de vegetação nativa",
                "fonte": "local.AVN",
                "estilo": "avn",
                "ordem": 30,
            },
        ],
        "elementos_layout": {"tabela": True},
        "saida": {"pasta": "Mapas", "nome_base": "Dinamica", "materializar_camadas_em": "SHP"},
    }
    return {"guard": guard, "fontes_idx": fontes_idx, "mapspec": mapspec, "raiz": tmp_path}


def _gerar(projeto: dict[str, Any]) -> list[dict[str, Any]]:
    eventos: list[dict[str, Any]] = []
    prog = RastreadorProgresso(lambda evento, dados: eventos.append({"evento": evento, **dados}))
    gerar_mapa(
        projeto["mapspec"],
        projeto["guard"],
        projeto["fontes_idx"],
        progresso=prog,
    )
    return eventos


def test_pipeline_emite_os_quatro_tipos(projeto: dict[str, Any]):
    eventos = _gerar(projeto)
    artefatos = [e for e in eventos if e["evento"] == EVENTO]
    tipos = {a["tipo"] for a in artefatos}
    assert tipos == set(TIPOS), f"faltou tipo: {set(TIPOS) - tipos}"


def test_artefato_camada_traz_id_e_ordem_do_mapspec(projeto: dict[str, Any]):
    camadas = [e for e in _gerar(projeto) if e["evento"] == EVENTO and e["tipo"] == "camada"]
    por_id = {c["camada_id"]: c for c in camadas}
    assert set(por_id) == {"perimetro", "avn"}
    assert por_id["avn"]["ordem"] == 30
    assert por_id["avn"]["etapa"] == "resolvendo_camadas_locais"
    assert por_id["avn"]["caminho"].startswith("SHP/")


def test_todo_caminho_e_relativo_e_existe_no_disco(projeto: dict[str, Any]):
    raiz: Path = projeto["raiz"]
    artefatos = [e for e in _gerar(projeto) if e["evento"] == EVENTO]
    assert artefatos
    for artefato in artefatos:
        caminho = artefato["caminho"]
        assert not Path(caminho).is_absolute(), caminho
        assert ".." not in caminho and "\\" not in caminho, caminho
        assert (raiz / caminho).exists(), f"artefato anunciado mas ausente: {caminho}"


def test_preview_png_sai_da_pasta_de_preview_com_pct(projeto: dict[str, Any]):
    previews = [e for e in _gerar(projeto) if e["evento"] == EVENTO and e["tipo"] == "preview_png"]
    assert len(previews) >= 2, "esperado ao menos um preview antes e um depois do layout"
    for preview in previews:
        assert preview["caminho"].startswith(f"{PASTA_PREVIEW}/")
        assert preview["etapa"] == "aplicando_layout"
        assert 0 <= preview["pct"] <= 100


def test_job_progresso_continua_intacto(projeto: dict[str, Any]):
    eventos = _gerar(projeto)
    progresso = [e for e in eventos if e["evento"] == "job.progresso"]
    assert [e["etapa"] for e in progresso if e["pct"] == 100][-1] == "validando_saida"
    pcts = [e["pct"] for e in progresso]
    assert pcts == sorted(pcts), "pct andou para trás"
    assert {e["etapa"] for e in progresso} == set(IDS_ETAPAS)


def test_sem_emissor_nada_quebra(projeto: dict[str, Any]):
    """Chamado como biblioteca (CLI, testes) o pipeline não emite nem rasteriza."""
    resultado = gerar_mapa(projeto["mapspec"], projeto["guard"], projeto["fontes_idx"])
    assert resultado["pdf"].endswith(".pdf")
    assert not (projeto["raiz"] / PASTA_PREVIEW).exists()


# --------------------------------------------------------------------------- artefato.ler


def test_artefato_ler_devolve_base64_do_preview(projeto: dict[str, Any]):
    from mapasfacil_nucleo import leitor_artefato
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    workspace_servico.abrir(str(projeto["raiz"]))
    eventos = _gerar(projeto)
    preview = next(e for e in eventos if e["evento"] == EVENTO and e["tipo"] == "preview_png")

    lido = leitor_artefato.ler({"caminho": preview["caminho"]})
    assert lido["mime"] == "image/png"
    assert lido["caminho"] == preview["caminho"]
    assert lido["tamanho"] > 0 and lido["base64"]


def test_artefato_ler_recusa_formato_e_fuga(projeto: dict[str, Any]):
    from mapasfacil_nucleo import leitor_artefato
    from mapasfacil_nucleo.erros import ErroNucleo
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    workspace_servico.abrir(str(projeto["raiz"]))
    with pytest.raises(ErroNucleo) as fora:
        leitor_artefato.ler({"caminho": "../../etc/passwd"})
    assert fora.value.codigo == "NU-010"
    with pytest.raises(ErroNucleo) as formato:
        leitor_artefato.ler({"caminho": "Mapas/Dinamica.pdf"})
    assert formato.value.codigo == "NU-043"
