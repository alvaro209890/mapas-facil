# Catálogo de tools tipadas do agente (F1-06 / G5).

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.conversas.redator import redigir
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria import servico as galeria_servico
from mapasfacil_nucleo.mapspec.validar import validar as validar_mapspec_fn
from mapasfacil_nucleo.workspace import servico as workspace_servico

HandlerTool = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _ok(dados: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **dados}


def _erro(codigo: str, mensagem: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "codigo": codigo, "mensagem": mensagem, **extra}


def _indice() -> dict[str, Any] | None:
    estado = workspace_servico.estado_atual()
    return None if estado is None else estado.indice


def _recibo() -> dict[str, Any] | None:
    estado = workspace_servico.estado_atual()
    if estado is None:
        return None
    return getattr(estado, "recibo", None)


def _relativo(caminho: str, raiz: str) -> str:
    try:
        return str(Path(caminho).resolve().relative_to(Path(raiz).resolve()))
    except Exception:
        return Path(caminho).name


# --------------------------------------------------------------------------- handlers


def tool_estado_do_projeto(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del args
    memoria = ctx.get("memoria_trabalho") or montar_memoria_trabalho(ctx.get("mapspec"))
    return _ok({"memoria": memoria})


def tool_listar_arquivos(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    indice = _indice()
    if indice is None:
        return _erro("NU-040", "Nenhuma pasta conectada. Use workspace.abrir primeiro.")
    tipo = args.get("tipo")
    papel = args.get("papel")
    itens: list[dict[str, Any]] = []
    for shp in indice.get("shapefiles") or []:
        if tipo and tipo not in ("shp", "shapefile"):
            continue
        if papel and shp.get("papel") != papel:
            continue
        itens.append(
            {
                "nome": Path(shp.get("caminho", "")).name,
                "tipo": "shapefile",
                "papel": shp.get("papel"),
                "area_ha": shp.get("area_ha"),
            }
        )
    for pdf in indice.get("pdfs") or []:
        if tipo and tipo != "pdf":
            continue
        itens.append({"nome": Path(pdf.get("caminho", "")).name, "tipo": "pdf", "papel": None})
    if limites.indice_precisa_resumo(len(itens)):
        por_tipo: dict[str, int] = {}
        for i in itens:
            por_tipo[i["tipo"]] = por_tipo.get(i["tipo"], 0) + 1
        return _ok({"resumo_por_tipo": por_tipo, "total": len(itens), "amostra": itens[:20]})
    return _ok({"arquivos": itens, "total": len(itens)})


def tool_inspecionar_shapefile(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del ctx
    nome = args.get("arquivo") or args.get("id_local")
    if not isinstance(nome, str) or not nome:
        return _erro("NU-001", "Parâmetro 'arquivo' ou 'id_local' é obrigatório.")
    indice = _indice()
    if indice is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    alvo = None
    for shp in indice.get("shapefiles") or []:
        if shp.get("id_local") == nome or Path(shp.get("caminho", "")).stem == nome:
            alvo = shp
            break
        if Path(shp.get("caminho", "")).name == nome:
            alvo = shp
            break
    if alvo is None:
        return _erro("NU-041", f"Shapefile não encontrado: {nome}")
    return _ok(
        {
            "id_local": alvo.get("id_local"),
            "feicoes": alvo.get("feicoes"),
            "campos": [{"nome": c, "tipo": "desconhecido"} for c in (alvo.get("campos") or [])][:40],
            "crs": alvo.get("crs"),
            "bbox_arredondado": alvo.get("bbox"),
            "area_ha": alvo.get("area_ha"),
            "valido": not bool(alvo.get("avisos")),
            "avisos": [{"codigo": a.get("codigo"), "mensagem": a.get("mensagem")} for a in (alvo.get("avisos") or [])],
        }
    )


def tool_ler_recibo_car(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del args, ctx
    recibo = _recibo()
    if not recibo:
        return _erro("NU-042", "Recibo do CAR não encontrado na pasta.")
    # CPF já é descartado pelo parser; redigir por segurança
    limpo = json.loads(redigir(json.dumps(recibo, ensure_ascii=False)))
    limpo.pop("cpf", None)
    limpo.pop("texto_integral", None)
    return _ok({"recibo": limpo})


def tool_listar_modelos_galeria(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del args, ctx
    lista = galeria_servico.listar({})
    modelos = [
        {
            "id": m["id"],
            "nome": m["nome"],
            "tags": m.get("tags", []),
            "status": m["status"],
            "motivo": m.get("motivo"),
        }
        for m in lista.get("modelos", [])[:20]
    ]
    return _ok({"modelos": modelos})


def tool_usar_modelo_da_galeria(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    modelo_id = args.get("modelo_id")
    if not isinstance(modelo_id, str) or not modelo_id:
        return _erro("NU-001", "Parâmetro 'modelo_id' é obrigatório.")
    sobrescritas = args.get("sobrescritas") if isinstance(args.get("sobrescritas"), dict) else None
    try:
        pacote = galeria_servico.montar(
            {"modelo_id": modelo_id, "sobrescritas": sobrescritas or {}}
        )
    except ErroNucleo as exc:
        return _erro(exc.codigo, exc.mensagem, detalhes=exc.detalhes)
    ctx["mapspec"] = pacote.get("mapspec")
    ctx["mapspec_origem"] = "galeria"
    ctx["modelo_id"] = modelo_id
    return _ok(
        {
            "mapspec_id": pacote["mapspec"].get("id"),
            "template": pacote["mapspec"].get("template"),
            "camadas": [c.get("id") for c in pacote["mapspec"].get("camadas") or []],
            "elementos_layout": pacote["mapspec"].get("elementos_layout"),
            "avisos": pacote.get("avisos", []),
        }
    )


def tool_validar_mapspec(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    mapspec = args.get("mapspec") or ctx.get("mapspec")
    if not isinstance(mapspec, dict):
        return _erro("NU-201", "Não há MapSpec para validar.")
    fontes = None
    indice = _indice()
    if indice and indice.get("fontes_locais"):
        fontes = frozenset(indice["fontes_locais"])
    resultado = validar_mapspec_fn(mapspec, fontes_locais=fontes)
    return _ok(resultado)


def tool_criar_mapa(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Só quando nenhum modelo da galeria serve — preferir usar_modelo_da_galeria."""
    template = args.get("template")
    if not isinstance(template, str) or not template:
        return _erro("NU-001", "Parâmetro 'template' é obrigatório.")
    return _erro(
        "IA-021",
        "criar_mapa ainda é esqueleto nesta versão; use usar_modelo_da_galeria quando houver modelo.",
        template=template,
    )


def _stub(nome: str) -> HandlerTool:
    def _fn(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        del args, ctx
        return _erro(
            "IA-022",
            f"Tool '{nome}' registrada mas ainda sem implementação completa nesta versão.",
        )

    return _fn


def montar_memoria_trabalho(mapspec: dict[str, Any] | None = None) -> dict[str, Any]:
    indice = _indice()
    recibo = _recibo()
    pasta = None
    if indice and indice.get("raiz"):
        pasta = Path(indice["raiz"]).name
    papeis: dict[str, int] = {}
    for shp in (indice or {}).get("shapefiles") or []:
        papel = shp.get("papel") or "outro"
        papeis[papel] = papeis.get(papel, 0) + 1
    imovel = None
    if recibo:
        imovel = {
            "nome": recibo.get("nome_imovel") or recibo.get("imovel"),
            "car": recibo.get("numero_car") or recibo.get("car"),
            "municipio": recibo.get("municipio"),
            "uf": recibo.get("uf") or "MT",
            "area_total_ha": recibo.get("area_total_ha"),
        }
    mapspec_atual = None
    if mapspec:
        mapspec_atual = {
            "id": mapspec.get("id"),
            "versao": mapspec.get("versao"),
            "template": mapspec.get("template"),
            "camadas": len(mapspec.get("camadas") or []),
        }
    memoria = {
        "pasta": pasta,
        "imovel": imovel,
        "papeis": papeis,
        "mapspec_atual": mapspec_atual,
        "mapas_gerados": [],
        "avisos_abertos": [],
    }
    # garante teto
    texto = json.dumps(memoria, ensure_ascii=False, sort_keys=True)
    if limites.excede_memoria_trabalho(limites.estimar_tokens(texto)):
        memoria = {"pasta": pasta, "papeis": papeis, "mapspec_atual": mapspec_atual}
    return memoria


# Nomes oficiais F1-06 (26 tools)
_HANDLERS: dict[str, HandlerTool] = {
    "estado_do_projeto": tool_estado_do_projeto,
    "listar_arquivos": tool_listar_arquivos,
    "inspecionar_shapefile": tool_inspecionar_shapefile,
    "ler_recibo_car": tool_ler_recibo_car,
    "listar_zip": _stub("listar_zip"),
    "listar_catalogo": _stub("listar_catalogo"),
    "consultar_sema": _stub("consultar_sema"),
    "distancia_ate": _stub("distancia_ate"),
    "calcular_quantitativos": _stub("calcular_quantitativos"),
    "listar_modelos_galeria": tool_listar_modelos_galeria,
    "usar_modelo_da_galeria": tool_usar_modelo_da_galeria,
    "criar_mapa": tool_criar_mapa,
    "definir_imovel": _stub("definir_imovel"),
    "adicionar_camada": _stub("adicionar_camada"),
    "remover_camada": _stub("remover_camada"),
    "editar_camada": _stub("editar_camada"),
    "definir_basemap": _stub("definir_basemap"),
    "definir_escala": _stub("definir_escala"),
    "definir_tabela": _stub("definir_tabela"),
    "editar_metadados": _stub("editar_metadados"),
    "alternar_elemento": _stub("alternar_elemento"),
    "definir_titulo": _stub("definir_titulo"),
    "validar_mapspec": tool_validar_mapspec,
    "gerar_mapa": _stub("gerar_mapa"),
    "gerar_planilha": _stub("gerar_planilha"),
    "analisar_referencia": _stub("analisar_referencia"),
    "comparar_com_modelo": _stub("comparar_com_modelo"),
}


def nomes_tools() -> list[str]:
    return sorted(_HANDLERS)


def schemas_openai() -> list[dict[str, Any]]:
    """Schemas mínimos para tool calling (nome + descrição curta)."""
    descricoes = {
        "estado_do_projeto": "Resumo estruturado da pasta, imóvel e MapSpec atual.",
        "listar_arquivos": "Lista shapefiles/PDFs da pasta (nome relativo, tipo, papel, área).",
        "inspecionar_shapefile": "Metadados de um shapefile sem geometria/WKT.",
        "ler_recibo_car": "Dados do recibo do CAR sem CPF.",
        "listar_modelos_galeria": "Modelos da galeria com status.",
        "usar_modelo_da_galeria": "Monta MapSpec a partir de um modelo da galeria.",
        "criar_mapa": "Novo MapSpec a partir de template — só se nenhum modelo servir.",
        "validar_mapspec": "Valida o MapSpec atual sem gerar artefatos.",
    }
    schemas = []
    for nome in nomes_tools():
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": nome,
                    "description": descricoes.get(nome, f"Tool {nome} do Mapas Fácil."),
                    "parameters": {"type": "object", "additionalProperties": True},
                },
            }
        )
    return schemas


def executar(nome: str, argumentos: dict[str, Any] | str, ctx: dict[str, Any]) -> dict[str, Any]:
    handler = _HANDLERS.get(nome)
    if handler is None:
        return _erro(
            limites.CODIGO_TOOL_INEXISTENTE,
            f"Tool inexistente: {nome}",
            tools_validas=nomes_tools(),
        )
    if isinstance(argumentos, str):
        try:
            argumentos = json.loads(argumentos) if argumentos.strip() else {}
        except json.JSONDecodeError:
            return _erro("NU-001", "Argumentos da tool não são JSON válido.")
    if not isinstance(argumentos, dict):
        argumentos = {}
    resultado = handler(argumentos, ctx)
    # envelope truncado
    texto = json.dumps(resultado, ensure_ascii=False, sort_keys=True)
    trunc = limites.truncar_resultado_tool(texto, ponteiro=f"tool:{nome}")
    if trunc["truncado"]:
        return {
            "ok": resultado.get("ok", True),
            "truncado": True,
            "conteudo": trunc["conteudo"],
            "ponteiro": trunc["ponteiro"],
        }
    return resultado
