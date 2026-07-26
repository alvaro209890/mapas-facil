from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import doctor
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace import indice
from mapasfacil_nucleo.workspace import watcher as watcher_mod
from mapasfacil_nucleo.workspace.recibo_car import parsear


@dataclass
class EstadoWorkspace:
    guard: WorkspaceGuard
    indice: dict[str, Any] = field(default_factory=dict)
    recibo: dict[str, Any] | None = None


_estado: EstadoWorkspace | None = None


def _obter_indice() -> dict[str, Any]:
    if _estado is None:
        return {}
    return _estado.indice


def _reindexar_interno() -> dict[str, Any]:
    """Reindexa sem reiniciar o watcher — usado pelo próprio A12."""
    global _estado
    if _estado is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
    idx = indice.varrer(_estado.guard.raiz, _estado.guard)
    _estado.indice = idx
    if idx.get("recibo_car"):
        try:
            _estado.recibo = parsear(_estado.guard.resolver(idx["recibo_car"])).para_dict()
        except ErroNucleo:
            pass
    return {"workspace": idx}


def _ligar_watcher() -> None:
    if _estado is None:
        return
    watcher_mod.reiniciar(
        _estado.guard.raiz,
        obter_indice=_obter_indice,
        reindexar=_reindexar_interno,
    )


def abrir(caminho: str) -> dict[str, Any]:
    global _estado
    guard = WorkspaceGuard(caminho)
    idx = indice.varrer(guard.raiz, guard)
    recibo_dados = None
    if idx.get("recibo_car"):
        recibo_dados = parsear(guard.resolver(idx["recibo_car"])).para_dict()

    _estado = EstadoWorkspace(guard=guard, indice=idx, recibo=recibo_dados)
    _ligar_watcher()
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
    return _reindexar_interno()


def fechar() -> None:
    """Para o watcher e limpa o estado — útil em testes e no shutdown do stdio."""
    global _estado
    watcher_mod.parar()
    _estado = None


def inspecionar(arquivo: str) -> dict[str, Any]:
    if _estado is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
    return indice.inspecionar_arquivo(_estado.guard, arquivo)


def estado_atual() -> EstadoWorkspace | None:
    return _estado


def fontes_idx(estado: EstadoWorkspace | None = None) -> dict[str, str]:
    """Mapa `fonte local` → caminho: `id_local` e alias de papel curto.

    O `id_local` vence quando há colisão com um papel de mesmo nome. Vive aqui
    porque tanto o roteador NDJSON quanto as tools do agente precisam do mesmo
    mapeamento — duplicá-lo faz as duas portas divergirem.
    """
    alvo = estado if estado is not None else _estado
    if alvo is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto. Use workspace.abrir primeiro.")
    idx: dict[str, str] = {}
    for item in alvo.indice.get("shapefiles", []):
        idx[item["id_local"]] = item["caminho"]
    for item in alvo.indice.get("shapefiles", []):
        papel = item.get("papel")
        if papel and papel not in idx:
            idx[papel] = item["caminho"]
    return idx


def resolver_workspace_path(caminho_relativo: str) -> Path:
    if _estado is None:
        raise ErroNucleo("NU-040", "Nenhum workspace aberto.")
    return _estado.guard.resolver(caminho_relativo)
