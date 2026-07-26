# Cassetes VCR do agente (G8 / F1-06) — anel 1 sem rede.
#
# Dois formatos:
#  · `passos` — roteiro do FakeProvedor (unitário / orquestrador);
#  · `sse_linhas` — corpo SSE cru rebobinado no DeepSeekProvedor (contrato HTTP).

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.fake import FakeProvedor, PassoFake

PASTA_CASSETES = Path(__file__).resolve().parents[2] / "tests" / "agente" / "cassetes"


def caminho_cassete(nome: str) -> Path:
    base = Path(nome)
    if base.suffix != ".json":
        base = base.with_suffix(".json")
    if base.is_absolute():
        return base
    return PASTA_CASSETES / base.name


def carregar_cassete(nome: str) -> dict[str, Any]:
    caminho = caminho_cassete(nome)
    if not caminho.is_file():
        raise FileNotFoundError(f"Cassete VCR ausente: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def provedor_de_cassete(nome: str) -> FakeProvedor:
    """Cassete com `passos` → FakeProvedor (CI sem HTTP)."""
    dados = carregar_cassete(nome)
    passos_brutos = dados.get("passos") or []
    passos = [
        PassoFake(
            texto=str(p.get("texto") or ""),
            tool_calls=list(p.get("tool_calls") or []),
            finish_reason=p.get("finish_reason") or "stop",
            truncado=bool(p.get("truncado")),
            pedacos=list(p.get("pedacos") or []),
        )
        for p in passos_brutos
    ]
    return FakeProvedor(passos)


class _RespostaSseFake:
    """Imita o file-like de `urlopen` para o parser SSE do DeepSeekProvedor."""

    def __init__(self, linhas: list[str]) -> None:
        corpo = "".join(linhas)
        if corpo and not corpo.endswith("\n"):
            corpo += "\n"
        self._buf = io.BytesIO(corpo.encode("utf-8"))

    def __iter__(self):
        return self

    def __next__(self) -> bytes:
        linha = self._buf.readline()
        if not linha:
            raise StopIteration
        return linha

    def close(self) -> None:
        self._buf.close()

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)


def opener_de_cassete(nome: str):
    """Devolve um `urlopen` que ignora a rede e serve o SSE do cassete."""
    dados = carregar_cassete(nome)
    linhas = list(dados.get("sse_linhas") or [])
    if not linhas:
        raise ValueError(f"Cassete sem sse_linhas: {nome}")

    def _urlopen(_req, timeout: float | None = None):  # noqa: ARG001
        del timeout
        return _RespostaSseFake(linhas)

    return _urlopen
