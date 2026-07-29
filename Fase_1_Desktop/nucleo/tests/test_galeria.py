# M4 / F1-15 — galeria determinística (anel 1).

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria.catalogo import carregar_galeria, limpar_cache, obter_modelo
from mapasfacil_nucleo.galeria import estado as estado_mod
from mapasfacil_nucleo.galeria.estado import avaliar_status
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.galeria.servico import detalhar, listar, montar
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


@pytest.fixture(autouse=True)
def _limpar_galeria_cache():
    limpar_cache()
    yield
    limpar_cache()


@pytest.fixture
def pasta_harmonia(tmp_path: Path) -> Path:
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    return tmp_path


def test_carregar_galeria_tem_6_modelos_com_analise_de_area():
    galeria = carregar_galeria()
    assert galeria["galeria_version"] == 2
    assert len(galeria["modelos"]) == 6
    ids = {m["id"] for m in galeria["modelos"]}
    assert "dinamica_2026_retrato" in ids
    assert "analise_de_area" in ids
    analise = obter_modelo("analise_de_area")
    assert analise["tipo_execucao"] == "analise_de_area"
    assert analise["saidas_padrao"] == ["mxd", "pdf"]


def test_listar_status_coerente_com_manifest(pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    resultado = listar({"workspace": str(pasta_harmonia)})
    assert len(resultado["modelos"]) == 6
    por_id = {m["id"]: m for m in resultado["modelos"]}
    assert por_id["dinamica_2026_retrato"]["status"] == "pronto"
    assert not por_id["dinamica_2026_retrato"].get("requisitos_faltando")
    for mid in (
        "dinamica_2026_quantitativos",
        "tipologia_paisagem",
        "terras_indigenas_paisagem",
        "uc_paisagem",
    ):
        assert por_id[mid]["status"] == "pronto"
    assert por_id["analise_de_area"]["status"] == "pronto"
    assert por_id["analise_de_area"]["tipo_execucao"] == "analise_de_area"


def test_listar_saida_nativa_nao_exige_template_arcmap(pasta_harmonia: Path):
    resultado = listar(
        {
            "workspace": str(pasta_harmonia),
            "saidas_pedidas": ["pdf", "png"],
        }
    )
    por_id = {m["id"]: m for m in resultado["modelos"]}
    for mid in (
        "dinamica_2026_quantitativos",
        "tipologia_paisagem",
        "terras_indigenas_paisagem",
        "uc_paisagem",
    ):
        assert por_id[mid]["status"] == "pronto"
        assert por_id[mid]["motivo"] is None


def test_saida_mxd_continua_exigindo_template_arcmap(pasta_harmonia: Path, monkeypatch):
    modelo = obter_modelo("tipologia_paisagem")
    monkeypatch.setattr(
        estado_mod,
        "_template_info",
        lambda _template: {"status": "a_preparar", "sha256_ok": False, "sha256": None},
    )
    estado = avaliar_status(modelo, {"fontes_locais": ["ATP"]}, ["mxd", "pdf"])
    assert estado["status"] == "indisponivel"
    assert "ArcMap" in estado["motivo"]


def test_serie_mxd_exige_os_20_templates(monkeypatch):
    modelo = obter_modelo("analise_de_area")

    def info(template_id: str) -> dict:
        if template_id == "serie_dla":
            return {"status": "a_preparar", "sha256_ok": False, "sha256": None}
        return {"status": "pronto", "sha256_ok": True, "sha256": "ok"}

    monkeypatch.setattr(estado_mod, "_template_info", info)
    indice = {"fontes_locais": ["ATP"]}
    assert avaliar_status(modelo, indice, ["pdf"])["status"] == "pronto"
    assert avaliar_status(modelo, indice, ["mxd", "pdf"])["status"] == "indisponivel"


def test_listar_rejeita_saida_desconhecida() -> None:
    with pytest.raises(ErroNucleo) as exc:
        listar({"saidas_pedidas": ["svg"]})
    assert exc.value.codigo == "NU-001"


def test_listar_sem_atp_faltam_dados(tmp_path: Path):
    escrever_shapefile_quadrado_utm(tmp_path / "SHP" / "AVN.shp", nome="AVN")
    resultado = listar({"workspace": str(tmp_path)})
    dinamica = next(m for m in resultado["modelos"] if m["id"] == "dinamica_2026_retrato")
    assert dinamica["status"] == "faltam_dados"
    assert "ATP" in dinamica["requisitos_faltando"]


def test_montar_mapspec_valida_e_deterministico(pasta_harmonia: Path):
    workspace_servico.abrir(str(pasta_harmonia))
    a = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta_harmonia))
    b = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta_harmonia))
    c = montar_mapspec("dinamica_2026_retrato", workspace=str(pasta_harmonia))

    fontes = frozenset(
        workspace_servico.estado_atual().indice["fontes_locais"]  # type: ignore[union-attr]
    )
    for pacote in (a, b, c):
        checagem = validar(pacote["mapspec"], fontes_locais=fontes)
        assert checagem["valido"] is True, checagem["erros"]

    def sem_id(spec: dict) -> dict:
        clone = copy.deepcopy(spec)
        clone.pop("id")
        return clone

    assert sem_id(a["mapspec"]) == sem_id(b["mapspec"]) == sem_id(c["mapspec"])
    assert a["mapspec"]["template"] == "dinamica_retrato"
    assert {cam["id"] for cam in a["mapspec"]["camadas"]} >= {"perimetro", "avn", "auas", "ac"}


def test_montar_pdf_nativo_com_template_a_preparar(pasta_harmonia: Path):
    pacote = montar_mapspec(
        "tipologia_paisagem",
        workspace=str(pasta_harmonia),
        sobrescritas={"saidas": ["pdf"]},
    )
    assert pacote["mapspec"]["template"] == "tipologia_paisagem"
    assert pacote["mapspec"]["saidas"] == ["pdf"]
    fontes = frozenset(
        workspace_servico.estado_atual().indice["fontes_locais"]  # type: ignore[union-attr]
    )
    checagem = validar(pacote["mapspec"], fontes_locais=fontes)
    assert checagem["valido"] is True, checagem["erros"]
    assert any(aviso["codigo"] == "AG-030" for aviso in checagem["avisos"])


def test_montar_mxd_com_template_preparado(pasta_harmonia: Path):
    pacote = montar_mapspec(
        "tipologia_paisagem",
        workspace=str(pasta_harmonia),
        sobrescritas={"saidas": ["mxd", "pdf"]},
    )
    assert pacote["mapspec"]["saidas"] == ["mxd", "pdf"]


def test_modelo_de_serie_nao_finge_ser_um_mapspec(pasta_harmonia: Path):
    with pytest.raises(ErroNucleo) as exc:
        montar_mapspec(
            "analise_de_area",
            workspace=str(pasta_harmonia),
            sobrescritas={"saidas": ["pdf"]},
        )
    assert exc.value.codigo == "NU-235"
    assert exc.value.detalhes == {
        "modelo_id": "analise_de_area",
        "metodo": "analise.executar",
    }


def test_montar_sem_atp_nu233(tmp_path: Path):
    escrever_shapefile_quadrado_utm(tmp_path / "SHP" / "AVN.shp", nome="AVN")
    with pytest.raises(ErroNucleo) as exc:
        montar_mapspec("dinamica_2026_retrato", workspace=str(tmp_path))
    assert exc.value.codigo == "NU-233"
    assert exc.value.detalhes and "ATP" in exc.value.detalhes.get("requisitos_faltando", [])


def test_sobrescritas_chave_ilegal_nu232(pasta_harmonia: Path):
    with pytest.raises(ErroNucleo) as exc:
        montar(
            {
                "modelo_id": "dinamica_2026_retrato",
                "workspace": str(pasta_harmonia),
                "sobrescritas": {"camadas": []},
            }
        )
    assert exc.value.codigo == "NU-232"


def test_modelo_inexistente_nu230():
    with pytest.raises(ErroNucleo) as exc:
        obter_modelo("nao_existe")
    assert exc.value.codigo == "NU-230"


def test_detalhar_traz_mapeamento(pasta_harmonia: Path):
    detalhe = detalhar(
        {"modelo_id": "dinamica_2026_retrato", "workspace": str(pasta_harmonia)}
    )
    assert detalhe["id"] == "dinamica_2026_retrato"
    assert detalhe["mapeamento_sugerido"]["ATP"] == "local.ATP"
    assert "requisitos_camadas" in detalhe


def test_avaliar_status_sem_indice():
    modelo = obter_modelo("dinamica_2026_retrato")
    estado = avaliar_status(modelo, None)
    assert estado["status"] == "faltam_dados"
