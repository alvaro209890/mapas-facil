from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.erros import ErroNucleo

HandlerTool = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _ok(dados: dict[str, Any] | None = None) -> dict[str, Any]:
    ret = {"ok": True}
    if dados:
        ret.update(dados)
    return ret


def _erro(codigo: str, mensagem: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "codigo": codigo, "mensagem": mensagem, **extra}


def _sugerir(valor: str, universo: Any) -> str | None:
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


@dataclass
class DefinicaoTool:
    """Metadados e manipulador de uma ferramenta do agente."""

    nome: str
    descricao: str
    categoria: str = "geral"
    parametros: dict[str, Any] = field(default_factory=dict)
    handler: HandlerTool | None = None
    requer_aprovacao: bool = False
    ativo: bool = True


class RegistroFerramentas:
    """Registro extensível de ferramentas do Agente V2.

    Evita switches gigantes centralizados; cada domínio (workspace, geo, layout,
    pdf, visao, mapa, memoria/skills) registra suas ferramentas de forma modular.
    """

    def __init__(self) -> None:
        self._tools: dict[str, DefinicaoTool] = {}

    def registrar(self, definicao: DefinicaoTool) -> None:
        self._tools[definicao.nome] = definicao

    def ferramenta(
        self,
        nome: str,
        descricao: str,
        *,
        categoria: str = "geral",
        parametros: dict[str, Any] | None = None,
        requer_aprovacao: bool = False,
        ativo: bool = True,
    ) -> Callable[[HandlerTool], HandlerTool]:
        """Decorador para registrar uma função como tool do agente."""

        def decorador(fn: HandlerTool) -> HandlerTool:
            params = parametros or {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
            definicao = DefinicaoTool(
                nome=nome,
                descricao=descricao,
                categoria=categoria,
                parametros=params,
                handler=fn,
                requer_aprovacao=requer_aprovacao,
                ativo=ativo,
            )
            self.registrar(definicao)
            return fn

        return decorador

    def obter(self, nome: str) -> DefinicaoTool | None:
        return self._tools.get(nome)

    def listar(self, categoria: str | None = None) -> list[DefinicaoTool]:
        tools = [t for t in self._tools.values() if t.ativo]
        if categoria is not None:
            tools = [t for t in tools if t.categoria == categoria]
        return sorted(tools, key=lambda t: t.nome)

    def nomes_tools(self, categoria: str | None = None) -> list[str]:
        return [t.nome for t in self.listar(categoria)]

    def schemas_openai(self, categoria: str | None = None) -> list[dict[str, Any]]:
        schemas = []
        for tool in self.listar(categoria):
            params = tool.parametros or {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.nome,
                        "description": tool.descricao,
                        "parameters": params,
                    },
                }
            )
        return schemas

    def executar(
        self,
        nome: str,
        argumentos: dict[str, Any] | str,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        tool = self._tools.get(nome)
        if tool is None or not tool.ativo or tool.handler is None:
            return _erro(
                limites.CODIGO_TOOL_INEXISTENTE,
                f"Tool inexistente: {nome}",
                sugestao=_sugerir(nome, self.nomes_tools()),
                tools_validas=self.nomes_tools(),
            )

        if isinstance(argumentos, str):
            try:
                argumentos = json.loads(argumentos) if argumentos.strip() else {}
            except json.JSONDecodeError:
                return _erro("NU-001", "Argumentos da tool não são JSON válido.")

        if not isinstance(argumentos, dict):
            argumentos = {}

        try:
            resultado = tool.handler(argumentos, ctx)
        except ErroNucleo as exc:
            resultado = _erro(exc.codigo, exc.mensagem, detalhes=exc.detalhes)
        except Exception as exc:
            resultado = _erro("NU-999", f"Falha inesperada em '{nome}': {exc}")

        if not isinstance(resultado, dict):
            resultado = _ok({"resultado": resultado})

        if "ok" not in resultado:
            resultado["ok"] = True

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


registro_padrao = RegistroFerramentas()


def carregar_todas_ferramentas_v2(registro: RegistroFerramentas | None = None) -> RegistroFerramentas:
    """Registra todas as ferramentas modulares do Agente V2 e preserva as ferramentas úteis."""
    reg = registro or registro_padrao

    from mapasfacil_nucleo.agente.plano import registrar_tools_plano
    from mapasfacil_nucleo.agente.tools_exec import registrar_tools_exec
    from mapasfacil_nucleo.agente.tools_geo import registrar_tools_geo
    from mapasfacil_nucleo.agente.tools_layout import registrar_tools_layout
    from mapasfacil_nucleo.agente.tools_mapa import registrar_tools_mapa
    from mapasfacil_nucleo.agente.tools_memoria import registrar_tools_memoria
    from mapasfacil_nucleo.agente.tools_pdf import registrar_tools_pdf
    from mapasfacil_nucleo.agente.tools_visao import registrar_tools_visao
    from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace

    registrar_tools_workspace(reg)
    registrar_tools_geo(reg)
    registrar_tools_layout(reg)
    registrar_tools_pdf(reg)
    registrar_tools_visao(reg)
    registrar_tools_mapa(reg)
    registrar_tools_memoria(reg)
    registrar_tools_exec(reg)
    registrar_tools_plano(reg)

    # Preservar ferramentas úteis legadas
    try:
        from mapasfacil_nucleo.agente import tools as tools_legado

        for nome, handler in tools_legado._HANDLERS.items():
            if reg.obter(nome) is None:
                cfg = tools_legado._ESQUEMAS.get(nome, {})
                params = {
                    "type": "object",
                    "properties": dict(cfg.get("props") or {}),
                    "additionalProperties": False,
                }
                if cfg.get("obrig"):
                    params["required"] = list(cfg["obrig"])
                reg.registrar(
                    DefinicaoTool(
                        nome=nome,
                        descricao=cfg.get("descricao") or f"Tool legada {nome}",
                        categoria="preservada",
                        parametros=params,
                        handler=handler,
                    )
                )

        # Alias útil: consultar_catalogo -> listar_catalogo
        if reg.obter("listar_catalogo") and reg.obter("consultar_catalogo") is None:
            t_orig = reg.obter("listar_catalogo")
            reg.registrar(
                DefinicaoTool(
                    nome="consultar_catalogo",
                    descricao="Consulta ou lista camadas do catálogo (alias de listar_catalogo).",
                    categoria="preservada",
                    parametros=t_orig.parametros,
                    handler=t_orig.handler,
                )
            )
    except Exception:
        pass

    return reg
