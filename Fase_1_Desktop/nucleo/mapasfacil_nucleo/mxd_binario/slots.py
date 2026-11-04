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
    arvore: ArvoreBlocos | None = None,  # noqa: ARG001 — mantido na assinatura; não há delta
) -> int:
    """Substitui as ocorrências de uma sentinela de texto UTF-16LE na stream.

    O texto novo ocupa **sempre** o mesmo número de bytes da sentinela: trocar o tamanho
    corrompia o PageLayout (o MXD do teste_22 abria no ArcMap com `pageLayout` vazio).
    Num rótulo, o texto é completado com espaços dos dois lados (continua centrado); numa
    consulta SQL (`"nome" = 'Vila Rica'`), os espaços vão depois da aspa. A decisão é por
    ocorrência — a mesma sentinela costuma estar no rótulo e na consulta do minimapa.
    Texto maior que a sentinela não entra (`ErroSlot`). Retorna o número de trocas.
    """
    if len(novo_texto) > len(sentinela):
        raise ErroSlot(
            f"Texto com {len(novo_texto)} caracteres não cabe na sentinela de {len(sentinela)}."
        )
    falta = len(sentinela) - len(novo_texto)
    sentinela_u16 = sentinela.encode("utf-16le")
    aspa_u16 = "'".encode("utf-16le")
    centrado = (" " * (falta // 2) + novo_texto + " " * (falta - falta // 2)).encode("utf-16le")
    em_consulta = (novo_texto + "'" + " " * falta).encode("utf-16le")

    substituicoes = 0
    pos = 0
    while True:
        idx = stream.find(sentinela_u16, pos)
        if idx == -1:
            break
        fim_s = idx + len(sentinela_u16)
        if stream[fim_s : fim_s + len(aspa_u16)] == aspa_u16:
            stream[idx : fim_s + len(aspa_u16)] = em_consulta
            pos = fim_s + len(aspa_u16)
        else:
            stream[idx:fim_s] = centrado
            pos = fim_s
        substituicoes += 1
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
