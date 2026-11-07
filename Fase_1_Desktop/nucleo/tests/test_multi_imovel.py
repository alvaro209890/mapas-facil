"""Testes do módulo multi_imovel do núcleo.

Testa:
- Identificação de imóvel único (singular compatível);
- Identificação de múltiplos imóveis a partir de ZIP sintético com 2 CARs;
- Helper de geração por imóvel sem tocar motores/gerar.py;
- Geração da planilha XLSX combinada institucional;
- Orquestrador multi-imóvel completo.
"""

from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import shapefile
import pymupdf as fitz
from openpyxl import load_workbook

from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.multi_imovel import (
    Imovel,
    gerar_mapas_por_imovel,
    gerar_multi_imovel,
    gerar_xlsx_combinado,
    identificar_imoveis,
)
from mapasfacil_nucleo.workspace import servico as workspace_servico

PRJ_TEXTO = (
    'PROJCS["SIRGAS_2000_UTM_zone_22S",GEOGCS["GCS_SIRGAS_2000",'
    'DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],'
    'PARAMETER["False_Northing",10000000.0],PARAMETER["Central_Meridian",-51.0],'
    'PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
)


def _criar_recibo_pdf(caminho: Path, nome_imovel: str, car_num: str, area_ha: float = 100.0) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    pagina = doc.new_page()
    linhas = [
        "Cadastro Ambiental Rural",
        "Recibo de Inscrição",
        "Nome do Imóvel:",
        nome_imovel,
        "Município:",
        "Querência",
        "UF:",
        "MT",
        "Nº do Registro no CAR:",
        car_num,
        "Recibo:",
        "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        "Situação:",
        "Ativo",
        "Área do Imóvel:",
        f"{area_ha:.4f}".replace(".", ","),
        "Dados das Áreas dos Imóveis Rurais",
    ]
    y = 40
    for linha in linhas:
        pagina.insert_text((40, y), linha, fontsize=10)
        y += 18
    doc.save(str(caminho))
    doc.close()
    return caminho


def _criar_shapefile_pyshp(destino: Path, nome: str, pontos: list[tuple[float, float]]) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    escritor = shapefile.Writer(str(destino / nome))
    escritor.field("NOME", "C", size=60)
    escritor.field("classe", "C", size=40)
    escritor.field("area_ha", "N", decimal=4)
    escritor.poly([list(pontos) + [pontos[0]]])
    escritor.record(nome, "ATP", 100.0)
    escritor.close()
    (destino / f"{nome}.prj").write_text(PRJ_TEXTO, encoding="utf-8")
    (destino / f"{nome}.cpg").write_text("ISO-8859-1", encoding="utf-8")


def test_identificar_imoveis_imovel_unico(tmp_path: Path) -> None:
    """Workspace padrão com 1 shapefile ATP e 1 recibo CAR."""
    pasta_car = tmp_path / "CAR"
    _criar_shapefile_pyshp(
        pasta_car,
        "ATP",
        [(600000.0, 8300000.0), (600000.0, 8301000.0), (601000.0, 8301000.0), (601000.0, 8300000.0)],
    )
    _criar_recibo_pdf(tmp_path / "CAR - Recibo.pdf", "Fazenda Alfa", "MT102042/2017", 250.5)

    imoveis = identificar_imoveis(tmp_path)
    assert len(imoveis) == 1
    im = imoveis[0]
    assert im["nome"] == "Fazenda Alfa"
    assert im["car"] == "MT102042/2017"
    assert im["area"] == 250.5
    assert im["principal"] is True
    assert "CAR/ATP.shp" in im["atp"].replace("\\", "/")


def test_identificar_imoveis_dois_cars_zip_sintetico(tmp_path: Path) -> None:
    """Import ZIP sintético com dois CARs identifica ambos com id, nome, car, area, atp, principal."""
    pasta_alfa = tmp_path / "CAR_Alfa"
    pasta_beta = tmp_path / "CAR_Beta"
    _criar_shapefile_pyshp(
        pasta_alfa,
        "ATP_Alfa",
        [(600000.0, 8300000.0), (600000.0, 8301000.0), (601000.0, 8301000.0), (601000.0, 8300000.0)],
    )
    _criar_shapefile_pyshp(
        pasta_beta,
        "ATP_Beta",
        [(602000.0, 8300000.0), (602000.0, 8301000.0), (603000.0, 8301000.0), (603000.0, 8300000.0)],
    )
    _criar_recibo_pdf(pasta_alfa / "Recibo_Alfa.pdf", "Fazenda Alfa", "MT102042/2017", 250.5)
    _criar_recibo_pdf(pasta_beta / "Recibo_Beta.pdf", "Fazenda Beta", "MT102043/2017", 180.0)

    # Empacota em um ZIP sintético
    zip_path = tmp_path / "dois_cars.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in pasta_alfa.glob("*.*"):
            zf.write(f, f"CAR_Alfa/{f.name}")
        for f in pasta_beta.glob("*.*"):
            zf.write(f, f"CAR_Beta/{f.name}")

    # Extrai em uma nova pasta para simular o workspace
    workspace_dir = tmp_path / "workspace_multi"
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(workspace_dir)

    imoveis = identificar_imoveis(workspace_dir)
    assert len(imoveis) == 2, f"Esperado 2 imóveis, obtido: {imoveis}"

    cars = {im["car"] for im in imoveis}
    assert "MT102042/2017" in cars
    assert "MT102043/2017" in cars

    nomes = {im["nome"] for im in imoveis}
    assert "Fazenda Alfa" in nomes
    assert "Fazenda Beta" in nomes

    # Exatamente um deve ser principal
    principais = [im for im in imoveis if im.get("principal")]
    assert len(principais) == 1
    assert principais[0]["principal"] is True

    # Todos possuem id único
    ids = [im["id"] for im in imoveis]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_workspace_abrir_com_multi_imoveis(tmp_path: Path) -> None:
    """Testa se workspace_servico.abrir popula 'imoveis' no retorno e no workspace."""
    pasta_alfa = tmp_path / "CAR_1"
    pasta_beta = tmp_path / "CAR_2"
    _criar_shapefile_pyshp(
        pasta_alfa,
        "ATP",
        [(600000.0, 8300000.0), (600000.0, 8301000.0), (601000.0, 8301000.0), (601000.0, 8300000.0)],
    )
    _criar_shapefile_pyshp(
        pasta_beta,
        "LOTE_45",
        [(602000.0, 8300000.0), (602000.0, 8301000.0), (603000.0, 8301000.0), (603000.0, 8300000.0)],
    )
    _criar_recibo_pdf(tmp_path / "recibo_alfa.pdf", "Fazenda Alfa", "MT102042/2017", 250.5)
    _criar_recibo_pdf(tmp_path / "recibo_beta.pdf", "Fazenda Beta", "MT102043/2017", 180.0)

    res = workspace_servico.abrir(str(tmp_path))
    assert "imoveis" in res
    assert len(res["imoveis"]) == 2
    assert "imoveis" in res["workspace"]
    assert len(res["workspace"]["imoveis"]) == 2


def test_gerar_mapas_por_imovel_chama_gerar_mapa(mapspec_canonico: dict, tmp_path: Path) -> None:
    """Helper chama gerar_mapa existente para cada imóvel filtrando camadas."""
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {"id": "imovel_1", "nome": "Fazenda Alfa", "car": "MT-001", "principal": True},
        {"id": "imovel_2", "nome": "Fazenda Beta", "car": "MT-002", "principal": False},
    ]
    spec["camadas"][0]["imovel_id"] = "imovel_1"

    chamadas = []

    def fake_gerar_mapa(spec_im, guard, fontes_idx, **kwargs):
        chamadas.append(spec_im)
        workspace_dir = guard.raiz if hasattr(guard, "raiz") else Path(guard)
        return {
            "pdf": str(workspace_dir / "Mapas" / f"{spec_im['saida']['nome_base']}.pdf"),
            "artefatos": {"pdf": "teste.pdf"},
            "quantitativos": {
                "detalhe": [
                    {"fonte": "local.ATP", "estilo": "atp", "area_ha": 150.0},
                    {"fonte": "local.AVN", "estilo": "vegetacao_nativa", "area_ha": 80.0},
                ]
            },
        }

    with patch("mapasfacil_nucleo.motores.gerar.gerar_mapa", side_effect=fake_gerar_mapa):
        resultados = gerar_mapas_por_imovel(spec, tmp_path)

    assert len(chamadas) == 2
    assert "imovel_1" in resultados
    assert "imovel_2" in resultados

    # Na chamada do imovel_1, a camada com imovel_id=imovel_1 deve estar presente
    spec_chamada_1 = chamadas[0]
    assert spec_chamada_1["imovel"]["nome"] == "Fazenda Alfa"
    assert spec_chamada_1["camadas"][0]["imovel_id"] == "imovel_1"

    # Na chamada do imovel_2, a camada com imovel_id=imovel_1 foi filtrada
    spec_chamada_2 = chamadas[1]
    assert spec_chamada_2["imovel"]["nome"] == "Fazenda Beta"
    assert not any(c.get("imovel_id") == "imovel_1" for c in spec_chamada_2["camadas"])


def test_gerar_xlsx_combinado(tmp_path: Path) -> None:
    """Testa geração de planilha Excel combinando os imóveis."""
    imoveis = [
        {"id": "imovel_1", "nome": "Fazenda Alfa", "car": "MT-001", "matricula": "100", "area": 250.5, "atp": "CAR_1/ATP.shp", "principal": True},
        {"id": "imovel_2", "nome": "Fazenda Beta", "car": "MT-002", "matricula": "200", "area": 180.0, "atp": "CAR_2/ATP.shp", "principal": False},
    ]
    resultados = {
        "imovel_1": {
            "quantitativos": {
                "detalhe": [
                    {"fonte": "local.ATP", "estilo": "atp", "area_ha": 250.5},
                    {"fonte": "local.AVN", "estilo": "vegetacao_nativa", "area_ha": 100.0},
                ]
            }
        },
        "imovel_2": {
            "quantitativos": {
                "detalhe": [
                    {"fonte": "local.ATP", "estilo": "atp", "area_ha": 180.0},
                    {"fonte": "local.AVN", "estilo": "vegetacao_nativa", "area_ha": 80.0},
                ]
            }
        },
    }
    destino = tmp_path / "saida_combinada.xlsx"
    gerar_xlsx_combinado(imoveis, resultados, destino, titulo_projeto="Projeto Teste")

    assert destino.is_file()
    wb = load_workbook(destino)
    nomes_abas = wb.sheetnames
    assert "Resumo Imóveis" in nomes_abas
    assert "Quantitativos Combinados" in nomes_abas
    assert "Q - Fazenda Alfa" in nomes_abas
    assert "Q - Fazenda Beta" in nomes_abas

    ws_resumo = wb["Resumo Imóveis"]
    assert ws_resumo["A2"].value == "ID"
    assert ws_resumo["B3"].value == "Fazenda Alfa"
    assert ws_resumo["B4"].value == "Fazenda Beta"
    assert ws_resumo["A5"].value == "TOTAL"


def test_gerar_multi_imovel_orquestrador(mapspec_canonico: dict, tmp_path: Path) -> None:
    """Testa o fluxo completo do orquestrador gerar_multi_imovel."""
    spec = copy.deepcopy(mapspec_canonico)
    spec["imoveis"] = [
        {"id": "imovel_1", "nome": "Fazenda Alfa", "car": "MT-001", "principal": True},
        {"id": "imovel_2", "nome": "Fazenda Beta", "car": "MT-002", "principal": False},
    ]
    spec["saida"]["pasta"] = "Mapas"
    spec["saida"]["nome_base"] = "dinamica_multi"

    def fake_gerar_mapa(spec_im, guard, fontes_idx, **kwargs):
        workspace_dir = guard.raiz if hasattr(guard, "raiz") else Path(guard)
        pdf_caminho = workspace_dir / "Mapas" / f"{spec_im['saida']['nome_base']}.pdf"
        pdf_caminho.parent.mkdir(parents=True, exist_ok=True)
        # Cria um PDF sintético válido
        doc = fitz.open()
        doc.new_page()
        doc.save(str(pdf_caminho))
        doc.close()
        return {
            "pdf": str(pdf_caminho.relative_to(workspace_dir)),
            "artefatos": {"pdf": str(pdf_caminho.relative_to(workspace_dir))},
            "quantitativos": {"detalhe": []},
        }

    with patch("mapasfacil_nucleo.motores.gerar.gerar_mapa", side_effect=fake_gerar_mapa):
        res = gerar_multi_imovel(spec, tmp_path)

    assert "imoveis" in res
    assert "xlsx_combinado" in res
    assert (tmp_path / res["xlsx_combinado"]).is_file()
