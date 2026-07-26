# Sessão em memória + gate AUTH-030 (F1-14 / M5).
#
# O núcleo sabe se há sessão, nunca a senha. `sessao.definir` é o que o main
# (ou os testes) usam para espelhar o estado sem reenviar credencial.

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo

_estado: str = "desconectado"
_conta_id: str | None = None
_expira_em: str | None = None


def resetar() -> None:
    """Testes e boot frio."""
    global _estado, _conta_id, _expira_em
    _estado = "desconectado"
    _conta_id = None
    _expira_em = None


def definir(
    *,
    estado: str,
    conta_id: str | None = None,
    expira_em: str | None = None,
) -> dict[str, Any]:
    global _estado, _conta_id, _expira_em
    if estado not in {"desconectado", "conectando", "conectado"}:
        raise ErroNucleo("NU-001", f"Estado de sessão inválido: {estado}")
    _estado = estado
    _conta_id = conta_id if estado == "conectado" else None
    _expira_em = expira_em if estado == "conectado" else None
    return estado_atual()


def estado_atual() -> dict[str, Any]:
    return {
        "estado": _estado,
        "conta_id": _conta_id,
        "expira_em": _expira_em,
    }


def conectada() -> bool:
    return _estado == "conectado"


def exigir_conectado(operacao: str = "esta operação") -> None:
    """Gate AUTH-030 — produto, não segurança contra o dono da máquina."""
    if not conectada():
        raise ErroNucleo(
            "AUTH-030",
            f"{operacao.capitalize()} exige conta neste PC. Crie uma conta ou entre.",
            {"estado": _estado},
        )


# --- handlers NDJSON ---


def handler_definir(params: dict[str, Any]) -> dict[str, Any]:
    estado = params.get("estado")
    if not isinstance(estado, str) or not estado:
        raise ErroNucleo("NU-001", "Parâmetro 'estado' é obrigatório.")
    conta_id = params.get("conta_id")
    if conta_id is not None and not isinstance(conta_id, str):
        raise ErroNucleo("NU-001", "Parâmetro 'conta_id' inválido.")
    expira_em = params.get("expira_em")
    if expira_em is not None and not isinstance(expira_em, str):
        raise ErroNucleo("NU-001", "Parâmetro 'expira_em' inválido.")
    return {"ok": True, **definir(estado=estado, conta_id=conta_id, expira_em=expira_em)}


def handler_estado(_params: dict[str, Any]) -> dict[str, Any]:
    return estado_atual()
