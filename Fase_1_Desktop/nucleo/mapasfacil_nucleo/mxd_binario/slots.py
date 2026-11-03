"""Definição e aplicação de slots em templates MXD binários.

Responsável por (W10-06 / W-08 §Slots):
1. Representar a especificação .slots.json de uma variante;
2. Localizar sentinelas de slots (texto, número, envelope, caminho, nome_camada);
3. Aplicar substituições preservando ou recalculando a estrutura de blocos OLE2/CFBF.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .blocos import ArvoreBlocos

# Tipos suportados de slots
TIPOS_VALIDOS = {"texto", "numero", "envelope", "caminho", "consulta", "nome_camada"}


class ErroSlot(Exception):
    """Erro ao localizar ou aplicar um slot em stream binária."""


@dataclass
class DefinicaoSlot:
    """Especificação de um slot em um template MXD."""

    id: str
    tipo: str
    obrigatorio: bool = True
    origem: str = ""
    sentinela: Any = None
    streams: list[str] = field(default_factory=lambda: ["PageLayout", "Mx Document"])

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_VALIDOS:
            raise ValueError(f"Tipo de slot inválido: {self.tipo}. Válidos: {TIPOS_VALIDOS}")
        if self.sentinela is None:
            if self.tipo == "texto":
                self.sentinela = f"«MF:{self.id}»"
            elif self.tipo == "caminho":
                self.sentinela = f"«MF:ws_{self.id}»"
            elif self.tipo == "nome_camada":
                self.sentinela = f"«MF:nome_{self.id}»"
            elif self.tipo == "consulta":
                self.sentinela = f"«MF:{self.id}»"


@dataclass
class ManifestoSlots:
    """Conjunto de slots definidos para uma variante de template."""

    template_id: str
    variante: dict[str, str] = field(default_factory=dict)
    arquivo_sha256: str = ""
    streams: list[str] = field(default_factory=lambda: ["Mx Document", "PageLayout", "Maps"])
    slots: list[DefinicaoSlot] = field(default_factory=list)

    @classmethod
    def carregar(cls, caminho_json: Path | str) -> ManifestoSlots:
        p = Path(caminho_json)
        dados = json.loads(p.read_text(encoding="utf-8"))
        return cls.de_dict(dados)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> ManifestoSlots:
        slots_def: list[DefinicaoSlot] = []
        for s in dados.get("slots", []):
            slots_def.append(
                DefinicaoSlot(
                    id=s["id"],
                    tipo=s["tipo"],
                    obrigatorio=s.get("obrigatorio", True),
                    origem=s.get("origem", ""),
                    sentinela=s.get("sentinela"),
                    streams=s.get("streams", ["PageLayout", "Mx Document"]),
                )
            )
        return cls(
            template_id=dados.get("template_id", ""),
            variante=dados.get("variante", {}),
            arquivo_sha256=dados.get("arquivo_sha256", ""),
            streams=dados.get("streams", ["Mx Document", "PageLayout", "Maps"]),
            slots=slots_def,
        )

    def para_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "variante": self.variante,
            "arquivo_sha256": self.arquivo_sha256,
            "streams": self.streams,
            "slots": [
                {
                    "id": s.id,
                    "tipo": s.tipo,
                    "obrigatorio": s.obrigatorio,
                    "origem": s.origem,
                    "sentinela": s.sentinela,
                    "streams": s.streams,
                }
                for s in self.slots
            ],
        }


# ------------------------------------------------------------------ Aplicadores


def aplicar_slot_texto(
    stream: bytearray,
    sentinela: str,
    novo_texto: str,
    arvore: ArvoreBlocos | None = None,
) -> int:
    """Substitui ocorrências de uma sentinela de texto UTF-16LE na stream.

    Atualiza o uint32 de comprimento da string e propaga o delta_bytes
    para os blocos ancestrais caso a árvore de blocos seja fornecida.
    Retorna o número de substituições realizadas.
    """
    sentinela_u16 = sentinela.encode("utf-16le")
    novo_u16 = novo_texto.encode("utf-16le")
    delta = len(novo_u16) - len(sentinela_u16)

    substituicoes = 0
    pos = 0

    while True:
        idx = stream.find(sentinela_u16, pos)
        if idx == -1:
            break

        # Procura uint32 de comprimento imediatamente anterior (ou até 8 bytes antes)
        # No ArcObjects: [uint32 tam_bytes][...sentinela...]
        offset_u32 = -1
        for recuo in (4, 6, 8):
            cand = idx - recuo
            if cand >= 0:
                tam_declarado = struct.unpack_from("<I", stream, cand)[0]
                # Se o tamanho declarado engloba a sentinela
                if tam_declarado >= len(sentinela_u16):
                    offset_u32 = cand
                    break

        if offset_u32 != -1:
            # Atualiza uint32
            tam_antigo = struct.unpack_from("<I", stream, offset_u32)[0]
            struct.pack_into("<I", stream, offset_u32, tam_antigo + delta)

        # Realiza a substituição de bytes
        stream[idx : idx + len(sentinela_u16)] = novo_u16
        substituicoes += 1

        # Atualiza a árvore de blocos ArcObjects se houver delta
        if delta != 0 and arvore is not None:
            arvore.ajustar_delta_tamanho(idx, delta, stream)

        pos = idx + len(novo_u16)

    return substituicoes


def aplicar_slot_numero(
    stream: bytearray,
    sentinela: float,
    novo_valor: float,
) -> int:
    """Substitui valor double IEEE-754 (8 bytes) in-place na stream."""
    sentinela_bytes = struct.pack("<d", float(sentinela))
    novo_bytes = struct.pack("<d", float(novo_valor))

    substituicoes = 0
    pos = 0
    while True:
        idx = stream.find(sentinela_bytes, pos)
        if idx == -1:
            break
        stream[idx : idx + 8] = novo_bytes
        substituicoes += 1
        pos = idx + 8

    return substituicoes


def aplicar_slot_envelope(
    stream: bytearray,
    sentinela: tuple[float, float, float, float] | list[float],
    novo_envelope: tuple[float, float, float, float] | list[float],
) -> int:
    """Substitui 4 doubles IEEE-754 (XMin, YMin, XMax, YMax = 32 bytes) in-place."""
    if len(sentinela) != 4 or len(novo_envelope) != 4:
        raise ValueError("Envelope exige exatamente 4 coordenadas (xmin, ymin, xmax, ymax)")

    sentinela_bytes = struct.pack(
        "<dddd",
        float(sentinela[0]),
        float(sentinela[1]),
        float(sentinela[2]),
        float(sentinela[3]),
    )
    novo_bytes = struct.pack(
        "<dddd",
        float(novo_envelope[0]),
        float(novo_envelope[1]),
        float(novo_envelope[2]),
        float(novo_envelope[3]),
    )

    substituicoes = 0
    pos = 0
    while True:
        idx = stream.find(sentinela_bytes, pos)
        if idx == -1:
            break
        stream[idx : idx + 32] = novo_bytes
        substituicoes += 1
        pos = idx + 32

    return substituicoes


def aplicar_slot_consulta(
    stream: bytearray,
    sentinela: str,
    novo_filtro: str,
    arvore: ArvoreBlocos | None = None,
) -> int:
    """Substitui a cláusula da consulta SQL com escape de aspas."""
    # Escapa aspas simples conforme SQL de shapefile ArcObjects
    novo_escapado = novo_filtro.replace("'", "''")
    return aplicar_slot_texto(stream, sentinela, novo_escapado, arvore)
