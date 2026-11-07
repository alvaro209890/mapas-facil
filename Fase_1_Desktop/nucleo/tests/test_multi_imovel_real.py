"""Testes E2E reais de multi-imóvel sem mocks do gerador.

Utiliza a fixture sintética reutilizável de dois CARs (gerar_zip_dois_imoveis)
para exercitar o fluxo real de:
1. Identificação inequívoca de múltiplos imóveis sem contaminação de CAR ou área;
2. Montagem e propagação de MapSpec com lista de imóveis;
3. Renderização real de PDFs sem dependência de MXD/ArcMap;
4. Consolidação imutável de PDFs individuais em um único documento multi-página;
5. Geração de planilha combinada Excel (.xlsx);
6. Retorno plano compatível com o contrato de versões e pacote de entrega.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pymupdf as fitz
import pytest
from openpyxl import load_workbook

# Garante acesso à fixture sintética reutilizável de Fase_3_Web/fixtures
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "Fase_3_Web" / "fixtures"
if str(FIXTURES_DIR) not in sys.path:
    sys.path.insert(0, str(FIXTURES_DIR))

from gerar_zip_dois_imoveis import gerar_zip_dois_imoveis
from mapasfacil_nucleo.multi_imovel import (
    gerar_mapas_por_imovel,
    gerar_multi_imovel,
    gerar_xlsx_combinado,
    identificar_imoveis,
)
from mapasfacil_nucleo.workspace import indice as indice_mod
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace import servico as servico_mod


def test_identificacao_real_dois_imoveis_sem_contaminacao(tmp_path: Path) -> None:
    """Valida se 2 imóveis em pastas separadas mantêm seus próprios atributos sem mistura arbitrária."""
    zip_dest = tmp_path / "dois_imoveis.zip"
    gerar_zip_dois_imoveis(zip_dest)

    workspace_dir = tmp_path / "workspace_e2e"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_dest, "r") as zf:
        zf.extractall(workspace_dir)

    imoveis = identificar_imoveis(workspace_dir)
    assert len(imoveis) == 2, f"Esperado 2 imóveis, obtido: {imoveis}"

    por_nome = {im["nome"]: im for im in imoveis}
    assert "Fazenda Alfa" in por_nome
    assert "Fazenda Beta" in por_nome

    alfa = por_nome["Fazenda Alfa"]
    beta = por_nome["Fazenda Beta"]

    # CARs não podem ser trocados ou repetidos
    assert alfa["car"] == "MT1000001/2026"
    assert beta["car"] == "MT1000002/2026"

    # Áreas preservadas sem atribuição do principal ao secundário
    assert pytest.approx(alfa["area"], rel=1e-2) == 100.0
    assert pytest.approx(beta["area"], rel=1e-2) == 64.0

    # Apenas um principal
    assert sum(1 for im in imoveis if im.get("principal")) == 1


def test_e2e_renderizacao_real_sem_mxd_e_consolidacao(tmp_path: Path, mapspec_canonico: dict) -> None:
    """Exercita renderização real sem MXD: gera 2 PDFs individuais, PDF consolidado e XLSX combinado."""
    zip_dest = tmp_path / "dois_imoveis.zip"
    gerar_zip_dois_imoveis(zip_dest)

    workspace_dir = tmp_path / "workspace_render"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_dest, "r") as zf:
        zf.extractall(workspace_dir)

    guard = WorkspaceGuard(workspace_dir)
    try:
        estado_ws = servico_mod.abrir(str(workspace_dir))

        imoveis = estado_ws.get("imoveis", [])
        assert len(imoveis) == 2

        # Monta MapSpec com dados dos dois imóveis
        import copy

        spec = copy.deepcopy(mapspec_canonico)
        # Esta prova é PDF-first: o canônico histórico pedia MXD explicitamente.
        spec["saidas"] = ["pdf", "png", "xlsx"]
        spec["escala"] = "auto"
        spec["metadados"] = [
            {"rotulo": "Satélite/Sensor", "valor": "Sem imagem - teste sintético"},
            {"rotulo": "Fonte", "valor": "Fixture de dois CARs fictícios"},
        ]
        spec["imoveis"] = imoveis
        spec["saida"]["pasta"] = "Mapas"
        spec["saida"]["nome_base"] = "mapa_e2e"

        # Associa camadas dos shapefiles encontrados aos imóveis correspondentes
        shp_alfa = None
        shp_beta = None
        for shp in estado_ws["workspace"].get("shapefiles", []):
            if "CAR_Alfa" in shp["caminho"]:
                shp_alfa = shp["id_local"]
            elif "CAR_Beta" in shp["caminho"]:
                shp_beta = shp["id_local"]

        spec["camadas"] = [
            {
                "id": "camada_atp_alfa",
                "nome_no_mxd": "Fazenda Alfa",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
                "imovel_id": imoveis[0]["id"],
            },
            {
                "id": "camada_atp_beta",
                "nome_no_mxd": "Fazenda Beta",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 20,
                "imovel_id": imoveis[1]["id"],
            },
        ]

        # Executa pela mesma superfície de progresso do chat público, não só CLI.
        from mapasfacil_nucleo.progresso import RastreadorProgresso
        eventos = []
        progresso = RastreadorProgresso(lambda nome, dados: eventos.append((nome, dados)), job_id='qa-multi-real')
        res = gerar_multi_imovel(spec, guard, progresso=progresso)
        percentuais = [d['pct'] for e, d in eventos if e == 'job.progresso']
        assert percentuais == sorted(percentuais)
        assert percentuais[-1] == 100
        assert len({d.get('imovel_id') for e, d in eventos if e == 'job.progresso' and d.get('imovel_id')}) == 2

        assert res["status"] == "concluido"
        assert "pdf" in res
        assert "xlsx" in res
        assert "artefatos" in res
        assert "imoveis" in res
        assert len(res["imoveis"]) == 2
        # Os dois ATP.shp precisam continuar distintos no pacote/versionamento.
        import shapefile
        for im in imoveis:
            shp_saida = workspace_dir / 'Mapas/SHP' / im['id'] / 'ATP.shp'
            assert shp_saida.is_file(), shp_saida
            with shapefile.Reader(str(shp_saida)) as leitor:
                assert round(leitor.bbox[0]) == (600000 if 'alfa' in im['id'] else 602000)

        # 1. Verifica PDF Consolidado
        pdf_cons_rel = res["pdf"]
        pdf_cons_abs = guard.resolver(pdf_cons_rel)
        assert pdf_cons_abs.is_file(), f"PDF consolidado não encontrado em {pdf_cons_abs}"
        assert pdf_cons_abs.stat().st_size > 0

        doc_cons = fitz.open(str(pdf_cons_abs))
        # Deve conter as páginas de ambos os imóveis
        assert len(doc_cons) >= 2, f"Esperado pelo menos 2 páginas no consolidado, obtido {len(doc_cons)}"
        doc_cons.close()

        # 2. Verifica PDFs individuais
        for im_id in res["imoveis"]:
            res_im = res["imoveis"][im_id]
            p_rel = res_im.get("pdf") or (res_im.get("artefatos") or {}).get("pdf")
            assert p_rel, f"Imóvel {im_id} sem PDF registrado"
            p_abs = guard.resolver(p_rel)
            assert p_abs.is_file(), f"PDF individual {p_abs} não existe"
            with fitz.open(str(p_abs)) as d_ind:
                assert len(d_ind) >= 1

        # 3. Verifica XLSX combinado
        xlsx_rel = res["xlsx"]
        xlsx_abs = guard.resolver(xlsx_rel)
        assert xlsx_abs.is_file(), f"XLSX combinado não encontrado em {xlsx_abs}"
        wb = load_workbook(str(xlsx_abs))
        nomes_abas = wb.sheetnames
        assert "Resumo Imóveis" in nomes_abas
        assert "Quantitativos Combinados" in nomes_abas

        ws_resumo = wb["Resumo Imóveis"]
        # Confere que ambos os imóveis constam no resumo
        valores_resumo = [str(ws_resumo.cell(row=r, column=2).value) for r in range(3, 5)]
        assert "Fazenda Alfa" in valores_resumo
        assert "Fazenda Beta" in valores_resumo
        assert not list(workspace_dir.rglob("*.mxd")), "PDF-first não deve gerar nenhum MXD"
    finally:
        servico_mod.fechar()
