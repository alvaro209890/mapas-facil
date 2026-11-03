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

    novo_titulo = "Fazenda Vista Alegre"
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

    # O novo título deve estar presente em UTF-16LE
    assert novo_titulo.encode("utf-16le") in pl_lido
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
    texto_novo = "Fazenda Esperança do Norte"

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
