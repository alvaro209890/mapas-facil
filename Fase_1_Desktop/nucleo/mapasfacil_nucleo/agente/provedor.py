# Interface do provedor de IA (F1-06 / G1). Troca de provedor = revisar o plano.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol


@dataclass
class MensagemLLM:
    papel: str  # system | user | assistant | tool
    conteudo: str
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class DeltaStream:
    """Pedacinho do stream: texto e/ou tool_calls acumulados no fim do turno."""

    texto: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    truncado: bool = False  # finish_reason == length → IA-050


class ProvedorIA(Protocol):
    def enviar_stream(
        self,
        mensagens: list[MensagemLLM],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8000,
        modelo: str | None = None,
    ) -> Iterator[DeltaStream]:
        """Gera deltas; o último pode trazer ``tool_calls`` e ``finish_reason``."""

    def cancelar(self) -> None:
        """Encerra o request HTTP em andamento, se houver."""
