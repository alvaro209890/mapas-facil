# Provedor fake / VCR para anel 1 e CI (sem rede, sem chave).

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from mapasfacil_nucleo.agente.provedor import DeltaStream, MensagemLLM


@dataclass
class PassoFake:
    """Uma resposta do modelo: texto streamado e/ou tool_calls."""

    texto: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = "stop"
    truncado: bool = False
    # pedaços para simular streaming (se vazio, manda texto de uma vez)
    pedacos: list[str] = field(default_factory=list)


class FakeProvedor:
    """Consome um roteiro de passos; cada ``enviar_stream`` avança um passo."""

    def __init__(self, passos: list[PassoFake] | None = None) -> None:
        self.passos = list(passos or [])
        self.indice = 0
        self.cancelado = False
        self.chamadas: list[list[MensagemLLM]] = []

    def enviar_stream(
        self,
        mensagens: list[MensagemLLM],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 8000,
        modelo: str | None = None,
    ) -> Iterator[DeltaStream]:
        del tools, max_tokens, modelo
        self.chamadas.append(list(mensagens))
        if self.cancelado:
            return
        if self.indice >= len(self.passos):
            yield DeltaStream(texto="(fim do roteiro fake)", finish_reason="stop")
            return
        passo = self.passos[self.indice]
        self.indice += 1
        pedacos = passo.pedacos or ([passo.texto] if passo.texto else [""])
        acumulado = ""
        for i, pedaco in enumerate(pedacos):
            if self.cancelado:
                return
            acumulado += pedaco
            ultimo = i == len(pedacos) - 1
            yield DeltaStream(
                texto=pedaco,
                tool_calls=passo.tool_calls if ultimo else [],
                finish_reason=passo.finish_reason if ultimo else None,
                truncado=passo.truncado if ultimo else False,
            )

    def cancelar(self) -> None:
        self.cancelado = True


def tool_call(nome: str, argumentos: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
    """Helper para montar tool_call no formato OpenAI/DeepSeek."""
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {"name": nome, "arguments": json.dumps(argumentos, ensure_ascii=False)},
    }
