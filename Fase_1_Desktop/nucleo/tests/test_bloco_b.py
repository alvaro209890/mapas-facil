from __future__ import annotations

import copy
import io
import json
import zipfile
from pathlib import Path

import pytest

from mapasfacil_nucleo.camadas.materializar import materializar_camadas_locais
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo.bbox_shp import ler_bbox_header_shp
from mapasfacil_nucleo.motores import arcpy_ponte, patch_mxd
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.motores.manifesto import sha256_arquivo
from mapasfacil_nucleo.workspace.zip_simcar import extrair, listar
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm, montar_workspace_minimo


@pytest.fixture
def projeto(tmp_path: Path) -> Path:
    montar_workspace_minimo(tmp_path)
    return tmp_path


def test_ler_bbox_header_shp(projeto: Path) -> None:
    shp = projeto / "dados" / "ATP.shp"
    bbox = ler_bbox_header_shp(shp)
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]


def test_zip_listar_e_extrair(projeto: Path) -> None:
    zip_path = projeto / "simcar.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("pasta/ATP.shp", b"fake")
        zf.writestr("pasta/ATP.dbf", b"fake")
    zip_path.write_bytes(buf.getvalue())

    info = listar(zip_path)
    assert info["total"] == 2
    assert "pasta/ATP.shp" in info["shapefiles"]

    guard = WorkspaceGuard(projeto)
    resultado = extrair(zip_path, guard=guard)
    assert (projeto / resultado["pasta"] / "pasta" / "ATP.shp").exists()


def test_zip_slip_rejeitado(projeto: Path) -> None:
    zip_path = projeto / "evil.zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../etc/passwd", b"nope")
    zip_path.write_bytes(buf.getvalue())

    guard = WorkspaceGuard(projeto)
    with pytest.raises(ErroNucleo) as exc:
        extrair(zip_path, guard=guard)
    assert exc.value.codigo == "NU-050"


def test_materializar_camadas_canonicas(projeto: Path) -> None:
    guard = WorkspaceGuard(projeto)
    fontes_idx = {
        "ATP": "dados/ATP.shp",
        "AVN": "dados/AVN.shp",
        "AC": "dados/AUAS.shp",
    }
    mapspec = {
        "camadas": [
            {"fonte": "local.ATP", "id": "perimetro"},
            {"fonte": "local.AVN", "id": "avn"},
            {"fonte": "local.AC", "id": "ac"},
        ]
    }
    resultado = materializar_camadas_locais(mapspec, guard=guard, fontes_idx=fontes_idx)
    assert (projeto / "SHP" / "ATP.shp").exists()
    assert (projeto / "SHP" / "AVN.shp").exists()
    assert (projeto / "SHP" / "AREA_CONSOLIDADA.shp").exists()
    assert len(resultado["materializados"]) == 3


def test_patch_float64_e_sentinela() -> None:
    dados = bytearray(16)
    patch_mxd.patch_float64_le(dados, 0, 111111.0)
    assert patch_mxd.validar_offset_sentinela(dados, 0, 111111.0)
    patch_mxd.patch_extent_le(dados, 0, (1.0, 2.0, 3.0, 4.0))
    assert patch_mxd.ler_float64_le(dados, 0) == 1.0


def test_copiar_template_dinamica(repo_root: Path, tmp_path: Path) -> None:
    destino = tmp_path / "saida.mxd"
    copia = patch_mxd.copiar_template("dinamica_retrato", destino)
    assert destino.exists()

    preparado = repo_root / "shared/templates/Dinamica_retrato.mxd"
    origem = preparado if preparado.is_file() else repo_root / "Referencias_IMAP/MXD/Dinamica_2026.mxd"
    assert sha256_arquivo(destino) == sha256_arquivo(origem)
    if preparado.is_file():
        assert copia["sha256_template_ok"] is True


def test_patch_texto_utf16le_slot() -> None:
    dados = bytearray(64)
    aviso = patch_mxd.patch_texto_utf16le_slot(dados, 0, "Dinâmica 2026", slot_caracteres=16)
    assert aviso is None
    lido = dados[0:32].decode("utf-16le").rstrip()
    assert lido == "Dinâmica 2026"
    aviso2 = patch_mxd.patch_texto_utf16le_slot(dados, 0, "x" * 20, slot_caracteres=16)
    assert aviso2 is not None


def test_gerar_mapa_com_mxd_e_pdf(projeto: Path, repo_root: Path) -> None:
    caminho = repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json"
    mapspec = copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8")))
    mapspec["camadas"] = [c for c in mapspec["camadas"] if c["fonte"].startswith("local.")]
    mapspec["saidas"] = ["mxd", "pdf"]
    mapspec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "Dinamica_teste_mxd",
        "materializar_camadas_em": "SHP",
    }

    fontes_idx = {
        "ATP": "dados/ATP.shp",
        "AVN": "dados/AVN.shp",
        "AUAS": "dados/AUAS.shp",
    }
    guard = WorkspaceGuard(projeto)
    resultado = gerar_mapa(mapspec, guard, fontes_idx)
    assert (projeto / resultado["mxd"]).exists()
    assert (projeto / resultado["pdf"]).exists()
    assert (projeto / "SHP" / "ATP.shp").exists()
    patch_info = resultado["artefatos"]["mxd"]
    assert patch_info["motor"] in ("copia_template", "patch", "arcpy")
    assert "validacao" in resultado
    assert (projeto / resultado["validacao"]).exists()
    assert resultado["validacao_dados"]["tier"] in (
        "T1",
        "T2",
        "copia_template",
        "nativo",
        "patch",
        "arcpy",
    )


def test_arcpy_ponte_monta_payload_e_script_existe() -> None:
    payload = arcpy_ponte.montar_payload(
        template=r"C:\templates\Dinamica.mxd",
        tmp_dir=r"C:\temp\mapasfacil",
        pasta_template_shp=r"C:\templates\SHP",
        pasta_saida_shp=r"D:\projeto\SHP",
        bbox_no_crs_do_data_frame=[500000, 8000000, 501000, 8001000],
        escala=60000,
        municipio="Vila Rica",
        uf_extenso="Mato Grosso",
        camadas=[
            {
                "id": "PERIMETRO",
                "nome": "Fazenda Harmonia",
                "dataset": "ATP",
                "aliases": ["CAR_ATP"],
            }
        ],
    )
    assert payload["escala"] == 60000
    assert payload["camadas"][0]["dataset"] == "ATP"
    assert arcpy_ponte.caminho_arcpy_job().exists()


def test_arcpy_ponte_sem_python_levanta_ag001() -> None:
    payload = arcpy_ponte.montar_payload(
        template="t.mxd",
        tmp_dir="/tmp",
        pasta_template_shp="/a",
        pasta_saida_shp="/b",
        bbox_no_crs_do_data_frame=[0, 0, 1, 1],
        escala=1,
        municipio="X",
        uf_extenso="Y",
    )
    with pytest.raises(ErroNucleo) as exc:
        arcpy_ponte.executar(payload, python_exe="/caminho/inexistente/python.exe")
    assert exc.value.codigo == "AG-001"
