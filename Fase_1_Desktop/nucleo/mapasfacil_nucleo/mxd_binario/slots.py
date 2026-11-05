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
    # Envelope: `quadro_cm` [w, h] do data frame e `epsg` — para ajustar a extensão à
    # proporção do quadro (o ArcMap respeita a extensão gravada e deriva a escala dela).
    extra: dict[str, Any] = field(default_factory=dict)

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
    # Arquivos que as camadas do template esperam ao lado do .mxd (`SHP/AIR.shp`,
    # `SHP/limites/lml_municipio_a.shp`, ...) e o papel de cada um — o núcleo grava as cópias.
    arquivos: list[dict[str, str]] = field(default_factory=list)

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
                    extra=dict(s.get("extra") or {}),
                )
            )
        return cls(
            template_id=dados.get("template_id", ""),
            variante=dados.get("variante", {}),
            arquivo_sha256=dados.get("arquivo_sha256", ""),
            streams=dados.get("streams", ["Mx Document", "PageLayout", "Maps"]),
            slots=slots_def,
            arquivos=list(dados.get("arquivos") or []),
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
                    **({"extra": s.extra} if s.extra else {}),
                }
                for s in self.slots
            ],
            **({"arquivos": self.arquivos} if self.arquivos else {}),
        }


# ------------------------------------------------------------------ Aplicadores


TAG_PEQUENA_ABRE = '<FNT size="1">'
TAG_PEQUENA_FECHA = "</FNT>"
"""Sobra de sentinela num rótulo vai em letra de 1 pt: com espaços normais, a caixa do título
(balão) ficava do tamanho da sentinela. O ArcMap interpreta as tags de formatação no texto."""


def _escapar_tags(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def variantes_gravadas(texto: str) -> list[str]:
    """Formas em que um texto pode ter sido gravado (para o gate G2 procurar)."""
    return [texto, texto.replace("'", "''"), _escapar_tags(texto)]


def _rotulo(novo: str, tamanho: int) -> str:
    falta = tamanho - len(novo)
    if falta == 0:
        return novo
    tags = len(TAG_PEQUENA_ABRE) + len(TAG_PEQUENA_FECHA)
    escapado = _escapar_tags(novo)
    sobra = tamanho - len(escapado) - tags
    if sobra >= 1:
        return escapado + TAG_PEQUENA_ABRE + " " * sobra + TAG_PEQUENA_FECHA
    return " " * (falta // 2) + novo + " " * (falta - falta // 2)


def aplicar_slot_texto(
    stream: bytearray,
    sentinela: str,
    novo_texto: str,
    arvore: ArvoreBlocos | None = None,  # noqa: ARG001 — mantido na assinatura; não há delta
) -> int:
    """Substitui as ocorrências de uma sentinela de texto UTF-16LE na stream.

    O texto novo ocupa **sempre** o mesmo número de bytes da sentinela: trocar o tamanho
    corrompia o PageLayout (o MXD do teste_22 abria no ArcMap com `pageLayout` vazio).
    A decisão é por ocorrência — a mesma sentinela está no rótulo e nas consultas:

    - consulta SQL (`"nome" = 'MFMUNICIPIO…'`): apóstrofo do valor vira `''` e a sobra são
      espaços **depois** da aspa (`'Canarana'   `);
    - rótulo: a sobra vai numa tag de letra 1 pt (`<FNT size="1">   </FNT>`), que não
      alarga a caixa; sem espaço para a tag, espaços dos dois lados.

    Texto maior que a sentinela não entra (`ErroSlot`). Retorna o número de trocas.
    """
    if len(novo_texto) > len(sentinela):
        raise ErroSlot(
            f"Texto com {len(novo_texto)} caracteres não cabe na sentinela de {len(sentinela)}."
        )
    sentinela_u16 = sentinela.encode("utf-16le")
    aspa_u16 = "'".encode("utf-16le")
    rotulo = _rotulo(novo_texto, len(sentinela)).encode("utf-16le")

    substituicoes = 0
    pos = 0
    while True:
        idx = stream.find(sentinela_u16, pos)
        if idx == -1:
            break
        fim_s = idx + len(sentinela_u16)
        if stream[fim_s : fim_s + len(aspa_u16)] == aspa_u16:
            valor = novo_texto.replace("'", "''")
            if len(valor) > len(sentinela):
                raise ErroSlot(f"Consulta com {len(valor)} caracteres não cabe na sentinela.")
            sobra = len(sentinela) - len(valor)
            stream[idx : fim_s + len(aspa_u16)] = (valor + "'" + " " * sobra).encode("utf-16le")
            pos = fim_s + len(aspa_u16)
        else:
            stream[idx:fim_s] = rotulo
            pos = fim_s
        substituicoes += 1
    return substituicoes


def _posicoes_aproximadas(stream: bytearray, valores: list[float], rel_tol: float = 1e-9) -> list[int]:
    """Offsets onde os `valores` aparecem em sequência (float64 LE), com tolerância.

    O ArcMap grava a mesma extensão/escala em vários lugares, às vezes diferindo no último
    bit (209463.9044549968 × 209463.90445499684) — e não só no último valor: busca exata
    deixava cópias velhas, e o minimapa desenhava pela cópia velha (em branco).
    """
    import numpy as np

    dados = bytes(stream)
    achados: list[int] = []
    n_val = len(valores)
    for alinhamento in range(8):
        n = (len(dados) - alinhamento) // 8
        if n < n_val:
            continue
        arr = np.frombuffer(dados, dtype="<f8", count=n, offset=alinhamento)
        with np.errstate(invalid="ignore"):
            ok = np.isclose(arr[: n - n_val + 1], valores[0], rtol=rel_tol, atol=0.0)
            for j in range(1, n_val):
                ok &= np.isclose(arr[j : n - n_val + 1 + j], valores[j], rtol=rel_tol, atol=0.0)
        achados.extend(int(alinhamento + 8 * i) for i in np.nonzero(ok)[0])
    return sorted(achados)


def aplicar_slot_numero(
    stream: bytearray,
    sentinela: float,
    novo_valor: float,
) -> int:
    """Substitui um double IEEE-754 (8 bytes) in-place, tolerando o último bit."""
    novo_bytes = struct.pack("<d", float(novo_valor))
    posicoes = _posicoes_aproximadas(stream, [float(sentinela)])
    for idx in posicoes:
        stream[idx : idx + 8] = novo_bytes
    return len(posicoes)


def aplicar_slot_envelope(
    stream: bytearray,
    sentinela: tuple[float, float, float, float] | list[float],
    novo_envelope: tuple[float, float, float, float] | list[float],
) -> int:
    """Substitui 4 doubles (XMin, YMin, XMax, YMax = 32 bytes) in-place, com tolerância."""
    if len(sentinela) != 4 or len(novo_envelope) != 4:
        raise ValueError("Envelope exige exatamente 4 coordenadas (xmin, ymin, xmax, ymax)")
    novo_bytes = struct.pack("<dddd", *(float(v) for v in novo_envelope))
    posicoes = _posicoes_aproximadas(stream, [float(v) for v in sentinela])
    for idx in posicoes:
        stream[idx : idx + 32] = novo_bytes
    return len(posicoes)


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
