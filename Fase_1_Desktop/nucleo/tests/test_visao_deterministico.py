# F1-07 — análise determinística (sem modelo, sem rede): imagem, PDF, .mxd, .zip.

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import fitz
import pytest
from PIL import Image, ImageDraw

from mapasfacil_nucleo.agente.visao import imagem as imagem_mod
from mapasfacil_nucleo.agente.visao import mxd_strings
from mapasfacil_nucleo.agente.visao import pdf as pdf_mod
from mapasfacil_nucleo.agente.visao import zip_inventario
from mapasfacil_nucleo.erros import ErroNucleo


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------- imagem


def test_medir_imagem_retrato_com_moldura_e_cores() -> None:
    img = Image.new("RGB", (630, 891), "white")  # proporção A4 retrato
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width - 1, img.height - 1], outline="black", width=12)
    d.rectangle([100, 100, 300, 300], fill=(0, 150, 0))
    d.rectangle([100, 320, 300, 420], fill=(255, 255, 0))

    medidas = imagem_mod.medir_imagem(_png_bytes(img))
    assert medidas["orientacao"] == "retrato"
    assert medidas["formato_sugerido"] == "A4_retrato"
    assert medidas["moldura_detectada"] is True
    hexs = {c["hex"] for c in medidas["cores_dominantes"]}
    assert "#009600" in hexs or "#009300" in hexs  # verde amostrado
    assert "#FFFF00" in hexs  # amarelo amostrado


def test_medir_imagem_paisagem_sem_moldura() -> None:
    img = Image.new("RGB", (400, 200), "white")
    medidas = imagem_mod.medir_imagem(_png_bytes(img))
    assert medidas["orientacao"] == "paisagem"
    assert medidas["moldura_detectada"] is False
    assert medidas["formato_sugerido"] == "personalizado"


def test_medir_imagem_quadrada() -> None:
    img = Image.new("RGB", (300, 300), "white")
    medidas = imagem_mod.medir_imagem(_png_bytes(img))
    assert medidas["orientacao"] == "quadrado"


def test_medir_imagem_arquivo_corrompido_erro_tipado() -> None:
    with pytest.raises(ErroNucleo) as exc:
        imagem_mod.medir_imagem(b"nao e uma imagem de verdade")
    assert exc.value.codigo == "NU-001"


def test_cores_dominantes_ignora_quase_branco_e_quase_preto() -> None:
    img = Image.new("RGB", (100, 100), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 20, 20], fill=(1, 1, 1))  # quase preto
    d.rectangle([80, 80, 99, 99], fill=(120, 60, 200))  # cor real
    cores = imagem_mod.cores_dominantes(img)
    hexs = {c["hex"] for c in cores}
    assert "#010101" not in hexs
    assert "#FFFFFF" not in hexs
    assert "#783CC8" in hexs


# --------------------------------------------------------------------------- pdf


def _pdf_com_texto(caminho: Path, texto: str | None) -> None:
    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    if texto:
        pagina.insert_text((50, 50), texto, fontsize=14)
    doc.save(caminho)
    doc.close()


def test_analisar_pdf_com_texto(tmp_path: Path) -> None:
    caminho = tmp_path / "mapa.pdf"
    _pdf_com_texto(caminho, "Dinamica 2026 - Fazenda Harmonia - Escala 1:60.000")
    info = pdf_mod.analisar_pdf(caminho)
    assert info["tem_texto"] is True
    assert "Dinamica 2026" in info["texto"]
    assert info["num_paginas"] == 1
    assert info["png_pagina1"][:8] == b"\x89PNG\r\n\x1a\n"


def test_analisar_pdf_sem_texto_ainda_rasteriza(tmp_path: Path) -> None:
    caminho = tmp_path / "escaneado.pdf"
    _pdf_com_texto(caminho, None)
    info = pdf_mod.analisar_pdf(caminho)
    assert info["tem_texto"] is False
    assert len(info["png_pagina1"]) > 0


def test_analisar_pdf_inexistente_erro_tipado(tmp_path: Path) -> None:
    with pytest.raises(ErroNucleo) as exc:
        pdf_mod.analisar_pdf(tmp_path / "nao_existe.pdf")
    assert exc.value.codigo == "NU-001"


def test_analisar_pdf_corrompido_erro_tipado(tmp_path: Path) -> None:
    caminho = tmp_path / "ruim.pdf"
    caminho.write_bytes(b"nao e um pdf")
    with pytest.raises(ErroNucleo) as exc:
        pdf_mod.analisar_pdf(caminho)
    assert exc.value.codigo == "NU-001"


# --------------------------------------------------------------------------- mxd


def _acervo_mxd(repo_root: Path) -> Path:
    return repo_root / "Referencias_IMAP" / "MXD"


def test_mxd_strings_acha_layer_real_do_catalogo_no_acervo(repo_root: Path) -> None:
    """Dinamica_2026.mxd de verdade referencia CAR_ATP (SEMA) — sem inventar nada."""
    acervo = _acervo_mxd(repo_root)
    if not (acervo / "Dinamica_2026.mxd").is_file():
        pytest.skip("acervo Referencias_IMAP/MXD/Dinamica_2026.mxd ausente")
    resultado = mxd_strings.extrair(acervo / "Dinamica_2026.mxd")
    assert resultado["estrutura_completa"] is False
    assert "CAR_ATP" in resultado["candidatos_camada"]
    assert resultado["total_strings_lidas"] > 0
    assert resultado["avisos"]  # honestidade: sempre avisa que não é parsing estrutural


def test_mxd_strings_definition_query_herdada(repo_root: Path) -> None:
    """Achado do plano F1-07: definition queries de análises anteriores sobrevivem no blob."""
    acervo = _acervo_mxd(repo_root)
    if not (acervo / "Dinamica_2026.mxd").is_file():
        pytest.skip("acervo Referencias_IMAP/MXD/Dinamica_2026.mxd ausente")
    resultado = mxd_strings.extrair(acervo / "Dinamica_2026.mxd")
    assert any("nome" in q.lower() for q in resultado["candidatos_definition_query"])


def test_mxd_strings_nunca_devolve_caminho_absoluto_da_maquina_de_origem(tmp_path: Path) -> None:
    """AP-09: `C:\\Users\\...` pode estar no blob — só o nome do arquivo pode sair daqui."""
    caminho = tmp_path / "sintetico.mxd"
    bruto = (
        b"lixo binario \x00\x01"
        + "C:\\Users\\Tecnico\\Documents\\ATP.shp\x00".encode("utf-16-le")
        + b"mais lixo \x02\x03 fim"
    )
    caminho.write_bytes(bruto)
    resultado = mxd_strings.extrair(caminho)
    assert resultado["candidatos_camada"] == ["ATP.shp"]
    for candidato in resultado["candidatos_camada"]:
        assert "Users" not in candidato
        assert "\\" not in candidato


def test_mxd_strings_arquivo_vazio_erro_tipado(tmp_path: Path) -> None:
    caminho = tmp_path / "vazio.mxd"
    caminho.write_bytes(b"")
    with pytest.raises(ErroNucleo) as exc:
        mxd_strings.extrair(caminho)
    assert exc.value.codigo == "NU-001"


def test_mxd_strings_inexistente_erro_tipado(tmp_path: Path) -> None:
    with pytest.raises(ErroNucleo) as exc:
        mxd_strings.extrair(tmp_path / "nao_existe.mxd")
    assert exc.value.codigo == "NU-001"


# --------------------------------------------------------------------------- zip


def test_zip_inventario_agrupa_por_tipo(tmp_path: Path) -> None:
    caminho = tmp_path / "projeto.zip"
    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr("ATP.shp", b"x")
        zf.writestr("ATP.dbf", b"x")
        zf.writestr("ATP.prj", b"x")
        zf.writestr("AVN.shp", b"x")
        zf.writestr("Mapa.mxd", b"x")
        zf.writestr("relatorio.pdf", b"x")
        zf.writestr("leia.txt", b"x")

    inventario = zip_inventario.inventariar(caminho)
    assert inventario["mxds"] == ["Mapa.mxd"]
    assert inventario["pdfs"] == ["relatorio.pdf"]
    assert sorted(inventario["shapefiles_stems"]) == ["ATP", "AVN"]
    assert inventario["outros_total"] == 1
    assert inventario["total_entradas"] == 7


def test_zip_inventario_arquivo_inexistente_erro_tipado(tmp_path: Path) -> None:
    with pytest.raises(ErroNucleo) as exc:
        zip_inventario.inventariar(tmp_path / "nao_existe.zip")
    assert exc.value.codigo == "NU-001"
