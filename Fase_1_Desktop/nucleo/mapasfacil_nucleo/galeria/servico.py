# Handlers NDJSON da galeria (listar / detalhar / montar_mapspec).

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria.catalogo import carregar_galeria, obter_modelo
from mapasfacil_nucleo.galeria.estado import SAIDAS_VALIDAS, avaliar_status, fontes_do_indice
from mapasfacil_nucleo.galeria.montar import montar_mapspec
from mapasfacil_nucleo.workspace import servico as workspace_servico


def _saidas_pedidas(params: dict[str, Any]) -> list[str] | None:
    saidas = params.get("saidas_pedidas")
    if saidas is None:
        return None
    if (
        not isinstance(saidas, list)
        or not saidas
        or not all(isinstance(s, str) and s in SAIDAS_VALIDAS for s in saidas)
    ):
        raise ErroNucleo("NU-001", "Parâmetro 'saidas_pedidas' inválido.")
    return saidas


def _indice_opcional(workspace: str | None) -> dict[str, Any] | None:
    if workspace:
        return workspace_servico.abrir(workspace)["workspace"]
    estado = workspace_servico.estado_atual()
    return None if estado is None else estado.indice


def _recibo_opcional(workspace: str | None) -> dict[str, Any] | None:
    if workspace:
        return workspace_servico.abrir(workspace).get("recibo")
    estado = workspace_servico.estado_atual()
    return None if estado is None else estado.recibo


def listar(params: dict[str, Any]) -> dict[str, Any]:
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    saidas_pedidas = _saidas_pedidas(params)
    galeria = carregar_galeria()
    indice = _indice_opcional(workspace)
    modelos = []
    for modelo in galeria["modelos"]:
        estado = avaliar_status(modelo, indice, saidas_pedidas)
        modelos.append(
            {
                "id": modelo["id"],
                "nome": modelo["nome"],
                "subtitulo": modelo["subtitulo"],
                "tags": modelo.get("tags", []),
                "orientacao": modelo["orientacao"],
                "preview": modelo["preview"],
                "tipo_execucao": modelo.get("tipo_execucao", "mapspec"),
                "status": estado["status"],
                "motivo": estado.get("motivo"),
                "requisitos_faltando": estado.get("requisitos_faltando", []),
            }
        )
    return {"galeria_version": galeria["galeria_version"], "modelos": modelos}


def detalhar(params: dict[str, Any]) -> dict[str, Any]:
    modelo_id = params.get("modelo_id")
    if not isinstance(modelo_id, str) or not modelo_id:
        raise ErroNucleo("NU-001", "Parâmetro 'modelo_id' é obrigatório.")
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    saidas_pedidas = _saidas_pedidas(params)

    modelo = obter_modelo(modelo_id)
    indice = _indice_opcional(workspace)
    estado = avaliar_status(modelo, indice, saidas_pedidas)
    fontes = fontes_do_indice(indice)
    mapeamento: dict[str, str] = {}
    for req in modelo.get("requisitos_camadas") or []:
        papel = req["papel"]
        if papel in fontes:
            mapeamento[papel] = f"local.{papel}"
        else:
            for shp in (indice or {}).get("shapefiles") or []:
                if shp.get("papel") == papel:
                    mapeamento[papel] = f"local.{shp['id_local']}"
                    break

    return {
        **modelo,
        "status": estado["status"],
        "motivo": estado.get("motivo"),
        "requisitos_faltando": estado.get("requisitos_faltando", []),
        "mapeamento_sugerido": mapeamento,
    }


def montar(params: dict[str, Any]) -> dict[str, Any]:
    from mapasfacil_nucleo import sessao

    sessao.exigir_conectado("montar MapSpec pela galeria")
    modelo_id = params.get("modelo_id")
    if not isinstance(modelo_id, str) or not modelo_id:
        raise ErroNucleo("NU-001", "Parâmetro 'modelo_id' é obrigatório.")
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    sobrescritas = params.get("sobrescritas") or {}
    if not isinstance(sobrescritas, dict):
        raise ErroNucleo("NU-232", "sobrescritas precisa ser um objeto.")
    return montar_mapspec(modelo_id, workspace=workspace, sobrescritas=sobrescritas)
