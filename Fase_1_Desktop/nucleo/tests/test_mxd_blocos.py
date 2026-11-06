"""Testes da árvore de blocos e extração ArcObjects (W10-03).

Valida:
1. Construção de árvore de blocos aninhados e recálculo de tamanhos por delta;
2. Extração de strings UTF-16LE com uint32;
3. Travessia de PageLayout, Maps e Mx Document em todos os templates de shared/templates/;
4. Conformidade das camadas e textos extraídos contra a auditoria do ArcPy (output/mxd_auditoria_templates/).
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mxd_binario import (
    ArvoreBlocos,
    Bloco,
    CompoundFile,
    extrair_strings_utf16,
    inspecionar_camadas_maps,
    inspecionar_dataframes_maps,
    inspecionar_textos_layout,
)

_RAIZ = raiz_repositorio()
_PASTA_TEMPLATES = _RAIZ / "shared" / "templates"
_PASTA_AUDITORIA = _RAIZ / "output" / "mxd_auditoria_templates"

_TEMPLATES_MXD = sorted(_PASTA_TEMPLATES.glob("*.mxd"))


# ------------------------------------------------------------------ 1. Testes sintéticos


def test_arvore_blocos_sintetica_aninhamento_e_delta() -> None:
    """Valida árvore de blocos com pai e filho aninhado e recálculo de uint64."""
    # Bloco pai: marcador + 8B (tam=50) + payload de 50 bytes
    # Dentro do payload (offset 20 do pai), bloco filho: marcador + 8B (tam=10) + 10B payload
    marcador = b"\xff\xff\xff\xff"
    payload_filho = b"0123456789"
    bloco_filho = marcador + struct.pack("<Q", len(payload_filho)) + payload_filho

    prefixo_pai = b"A" * 10
    sufixo_pai = b"B" * (50 - 10 - len(bloco_filho))
    payload_pai = prefixo_pai + bloco_filho + sufixo_pai
    assert len(payload_pai) == 50

    stream = bytearray(b"HEADER__" + marcador + struct.pack("<Q", 50) + payload_pai + b"TRAILER_")
    arvore = ArvoreBlocos.construir(stream)

    assert len(arvore.blocos) == 1
    pai = arvore.blocos[0]
    assert pai.offset_marcador == 8
    assert pai.tamanho_payload == 50
    assert len(pai.filhos) == 1

    filho = pai.filhos[0]
    assert filho.tamanho_payload == 10
    assert filho.pai is pai

    # Testa busca de ancestrais
    offset_alvo = filho.offset_payload + 2
    ancestrais = arvore.ancestrais_de_offset(offset_alvo)
    assert len(ancestrais) == 2
    assert ancestrais[0] is filho
    assert ancestrais[1] is pai

    # Testa ajuste de tamanho (+15 bytes)
    modifs = arvore.ajustar_delta_tamanho(offset_alvo, 15, stream)
    assert len(modifs) == 2
    # uint64 do filho atualizado para 25
    tam_filho_lido = struct.unpack_from("<Q", stream, filho.offset_tamanho)[0]
    assert tam_filho_lido == 25
    # uint64 do pai atualizado para 65
    tam_pai_lido = struct.unpack_from("<Q", stream, pai.offset_tamanho)[0]
    assert tam_pai_lido == 65


def test_extrair_strings_utf16_sintetico() -> None:
    """Valida extração de strings UTF-16LE com prefixo uint32."""
    texto1 = "Área de Preservação Permanente"
    raw_u16 = texto1.encode("utf-16le") + b"\x00\x00"
    tam_bytes = len(raw_u16)

    stream = b"\x00\x01\x02\x03" + struct.pack("<I", tam_bytes) + raw_u16 + b"\x99\x99"
    strings = extrair_strings_utf16(stream)

    assert len(strings) == 1
    offset_u32, offset_str, txt = strings[0]
    assert offset_u32 == 4
    assert offset_str == 8
    assert txt == texto1


# ------------------------------------------------------------------ 2. Testes contra o corpus de templates


def test_contagem_templates_existentes() -> None:
    """Garante que encontramos os 22 templates da suíte oficial."""
    assert len(_TEMPLATES_MXD) == 22


@pytest.mark.parametrize("mxd_path", _TEMPLATES_MXD, ids=lambda p: p.stem)
def test_percorrer_streams_template_sem_erro(mxd_path: Path) -> None:
    """W10-03: percorre PageLayout, Maps e Mx Document de cada template sem erro."""
    cf = CompoundFile.abrir(mxd_path)
    streams = dict(cf.listar_streams())

    # Todo MXD tem PageLayout, Maps e Mx Document
    assert "PageLayout" in streams, f"PageLayout ausente em {mxd_path.name}"
    assert "Maps" in streams, f"Maps ausente em {mxd_path.name}"
    assert "Mx Document" in streams, f"Mx Document ausente em {mxd_path.name}"

    pl_dados = cf.obter_stream("PageLayout")
    maps_dados = cf.obter_stream("Maps")
    mx_dados = cf.obter_stream("Mx Document")

    # Garante que os dados são não-vazios
    assert len(pl_dados) > 0
    assert len(maps_dados) > 0
    assert len(mx_dados) > 0

    # Constrói árvores de blocos em cada stream
    arv_pl = ArvoreBlocos.construir(pl_dados)
    arv_maps = ArvoreBlocos.construir(maps_dados)
    arv_mx = ArvoreBlocos.construir(mx_dados)

    assert len(arv_pl.blocos) > 0, f"PageLayout de {mxd_path.name} sem blocos"
    assert len(arv_maps.blocos) > 0, f"Maps de {mxd_path.name} sem blocos"
    assert len(arv_mx.blocos) > 0, f"Mx Document de {mxd_path.name} sem blocos"


def test_concordancia_auditoria_arcpy_dinamica_retrato() -> None:
    """W10-03: compara camadas e textos de Dinamica_retrato contra inspecionar_mxd_arcpy.py."""
    audit_file = _PASTA_AUDITORIA / "Dinamica_retrato.json"
    if not audit_file.exists():
        pytest.skip(f"Arquivo de auditoria {audit_file} não encontrado")

    audit = json.loads(audit_file.read_text(encoding="utf-8"))
    camadas_arcpy = [c["name"] for c in audit.get("camadas", [])]
    textos_arcpy = [t["text"] for t in audit.get("text_elements", [])]
    dfs_arcpy = [df["name"] for df in audit.get("data_frames", [])]

    mxd_path = _PASTA_TEMPLATES / "Dinamica_retrato.mxd"
    cf = CompoundFile.abrir(mxd_path)

    pl_dados = cf.obter_stream("PageLayout")
    maps_dados = cf.obter_stream("Maps")

    camadas_bin = inspecionar_camadas_maps(maps_dados)
    textos_bin = inspecionar_textos_layout(pl_dados)
    dfs_bin = inspecionar_dataframes_maps(maps_dados)

    # 1. Valida data frames
    for df in dfs_arcpy:
        assert df in dfs_bin, f"DataFrame {df} do ArcPy não encontrado no binário"

    # 2. Valida que camadas auditadas foram identificadas no binário
    for camada in ("AC", "PERIMETRO", "MUNICIPIOS", "Fazenda_Unificada"):
        assert camada in camadas_bin, f"Camada {camada} ausente da extração binária"

    # 3. Valida que textos do layout auditados aparecem no binário
    texto_concat = " ".join(textos_bin)
    for t in textos_arcpy:
        t_clean = t.replace("<bol>", "").replace("</bol>", "").strip()
        palavras_chave = [w for w in t_clean.split() if len(w) > 3][:2]
        if palavras_chave:
            assert any(pw in texto_concat for pw in palavras_chave), (
                f"Texto auditado '{t}' (chaves {palavras_chave}) não encontrado em PageLayout"
            )
