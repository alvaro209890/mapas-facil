from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace, _resolver_caminho_seguro
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.layout import (
    CaixaMm,
    LayoutSpec,
    carregar as layout_carregar,
    medir as layout_medir_fn,
    obter_layout as layout_obter_layout,
    validar as layout_validar_fn,
)
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.protocolo import Emissor


def _obter_mapspec(ctx: dict[str, Any]) -> dict[str, Any]:
    ms = ctx.get("mapspec")
    if isinstance(ms, dict):
        return ms
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    estado = workspace_servico.estado_atual()
    if estado is not None and getattr(estado, "mapspec", None):
        return estado.mapspec

    ms_padrao = {
        "id": "ms-auto",
        "versao": 1,
        "template": "serie_dinamica_2026",
        "folha": {
            "tamanho": "A4",
            "orientacao": "retrato",
            "largura_mm": 210.0,
            "altura_mm": 297.0,
            "margem_mm": 10.0,
        },
    }
    ctx["mapspec"] = ms_padrao
    return ms_padrao


def _obter_ou_inicializar_layout_spec(mapspec: dict[str, Any]) -> dict[str, Any]:
    raw_spec = mapspec.get("layout_spec")
    if isinstance(raw_spec, dict):
        return raw_spec

    template_id = str(mapspec.get("template") or "serie_dinamica_2026")
    folha = mapspec.get("folha")
    try:
        spec = layout_obter_layout(template_id, folha=folha)
    except Exception:
        spec = layout_obter_layout("serie_dinamica_2026", folha=folha)

    spec_dict = spec.para_dict()
    mapspec["layout_spec"] = spec_dict
    return spec_dict


def registrar_tools_layout(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="layout_ler",
        descricao="Lê a especificação declarativa do LayoutSpec ativo ou pelo ID/template.",
        categoria="layout",
        parametros={
            "type": "object",
            "properties": {
                "layout_id": {
                    "type": "string",
                    "description": "ID ou template opcional para consultar layout registrado.",
                }
            },
            "additionalProperties": False,
        },
    )
    def tool_layout_ler(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ms = _obter_mapspec(ctx)
            layout_id = args.get("layout_id")
            if layout_id:
                spec = layout_obter_layout(layout_id, folha=ms.get("folha"))
                spec_dict = spec.para_dict()
            else:
                spec_dict = _obter_ou_inicializar_layout_spec(ms)

            return _ok(
                {
                    "layout_spec": spec_dict,
                    "id": spec_dict.get("id"),
                    "nome": spec_dict.get("nome"),
                    "orientacao": spec_dict.get("orientacao"),
                    "folha": spec_dict.get("folha_padrao") or ms.get("folha", {}),
                    "dimensoes_mm": spec_dict.get("dimensoes_mm"),
                    "elementos": spec_dict.get("elementos", {}),
                    "versao": spec_dict.get("versao", 1),
                }
            )
        except Exception as exc:
            return _erro("LAY-004", f"Falha ao ler layout: {exc}")

    @registro.ferramenta(
        nome="layout_editar",
        descricao="Edita elementos ou propriedades do LayoutSpec ativo conforme o schema oficial.",
        categoria="layout",
        parametros={
            "type": "object",
            "properties": {
                "elemento_id": {
                    "type": "string",
                    "description": "Identificador do elemento (ex: mapa, titulo, rosa, minimapa, legenda, metadados, logo, tabela).",
                },
                "propriedades": {
                    "type": "object",
                    "description": "Coordenadas em milímetros (x0, y0, x1, y1) ou propriedades do elemento.",
                },
                "layout_spec": {
                    "type": "object",
                    "description": "Substituição completa do LayoutSpec opcional.",
                },
            },
            "additionalProperties": False,
        },
    )
    def tool_layout_editar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ms = _obter_mapspec(ctx)
            if "layout_spec" in args and isinstance(args["layout_spec"], dict):
                spec_obj = layout_carregar(args["layout_spec"])
                res_val = layout_validar_fn(spec_obj)
                if not res_val["valido"]:
                    return _erro("LAY-005", "LayoutSpec inválido para edição.", erros=res_val["erros"])
                ms["layout_spec"] = spec_obj.para_dict()
                return _ok({"layout_spec": ms["layout_spec"], "atualizado": True})

            elemento_id = args.get("elemento_id", "").strip()
            props = args.get("propriedades", {})
            if not elemento_id:
                return _erro("LAY-006", "Parâmetro 'elemento_id' é obrigatório para edição.")

            spec_dict = _obter_ou_inicializar_layout_spec(ms)
            elementos = spec_dict.setdefault("elementos", {})

            if elemento_id not in elementos:
                elementos[elemento_id] = {"x0": 0.0, "y0": 0.0, "x1": 50.0, "y1": 50.0}

            alvo_elem = elementos[elemento_id]
            for k in ("x0", "y0", "x1", "y1"):
                if k in props:
                    alvo_elem[k] = float(props[k])

            spec_dict["versao"] = int(spec_dict.get("versao", 1)) + 1
            ms["versao"] = int(ms.get("versao", 1)) + 1

            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir(
                    "layout.elemento",
                    {
                        "elemento_id": elemento_id,
                        "propriedades": alvo_elem,
                        "versao": spec_dict["versao"],
                    },
                )

            return _ok(
                {
                    "elemento_id": elemento_id,
                    "propriedades": alvo_elem,
                    "versao": spec_dict["versao"],
                }
            )
        except Exception as exc:
            return _erro("LAY-007", f"Falha ao editar layout: {exc}")

    @registro.ferramenta(
        nome="layout_medir",
        descricao="Mede a geometria cartográfica de um PDF de referência física gerando um LayoutSpec real.",
        categoria="layout",
        parametros={
            "type": "object",
            "properties": {
                "caminho_pdf": {
                    "type": "string",
                    "description": "Caminho relativo do arquivo PDF no workspace.",
                },
                "pagina": {
                    "type": "integer",
                    "description": "Número da página a medir (1-indexado, padrão: 1).",
                },
                "id": {
                    "type": "string",
                    "description": "Identificador do LayoutSpec medido (padrão: 'medido').",
                },
                "nome": {
                    "type": "string",
                    "description": "Nome do LayoutSpec medido.",
                },
            },
            "required": ["caminho_pdf"],
            "additionalProperties": False,
        },
    )
    def tool_layout_medir(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args.get("caminho_pdf", "")
            alvo = _resolver_caminho_seguro(caminho_str, ws_root)

            if not alvo.exists():
                return _erro("PDF-001", f"Arquivo PDF '{caminho_str}' não existe.")
            if not alvo.is_file():
                return _erro("PDF-002", f"'{caminho_str}' não é um arquivo.")

            num_pagina = int(args.get("pagina", 1))
            pagina_idx = max(0, num_pagina - 1)
            id_layout = str(args.get("id") or "medido")
            nome_layout = str(args.get("nome") or "Layout Medido")

            spec = layout_medir_fn(alvo, id=id_layout, nome=nome_layout, pagina=pagina_idx)
            spec_dict = spec.para_dict()

            return _ok(
                {
                    "caminho_pdf": alvo.relative_to(ws_root).as_posix(),
                    "layout_spec": spec_dict,
                    "id": spec.id,
                    "orientacao": spec.orientacao,
                    "dimensoes_mm": spec_dict["dimensoes_mm"],
                    "elementos": spec_dict["elementos"],
                }
            )
        except Exception as exc:
            return _erro("LAY-001", f"Falha na medição do PDF de referência: {exc}")

    @registro.ferramenta(
        nome="layout_validar",
        descricao="Valida conformidade do LayoutSpec contra o schema oficial e regras milimétricas.",
        categoria="layout",
        parametros={
            "type": "object",
            "properties": {
                "layout_spec": {
                    "type": "object",
                    "description": "Objeto LayoutSpec opcional para validação isolada.",
                }
            },
            "additionalProperties": False,
        },
    )
    def tool_layout_validar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ms = _obter_mapspec(ctx)
            dados_spec = args.get("layout_spec") or _obter_ou_inicializar_layout_spec(ms)
            resultado = layout_validar_fn(dados_spec)
            return _ok(
                {
                    "valido": bool(resultado.get("valido", False)),
                    "erros": resultado.get("erros", []),
                    "layout_id": dados_spec.get("id"),
                }
            )
        except Exception as exc:
            return _erro("LAY-008", f"Falha ao validar layout: {exc}")

    @registro.ferramenta(
        nome="layout_renderizar",
        descricao="Renderiza PDF real via motor cartográfico existente e gera preview se o arquivo existir.",
        categoria="layout",
        parametros={
            "type": "object",
            "properties": {
                "formato": {
                    "type": "string",
                    "enum": ["pdf", "png"],
                    "description": "Formato de saída principal (padrão: 'pdf').",
                }
            },
            "additionalProperties": False,
        },
    )
    def tool_layout_renderizar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            ms = _obter_mapspec(ctx)
            formato = args.get("formato", "pdf")

            # Garantir pasta de saída
            saida_cfg = ms.setdefault("saida", {})
            saida_cfg.setdefault("pasta", "Mapas")
            saida_cfg.setdefault("nome_base", "layout_preview")

            guard = WorkspaceGuard(ws_root)
            pdf_path, _ = gerar_pdf_minimo(ms, guard=guard, fontes_idx={})

            if not pdf_path.exists() or not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                return _erro("LAY-002", "Falha na renderização: arquivo PDF não gerado no disco.")

            # Gera preview rasterizado real usando PyMuPDF
            import pymupdf

            doc = pymupdf.open(str(pdf_path))
            if len(doc) == 0:
                doc.close()
                return _erro("LAY-002", "PDF gerado está vazio.")

            pag = doc[0]
            pix = pag.get_pixmap(dpi=150)
            pasta_previews = ws_root / "Mapas" / "previews"
            pasta_previews.mkdir(parents=True, exist_ok=True)
            preview_arq = pasta_previews / f"{pdf_path.stem}.png"
            pix.save(str(preview_arq))
            doc.close()

            if not preview_arq.exists() or not preview_arq.is_file():
                return _erro("LAY-003", "Falha na geração do arquivo de preview no disco.")

            preview_rel = preview_arq.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.preview", {"caminho": preview_rel, "pagina": 1})

            return _ok(
                {
                    "status": "renderizado",
                    "caminho_pdf": pdf_path.relative_to(ws_root).as_posix(),
                    "preview": preview_rel,
                    "tamanho_bytes": pdf_path.stat().st_size,
                    "formato": formato,
                }
            )
        except Exception as exc:
            return _erro("LAY-002", f"Falha na renderização real do layout: {exc}")
