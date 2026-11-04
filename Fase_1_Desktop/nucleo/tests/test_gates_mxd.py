"""Testes dos portões de qualidade G1, G2 e G3 e testes de sabotagem (W10-07).

Valida:
1. Aprovação completa (G1, G2, G3) de um documento MXD validamente transformado;
2. Sabotagem de sentinela órfã -> reprovação em G1 com MX-012;
3. Sabotagem de integridade de stream -> reprovação em G1 com MX-013;
4. Sabotagem com inserção de segredo/authkey -> reprovação em G2 com MX-040;
5. Sabotagem com caminho absoluto proibido -> reprovação em G2 com MX-050;
6. Sabotagem com mutação fora dos slots declarados -> reprovação em G3 com MX-013.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mxd_binario import (
    CompoundFile,
    DefinicaoSlot,
    DocumentoMxd,
    ManifestoSlots,
    verificar_g1,
    verificar_g2,
    verificar_g3,
    verificar_todos,
)

_RAIZ = raiz_repositorio()
_PASTA_TEMPLATES = _RAIZ / "shared" / "templates"


@pytest.fixture
def doc_valido_e_manifesto() -> tuple[bytes, bytes, ManifestoSlots, dict[str, Any]]:
    """Gera um par (template_bytes, gerado_bytes, manifesto, valores) válido."""
    mxd_origem = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    if not mxd_origem.exists():
        pytest.skip(f"Template {mxd_origem} não encontrado")

    template_bytes = mxd_origem.read_bytes()
    doc = DocumentoMxd.abrir(mxd_origem)

    manifesto = ManifestoSlots(
        template_id="dinamica_retrato",
        streams=["Mx Document", "PageLayout", "Maps"],
        slots=[
            DefinicaoSlot(
                id="nome_imovel",
                tipo="texto",
                sentinela="Fazenda Harmonia",
                streams=["PageLayout", "Mx Document"],
            ),
            DefinicaoSlot(
                id="escala",
                tipo="numero",
                sentinela=987654.0,
                streams=["Mx Document"],
            ),
        ],
    )

    valores = {"nome_imovel": "Faz. Alvorada", "escala": 50000.0}  # cabe nas 16 letras
    doc.aplicar(valores, manifesto=manifesto)
    gerado_bytes = doc.obter_bytes()

    return template_bytes, gerado_bytes, manifesto, valores


def test_gates_aprovacao_documento_valido(doc_valido_e_manifesto: tuple) -> None:
    """Valida aprovação integral de G1, G2 e G3 para documento válido."""
    template_bytes, gerado_bytes, manifesto, valores = doc_valido_e_manifesto

    resultados = verificar_todos(template_bytes, gerado_bytes, manifesto, valores)
    assert len(resultados) == 3
    assert all(r.ok for r in resultados), f"Falhas nos gates: {[r.mensagem for r in resultados if not r.ok]}"
    assert [r.gate for r in resultados] == ["G1", "G2", "G3"]


def test_sabotagem_sentinela_orfa_g1(doc_valido_e_manifesto: tuple) -> None:
    """Sabotagem: insere sentinela órfã «MF:imovel» -> reprova no G1 com MX-012."""
    _, gerado_bytes, manifesto, _ = doc_valido_e_manifesto
    cf = CompoundFile.de_bytes(gerado_bytes)

    # Injeta sentinela não substituída em PageLayout
    pl_mod = cf.obter_stream("PageLayout") + "«MF:imovel_orfa»".encode("utf-16le")
    cf.substituir("PageLayout", pl_mod)
    bytes_sabotados = CompoundFile.de_bytes(gerado_bytes)
    bytes_sabotados.substituir("PageLayout", pl_mod)

    # Salva em bytes
    import io
    buf = io.BytesIO()
    bytes_sabotados.salvar(buf)

    r = verificar_g1(buf.getvalue(), manifesto.streams)
    assert r.ok is False
    assert r.codigo_erro == "MX-012"
    assert "Sentinela órfã encontrada" in r.mensagem


def test_sabotagem_integridade_stream_g1(doc_valido_e_manifesto: tuple) -> None:
    """Sabotagem: corrompe estrutura CFBF -> reprova no G1 com MX-013."""
    _, gerado_bytes, manifesto, _ = doc_valido_e_manifesto

    # Corrompe os primeiros 512 bytes destruindo o cabeçalho
    corrompido = bytearray(gerado_bytes)
    corrompido[0:16] = b"\x00" * 16

    r = verificar_g1(bytes(corrompido), manifesto.streams)
    assert r.ok is False
    assert r.codigo_erro == "MX-013"


def test_sabotagem_segredo_authkey_g2(doc_valido_e_manifesto: tuple) -> None:
    """Sabotagem: insere authkey em stream -> reprova no G2 com MX-040."""
    _, gerado_bytes, manifesto, valores = doc_valido_e_manifesto
    cf = CompoundFile.de_bytes(gerado_bytes)

    # Injeta segredo simulado
    pl_segredo = cf.obter_stream("PageLayout") + b"http://wms.sema.mt.gov.br?authkey=abcdef123456"
    cf.substituir("PageLayout", pl_segredo)

    import io
    buf = io.BytesIO()
    cf.salvar(buf)

    r = verificar_g2(buf.getvalue(), manifesto, valores)
    assert r.ok is False
    assert r.codigo_erro == "MX-040"
    assert "segredo ou authkey detectado" in r.mensagem


def test_sabotagem_caminho_absoluto_g2(doc_valido_e_manifesto: tuple) -> None:
    """Sabotagem: insere caminho absoluto proibido C:\\ -> reprova no G2 com MX-050."""
    _, gerado_bytes, manifesto, valores = doc_valido_e_manifesto
    cf = CompoundFile.de_bytes(gerado_bytes)

    # Injeta caminho absoluto do Windows em Maps
    maps_abs = cf.obter_stream("Maps") + "C:\\GIS\\dados\\ATP.shp".encode("utf-16le")
    cf.substituir("Maps", maps_abs)

    import io
    buf = io.BytesIO()
    cf.salvar(buf)

    r = verificar_g2(buf.getvalue(), manifesto, valores, pasta_pacote=Path("pacote"))
    assert r.ok is False
    assert r.codigo_erro == "MX-050"
    assert "Caminho absoluto de dado detectado" in r.mensagem


def test_sabotagem_mutacao_fora_de_slot_g3(doc_valido_e_manifesto: tuple) -> None:
    """Sabotagem: altera bytes de stream não declarada no manifesto -> reprova no G3 com MX-013."""
    template_bytes, gerado_bytes, manifesto, valores = doc_valido_e_manifesto

    # Cria manifesto com escopo restrito apenas a PageLayout
    manifesto_restrito = ManifestoSlots(
        template_id="dinamica_retrato",
        streams=["PageLayout"],  # Maps e Mx Document NÃO estão autorizados a mudar
        slots=[
            DefinicaoSlot(
                id="nome_imovel",
                tipo="texto",
                sentinela="Fazenda Harmonia",
                streams=["PageLayout"],
            )
        ],
    )

    # gerado_bytes teve modificação em Mx Document (a escala), o que viola o manifesto_restrito
    r = verificar_g3(template_bytes, gerado_bytes, manifesto_restrito, valores)
    assert r.ok is False
    assert r.codigo_erro == "MX-013"
    assert "Stream não declarada" in r.mensagem or "divergiu" in r.mensagem
