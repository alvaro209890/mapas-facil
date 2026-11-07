from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.protocolo import Emissor

STATUS_VALIDOS = frozenset({"pendente", "em_andamento", "concluido", "erro", "cancelado"})


@dataclass
class PassoPlano:
    id: str
    titulo: str
    status: str = "pendente"
    resumo: str = ""

    def para_dict(self) -> dict[str, Any]:
        d = {"id": self.id, "titulo": self.titulo, "status": self.status}
        if self.resumo:
            d["resumo"] = self.resumo
        return d


class PlanoAgente:
    """Gerencia o plano de execução e a emissão de eventos agente.plano e agente.passo."""

    def __init__(self, emissor: Emissor | None = None) -> None:
        self.passos: list[PassoPlano] = []
        self.emissor = emissor

    def definir(self, passos_dados: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.passos = []
        for p in passos_dados:
            pid = str(p.get("id") or f"passo_{len(self.passos) + 1}")
            titulo = str(p.get("titulo") or "Sem título")
            status = str(p.get("status") or "pendente").lower()
            if status not in STATUS_VALIDOS:
                status = "pendente"
            resumo = str(p.get("resumo") or "")
            self.passos.append(PassoPlano(id=pid, titulo=titulo, status=status, resumo=resumo))

        passos_dict = [p.para_dict() for p in self.passos]
        if self.emissor is not None:
            self.emissor.emitir(
                "agente.plano",
                {"passos": [{"id": p["id"], "titulo": p["titulo"], "status": p["status"]} for p in passos_dict]},
            )
        return passos_dict

    def atualizar(self, passo_id: str, status: str, resumo: str = "") -> dict[str, Any] | None:
        status_norm = status.lower()
        if status_norm not in STATUS_VALIDOS:
            status_norm = "em_andamento"

        for p in self.passos:
            if p.id == passo_id:
                p.status = status_norm
                if resumo:
                    p.resumo = resumo

                if self.emissor is not None:
                    dados = {"id": p.id, "titulo": p.titulo, "status": p.status}
                    if p.resumo:
                        dados["resumo"] = p.resumo
                    self.emissor.emitir("agente.passo", dados)

                return p.para_dict()
        return None

    def obter_passos_dict(self) -> list[dict[str, Any]]:
        return [p.para_dict() for p in self.passos]


def registrar_tools_plano(registro: RegistroFerramentas, plano: PlanoAgente | None = None) -> None:
    @registro.ferramenta(
        nome="plano_definir",
        descricao="Define os passos planejados para a execução da tarefa do agente.",
        categoria="plano",
        parametros={
            "type": "object",
            "properties": {
                "passos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "titulo": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pendente", "em_andamento", "concluido", "erro", "cancelado"],
                            },
                        },
                        "required": ["id", "titulo"],
                    },
                    "description": "Lista ordenada de passos planejados.",
                }
            },
            "required": ["passos"],
            "additionalProperties": False,
        },
    )
    def tool_plano_definir(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        instancia = ctx.get("plano") or plano
        if instancia is None:
            instancia = PlanoAgente(emissor=ctx.get("emissor"))
            ctx["plano"] = instancia
        else:
            instancia.emissor = ctx.get("emissor")

        passos = args.get("passos", [])
        resultado = instancia.definir(passos)
        return _ok({"passos": resultado, "total": len(resultado)})

    @registro.ferramenta(
        nome="plano_atualizar",
        descricao="Atualiza o status e resumo de um passo do plano em execução.",
        categoria="plano",
        parametros={
            "type": "object",
            "properties": {
                "passo_id": {"type": "string", "description": "ID do passo a atualizar."},
                "status": {
                    "type": "string",
                    "enum": ["pendente", "em_andamento", "concluido", "erro", "cancelado"],
                    "description": "Novo status do passo.",
                },
                "resumo": {"type": "string", "description": "Resumo opcional do que foi feito no passo."},
            },
            "required": ["passo_id", "status"],
            "additionalProperties": False,
        },
    )
    def tool_plano_atualizar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        instancia = ctx.get("plano") or plano
        if instancia is None:
            return _erro("PLAN-001", "Nenhum plano ativo para atualizar.")

        instancia.emissor = ctx.get("emissor")
        passo_id = args.get("passo_id", "")
        status = args.get("status", "")
        resumo = args.get("resumo", "")

        atualizado = instancia.atualizar(passo_id, status, resumo=resumo)
        if atualizado is None:
            return _erro("PLAN-002", f"Passo com ID '{passo_id}' não encontrado no plano.")

        return _ok({"passo": atualizado})
