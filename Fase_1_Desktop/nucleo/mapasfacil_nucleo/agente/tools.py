# Catálogo de tools tipadas do agente (F1-06 / G5).
#
# Contrato de todas elas: entrada validada na própria tool, saída **resumo
# tipado** — nunca geometria, WKT, caminho absoluto, CPF ou blob (AP-06 / AP-09).
# Tool que altera o mapa cria uma nova versão via `agente/edicao.py`.

from __future__ import annotations

import copy
import difflib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.edicao import EdicaoInvalida, descrever_diff, nova_versao, resumo_versao
from mapasfacil_nucleo.agente.visao import servico as visao_servico
from mapasfacil_nucleo.camadas import clip as clip_camadas
from mapasfacil_nucleo.camadas.resolver import resolver_camada
from mapasfacil_nucleo.config import ESCALAS_PERMITIDAS, caminho_shared, modo_servidor, pasta_saida
from mapasfacil_nucleo.mapspec.migrar import CONTRACT_ATUAL
from mapasfacil_nucleo.motores.folhas import folha_do_template, folha_padrao
from mapasfacil_nucleo.conversas.redator import redigir
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.galeria import servico as galeria_servico
from mapasfacil_nucleo.geo import area as geo_area
from mapasfacil_nucleo.geo.distancia import distancia_minima_km
from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
from mapasfacil_nucleo.mapspec.validar import ESTILOS_PERMITIDOS, OPERADORES_FILTRO
from mapasfacil_nucleo.mapspec.validar import validar as validar_mapspec_fn
from mapasfacil_nucleo.motores.manifesto import listar_templates, obter_template
from mapasfacil_nucleo.protocolo import novo_id
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos_fn
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace.shapefile import ler_geometrias_e_epsg
from mapasfacil_nucleo.workspace.zip_simcar import listar as zip_listar

HandlerTool = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

# Elementos de layout do perfil Harmonia (F1-05 §layout / galeria).
ELEMENTOS_LAYOUT = frozenset(
    {
        "titulo_caixa",
        "norte",
        "grade",
        "grade_linhas",
        "escala_grafica",
        "minimapa",
        "metadados",
        "legenda",
        "logo",
        "tabela",
        "creditos",
    }
)

CODIGO_CATALOGO = limites.CODIGO_TOOL_INEXISTENTE  # IA-020 — item fora do catálogo
CODIGO_DEPENDENCIA = "IA-022"  # tool registrada cuja dependência ainda não existe


def _ok(dados: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **dados}


def _erro(codigo: str, mensagem: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "codigo": codigo, "mensagem": mensagem, **extra}


def _erro_dependencia(nome: str, depende_de: str) -> dict[str, Any]:
    return _erro(
        CODIGO_DEPENDENCIA,
        f"'{nome}' ainda não está disponível nesta versão: depende de {depende_de}. "
        "Siga sem ela e diga isso ao usuário.",
        depende_de=depende_de,
    )


def _sugerir(valor: str, universo) -> str | None:
    """Item mais próximo do catálogo — o modelo erra por variação, não por invenção.

    Além da distância de edição, casa por prefixo: "avn_roxo_listrado" tem de
    sugerir "avn", e a razão de similaridade sozinha não pega isso.
    """
    alvo = str(valor or "").strip().lower()
    if not alvo:
        return None
    candidatos = sorted(str(u) for u in universo)
    prox = difflib.get_close_matches(alvo, candidatos, n=1, cutoff=0.5)
    if prox:
        return prox[0]
    por_prefixo = [c for c in candidatos if alvo.startswith(c.lower()) or c.lower().startswith(alvo)]
    if por_prefixo:
        return max(por_prefixo, key=len)
    return None


def _estado():
    return workspace_servico.estado_atual()


def _indice() -> dict[str, Any] | None:
    estado = _estado()
    return None if estado is None else estado.indice


def _recibo() -> dict[str, Any] | None:
    estado = _estado()
    if estado is None:
        return None
    return getattr(estado, "recibo", None)


def _mapspec_do_ctx(ctx: dict[str, Any]) -> dict[str, Any] | None:
    mapspec = ctx.get("mapspec")
    return mapspec if isinstance(mapspec, dict) else None


def _fontes_locais() -> frozenset[str] | None:
    indice = _indice()
    if indice and indice.get("fontes_locais"):
        return frozenset(indice["fontes_locais"])
    return None


def _projeto_do_servidor() -> dict[str, Any] | None:
    """Nome e folha do projeto do site (modo servidor). `None` no desktop."""
    from mapasfacil_nucleo import projeto_servidor

    return projeto_servidor.para_memoria()


@lru_cache(maxsize=1)
def _catalogo_camadas() -> tuple[dict[str, Any], ...]:
    caminho = caminho_shared("catalog", "camadas.json")
    with caminho.open(encoding="utf-8") as fh:
        return tuple(json.load(fh).get("camadas") or [])


def _ids_catalogo() -> frozenset[str]:
    return frozenset(str(c.get("id")) for c in _catalogo_camadas())


# --------------------------------------------------------------------------- contexto


def tool_estado_do_projeto(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del args
    memoria = ctx.get("memoria_trabalho") or montar_memoria_trabalho(_mapspec_do_ctx(ctx))
    return _ok({"memoria": memoria})


def tool_listar_arquivos(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del ctx
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
                "id_local": shp.get("id_local"),
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
        caminho = shp.get("caminho", "")
        if shp.get("id_local") == nome or Path(caminho).stem == nome or Path(caminho).name == nome:
            alvo = shp
            break
    if alvo is None:
        conhecidos = [s.get("id_local") for s in indice.get("shapefiles") or [] if s.get("id_local")]
        return _erro(
            "NU-041",
            f"Shapefile não encontrado: {nome}",
            sugestao=_sugerir(nome, conhecidos),
            disponiveis=conhecidos[:20],
        )
    return _ok(
        {
            "id_local": alvo.get("id_local"),
            "feicoes": alvo.get("feicoes"),
            "campos": [{"nome": c, "tipo": "desconhecido"} for c in (alvo.get("campos") or [])][:40],
            "crs": alvo.get("crs"),
            "bbox_arredondado": alvo.get("bbox"),
            "area_ha": alvo.get("area_ha"),
            "valido": not bool(alvo.get("avisos")),
            "avisos": [
                {"codigo": a.get("codigo"), "mensagem": a.get("mensagem")}
                for a in (alvo.get("avisos") or [])
            ],
        }
    )


def tool_ler_recibo_car(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    del args, ctx
    recibo = _recibo()
    if not recibo:
        return _erro("NU-042", "Recibo do CAR não encontrado na pasta.")
    # CPF já é descartado pelo parser; redigir por segurança (AP-09)
    limpo = json.loads(redigir(json.dumps(recibo, ensure_ascii=False)))
    limpo.pop("cpf", None)
    limpo.pop("texto_integral", None)
    return _ok({"recibo": limpo})


def tool_listar_zip(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Conteúdo de um `.zip` do SIMCAR sem extrair — só nomes e tamanhos."""
    del ctx
    caminho = args.get("arquivo") or args.get("caminho")
    if not isinstance(caminho, str) or not caminho:
        return _erro("NU-001", "Parâmetro 'arquivo' é obrigatório (caminho relativo à pasta).")
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    try:
        dados = zip_listar(estado.guard.resolver(caminho))
    except ErroNucleo as exc:
        return _erro(exc.codigo, exc.mensagem)
    entradas = [{"nome": e["caminho"], "tamanho": e["tamanho"]} for e in dados.get("entradas") or []]
    return _ok(
        {
            "arquivo": Path(caminho).name,
            "total": dados.get("total", len(entradas)),
            "shapefiles": [Path(s).name for s in dados.get("shapefiles") or []],
            "entradas": entradas[:30],
            "entradas_omitidas": max(0, len(entradas) - 30),
        }
    )


def tool_listar_catalogo(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Camadas, estilos e templates disponíveis — paginado em ≤ 30 itens (AP-06)."""
    del ctx
    tema = args.get("tema")
    try:
        pagina = max(1, int(args.get("pagina") or 1))
    except (TypeError, ValueError):
        return _erro("NU-001", "Parâmetro 'pagina' deve ser inteiro.")
    camadas = [
        {"id": c["id"], "nome": c.get("nome"), "tema": c.get("tema"), "tipo": c.get("tipo")}
        for c in _catalogo_camadas()
        if not tema or c.get("tema") == tema
    ]
    inicio = (pagina - 1) * 30
    fatia = camadas[inicio : inicio + 30]
    return _ok(
        {
            "camadas": fatia,
            "pagina": pagina,
            "total_camadas": len(camadas),
            "tem_mais": inicio + 30 < len(camadas),
            "temas": sorted({str(c.get("tema")) for c in _catalogo_camadas() if c.get("tema")}),
            "estilos": sorted(ESTILOS_PERMITIDOS),
            "templates": [t["id"] for t in listar_templates()],
            "escalas": sorted(ESCALAS_PERMITIDAS),
        }
    )


def tool_calcular_quantitativos(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Matriz classe × hectare a partir das camadas locais — nunca o overlay bruto."""
    del args
    mapspec = _mapspec_do_ctx(ctx)
    if mapspec is None:
        return _erro("NU-201", "Não há MapSpec. Use usar_modelo_da_galeria ou criar_mapa antes.")
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    dados = calcular_quantitativos_fn(
        mapspec,
        guard=estado.guard,
        fontes_idx=workspace_servico.fontes_idx(estado),
    )
    return _ok(
        {
            "areas_ha": dados.get("areas"),
            "colunas": dados.get("colunas"),
            "linhas": dados.get("linhas"),
            "total_geral_ha": dados.get("total_geral"),
            "avisos": (dados.get("avisos") or [])[:10],
        }
    )


# --------------------------------------------------------------------------- galeria


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
    from mapasfacil_nucleo.galeria.montar import montar_mapspec

    modelo_id = args.get("modelo_id")
    if not isinstance(modelo_id, str) or not modelo_id:
        return _erro("NU-001", "Parâmetro 'modelo_id' é obrigatório.")
    sobrescritas = args.get("sobrescritas") if isinstance(args.get("sobrescritas"), dict) else None
    try:
        pacote = montar_mapspec(modelo_id, sobrescritas=sobrescritas or {})
    except ErroNucleo as exc:
        return _erro(exc.codigo, exc.mensagem, detalhes=exc.detalhes)
    novo = pacote.get("mapspec")
    ctx["mapspec"] = novo
    ctx["mapspec_origem"] = "galeria"
    ctx["modelo_id"] = modelo_id
    if isinstance(novo, dict):
        _emitir_mapspec_atualizado(ctx, novo, mapspec_diff({}, novo))
    return _ok(
        {
            "mapspec_id": pacote["mapspec"].get("id"),
            "template": pacote["mapspec"].get("template"),
            "camadas": [c.get("id") for c in pacote["mapspec"].get("camadas") or []],
            "elementos_layout": pacote["mapspec"].get("elementos_layout"),
            "avisos": pacote.get("avisos", []),
        }
    )


# --------------------------------------------------------------------------- edição


def _emitir_pergunta(
    ctx: dict[str, Any],
    *,
    pergunta: str,
    opcoes: list[dict[str, str]],
    permite_texto_livre: bool = True,
    motivo: str = "",
) -> dict[str, Any]:
    """Emite pergunta estruturada via tool_perguntar (D40 / W5-21)."""
    return tool_perguntar(
        {
            "pergunta": pergunta,
            "opcoes": opcoes,
            "permitir_texto": permite_texto_livre,
            "motivo": motivo,
        },
        ctx,
    )


def _emitir_mapspec_atualizado(
    ctx: dict[str, Any], mapspec: dict[str, Any], diff: dict[str, Any]
) -> None:
    """`mapspec.atualizado` (H6/A6) — troca de versão na UI. Sem `Emissor`, não-op.

    Payload fechado em F1-01/F1-16: `{id, versao, diff}`. `diff` carrega as
    operações estruturadas de `mapspec.diff` **e** o resumo em português de
    `edicao.descrever_diff` — a UI usa as operações para achar a linha que mudou
    e o resumo para o texto. Nunca geometria/WKT/CPF (AP-06/AP-09): o `MapSpec`
    já não guarda nenhum dos dois, e o diff só compara os campos dele.
    """
    emissor = ctx.get("emissor")
    if emissor is None:
        return
    emissor.emitir(
        "mapspec.atualizado",
        {
            "id": mapspec.get("id"),
            "versao": mapspec.get("versao"),
            "diff": {**diff, "resumo": descrever_diff(diff)},
        },
    )


def _editar(ctx: dict[str, Any], mutar: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Aplica uma edição versionada sobre o MapSpec do contexto."""
    mapspec = _mapspec_do_ctx(ctx)
    if mapspec is None:
        return _erro(
            "NU-201",
            "Não há MapSpec nesta conversa. Use usar_modelo_da_galeria (preferido) ou criar_mapa.",
        )
    try:
        novo, diff = nova_versao(mapspec, mutar, fontes_locais=_fontes_locais())
    except EdicaoInvalida as exc:
        return _erro(
            "NU-201",
            "A edição deixaria o MapSpec inválido; a versão anterior continua valendo.",
            erros=exc.erros[:5],
        )
    ctx["mapspec"] = novo
    _emitir_mapspec_atualizado(ctx, novo, diff)
    return _ok(resumo_versao(novo, diff))


def tool_criar_mapa(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Novo MapSpec a partir de um template — só quando nenhum modelo da galeria serve."""
    template = args.get("template")
    if not isinstance(template, str) or not template:
        return _erro("NU-001", "Parâmetro 'template' é obrigatório.")
    ids_template = [t["id"] for t in listar_templates()]
    if template not in ids_template:
        return _erro(
            CODIGO_CATALOGO,
            f"Template desconhecido: {template}",
            sugestao=_sugerir(template, ids_template),
            templates=ids_template,
        )
    tpl = obter_template(template)

    indice = _indice()
    if indice is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    shapefiles = indice.get("shapefiles") or []
    perimetro = next((s for s in shapefiles if s.get("papel") == "ATP"), None)
    if perimetro is None:
        if not shapefiles:
            return _erro(
                "NU-233",
                "A pasta não tem shapefile com papel ATP (perímetro) — sem ele não dá para criar o mapa.",
            )
        # Nome não bate com nenhum alias/heurística conhecido (workspace/papeis.py):
        # em vez de travar ou chutar, pergunta ao usuário qual arquivo é o perímetro.
        candidatos = [
            {"id": s["id_local"], "rotulo": Path(s["caminho"]).name} for s in shapefiles
        ]
        _emitir_pergunta(
            ctx,
            pergunta=(
                "Não reconheci automaticamente qual shapefile é o perímetro do imóvel "
                "(papel ATP). Qual desses arquivos é ele?"
            ),
            opcoes=candidatos,
            motivo="perimetro_nao_reconhecido",
        )
        return _erro(
            "NU-233",
            "Não encontrei o perímetro (ATP) automaticamente. Já perguntei ao usuário pelas "
            "opções no chat — não escolha por conta própria, espere a resposta dele antes de "
            "tentar de novo.",
            opcoes=candidatos,
        )

    recibo = _recibo() or {}
    nome_imovel = recibo.get("nome_imovel") or recibo.get("imovel") or "Imovel"
    fonte = f"local.{perimetro.get('id_local')}"
    titulo = args.get("titulo") if isinstance(args.get("titulo"), str) else None
    mapspec: dict[str, Any] = {
        "contract_version": CONTRACT_ATUAL,
        "perfil": "harmonia",
        "id": novo_id(),
        "versao": 1,
        "parent_id": None,
        "titulo": titulo or nome_imovel,
        "template": template,
        "folha": folha_do_template(template) or folha_padrao(),
        "saidas": ["pdf"],
        "imovel": {
            "nome": nome_imovel,
            "car": recibo.get("car_estadual") or recibo.get("car"),
            "matricula": None,
            "area_total_ha": recibo.get("area_total_ha"),
            "municipio": {
                "nome": recibo.get("municipio") or "Desconhecido",
                "uf": (recibo.get("uf") or "MT")[:2],
            },
            "geometria": fonte,
        },
        "crs": tpl.get("crs_data_frame") or "EPSG:31982",
        "escala": "auto",
        "extent": None,
        "camadas": [
            {
                "id": "perimetro",
                "nome_no_mxd": nome_imovel,
                "fonte": fonte,
                "estilo": "perimetro_imovel",
                "legenda": nome_imovel,
                "ordem": 10,
            }
        ],
        "elementos_layout": {"titulo_caixa": True, "norte": True, "legenda": True},
        "metadados": [],
        "tabela": None,
        "saida": {"pasta": pasta_saida(versao=1), "nome_base": "Mapa"},
    }
    resultado = validar_mapspec_fn(mapspec, fontes_locais=_fontes_locais())
    if not resultado["valido"]:
        return _erro(
            "NU-201",
            "Não consegui montar um MapSpec válido a partir deste template.",
            erros=resultado["erros"][:5],
        )
    ctx["mapspec"] = mapspec
    ctx["mapspec_origem"] = "criar_mapa"
    _emitir_mapspec_atualizado(ctx, mapspec, mapspec_diff({}, mapspec))
    return _ok(
        {
            "mapspec_id": mapspec["id"],
            "template": template,
            "camadas": ["perimetro"],
            "aviso": "Criado do zero. Se existir modelo equivalente na galeria, prefira o modelo.",
        }
    )


def tool_definir_imovel(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    campos = {k: args[k] for k in ("nome", "car", "matricula", "area_total_ha") if k in args}
    municipio = args.get("municipio")
    uf = args.get("uf")
    if not campos and not municipio and not uf:
        return _erro("NU-001", "Informe ao menos um campo do imóvel para alterar.")

    def mutar(spec: dict[str, Any]) -> None:
        imovel = spec.setdefault("imovel", {})
        imovel.update(campos)
        if municipio or uf:
            bloco = imovel.setdefault("municipio", {})
            if municipio:
                bloco["nome"] = municipio
            if uf:
                bloco["uf"] = str(uf)[:2].upper()

    return _editar(ctx, mutar)


def tool_adicionar_camada(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    fonte = args.get("fonte")
    estilo = args.get("estilo")
    nome_no_mxd = args.get("nome_no_mxd")
    if not isinstance(fonte, str) or not fonte:
        return _erro("NU-001", "Parâmetro 'fonte' é obrigatório (local.X ou catalogo.Y).")
    if not isinstance(nome_no_mxd, str) or not nome_no_mxd:
        return _erro("NU-001", "Parâmetro 'nome_no_mxd' é obrigatório.")
    for erro in (_conferir_estilo(estilo), _conferir_fonte(fonte)):
        if erro:
            return erro
    filtro = args.get("filtro")
    if filtro is not None:
        erro_filtro = _conferir_filtro(filtro)
        if erro_filtro:
            return erro_filtro

    camada: dict[str, Any] = {
        "id": args.get("id") or fonte.split(".", 1)[-1].lower(),
        "nome_no_mxd": nome_no_mxd,
        "fonte": fonte,
        "estilo": estilo,
        "legenda": args.get("legenda") or nome_no_mxd,
        "ordem": int(args.get("ordem") or 50),
    }
    if isinstance(args.get("rotulo_texto"), str):
        camada["rotulo_texto"] = args["rotulo_texto"]
    if filtro is not None:
        camada["filtro"] = filtro

    def mutar(spec: dict[str, Any]) -> None:
        camadas = spec.setdefault("camadas", [])
        if any(c.get("id") == camada["id"] for c in camadas):
            camada["id"] = f"{camada['id']}_{len(camadas) + 1}"
        camadas.append(camada)
        camadas.sort(key=lambda c: int(c.get("ordem") or 0))

    return _editar(ctx, mutar)


def _camada_existente(ctx: dict[str, Any], camada_id: Any) -> dict[str, Any] | None:
    """Devolve o erro tipado quando o id não existe no MapSpec; `None` se existe."""
    if not isinstance(camada_id, str) or not camada_id:
        return _erro("NU-001", "Parâmetro 'id' é obrigatório.")
    mapspec = _mapspec_do_ctx(ctx)
    if mapspec is None:
        return _erro("NU-201", "Não há MapSpec nesta conversa.")
    ids = [c.get("id") for c in mapspec.get("camadas") or []]
    if camada_id not in ids:
        return _erro(
            CODIGO_CATALOGO,
            f"Camada inexistente no MapSpec: {camada_id}",
            sugestao=_sugerir(camada_id, [i for i in ids if i]),
            camadas=ids,
        )
    return None


def tool_remover_camada(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    camada_id = args.get("id") or args.get("camada_id")
    erro = _camada_existente(ctx, camada_id)
    if erro:
        return erro
    mapspec = _mapspec_do_ctx(ctx) or {}
    if len(mapspec.get("camadas") or []) <= 1:
        return _erro("NU-201", "O MapSpec ficaria sem camada nenhuma; remoção recusada.")

    def mutar(spec: dict[str, Any]) -> None:
        spec["camadas"] = [c for c in spec.get("camadas") or [] if c.get("id") != camada_id]

    return _editar(ctx, mutar)


def tool_editar_camada(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    camada_id = args.get("id") or args.get("camada_id")
    erro = _camada_existente(ctx, camada_id)
    if erro:
        return erro
    if "estilo" in args:
        erro_estilo = _conferir_estilo(args.get("estilo"))
        if erro_estilo:
            return erro_estilo
    if args.get("filtro") is not None:
        erro_filtro = _conferir_filtro(args["filtro"])
        if erro_filtro:
            return erro_filtro

    def mutar(spec: dict[str, Any]) -> None:
        for camada in spec.get("camadas") or []:
            if camada.get("id") != camada_id:
                continue
            for chave in ("estilo", "legenda", "rotulo_texto", "nome_no_mxd"):
                if chave in args:
                    camada[chave] = args[chave]
            if "ordem" in args:
                camada["ordem"] = int(args["ordem"])
            if "filtro" in args:
                if args["filtro"] is None:
                    camada.pop("filtro", None)
                else:
                    camada["filtro"] = args["filtro"]
        (spec.get("camadas") or []).sort(key=lambda c: int(c.get("ordem") or 0))

    return _editar(ctx, mutar)


def tool_definir_basemap(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    tipo = args.get("tipo")
    if not isinstance(tipo, str) or not tipo:
        return _erro("NU-001", "Parâmetro 'tipo' é obrigatório.")

    def mutar(spec: dict[str, Any]) -> None:
        basemap = spec.setdefault("basemap", {})
        basemap["tipo"] = tipo
        if isinstance(args.get("mosaico"), str):
            basemap["mosaico"] = args["mosaico"]

    return _editar(ctx, mutar)


def tool_definir_escala(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    escala = args.get("escala")
    if escala == "auto":
        valor: Any = "auto"
    else:
        try:
            valor = int(escala)
        except (TypeError, ValueError):
            return _erro("NU-001", 'Parâmetro "escala" deve ser inteiro da lista ou "auto".')
        if valor not in ESCALAS_PERMITIDAS:
            return _erro(
                CODIGO_CATALOGO,
                f"Escala fora da lista permitida: 1:{valor}",
                escalas=sorted(ESCALAS_PERMITIDAS),
            )

    def mutar(spec: dict[str, Any]) -> None:
        spec["escala"] = valor

    return _editar(ctx, mutar)


def tool_definir_tabela(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    colunas = args.get("colunas")
    if colunas is not None and (
        not isinstance(colunas, list) or not all(isinstance(c, str) for c in colunas)
    ):
        return _erro("NU-001", "Parâmetro 'colunas' deve ser lista de textos.")

    def mutar(spec: dict[str, Any]) -> None:
        tabela = spec.get("tabela")
        if not isinstance(tabela, dict):
            tabela = {"colunas": list(colunas or []), "linhas": []}
            spec["tabela"] = tabela
        if colunas is not None:
            tabela["colunas"] = list(colunas)
        if "total_geral" in args:
            tabela["total_geral"] = bool(args["total_geral"])
        if "casas_decimais" in args:
            tabela["casas_decimais"] = max(0, min(6, int(args["casas_decimais"])))
        if "titulo_bloco" in args:
            tabela["titulo_bloco"] = args["titulo_bloco"]

    return _editar(ctx, mutar)


def tool_editar_metadados(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    acao = args.get("acao") or "definir"
    rotulo = args.get("rotulo")
    if not isinstance(rotulo, str) or not rotulo:
        return _erro("NU-001", "Parâmetro 'rotulo' é obrigatório.")
    if acao not in ("definir", "remover"):
        return _erro("NU-001", "Parâmetro 'acao' deve ser 'definir' ou 'remover'.")
    valor = args.get("valor")
    if acao == "definir" and not isinstance(valor, str):
        return _erro("NU-001", "Parâmetro 'valor' é obrigatório para acao='definir'.")

    def mutar(spec: dict[str, Any]) -> None:
        linhas = spec.setdefault("metadados", [])
        if acao == "remover":
            spec["metadados"] = [m for m in linhas if m.get("rotulo") != rotulo]
            return
        for linha in linhas:
            if linha.get("rotulo") == rotulo:
                linha["valor"] = valor
                return
        linhas.append({"rotulo": rotulo, "valor": valor})

    return _editar(ctx, mutar)


def tool_alternar_elemento(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    elemento = args.get("elemento")
    if not isinstance(elemento, str) or elemento not in ELEMENTOS_LAYOUT:
        return _erro(
            CODIGO_CATALOGO,
            f"Elemento de layout desconhecido: {elemento}",
            sugestao=_sugerir(elemento, ELEMENTOS_LAYOUT),
            elementos=sorted(ELEMENTOS_LAYOUT),
        )
    ligado = args.get("ligado")
    if ligado is not None and not isinstance(ligado, bool):
        return _erro("NU-001", "Parâmetro 'ligado' deve ser booleano.")

    def mutar(spec: dict[str, Any]) -> None:
        elementos = spec.setdefault("elementos_layout", {})
        elementos[elemento] = (not bool(elementos.get(elemento))) if ligado is None else ligado

    return _editar(ctx, mutar)


def tool_definir_titulo(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    titulo = args.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        return _erro("NU-001", "Parâmetro 'titulo' é obrigatório.")

    def mutar(spec: dict[str, Any]) -> None:
        spec["titulo"] = titulo.strip()

    return _editar(ctx, mutar)


def _conferir_estilo(estilo: Any) -> dict[str, Any] | None:
    if not isinstance(estilo, str) or estilo not in ESTILOS_PERMITIDOS:
        return _erro(
            CODIGO_CATALOGO,
            f"Estilo fora do catálogo: {estilo}",
            sugestao=_sugerir(estilo, ESTILOS_PERMITIDOS),
            estilos=sorted(ESTILOS_PERMITIDOS),
        )
    return None


def _conferir_fonte(fonte: str) -> dict[str, Any] | None:
    if fonte.startswith("catalogo."):
        alvo = fonte.split(".", 1)[1]
        if alvo not in _ids_catalogo():
            return _erro(
                CODIGO_CATALOGO,
                f"Camada fora do catálogo: {fonte}",
                sugestao=_sugerir(alvo, _ids_catalogo()),
            )
        return None
    if fonte.startswith("local."):
        fontes = _fontes_locais()
        alvo = fonte.split(".", 1)[1]
        if fontes is not None and alvo not in fontes:
            return _erro(
                CODIGO_CATALOGO,
                f"Fonte local inexistente na pasta: {fonte}",
                sugestao=_sugerir(alvo, fontes),
                fontes=sorted(fontes)[:20],
            )
        return None
    return _erro("NU-001", "Fonte deve começar com 'local.' ou 'catalogo.'.")


def _conferir_filtro(filtro: Any) -> dict[str, Any] | None:
    """Filtro é objeto tipado — SQL livre não existe neste contrato (AP-02)."""
    if not isinstance(filtro, dict):
        return _erro("NU-001", "Filtro deve ser objeto {campo, operador, valor}.")
    if not isinstance(filtro.get("campo"), str) or "valor" not in filtro:
        return _erro("NU-001", "Filtro precisa de 'campo' e 'valor'.")
    if filtro.get("operador") not in OPERADORES_FILTRO:
        return _erro(
            CODIGO_CATALOGO,
            f"Operador de filtro não permitido: {filtro.get('operador')}",
            operadores=sorted(OPERADORES_FILTRO),
        )
    return None


# --------------------------------------------------------------------------- fluxo


def tool_validar_mapspec(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    mapspec = args.get("mapspec") or _mapspec_do_ctx(ctx)
    if not isinstance(mapspec, dict):
        return _erro("NU-201", "Não há MapSpec para validar.")
    return _ok(validar_mapspec_fn(mapspec, fontes_locais=_fontes_locais()))


def tool_gerar_mapa(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Executa o job de geração e devolve artefatos + validação (nunca o PDF em si)."""
    from mapasfacil_nucleo.motores.gerar import gerar_mapa as gerar_mapa_fn
    from mapasfacil_nucleo.progresso import RastreadorProgresso

    mapspec = _mapspec_do_ctx(ctx)
    if mapspec is None:
        return _erro("NU-201", "Não há MapSpec. Use usar_modelo_da_galeria ou criar_mapa antes.")
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")

    # Modo servidor: a pasta de saída é a da versão que o servidor mandou gerar
    # (`MAPASFACIL_VERSAO_SAIDA`), não a que ficou gravada no MapSpec quando ele nasceu —
    # senão toda geração cai em `Mapas/v001` e a segunda sobrescreve a primeira.
    if modo_servidor():
        from mapasfacil_nucleo.config import versao_saida as _versao_saida

        mapspec = copy.deepcopy(mapspec)
        mapspec.setdefault("saida", {})["pasta"] = pasta_saida(versao=_versao_saida())

    saidas = args.get("saidas")
    if saidas is not None:
        if not isinstance(saidas, list) or not saidas:
            return _erro("NU-001", "Parâmetro 'saidas' deve ser lista não vazia.")
        mapspec = {**mapspec, "saidas": list(saidas)}

    emissor = ctx.get("emissor")
    # O job precisa de id também quando a geração vem de uma tool do chat: é o id que amarra
    # os eventos do palco (`viewport.foco`, `camada.renderizada`, `layout.elemento`) ao job —
    # sem ele o palco da web não teria o que animar (W7).
    from mapasfacil_nucleo import jobs as jobs_mod

    job_id = jobs_mod.registrar()
    progresso = RastreadorProgresso(emissor.emitir, job_id=job_id) if emissor is not None else None
    try:
        resultado = gerar_mapa_fn(
            mapspec,
            estado.guard,
            workspace_servico.fontes_idx(estado),
            recibo=_recibo(),
            progresso=progresso,
        )
    finally:
        jobs_mod.liberar(job_id)

    # W5-15: o MapSpec da versão fica gravado ao lado dos artefatos, para
    # `listar_versoes`/`restaurar_versao` funcionarem mesmo depois de o worker morrer.
    pdf = resultado.get("pdf")
    if pdf:
        from pathlib import Path as _Path

        from mapasfacil_nucleo import versoes

        try:
            versoes.salvar_na_pasta(mapspec, _Path(str(pdf)).parent)
        except OSError:
            pass  # não derruba a geração por causa do registro

    validacao = resultado.get("validacao_dados") or {}

    # Revisão visual com autocorreção (Recurso C / W11-13 / D42)
    from mapasfacil_nucleo.validacao.revisao_visual import executar_revisao_completa

    layout_elementos = mapspec.get("elementos_layout_posicionados") or []
    if not layout_elementos and mapspec.get("elementos_layout"):
        for k, v in mapspec["elementos_layout"].items():
            if v:
                layout_elementos.append({"id": k, "tipo": k, "bbox_mm": [10.0, 10.0, 50.0, 30.0]})

    rev_res = executar_revisao_completa(
        mapspec=mapspec,
        layout_elementos=layout_elementos,
        emissor=emissor,
        job_id=job_id,
        folha_largura_mm=210.0,
        folha_altura_mm=297.0,
    )
    if rev_res.get("problemas_restantes"):
        for prob in rev_res["problemas_restantes"]:
            validacao.setdefault("checks", {}).setdefault("soft", []).append(
                {
                    "id": prob["id"],
                    "ok": False,
                    "mensagem": prob["mensagem"],
                    "sugestao": prob.get("sugestao"),
                }
            )
    gerados = ctx.setdefault("mapas_gerados", [])
    artefatos = {
        chave: resultado[chave]
        for chave in ("pdf", "mxd", "xlsx", "png_tabela", "validacao")
        if resultado.get(chave)
    }
    for chave in ("pdf", "xlsx", "png_tabela", "mxd"):
        if resultado.get(chave):
            gerados.append(str(resultado[chave]))
    return _ok(
        {
            "artefatos": artefatos,
            "motor": validacao.get("motor"),
            "confianca": validacao.get("confianca"),
            "avisos": (resultado.get("avisos") or [])[:10],
            "conferencia": resultado.get("conferencia"),
        }
    )


def tool_gerar_planilha(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """`.xlsx` de quantitativos, com o bloco de conferência contra o recibo."""
    del args
    from mapasfacil_nucleo.quantitativos.conferencia import montar_conferencia
    from mapasfacil_nucleo.quantitativos.xlsx import exportar_xlsx

    mapspec = _mapspec_do_ctx(ctx)
    if mapspec is None:
        return _erro("NU-201", "Não há MapSpec. Use usar_modelo_da_galeria ou criar_mapa antes.")
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    dados = calcular_quantitativos_fn(
        mapspec,
        guard=estado.guard,
        fontes_idx=workspace_servico.fontes_idx(estado),
    )
    saida_cfg = mapspec.get("saida") or {}
    destino = estado.guard.resolver(
        f"{saida_cfg.get('pasta', 'Mapas')}/{saida_cfg.get('nome_base', 'mapa')}_Quantitativos.xlsx",
        escrita=True,
    )
    recibo = _recibo()
    exportar_xlsx(dados, destino, recibo=recibo)
    ctx.setdefault("mapas_gerados", []).append(str(destino.relative_to(estado.guard.raiz)))
    return _ok(
        {
            "xlsx": str(destino.relative_to(estado.guard.raiz)),
            "conferencia": montar_conferencia(dados, recibo),
            "avisos": (dados.get("avisos") or [])[:10],
        }
    )


def tool_comparar_com_modelo(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Compara o PDF gerado com o PDF-modelo (baseline) da série — diff raster."""
    from mapasfacil_nucleo.validacao.comparar_pdf import comparar_pdf, resolver_baseline_template

    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada.")
    mapspec = _mapspec_do_ctx(ctx)
    pdf_rel = args.get("pdf")
    if not isinstance(pdf_rel, str) or not pdf_rel:
        gerados = [g for g in (ctx.get("mapas_gerados") or []) if str(g).lower().endswith(".pdf")]
        if not gerados:
            return _erro("NU-041", "Informe 'pdf' ou gere um mapa antes de comparar.")
        pdf_rel = gerados[-1]
    template = args.get("template") or (mapspec or {}).get("template")
    if not isinstance(template, str) or not template:
        return _erro("NU-001", "Sem template para escolher o PDF-modelo da série.")
    baseline = resolver_baseline_template(template)
    if baseline is None:
        return _erro(
            CODIGO_DEPENDENCIA,
            f"O template '{template}' ainda não tem PDF-modelo (baseline) no MANIFEST.",
            depende_de="MANIFEST.baseline_pdf",
        )
    comparacao = comparar_pdf(estado.guard.resolver(pdf_rel), baseline)
    return _ok(
        {
            "pdf": Path(pdf_rel).name,
            "diferenca_pct": comparacao.get("diferenca_pct"),
            "tolerancia_pct": comparacao.get("tolerancia_pct"),
            "dentro_da_tolerancia": comparacao.get("ok"),
        }
    )


_ALVO_DISTANCIA: dict[str, str] = {
    "ti": "terras_indigenas_funai",
    "uc": "unidades_conservacao",
    "embargo": "embargos_siga",
}
RAIOS_BUSCA_KM: tuple[float, ...] = (10.0, 30.0, 60.0, 120.0)


def _geometria_imovel(estado) -> tuple[BaseGeometry, int] | None:
    """União do(s) polígono(s) ATP local — base para bbox/clip/distância (A13)."""
    fontes = workspace_servico.fontes_idx(estado)
    rel = fontes.get("ATP")
    if not rel:
        return None
    try:
        caminho = estado.guard.resolver(rel)
        geometrias, epsg = ler_geometrias_e_epsg(caminho)
    except ErroNucleo:
        return None
    if not geometrias or epsg is None:
        return None
    return unary_union(geometrias), epsg


def _geometria_imovel_4674(geom: BaseGeometry, epsg: int) -> BaseGeometry:
    return geom if epsg == 4674 else geo_area.reprojetar(geom, epsg, 4674)


def _bbox_raio_km(geom_4674: BaseGeometry, raio_km: float) -> tuple[float, float, float, float]:
    centro = geom_4674.centroid
    delta_lat = raio_km / 111.0
    delta_lon = raio_km / (111.320 * max(math.cos(math.radians(centro.y)), 0.15))
    minx, miny, maxx, maxy = geom_4674.bounds
    return (minx - delta_lon, miny - delta_lat, maxx + delta_lon, maxy + delta_lat)


def tool_consultar_sema(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Recorte de camada do catálogo no imóvel: contagem e área, nunca geometria (A13/R21)."""
    del ctx
    camada_id = args.get("camada")
    if not isinstance(camada_id, str) or not camada_id:
        return _erro("NU-001", "Parâmetro 'camada' é obrigatório.")
    if camada_id not in _ids_catalogo():
        return _erro(
            CODIGO_CATALOGO,
            f"Camada fora do catálogo: {camada_id}",
            sugestao=_sugerir(camada_id, _ids_catalogo()),
        )
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada — abra o workspace antes de consultar.")
    imovel = _geometria_imovel(estado)
    if imovel is None:
        return _erro(
            "NU-041",
            "Não encontrei o shapefile ATP (perímetro do imóvel) no workspace.",
        )
    geom_imovel, epsg_imovel = imovel
    geom_4674 = _geometria_imovel_4674(geom_imovel, epsg_imovel)
    bbox = tuple(geom_4674.bounds)

    try:
        resultado = resolver_camada(camada_id, bbox, "EPSG:4674", guard=estado.guard)
    except ErroNucleo as exc:
        return _erro(exc.codigo, exc.mensagem)

    recortar = args.get("recortar_no_imovel")
    recortar = True if recortar is None else bool(recortar)
    geometrias = resultado.geometrias
    if recortar and geometrias:
        geometrias = clip_camadas.clip_poligono(geometrias, geom_4674)

    area_ha = 0.0
    if geometrias:
        area_ha, _ = geo_area.area_hectares(
            geometrias, epsg_origem=4674, longitude_centroide=geom_4674.centroid.x
        )

    nome = next((c.get("nome") for c in _catalogo_camadas() if c["id"] == camada_id), camada_id)
    return _ok(
        {
            "camada": camada_id,
            "nome": nome,
            "contagem": len(geometrias),
            "area_ha": area_ha,
            "recortado_no_imovel": recortar,
            "parcial": resultado.parcial,
            "avisos": resultado.avisos,
        }
    )


def tool_distancia_ate(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Menor distância do imóvel até TI, UC ou embargo mais próximo (A13/R21).

    Busca por raio crescente (10/30/60/120 km) até achar a primeira feição — não é
    garantidamente a mais próxima do Brasil inteiro, mas cobre a vizinhança
    relevante para um mapa IMAP sem varrer o país inteiro a cada turno.
    """
    del ctx
    alvo = args.get("alvo")
    if alvo not in _ALVO_DISTANCIA:
        return _erro("NU-001", "Parâmetro 'alvo' precisa ser 'ti', 'uc' ou 'embargo'.")
    camada_id = _ALVO_DISTANCIA[alvo]
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada — abra o workspace antes de consultar.")
    imovel = _geometria_imovel(estado)
    if imovel is None:
        return _erro(
            "NU-041",
            "Não encontrei o shapefile ATP (perímetro do imóvel) no workspace.",
        )
    geom_imovel, epsg_imovel = imovel
    geom_4674 = _geometria_imovel_4674(geom_imovel, epsg_imovel)

    resultado = None
    for raio in RAIOS_BUSCA_KM:
        bbox = _bbox_raio_km(geom_4674, raio)
        try:
            resultado = resolver_camada(camada_id, bbox, "EPSG:4674", guard=estado.guard)
        except ErroNucleo as exc:
            return _erro(exc.codigo, exc.mensagem)
        if not resultado.vazia:
            break

    if resultado is None or resultado.vazia:
        return _ok(
            {
                "alvo": alvo,
                "camada": camada_id,
                "distancia_km": None,
                "mensagem": f"Nada encontrado em até {RAIOS_BUSCA_KM[-1]:.0f} km do imóvel.",
            }
        )

    distancia_km = distancia_minima_km(geom_4674, 4674, resultado.geometrias, 4674)
    return _ok(
        {
            "alvo": alvo,
            "camada": camada_id,
            "distancia_km": distancia_km,
            "parcial": resultado.parcial,
            "avisos": resultado.avisos,
        }
    )


def tool_analisar_referencia(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Print/PDF/.mxd/.zip de referência → proposta F1-07 (determinístico + visão)."""
    arquivo = args.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo:
        return _erro("NU-001", "Parâmetro 'arquivo' é obrigatório.")
    estado = _estado()
    if estado is None:
        return _erro("NU-040", "Nenhuma pasta conectada — abra o workspace antes de analisar.")
    try:
        resultado = visao_servico.analisar_referencia(arquivo, guard=estado.guard)
    except ErroNucleo as exc:
        return _erro(exc.codigo, exc.mensagem, detalhes=exc.detalhes)

    mapspec_candidato = resultado.pop("mapspec_candidato", None)
    if isinstance(mapspec_candidato, dict):
        ctx["mapspec"] = mapspec_candidato
        ctx["mapspec_origem"] = "analisar_referencia"
        _emitir_mapspec_atualizado(ctx, mapspec_candidato, mapspec_diff({}, mapspec_candidato))
        resultado["mapspec_id"] = mapspec_candidato.get("id")
        resultado["mapspec_versao"] = mapspec_candidato.get("versao")
    return _ok(resultado)


# --------------------------------------------------------------------------- memória


def _folha_como_texto(folha: Any) -> str | None:
    """`{formato, orientacao}` → "A3 paisagem", do jeito que a IA fala com o usuário."""
    if not isinstance(folha, dict):
        return None
    formato = str(folha.get("formato") or "").strip().upper()
    if not formato:
        return None
    orientacao = str(folha.get("orientacao") or "paisagem").strip().lower()
    return f"{formato} {orientacao}"


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
            "folha": _folha_como_texto(mapspec.get("folha")),
        }
    memoria = {
        "pasta": pasta,
        "imovel": imovel,
        "papeis": papeis,
        "mapspec_atual": mapspec_atual,
        "mapas_gerados": [],
        "avisos_abertos": [],
    }
    # Modo servidor (W1-07): o projeto tem nome e folha escolhidos no site; entram na
    # memória de trabalho para o agente não perguntar de novo o que já foi decidido.
    projeto_servidor = _projeto_do_servidor()
    if projeto_servidor:
        memoria["projeto"] = {
            "nome": projeto_servidor.get("nome"),
            "folha": projeto_servidor.get("folha"),
            "folha_texto": _folha_como_texto(projeto_servidor.get("folha")),
        }
    # garante teto
    texto = json.dumps(memoria, ensure_ascii=False, sort_keys=True)
    if limites.excede_memoria_trabalho(limites.estimar_tokens(texto)):
        memoria = {"pasta": pasta, "papeis": papeis, "mapspec_atual": mapspec_atual}
    return memoria


# --------------------------------------------------------------------------- registro

# --- W5-12: tools do chat web (folha, versões, validação) -------------------

_FORMATOS_FOLHA = ("A4", "A3", "A2", "A1", "A0")
_ORIENTACOES = ("retrato", "paisagem")

# O que cada check HARD significa para quem não é cartógrafo. Chave = id.
_EXPLICACAO_HARD: dict[str, str] = {
    "H01": "o arquivo do mapa (.mxd) não foi gerado",
    "H02": "o PDF não foi gerado",
    "H03": "a camada do imóvel não aparece no mapa",
    "H06": "a escala pedida não cabe na folha; o mapa sairia com outra escala",
    "H09": "as cores da legenda não batem com as do mapa",
    "H10": "o mapa não tem escala gráfica legível",
    "H12": "o texto do rodapé não cabe na folha",
    "H14": "a imagem de fundo não foi encontrada",
    "H17": "as áreas do imóvel não conferem com o recibo do CAR",
}

_EXPLICACAO_SOFT: dict[str, str] = {
    "S10": "tabela embutida com resolução do arquivo original",
    "S21": "texto ou caixa posicionado sobre linhas de vetor no mapa",
    "S22": "elemento do layout ultrapassando a margem da folha ou cortado",
    "S23": "legenda com itens de camadas inativas ou ausentes",
    "S24": "minimapa de localização sem conter o centroide do imóvel",
    "S25": "sobreposição entre elementos visuais do layout",
}


def tool_definir_folha(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Troca o tamanho/orientação da folha mantendo o resto do mapa."""
    formato = str(args.get("formato") or "").strip().upper()
    orientacao = args.get("orientacao")
    if formato not in _FORMATOS_FOLHA:
        return _erro(
            "AG-201",
            f"Formato de folha inválido: {formato or '(vazio)'}.",
            validos=list(_FORMATOS_FOLHA),
        )
    if orientacao is not None:
        orientacao = str(orientacao).strip().lower()
        if orientacao not in _ORIENTACOES:
            return _erro(
                "AG-201",
                f"Orientação inválida: {orientacao}.",
                validos=list(_ORIENTACOES),
            )
    escala_elementos = args.get("escala_elementos")

    def mutar(candidato: dict[str, Any]) -> None:
        folha = dict(candidato.get("folha") or {})
        folha["formato"] = formato
        if orientacao is not None:
            folha["orientacao"] = orientacao
        if escala_elementos is not None:
            folha["escala_elementos"] = escala_elementos
        folha.setdefault("orientacao", "paisagem")
        folha.setdefault("escala_elementos", "proporcional")
        candidato["folha"] = folha

    return _editar(ctx, mutar)


def tool_sugerir_enquadramento(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Qual folha/orientação deixa o mapa mais detalhado para este imóvel (W-10/W5-12).

    Devolve a tabela folha × orientação **e** o enquadramento resolvido da folha atual: escala
    redonda, extent, CRS e deslocamento da faixa útil. É o que o agente usa para responder
    "dá em A3 ou só em A2?" com número, não com opinião.
    """
    from mapasfacil_nucleo.motores import enquadramento

    estado = _estado()
    if estado is None:
        return _erro("AG-202", "Nenhuma pasta conectada — sem perímetro não há enquadramento.")
    geometria = _geometria_imovel(estado)
    if geometria is None:
        return _erro("AG-202", "A pasta não tem o perímetro do imóvel (ATP) para calcular o enquadramento.")
    geom, _epsg = geometria
    xmin, ymin, xmax, ymax = geom.bounds
    bbox = {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}

    tipo = str(args.get("caixa") or "imovel").strip().lower()
    if tipo not in enquadramento.TIPOS_CAIXA:
        return _erro(
            "AG-204",
            f"Caixa de conteúdo desconhecida: {tipo!r}.",
            tipos=list(enquadramento.TIPOS_CAIXA),
        )

    formatos = args.get("formatos")
    if isinstance(formatos, list) and formatos:
        formatos = [str(f).upper() for f in formatos]
    else:
        formatos = list(_FORMATOS_FOLHA)

    linhas = enquadramento.sugerir(bbox, formatos=formatos)

    # Enquadramento da folha que está no MapSpec agora (ou a melhor, se ainda não há folha).
    folha_ctx = _folha_como_texto((_mapspec_do_ctx(ctx) or {}).get("folha")) or {}
    formato_atual = str(folha_ctx.get("formato") or (linhas[0]["folha"] if linhas else "A4")).upper()
    orientacao_atual = str(folha_ctx.get("orientacao") or "paisagem").lower()
    atual = None
    if linhas:
        perfil = enquadramento.perfil_para(formato_atual, orientacao_atual)
        try:
            resolvido = enquadramento.enquadrar(
                bbox,
                perfil,
                tipo=tipo,
                escala_fixa=args.get("escala_fixa"),
                alternativas=False,
            )
            atual = resolvido.para_dict()
        except Exception as exc:  # NU-310 (não cabe) e NU-311/312 — viram resposta, não crash
            codigo = getattr(exc, "codigo", "AG-205")
            atual = {
                "folha": formato_atual,
                "orientacao": orientacao_atual,
                "erro": codigo,
                "mensagem": getattr(exc, "mensagem", str(exc)),
                "detalhes": getattr(exc, "detalhes", None),
            }

    return _ok(
        {
            "tabela": linhas,
            "melhor": linhas[0] if linhas else None,
            "atual": atual,
            "folha_atual": folha_ctx,
            "caixa": tipo,
            "margem": enquadramento.MARGEM,
        }
    )


def tool_listar_versoes(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Versões já geradas do projeto, da mais nova para a mais antiga."""
    from mapasfacil_nucleo import versoes

    lista = versoes.listar()
    atual = (_mapspec_do_ctx(ctx) or {}).get("versao")
    return _ok({"versoes": lista, "atual": atual, "total": len(lista)})


def tool_restaurar_versao(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Recria o mapa como estava na versão pedida — em versão NOVA, sem apagar nada."""
    from mapasfacil_nucleo import versoes

    try:
        alvo = int(args.get("versao"))
    except (TypeError, ValueError):
        return _erro("AG-203", "Informe 'versao' como número inteiro.")
    antigo = versoes.carregar(alvo)
    if antigo is None:
        existentes = [v["versao"] for v in versoes.listar()]
        return _erro(
            "AG-203",
            f"A versão {alvo} não tem mapa gerado; não há o que restaurar.",
            versoes=existentes,
        )
    atual = _mapspec_do_ctx(ctx)
    if atual is None:
        return _erro("NU-201", "Não há MapSpec nesta conversa para receber a restauração.")

    # Restauração não é edição: o conteúdo volta inteiro e o `parent_id` aponta
    # para a versão de origem (o `_editar` apontaria para a versão corrente).
    from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
    from mapasfacil_nucleo.mapspec.validar import validar as validar_mapspec
    from mapasfacil_nucleo.protocolo import novo_id

    candidato = copy.deepcopy(antigo)
    candidato["id"] = novo_id()
    candidato["versao"] = int(atual.get("versao") or 1) + 1
    candidato["parent_id"] = antigo.get("id")
    resultado = validar_mapspec(candidato, fontes_locais=_fontes_locais())
    if not resultado["valido"]:
        return _erro(
            "NU-201",
            f"A versão {alvo} não pode ser restaurada nesta pasta: ela não valida no ambiente atual.",
            erros=resultado["erros"][:5],
        )
    ctx["mapspec"] = candidato
    diff = mapspec_diff(atual, candidato)
    _emitir_mapspec_atualizado(ctx, candidato, diff)
    resumo = resumo_versao(candidato, diff)
    resumo["restaurada_de"] = alvo
    return _ok(resumo)


def tool_perguntar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Faz uma pergunta estruturada ao usuário e aguarda resposta (D40 / W5-21)."""
    import uuid

    pergunta = str(args.get("pergunta") or "").strip()
    if not pergunta:
        return _erro("AG-210", "Parâmetro 'pergunta' é obrigatório.")
    opcoes_raw = args.get("opcoes")
    if not isinstance(opcoes_raw, list) or len(opcoes_raw) < 1 or len(opcoes_raw) > 6:
        return _erro("AG-211", "Parâmetro 'opcoes' precisa ter entre 1 e 6 opções.")
    opcoes: list[dict[str, str]] = []
    for item in opcoes_raw:
        if isinstance(item, str):
            opcoes.append({"id": item, "rotulo": item})
        elif isinstance(item, dict) and item.get("id") and item.get("rotulo"):
            op = {"id": str(item["id"]), "rotulo": str(item["rotulo"])}
            if item.get("descricao"):
                op["descricao"] = str(item["descricao"])
            opcoes.append(op)
        else:
            return _erro("AG-212", "Cada opção precisa ter 'id' e 'rotulo' (ou ser string).")

    multipla = bool(args.get("multipla", False))
    permitir_texto = bool(args.get("permitir_texto", True))
    motivo = str(args.get("motivo") or "")

    pergunta_id = uuid.uuid4().hex[:12]
    ctx["aguardando_pergunta"] = True
    ctx["pergunta_pendente"] = {
        "pergunta_id": pergunta_id,
        "pergunta": pergunta,
        "opcoes": opcoes,
        "multipla": multipla,
        "permitir_texto": permitir_texto,
        "motivo": motivo,
    }

    emissor = ctx.get("emissor")
    if emissor is not None:
        emissor.emitir(
            "chat.pergunta",
            {
                "pergunta_id": pergunta_id,
                "pergunta": pergunta,
                "opcoes": opcoes,
                "multipla": multipla,
                "permitir_texto": permitir_texto,
                "permite_texto_livre": permitir_texto,  # compatibilidade com F1-06
                "motivo": motivo,
            },
        )

    return _ok(
        {
            "pergunta_id": pergunta_id,
            "pergunta": pergunta,
            "opcoes": [op["id"] for op in opcoes],
            "multipla": multipla,
            "permitir_texto": permitir_texto,
            "status": "aguardando_resposta",
        }
    )


def tool_explicar_validacao(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Explica em português o que a validação da última geração apontou."""
    from mapasfacil_nucleo import versoes

    versao = args.get("versao")
    pasta = versoes.pasta_da_versao(int(versao)) if versao else None
    if pasta is None:
        ultima = versoes.ultima()
        if ultima is None:
            return _erro("AG-203", "Nenhuma versão gerada ainda — não há validação para explicar.")
        pasta = versoes.pasta_da_versao(ultima)
    arquivos = sorted(Path(str(pasta)).glob("*_validacao.json"))
    if not arquivos:
        return _erro("AG-203", f"A pasta {pasta.name} não tem relatório de validação.")
    try:
        relatorio = json.loads(arquivos[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _erro("AG-203", f"Não consegui ler o relatório de validação: {exc}")

    checks = relatorio.get("checks") or {}
    hard = [c for c in (checks.get("hard") or []) if isinstance(c, dict)]
    soft = [c for c in (checks.get("soft") or []) if isinstance(c, dict)]
    falhas = []
    for check in hard:
        if check.get("ok"):
            continue
        ident = str(check.get("id") or "")
        falhas.append(
            {
                "id": ident,
                "o_que_e": _EXPLICACAO_HARD.get(ident, check.get("mensagem") or "check sem descrição"),
                "detalhe": check.get("mensagem"),
            }
        )
    avisos = [
        {
            "id": str(c.get("id") or ""),
            "o_que_e": _EXPLICACAO_SOFT.get(str(c.get("id") or ""), "aviso de validação"),
            "detalhe": c.get("mensagem"),
        }
        for c in soft
        if not c.get("ok")
    ]
    return _ok(
        {
            "versao": relatorio.get("versao") or (int(versao) if versao else versoes.ultima()),
            "conforme": not falhas,
            "veredito": (
                "O mapa passou nos checks obrigatórios."
                if not falhas
                else "O mapa NÃO passou nos checks obrigatórios — não é para dizer que está pronto."
            ),
            "falhas": falhas,
            "avisos": avisos,
            "motor": relatorio.get("motor"),
            "confianca": relatorio.get("confianca"),
        }
    )


_HANDLERS: dict[str, HandlerTool] = {
    # contexto
    "estado_do_projeto": tool_estado_do_projeto,
    "listar_arquivos": tool_listar_arquivos,
    "inspecionar_shapefile": tool_inspecionar_shapefile,
    "ler_recibo_car": tool_ler_recibo_car,
    "listar_zip": tool_listar_zip,
    "listar_catalogo": tool_listar_catalogo,
    "consultar_sema": tool_consultar_sema,
    "distancia_ate": tool_distancia_ate,
    "calcular_quantitativos": tool_calcular_quantitativos,
    # galeria
    "listar_modelos_galeria": tool_listar_modelos_galeria,
    "usar_modelo_da_galeria": tool_usar_modelo_da_galeria,
    # construção
    "criar_mapa": tool_criar_mapa,
    "definir_imovel": tool_definir_imovel,
    "adicionar_camada": tool_adicionar_camada,
    "remover_camada": tool_remover_camada,
    "editar_camada": tool_editar_camada,
    "definir_basemap": tool_definir_basemap,
    "definir_escala": tool_definir_escala,
    "definir_tabela": tool_definir_tabela,
    "editar_metadados": tool_editar_metadados,
    "alternar_elemento": tool_alternar_elemento,
    "definir_titulo": tool_definir_titulo,
    # fluxo
    "validar_mapspec": tool_validar_mapspec,
    "gerar_mapa": tool_gerar_mapa,
    "gerar_planilha": tool_gerar_planilha,
    "analisar_referencia": tool_analisar_referencia,
    # W5-12 — chat web
    "definir_folha": tool_definir_folha,
    "sugerir_enquadramento": tool_sugerir_enquadramento,
    "listar_versoes": tool_listar_versoes,
    "restaurar_versao": tool_restaurar_versao,
    "explicar_validacao": tool_explicar_validacao,
    "perguntar": tool_perguntar,
    "comparar_com_modelo": tool_comparar_com_modelo,
}

# Tools registradas cuja dependência ainda não existe — respondem IA-022 por contrato.
# `consultar_sema`/`distancia_ate` saíram daqui em A13 (camada.resolver / cliente WFS);
# `analisar_referencia` saiu em F1-07 (agente/visao/). Vazio — nenhuma tool é stub hoje.
TOOLS_COM_DEPENDENCIA_PENDENTE: frozenset[str] = frozenset()

_STR: dict[str, Any] = {"type": "string"}
_ESQUEMAS: dict[str, dict[str, Any]] = {
    "estado_do_projeto": {
        "descricao": "Resumo estruturado da pasta, imóvel e MapSpec atual (memória de trabalho).",
        "props": {},
    },
    "listar_arquivos": {
        "descricao": "Lista arquivos da pasta (nome, tipo, papel, área). Sem caminho absoluto.",
        "props": {
            "tipo": {"type": "string", "enum": ["shapefile", "pdf"]},
            "papel": {**_STR, "description": "ATP, AVN, AC, AUAS…"},
        },
    },
    "inspecionar_shapefile": {
        "descricao": "CRS, feições, campos, bbox e área de um shapefile. Nunca devolve geometria.",
        "props": {"arquivo": {**_STR, "description": "id_local ou nome do arquivo"}},
        "obrig": ["arquivo"],
    },
    "ler_recibo_car": {
        "descricao": "Nome, município, nº do CAR e áreas do recibo. Nunca devolve CPF.",
        "props": {},
    },
    "listar_zip": {
        "descricao": "Conteúdo de um .zip do SIMCAR sem extrair.",
        "props": {"arquivo": {**_STR, "description": "caminho relativo à pasta do projeto"}},
        "obrig": ["arquivo"],
    },
    "listar_catalogo": {
        "descricao": "Camadas, estilos, templates e escalas disponíveis (paginado, ≤30 camadas).",
        "props": {"tema": _STR, "pagina": {"type": "integer", "minimum": 1}},
    },
    "consultar_sema": {
        "descricao": "Camada do catálogo recortada no imóvel: contagem e área, nunca geometria.",
        "props": {
            "camada": _STR,
            "recortar_no_imovel": {"type": "boolean"},
            "ano": {"type": "integer"},
        },
        "obrig": ["camada"],
    },
    "distancia_ate": {
        "descricao": "Menor distância do imóvel até TI, UC ou embargo mais próximo.",
        "props": {"alvo": {"type": "string", "enum": ["ti", "uc", "embargo"]}},
        "obrig": ["alvo"],
    },
    "calcular_quantitativos": {
        "descricao": "Matriz classe × área em hectare do MapSpec atual, com avisos.",
        "props": {},
    },
    "listar_modelos_galeria": {
        "descricao": "Modelos prontos da galeria, com status e motivo de indisponibilidade.",
        "props": {},
    },
    "usar_modelo_da_galeria": {
        "descricao": "Monta o MapSpec a partir de um modelo pronto. PREFIRA isto a criar_mapa.",
        "props": {
            "modelo_id": _STR,
            "sobrescritas": {
                "type": "object",
                "description": "titulo, escala, saidas, mapeamento, elementos_layout",
            },
        },
        "obrig": ["modelo_id"],
    },
    "criar_mapa": {
        "descricao": "Cria MapSpec do zero a partir de um template — só se nenhum modelo servir.",
        "props": {"template": _STR, "titulo": _STR},
        "obrig": ["template"],
    },
    "definir_imovel": {
        "descricao": "Preenche/corrige os dados do imóvel no MapSpec.",
        "props": {
            "nome": _STR,
            "car": _STR,
            "matricula": _STR,
            "area_total_ha": {"type": "number"},
            "municipio": _STR,
            "uf": _STR,
        },
    },
    "adicionar_camada": {
        "descricao": "Acrescenta camada ao MapSpec (fonte local.X ou catalogo.Y).",
        "props": {
            "fonte": _STR,
            "estilo": {"type": "string", "enum": sorted(ESTILOS_PERMITIDOS)},
            "nome_no_mxd": _STR,
            "legenda": _STR,
            "ordem": {"type": "integer"},
            "rotulo_texto": _STR,
            "filtro": {
                "type": "object",
                "description": "objeto tipado {campo, operador, valor} — SQL livre não existe",
                "properties": {
                    "campo": _STR,
                    "operador": {"type": "string", "enum": sorted(OPERADORES_FILTRO)},
                    "valor": {},
                },
            },
        },
        "obrig": ["fonte", "estilo", "nome_no_mxd"],
    },
    "remover_camada": {
        "descricao": "Remove uma camada do MapSpec pelo id.",
        "props": {"id": _STR},
        "obrig": ["id"],
    },
    "editar_camada": {
        "descricao": "Troca estilo, legenda, rótulo, ordem ou filtro de uma camada.",
        "props": {
            "id": _STR,
            "estilo": {"type": "string", "enum": sorted(ESTILOS_PERMITIDOS)},
            "legenda": _STR,
            "rotulo_texto": _STR,
            "nome_no_mxd": _STR,
            "ordem": {"type": "integer"},
            "filtro": {"type": ["object", "null"]},
        },
        "obrig": ["id"],
    },
    "definir_basemap": {
        "descricao": "Define tipo e mosaico do basemap.",
        "props": {"tipo": _STR, "mosaico": _STR},
        "obrig": ["tipo"],
    },
    "definir_escala": {
        "descricao": 'Define a escala: valor da lista permitida ou "auto".',
        "props": {"escala": {"description": 'inteiro da lista permitida ou "auto"'}},
        "obrig": ["escala"],
    },
    "definir_tabela": {
        "descricao": "Configura a tabela de quantitativos (colunas, total geral, casas decimais).",
        "props": {
            "colunas": {"type": "array", "items": _STR},
            "total_geral": {"type": "boolean"},
            "casas_decimais": {"type": "integer", "minimum": 0, "maximum": 6},
            "titulo_bloco": {"type": ["string", "null"]},
        },
    },
    "editar_metadados": {
        "descricao": "Insere, edita ou remove uma linha do bloco de metadados.",
        "props": {
            "acao": {"type": "string", "enum": ["definir", "remover"]},
            "rotulo": _STR,
            "valor": _STR,
        },
        "obrig": ["rotulo"],
    },
    "alternar_elemento": {
        "descricao": "Liga/desliga um elemento de layout (tabela, minimapa, legenda…).",
        "props": {
            "elemento": {"type": "string", "enum": sorted(ELEMENTOS_LAYOUT)},
            "ligado": {"type": "boolean", "description": "omitido = inverte o estado atual"},
        },
        "obrig": ["elemento"],
    },
    "definir_titulo": {
        "descricao": "Texto da caixa branca de título.",
        "props": {"titulo": _STR},
        "obrig": ["titulo"],
    },
    "validar_mapspec": {
        "descricao": "Roda todos os checks predizíveis sem gerar nada. Rode antes de gerar_mapa.",
        "props": {},
    },
    "gerar_mapa": {
        "descricao": (
            "Executa o job e devolve artefatos + validação. Valide antes. "
            "Com elementos_layout.minimapa e ArcMap (T1), aplica definition query IBGE, "
            "rótulo, retângulo vermelho e linha-guia L a partir de imovel.municipio."
        ),
        "props": {
            "saidas": {
                "type": "array",
                "items": {"type": "string", "enum": ["mxd", "pdf", "png", "xlsx", "geojson"]},
                "description": "opcional: sobrescreve as saídas do MapSpec neste job",
            }
        },
    },
    "gerar_planilha": {"descricao": "Exporta o .xlsx de quantitativos.", "props": {}},
    "analisar_referencia": {
        "descricao": (
            "Print, PDF, .mxd ou .zip de referência → proposta com mapa da série, camadas "
            "reconhecidas e MapSpec candidato (ou perguntas quando a confiança é baixa). "
            "Em .mxd detecta minimapa Harmonia (elementos/queries) e sugere "
            "elementos_layout.minimapa + município."
        ),
        "props": {"arquivo": {**_STR, "description": "caminho relativo à pasta do projeto"}},
        "obrig": ["arquivo"],
    },
    "definir_folha": {
        "descricao": "Troca o tamanho/orientação da folha do mapa (A4 a A0), mantendo o resto.",
        "props": {
            "formato": {"type": "string", "enum": list(_FORMATOS_FOLHA)},
            "orientacao": {"type": "string", "enum": list(_ORIENTACOES)},
            "escala_elementos": {
                "type": "string",
                "enum": ["proporcional", "fixa"],
                "description": "proporcional = textos e legendas acompanham o tamanho da folha",
            },
        },
        "obrig": ["formato"],
    },
    "sugerir_enquadramento": {
        "descricao": (
            "Tabela folha × orientação com a escala redonda que cabe (margem de 15%) e o "
            "aproveitamento do quadro, mais o enquadramento resolvido da folha atual."
        ),
        "props": {
            "formatos": {
                "type": "array",
                "items": {"type": "string", "enum": list(_FORMATOS_FOLHA)},
                "description": "folhas a comparar (padrão: A4 a A0)",
            },
            "caixa": {
                "type": "string",
                "enum": ["imovel", "imovel_mais_alvo", "area_tematica"],
                "description": (
                    "o que manda no zoom: imovel (padrão) · imovel_mais_alvo (TI/UC/TE, une a "
                    "feição alvo) · area_tematica (DLA/AUAS, só a feição do tema)"
                ),
            },
            "escala_fixa": {
                "type": "integer",
                "description": (
                    "escala pedida pelo usuário; se cortar o imóvel, a tool explica e sugere a "
                    "menor que cabe"
                ),
            },
        },
    },
    "listar_versoes": {
        "descricao": "Lista as versões já geradas do projeto (folha, escala, artefatos).",
        "props": {},
    },
    "restaurar_versao": {
        "descricao": "Recria o mapa como estava numa versão anterior, em versão nova. Nunca apaga arquivo.",
        "props": {"versao": {"type": "integer", "description": "número da versão a restaurar"}},
        "obrig": ["versao"],
    },
    "perguntar": {
        "descricao": (
            "Faz uma pergunta estruturada com 2 a 6 opções de escolha ao usuário e encerra o "
            "turno à espera da resposta. Use quando faltar dado essencial que mude o resultado "
            "do mapa (qual perímetro entre vários, papel de camada incerto, confirmação de "
            "série com 4+ mapas, ou parâmetro indefinido como ano). Nunca use em pedidos claros "
            "nem repita perguntas já respondidas."
        ),
        "props": {
            "pergunta": {"type": "string", "description": "Texto claro da pergunta para o usuário."},
            "opcoes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Identificador da opção"},
                        "rotulo": {"type": "string", "description": "Texto exibido no botão/chip"},
                        "descricao": {"type": "string", "description": "Detalhe opcional"},
                    },
                    "required": ["id", "rotulo"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 6,
                "description": "Entre 2 e 6 opções estruturadas para o usuário clicar.",
            },
            "multipla": {
                "type": "boolean",
                "description": "True se o usuário puder marcar mais de uma opção (padrão False).",
            },
            "permitir_texto": {
                "type": "boolean",
                "description": "True se permitir digitar texto livre além dos botões (padrão True).",
            },
            "motivo": {
                "type": "string",
                "description": "Justificativa técnica do porquê a pergunta é necessária.",
            },
        },
        "obrig": ["pergunta", "opcoes"],
    },
    "explicar_validacao": {
        "descricao": "Explica em português o que a validação apontou (checks obrigatórios e avisos).",
        "props": {
            "versao": {"type": "integer", "description": "versão a explicar (padrão: a última)"}
        },
    },
    "comparar_com_modelo": {
        "descricao": "Compara o PDF gerado com o PDF-modelo da série (diff raster).",
        "props": {"pdf": _STR, "template": _STR},
    },
}


def nomes_tools() -> list[str]:
    return sorted(_HANDLERS)


def schemas_openai() -> list[dict[str, Any]]:
    """Schemas de tool calling tipados — o modelo não deve adivinhar parâmetro."""
    schemas = []
    for nome in nomes_tools():
        cfg = _ESQUEMAS.get(nome, {})
        parametros: dict[str, Any] = {
            "type": "object",
            "properties": dict(cfg.get("props") or {}),
            "additionalProperties": False,
        }
        if cfg.get("obrig"):
            parametros["required"] = list(cfg["obrig"])
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": nome,
                    "description": cfg.get("descricao") or f"Tool {nome} do Mapas Fácil.",
                    "parameters": parametros,
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
            sugestao=_sugerir(nome, _HANDLERS),
            tools_validas=nomes_tools(),
        )
    if isinstance(argumentos, str):
        try:
            argumentos = json.loads(argumentos) if argumentos.strip() else {}
        except json.JSONDecodeError:
            return _erro("NU-001", "Argumentos da tool não são JSON válido.")
    if not isinstance(argumentos, dict):
        argumentos = {}
    try:
        resultado = handler(argumentos, ctx)
    except ErroNucleo as exc:
        # Tool nunca derruba o turno: o erro tipado volta ao modelo e conta rodada.
        resultado = _erro(exc.codigo, exc.mensagem, detalhes=exc.detalhes)
    except Exception as exc:  # defesa: bug de tool não pode matar o chat
        resultado = _erro("NU-999", f"Falha inesperada em '{nome}': {exc}")
    # envelope truncado (RESULTADO_TOOL_MAX)
    texto = json.dumps(resultado, ensure_ascii=False, sort_keys=True, default=str)
    trunc = limites.truncar_resultado_tool(texto, ponteiro=f"tool:{nome}")
    if trunc["truncado"]:
        return {
            "ok": resultado.get("ok", True),
            "truncado": True,
            "conteudo": trunc["conteudo"],
            "ponteiro": trunc["ponteiro"],
        }
    return resultado
