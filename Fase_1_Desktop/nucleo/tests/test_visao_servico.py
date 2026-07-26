# F1-07 — orquestrador `analisar_referencia`: despacha por extensão, nunca
# derruba o processo quando o modelo de visão falha (degrade honesto).

from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

from mapasfacil_nucleo.agente.visao import servico as visao_servico
from mapasfacil_nucleo.agente.visao.provedor import ProvedorVisaoFalha, ProvedorVisaoFixo
from mapasfacil_nucleo.erros import ErroNucleo, CaminhoNaoAutorizado
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_recibo_car_pdf, escrever_shapefile_quadrado_utm

RESPOSTA_ALTA_CONFIANCA = json.dumps(
    {
        "mapa_da_serie": "dinamica",
        "ano": 2026,
        "template_sugerido": "dinamica_retrato",
        "confianca": 0.9,
        "camadas": [
            {
                "legenda_lida": "Fazenda Harmonia",
                "cor_amostrada": "#FFFF00",
                "estilo_sugerido": "perimetro_imovel",
                "confianca": 0.95,
            }
        ],
        "metadados_lidos": [],
        "tabela_presente": True,
        "observacoes": [],
    }
)


@pytest.fixture(autouse=True)
def _sem_provedor_pendurado():
    yield
    visao_servico.configurar_provedor(None)


@pytest.fixture
def pasta_harmonia(tmp_path: Path):
    shp = tmp_path / "SHP"
    escrever_shapefile_quadrado_utm(shp / "ATP.shp", nome="Harmonia", lado_m=6000)
    escrever_shapefile_quadrado_utm(shp / "AVN.shp", nome="AVN", lado_m=1200)
    escrever_shapefile_quadrado_utm(shp / "AC.shp", nome="AC", lado_m=800)
    escrever_shapefile_quadrado_utm(shp / "AUAS.shp", nome="AUAS", lado_m=700)
    escrever_recibo_car_pdf(tmp_path / "recibo_car.pdf")
    workspace_servico.abrir(str(tmp_path))
    yield tmp_path
    workspace_servico.fechar()


@pytest.fixture
def guard(pasta_harmonia: Path) -> WorkspaceGuard:
    return WorkspaceGuard(pasta_harmonia)


def _png_bytes() -> bytes:
    img = Image.new("RGB", (630, 891), "white")
    ImageDraw.Draw(img).rectangle([0, 0, img.width - 1, img.height - 1], outline="black", width=10)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_imagem_com_provedor_alta_confianca_gera_mapspec(
    pasta_harmonia: Path, guard: WorkspaceGuard
) -> None:
    (pasta_harmonia / "referencia.png").write_bytes(_png_bytes())
    visao_servico.configurar_provedor(ProvedorVisaoFixo(RESPOSTA_ALTA_CONFIANCA))

    resultado = visao_servico.analisar_referencia("referencia.png", guard=guard)
    assert resultado["fonte"] == "imagem"
    assert resultado["mapspec_candidato"] is not None
    assert resultado["modelo_galeria_usado"] == "dinamica_2026_retrato"
    assert "medidas_deterministicas" in resultado


def test_pdf_extrai_texto_e_analisa_pagina1(pasta_harmonia: Path, guard: WorkspaceGuard) -> None:
    caminho = pasta_harmonia / "referencia.pdf"
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_text((50, 50), "Dinamica 2026 - Fazenda Harmonia - Escala 1:60.000")
    doc.save(caminho)
    doc.close()
    visao_servico.configurar_provedor(ProvedorVisaoFixo(RESPOSTA_ALTA_CONFIANCA))

    resultado = visao_servico.analisar_referencia("referencia.pdf", guard=guard)
    assert resultado["fonte"] == "pdf"
    assert resultado["tem_texto_pdf"] is True
    assert "Dinamica 2026" in resultado["texto_extraido"]
    assert resultado["mapspec_candidato"] is not None


def test_mxd_nao_chama_modelo_de_visao(pasta_harmonia: Path, guard: WorkspaceGuard) -> None:
    """Caminho 2 é puro determinismo — nenhuma chamada de rede precisa existir."""
    repo_root = Path(__file__).resolve().parents[3]
    origem = repo_root / "Referencias_IMAP" / "MXD" / "Dinamica_2026.mxd"
    if not origem.is_file():
        pytest.skip("acervo Referencias_IMAP/MXD ausente")
    shutil.copy(origem, pasta_harmonia / "referencia.mxd")
    visao_servico.configurar_provedor(ProvedorVisaoFalha())  # se chamar, o teste falha

    resultado = visao_servico.analisar_referencia("referencia.mxd", guard=guard)
    assert resultado["fonte"] == "mxd_strings"
    assert resultado["estrutura_completa"] is False
    assert resultado["mapspec_candidato"] is None
    assert resultado["proximos_passos"]


def test_zip_com_mxd_segue_caminho_2(pasta_harmonia: Path, guard: WorkspaceGuard) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    origem = repo_root / "Referencias_IMAP" / "MXD" / "Dinamica_2026.mxd"
    if not origem.is_file():
        pytest.skip("acervo Referencias_IMAP/MXD ausente")
    caminho_zip = pasta_harmonia / "projeto.zip"
    with zipfile.ZipFile(caminho_zip, "w") as zf:
        zf.write(origem, "Mapa.mxd")

    resultado = visao_servico.analisar_referencia("projeto.zip", guard=guard)
    assert resultado["fonte"] == "zip_mxd"
    assert resultado["inventario"]["mxds"] == ["Mapa.mxd"]
    assert "candidatos_camada" in resultado


def test_zip_com_pdf_unico_segue_caminho_1(pasta_harmonia: Path, guard: WorkspaceGuard) -> None:
    pdf_tmp = pasta_harmonia / "_fonte.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(pdf_tmp)
    doc.close()
    caminho_zip = pasta_harmonia / "projeto.zip"
    with zipfile.ZipFile(caminho_zip, "w") as zf:
        zf.write(pdf_tmp, "relatorio.pdf")
    visao_servico.configurar_provedor(ProvedorVisaoFixo(RESPOSTA_ALTA_CONFIANCA))

    resultado = visao_servico.analisar_referencia("projeto.zip", guard=guard)
    assert resultado["fonte"] == "zip_pdf"
    assert resultado["inventario"]["pdfs"] == ["relatorio.pdf"]


def test_zip_so_shapefiles_devolve_inventario_e_proximos_passos(
    pasta_harmonia: Path, guard: WorkspaceGuard
) -> None:
    caminho_zip = pasta_harmonia / "so_shapes.zip"
    with zipfile.ZipFile(caminho_zip, "w") as zf:
        zf.writestr("AVN.shp", b"x")
        zf.writestr("AVN.dbf", b"x")

    resultado = visao_servico.analisar_referencia("so_shapes.zip", guard=guard)
    assert resultado["fonte"] == "zip"
    assert resultado["inventario"]["shapefiles_stems"] == ["AVN"]
    assert resultado["mapspec_candidato"] is None
    assert any("AVN" in p for p in resultado["proximos_passos"])


def test_arquivo_inexistente_e_nu001(guard: WorkspaceGuard) -> None:
    with pytest.raises(ErroNucleo) as exc:
        visao_servico.analisar_referencia("nao_existe.png", guard=guard)
    assert exc.value.codigo == "NU-001"


def test_arquivo_fora_do_workspace_e_recusado(guard: WorkspaceGuard) -> None:
    with pytest.raises(CaminhoNaoAutorizado):
        visao_servico.analisar_referencia("/etc/passwd", guard=guard)


def test_extensao_nao_suportada_e_nu001(pasta_harmonia: Path, guard: WorkspaceGuard) -> None:
    (pasta_harmonia / "referencia.docx").write_bytes(b"x")
    with pytest.raises(ErroNucleo) as exc:
        visao_servico.analisar_referencia("referencia.docx", guard=guard)
    assert exc.value.codigo == "NU-001"


def test_sem_chave_degrada_sem_derrubar_o_processo(
    pasta_harmonia: Path, guard: WorkspaceGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    (pasta_harmonia / "referencia.png").write_bytes(_png_bytes())
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(visao_servico, "ler_chave_deepseek", lambda **_kw: None)

    resultado = visao_servico.analisar_referencia("referencia.png", guard=guard)
    assert resultado["fonte"] == "imagem"
    assert resultado["mapspec_candidato"] is None
    assert any("chave" in a.lower() for a in resultado["avisos"])
    assert resultado["medidas_deterministicas"]["orientacao"] == "retrato"  # segue honesto


def test_provedor_falha_nao_derruba_devolve_deterministico(
    pasta_harmonia: Path, guard: WorkspaceGuard
) -> None:
    (pasta_harmonia / "referencia.png").write_bytes(_png_bytes())
    visao_servico.configurar_provedor(ProvedorVisaoFalha())

    resultado = visao_servico.analisar_referencia("referencia.png", guard=guard)
    assert resultado["mapspec_candidato"] is None
    assert any("IA-060" in a for a in resultado["avisos"])
    assert resultado["medidas_deterministicas"]["moldura_detectada"] is True
