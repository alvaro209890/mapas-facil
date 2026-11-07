from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace


def registrar_tools_mapa(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="mapa_validar",
        descricao="Valida as regras técnicas e a conformidade do mapa e do MapSpec ativo.",
        categoria="mapa",
        parametros={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    def tool_mapa_validar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        ms = ctx.get("mapspec")
        if not ms:
            return _erro("MAP-001", "Nenhum MapSpec carregado no contexto.")

        from mapasfacil_nucleo.mapspec.validar import validar

        try:
            resultado = validar(ms)
            return _ok(
                {
                    "valido": bool(resultado.get("valido", False)),
                    "erros": resultado.get("erros", []),
                    "avisos": resultado.get("avisos", []),
                    "mapspec_id": ms.get("id"),
                    "versao": ms.get("versao"),
                }
            )
        except Exception as exc:
            return _erro("MAP-002", f"Erro ao validar MapSpec: {exc}")

    @registro.ferramenta(
        nome="mapa_gerar",
        descricao="Executa a geração do mapa cartográfico (PDF/MXD) a partir do MapSpec.",
        categoria="mapa",
        parametros={
            "type": "object",
            "properties": {
                "motor": {
                    "type": "string",
                    "enum": ["nativo", "arcpy", "auto"],
                    "description": "Motor de renderização.",
                }
            },
            "additionalProperties": False,
        },
    )
    def tool_mapa_gerar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        from mapasfacil_nucleo.agente import tools as tools_legado

        handler = tools_legado._HANDLERS.get("gerar_mapa")
        if handler is not None:
            return handler(args, ctx)
        return _erro("MAP-010", "Handler de geração de mapa não disponível no ambiente.")

    @registro.ferramenta(
        nome="versao_listar",
        descricao="Lista as versões de mapas e especificações já geradas no projeto.",
        categoria="mapa",
        parametros={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    def tool_versao_listar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            mapas_dir = ws_root / "Mapas"
            if not mapas_dir.exists():
                return _ok({"versoes": [], "total": 0})

            versoes = []
            # Procura por subpastas v001, v002...
            for pasta_v in sorted(mapas_dir.glob("v*")):
                if pasta_v.is_dir() and re.match(r"^v\d+$", pasta_v.name):
                    num = int(pasta_v.name[1:])
                    arquivos = [f.name for f in pasta_v.glob("*") if f.is_file()]
                    versoes.append({"versao": num, "pasta": pasta_v.name, "arquivos": arquivos})

            # Procura por arquivos com _vN
            for arq in sorted(mapas_dir.glob("*.pdf")):
                m = re.search(r"_v(\d+)\.pdf$", arq.name)
                if m:
                    num = int(m.group(1))
                    versoes.append({"versao": num, "arquivo": arq.name})

            if not versoes:
                # Se houver apenas PDFs avulsos
                for arq in sorted(mapas_dir.glob("*.pdf")):
                    versoes.append({"versao": 1, "arquivo": arq.name})

            return _ok({"versoes": versoes, "total": len(versoes)})
        except Exception as exc:
            return _erro("MAP-003", f"Falha ao listar versões: {exc}")

    @registro.ferramenta(
        nome="versao_restaurar",
        descricao="Restaura uma versão anterior do MapSpec ou do mapa do projeto.",
        categoria="mapa",
        parametros={
            "type": "object",
            "properties": {
                "versao": {"type": "integer", "description": "Número da versão a restaurar."}
            },
            "required": ["versao"],
            "additionalProperties": False,
        },
    )
    def tool_versao_restaurar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        from mapasfacil_nucleo.agente import tools as tools_legado

        handler = tools_legado._HANDLERS.get("restaurar_versao")
        if handler is not None:
            return handler(args, ctx)
        return _erro("MAP-011", "Handler de restauração de versão não disponível no ambiente.")
