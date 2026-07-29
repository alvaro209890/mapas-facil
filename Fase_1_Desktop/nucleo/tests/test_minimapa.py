# Minimapa IBGE — cálculo de página, resolução local e detecção em .mxd.

from __future__ import annotations

from pathlib import Path

from PIL import Image

from mapasfacil_nucleo.agente.visao import mapear, mxd_strings
from mapasfacil_nucleo.camadas import ibge as ibge_mod
from mapasfacil_nucleo.motores import minimapa as minimapa_mod
from mapasfacil_nucleo.motores.minimapa_job import (
    _garantir_homonimos_shp,
    _gravar_georreferencia_raster,
    montar_contexto_minimapa,
)
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm


def test_retangulo_e_guia_L_tem_tres_pontos_quando_nao_alinhado() -> None:
    calc = minimapa_mod.retangulo_e_guia_L(centro_page_mm=(30.0, 280.0))
    assert "retangulo_mm" in calc
    assert len(calc["guia_L_mm"]) == 3
    g = calc["graficos_arcpy_cm"]
    assert "MINIMAPA_RETANGULO" in g and "MINIMAPA_GUIA" in g
    assert g["MINIMAPA_GUIA"]["width_cm"] > 0
    assert g["MINIMAPA_GUIA"]["height_cm"] > 0


def test_homonimos_incluem_alias_da_camada_tematica(tmp_path: Path) -> None:
    for extensao in (".shp", ".shx", ".dbf", ".prj"):
        (tmp_path / f"ALERTAS_MAPBIOMAS{extensao}").write_bytes(extensao.encode())
    _garantir_homonimos_shp(
        tmp_path,
        [
            {
                "id": "alertas_mapbiomas",
                "fonte": "local.ALERTAS_MAPBIOMAS",
            }
        ],
    )
    for extensao in (".shp", ".shx", ".dbf", ".prj"):
        assert (tmp_path / f"AIR{extensao}").read_bytes() == extensao.encode()


def test_world_file_do_basemap_arcmap(tmp_path: Path) -> None:
    raster = tmp_path / "basemap.png"
    Image.new("RGB", (100, 50), "white").save(raster)
    _gravar_georreferencia_raster(raster, (1000.0, 2000.0, 1200.0, 2100.0), 31982)
    linhas = [float(item) for item in raster.with_suffix(".pgw").read_text().splitlines()]
    assert linhas == [2.0, 0.0, 0.0, -2.0, 1001.0, 2099.0]
    assert "SIRGAS" in raster.with_suffix(".prj").read_text(encoding="utf-8")


def test_graficos_para_centroide_vila_rica() -> None:
    # bbox aproximado Vila Rica (WGS84), com padding
    extent = (-52.6, -10.5, -51.0, -9.5)
    calc = minimapa_mod.graficos_para_centroide(
        lon=-51.8,
        lat=-10.0,
        extent_minimapa_wgs84=extent,
    )
    assert calc["centro_page_mm"]
    assert calc["extent_minimapa_df"]
    assert "MINIMAPA_RETANGULO" in calc["graficos_arcpy_cm"]


def test_resolver_municipio_vila_rica_local() -> None:
    shp = ibge_mod.shapefile_municipios()
    if not shp.is_file():
        return  # base não materializada neste checkout
    hit = ibge_mod.resolver_municipio(nome="Vila Rica")
    assert hit is not None
    assert hit["nome"] == "Vila Rica"
    assert hit["sigla_uf"] == "MT"
    assert hit["cod_ibge"].startswith("51")
    ext = ibge_mod.extent_municipio(nome="Vila Rica")
    assert ext is not None
    assert ext[0] < ext[2] and ext[1] < ext[3]


def test_uf_sigla_para_nome() -> None:
    assert ibge_mod.uf_sigla_para_nome("MT") == "Mato Grosso"
    assert ibge_mod.uf_sigla_para_nome("mt") == "Mato Grosso"


def test_sanitizar_minimapa_presente() -> None:
    bruto = {
        "mapa_da_serie": "dinamica",
        "confianca": 0.9,
        "minimapa_presente": True,
        "tabela_presente": False,
        "camadas": [],
    }
    analise, _ = mapear.sanitizar_resposta(bruto)
    assert analise["minimapa_presente"] is True


def test_montar_proposta_liga_minimapa_no_mapspec(tmp_path: Path) -> None:
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    try:
        analise, avisos = mapear.sanitizar_resposta(
            {
                "mapa_da_serie": "dinamica",
                "confianca": 0.95,
                "minimapa_presente": True,
                "camadas": [],
            }
        )
        proposta = mapear.montar_proposta(
            analise=analise, avisos_sanitizacao=avisos, orientacao="retrato"
        )
        assert proposta["mapspec_candidato"] is not None
        assert proposta["mapspec_candidato"]["elementos_layout"].get("minimapa") is True
        mun = proposta["mapspec_candidato"]["imovel"]["municipio"]
        assert mun["nome"] == "Vila Rica"
        if ibge_mod.shapefile_municipios().is_file():
            assert mun.get("ibge", "").startswith("51")
    finally:
        workspace_servico.fechar()


def test_mxd_strings_detecta_elementos_minimapa(tmp_path: Path) -> None:
    # blob mínimo com nomes canônicos (UTF-16-LE como no OLE do ArcMap)
    nomes = ["MINIMAPA", "MINIMAPA_RETANGULO", "MINIMAPA_GUIA", 'nome = \'Vila Rica\'']
    bruto = b"".join(n.encode("utf-16-le") + b"\x00\x00" for n in nomes)
    mxd = tmp_path / "ref.mxd"
    mxd.write_bytes(bruto)
    resultado = mxd_strings.extrair(mxd)
    assert resultado["minimapa_detectado"] is True
    assert "MINIMAPA" in resultado["candidatos_elementos_minimapa"]
    assert "Vila Rica" in (resultado["queries_municipio_uf"].get("municipios") or [])


def test_montar_contexto_minimapa_com_recibo(tmp_path: Path) -> None:
    if not ibge_mod.shapefile_municipios().is_file():
        return
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    guard = WorkspaceGuard(tmp_path)
    mapspec = {
        "imovel": {
            "nome": "Harmonia",
            "municipio": {"nome": "Vila Rica", "uf": "MT"},
            "geometria": "local.ATP",
        }
    }
    ctx = montar_contexto_minimapa(
        mapspec,
        guard=guard,
        fontes_idx={"ATP": "SHP/ATP.shp"},
    )
    assert ctx["municipio"] == "Vila Rica"
    assert ctx["uf_extenso"] == "Mato Grosso"
    assert ctx["extent_minimapa_wgs84"]
    assert Path(ctx["pasta_ibge"]).is_dir()
