from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErroNucleo(Exception):
    codigo: str
    mensagem: str
    detalhes: dict | None = None

    def para_dict(self) -> dict:
        payload: dict = {"codigo": self.codigo, "mensagem": self.mensagem}
        if self.detalhes:
            payload["detalhes"] = self.detalhes
        return payload


class CaminhoNaoAutorizado(ErroNucleo):
    def __init__(self, mensagem: str, detalhes: dict | None = None) -> None:
        super().__init__("NU-010", mensagem, detalhes)


class MetodoDesconhecido(ErroNucleo):
    def __init__(self, metodo: str) -> None:
        super().__init__(
            "NU-002",
            f"Método não implementado: {metodo}",
            {"metodo": metodo},
        )
