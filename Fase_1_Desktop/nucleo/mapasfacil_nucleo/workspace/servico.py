from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import doctor
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace import indice
from mapasfacil_nucleo.workspace.recibo_car import parsear


@dataclass
class EstadoWorkspace:
    guard: WorkspaceGuard
    indice: dict[str, Any] = field(default_factory=dict)


_estado: EstadoWorkspace | None = None


def abrir(caminho: str) -> dict[str, Any]:
    global _estado
    guard = WorkspaceGuard(caminho)
    idx = indice.varrer(guard.raiz, guard)
    recibo_dados = None
    if idx.get("recibo_car"):
        recibo_dados = parsear(guard.resolver(idx["recibo_car"])).para_dict()

    _estado = EstadoWorkspace(guard=guard, indice=idx)
    doctor_resumo = doctor.rodar(sondar_arcpy=False)
    return {
        "workspace": idx,
        "recibo": recibo_dados,
        "doctor": {
            "nucleo": doctor_resumo["nucleo"],
            "pronto_para_mxd": doctor_resumo["pronto_para_mxd"],
            "motor_preferido": doctor_resumo["motor_preferido"],
        },
    }


def reindexar(caminho: str | None = None) -> dict[str, Any]:
    global _estado
    if _estado is None and not caminho:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
    if caminho:
        return abrir(caminho)
    idx = indice.varrer(_estado.guard.raiz, _estado.guard)
    _estado.indice = idx
    return {"workspace": idx}


def inspecionar(arquivo: str) -> dict[str, Any]:
    if _estado is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
    return indice.inspecionar_arquivo(_estado.guard, arquivo)


def estado_atual() -> EstadoWorkspace | None:
    return _estado


def resolver_workspace_path(caminho_relativo: str) -> Path:
    if _estado is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto.")
    return _estado.guard.resolver(caminho_relativo)
