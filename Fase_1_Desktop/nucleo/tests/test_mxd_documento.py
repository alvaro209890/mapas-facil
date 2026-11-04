"""Testes da camada de slots e documento MXD binário (W10-06).

Valida:
1. Carregamento e serialização de ManifestoSlots (.slots.json);
2. Aplicação de slots de texto, número, envelope e consulta;
3. Ciclo DocumentoMxd.abrir -> aplicar -> obter_bytes -> salvar;
4. Conformidade contra template real do corpus (substituição de textos e escala).
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

import olefile
import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mxd_binario import (
    CompoundFile,
    DefinicaoSlot,
    DocumentoMxd,
    ErroSlot,
    ManifestoSlots,
)

_RAIZ = raiz_repositorio()
_PASTA_TEMPLATES = _RAIZ / "shared" / "templates"


def test_manifesto_slots_serializacao_roundtrip() -> None:
    """Valida serialização e desserialização de ManifestoSlots."""
    manifesto = ManifestoSlots(
        template_id="dinamica_retrato",
        variante={"formato": "A4", "orientacao": "retrato"},
        arquivo_sha256="abc123hash",
        slots=[
            DefinicaoSlot(id="titulo", tipo="texto", obrigatorio=True, origem="mapspec.titulo"),
            DefinicaoSlot(
                id="escala",
                tipo="numero",
                obrigatorio=True,
                origem="enquadramento.escala",
                sentinela=987654.0,
            ),
            DefinicaoSlot(
                id="df_principal",
                tipo="envelope",
                obrigatorio=False,
                origem="enquadramento.extent",
                sentinela=[100.0, 200.0, 300.0, 400.0],
            ),
        ],
    )

    d = manifesto.para_dict()
    assert d["template_id"] == "dinamica_retrato"
    assert len(d["slots"]) == 3

    m2 = ManifestoSlots.de_dict(d)
    assert m2.template_id == manifesto.template_id
    assert m2.variante == manifesto.variante
    assert len(m2.slots) == 3
    assert m2.slots[1].sentinela == 987654.0


def test_documento_mxd_sintetico_aplicacao_slots(tmp_path: Path) -> None:
    """Valida substituição de slots de texto e número em um documento CFBF."""
    mxd_base = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    if not mxd_base.exists():
        pytest.skip("Template base não encontrado")

    doc = DocumentoMxd.abrir(mxd_base)
    sentinela_txt = "Fazenda Harmonia"
    sentinela_num = 987654.0

    manifesto = ManifestoSlots(
        template_id="teste_sintetico",
        slots=[
            DefinicaoSlot(id="titulo", tipo="texto", sentinela=sentinela_txt, streams=["PageLayout", "Mx Document"]),
            DefinicaoSlot(id="escala", tipo="numero", sentinela=sentinela_num, streams=["Maps", "Mx Document"]),
        ],
    )

    novo_titulo = "Faz. Vista Alegre"[:16]
    nova_escala = 50000.0

    doc.aplicar({"titulo": novo_titulo, "escala": nova_escala}, manifesto=manifesto)

    # Verifica os bytes gerados
    bytes_gerados = doc.obter_bytes()
    assert len(bytes_gerados) > 0

    # Valida com olefile independente
    ole = olefile.OleFileIO(io.BytesIO(bytes_gerados))
    assert ole.exists("PageLayout")
    assert ole.exists("Maps")

    pl_lido = ole.openstream("PageLayout").read()
    mx_lido = ole.openstream("Mx Document").read()

    # O novo título deve estar presente em UTF-16LE — e a stream não muda de tamanho
    assert novo_titulo.encode("utf-16le") in pl_lido
    original = olefile.OleFileIO(str(mxd_base))
    assert len(pl_lido) == len(original.openstream("PageLayout").read())
    # A sentinela antiga não deve mais estar presente
    assert sentinela_txt.encode("utf-16le") not in pl_lido

    # A nova escala deve estar gravada
    assert struct.pack("<d", nova_escala) in mx_lido
    assert struct.pack("<d", sentinela_num) not in mx_lido


def test_documento_mxd_slot_obrigatorio_ausente_dispara_erro() -> None:
    """Valida que slot obrigatório ausente levanta ErroSlot."""
    mxd_base = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    if not mxd_base.exists():
        pytest.skip("Template base não encontrado")
    doc = DocumentoMxd.abrir(mxd_base)

    manifesto = ManifestoSlots(
        template_id="teste",
        slots=[DefinicaoSlot(id="campo_critico", tipo="texto", obrigatorio=True)],
    )

    with pytest.raises(ErroSlot, match="Slot obrigatório não fornecido"):
        doc.aplicar({}, manifesto=manifesto)


def test_documento_mxd_template_real_edicao_e_salvamento(tmp_path: Path) -> None:
    """Valida abertura de template real, aplicação de substituições e reabertura via olefile."""
    mxd_origem = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    if not mxd_origem.exists():
        pytest.skip(f"Template {mxd_origem} não encontrado")

    doc = DocumentoMxd.abrir(mxd_origem)

    # Define substituição para um texto auditado do template
    texto_original = "Fazenda Harmonia"
    texto_novo = "Faz. Esperança"  # cabe nas 16 letras da sentinela

    manifesto = ManifestoSlots(
        template_id="dinamica_retrato",
        slots=[
            DefinicaoSlot(
                id="nome_imovel",
                tipo="texto",
                sentinela=texto_original,
                streams=["PageLayout", "Mx Document"],
            ),
            DefinicaoSlot(
                id="escala",
                tipo="numero",
                sentinela=987654.0,  # Escala auditada no data frame principal deste template
                streams=["Maps", "Mx Document"],
            ),
        ],
    )

    doc.aplicar({"nome_imovel": texto_novo, "escala": 50000.0}, manifesto=manifesto)

    mxd_saida = tmp_path / "Dinamica_gerado.mxd"
    doc.salvar(mxd_saida)
    assert mxd_saida.exists()

    # Valida com olefile
    ole = olefile.OleFileIO(str(mxd_saida))
    pl_lido = ole.openstream("PageLayout").read()
    mx_lido = ole.openstream("Mx Document").read()

    assert texto_novo.encode("utf-16le") in pl_lido
    assert struct.pack("<d", 50000.0) in mx_lido


# — troca de texto do mesmo tamanho (teste_22, 04/11/2026) —
# Mudar o comprimento de uma string UTF-16 dentro do PageLayout corrompia o layout: o
# ArcMap abria o .mxd do teste_22 com `pageLayout` vazio. Agora o texto é completado com
# espaços até o tamanho da sentinela; maior que ela não entra.


def _stream_com(texto: str) -> bytearray:
    corpo = texto.encode("utf-16le")
    return bytearray(b"\x01\x02" + struct.pack("<I", len(texto) + 1) + corpo + b"\x00\x00\xff")


def test_texto_menor_e_completado_com_espacos() -> None:
    from mapasfacil_nucleo.mxd_binario.slots import aplicar_slot_texto

    st = _stream_com("Fazenda Harmonia")
    tamanho = len(st)
    assert aplicar_slot_texto(st, "Fazenda Harmonia", "Faz. Sol") == 1
    assert len(st) == tamanho
    assert "    Faz. Sol    ".encode("utf-16le") in st


def test_texto_maior_que_a_sentinela_e_recusado() -> None:
    from mapasfacil_nucleo.mxd_binario.slots import ErroSlot, aplicar_slot_texto

    st = _stream_com("Vila Rica")
    with pytest.raises(ErroSlot):
        aplicar_slot_texto(st, "Vila Rica", "Santa Cruz do Xingu")


def test_texto_em_consulta_completa_depois_da_aspa() -> None:
    from mapasfacil_nucleo.mxd_binario.slots import aplicar_slot_texto

    st = _stream_com("\"nome\" = 'Vila Rica'")
    tamanho = len(st)
    aplicar_slot_texto(st, "Vila Rica", "Canarana")
    assert len(st) == tamanho
    assert "\"nome\" = 'Canarana' ".encode("utf-16le") in st


def test_caber_nas_sentinelas_rotulo_em_branco_municipio_bloqueia() -> None:
    from mapasfacil_nucleo.motores.patch_mxd import _caber_nas_sentinelas

    manifesto = ManifestoSlots(
        template_id="t",
        slots=[
            DefinicaoSlot(id="rotulo_imovel", tipo="texto", sentinela="Fazenda Harmonia", streams=["PageLayout"]),
            DefinicaoSlot(id="municipio", tipo="texto", sentinela="Vila Rica", streams=["PageLayout"]),
        ],
    )
    valores, avisos, bloqueio = _caber_nas_sentinelas(
        {"rotulo_imovel": "Fazenda Esperança do Norte", "municipio": "Querência"}, manifesto
    )
    assert valores["rotulo_imovel"] == "" and valores["municipio"] == "Querência"
    assert len(avisos) == 1 and "MX-050" in avisos[0]
    assert bloqueio is None

    _, _, bloqueio = _caber_nas_sentinelas({"municipio": "Santa Cruz do Xingu"}, manifesto)
    assert bloqueio and "MX-050" in bloqueio


def test_mesma_sentinela_no_rotulo_e_na_consulta() -> None:
    """Rótulo e consulta do minimapa usam 'Vila Rica': cada ocorrência no seu jeito."""
    from mapasfacil_nucleo.mxd_binario.slots import aplicar_slot_texto

    st = _stream_com("Vila Rica") + _stream_com("\"nome\" = 'Vila Rica'")
    tamanho = len(st)
    assert aplicar_slot_texto(st, "Vila Rica", "Canarana") == 2
    assert len(st) == tamanho
    assert "Canarana ".encode("utf-16le") in st
    assert "'Canarana' ".encode("utf-16le") in st
    assert "Vila Rica".encode("utf-16le") not in st
