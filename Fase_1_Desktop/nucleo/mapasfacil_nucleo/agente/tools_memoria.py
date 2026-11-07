from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace
from mapasfacil_nucleo.config import caminho_shared


def _obter_pasta_skills() -> Path:
    base = caminho_shared() / "skills"
    if base.exists():
        return base
    # Fallback procurando da raiz do repo
    atual = Path(__file__).resolve()
    for parent in atual.parents:
        cand = parent / "shared" / "skills"
        if cand.exists():
            return cand
    return base


def registrar_tools_memoria(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="skill_listar",
        descricao="Lista as competências e regras especializadas disponíveis sob demanda (em shared/skills).",
        categoria="skills",
        parametros={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    def tool_skill_listar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        pasta = _obter_pasta_skills()
        if not pasta.exists():
            return _ok({"skills": [], "total": 0})

        skills = []
        for arq in sorted(pasta.glob("*.md")):
            nome = arq.stem
            texto = arq.read_text(encoding="utf-8", errors="replace")
            descricao = ""
            desc_match = re.search(r'description:\s*["\']?([^"\']+)["\']?', texto)
            if desc_match:
                descricao = desc_match.group(1).strip()
            skills.append({"nome": nome, "descricao": descricao, "arquivo": arq.name})

        return _ok({"skills": skills, "total": len(skills)})

    @registro.ferramenta(
        nome="skill_ler",
        descricao="Carrega o texto de instruções especializadas de uma skill específica.",
        categoria="skills",
        parametros={
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome da skill (ex: cartografia-padrao)."}
            },
            "required": ["nome"],
            "additionalProperties": False,
        },
    )
    def tool_skill_ler(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        nome = args.get("nome", "").strip()
        pasta = _obter_pasta_skills()
        alvo = pasta / f"{nome}.md"
        if not alvo.exists():
            return _erro("SKILL-001", f"Skill '{nome}' não encontrada em {pasta.as_posix()}.")

        conteudo = alvo.read_text(encoding="utf-8", errors="replace")
        return _ok({"nome": nome, "conteudo": conteudo})

    @registro.ferramenta(
        nome="memoria_ler",
        descricao="Lê anotações e fatos duráveis do projeto gravados na memória local (.agente/memoria.md).",
        categoria="memoria",
        parametros={
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    )
    def tool_memoria_ler(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            alvo = ws_root / ".agente" / "memoria.md"
            if not alvo.exists():
                return _ok({"conteudo": ""})
            return _ok({"conteudo": alvo.read_text(encoding="utf-8", errors="replace")})
        except Exception as exc:
            return _erro("MEM-001", f"Falha ao ler memória: {exc}")

    @registro.ferramenta(
        nome="memoria_gravar",
        descricao="Grava ou acrescenta notas e decisões importantes na memória do projeto (.agente/memoria.md).",
        categoria="memoria",
        parametros={
            "type": "object",
            "properties": {
                "conteudo": {
                    "type": "string",
                    "description": "Texto completo para sobrescrever a memória.",
                },
                "adicionar": {
                    "type": "string",
                    "description": "Trecho de texto a ser acrescentado ao final.",
                },
            },
            "additionalProperties": False,
        },
    )
    def tool_memoria_gravar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            pasta = ws_root / ".agente"
            pasta.mkdir(parents=True, exist_ok=True)
            alvo = pasta / "memoria.md"

            if "conteudo" in args and args["conteudo"] is not None:
                alvo.write_text(args["conteudo"], encoding="utf-8")
            elif "adicionar" in args and args["adicionar"]:
                anterior = alvo.read_text(encoding="utf-8", errors="replace") if alvo.exists() else ""
                nova = f"{anterior}\n{args['adicionar']}".strip() + "\n"
                alvo.write_text(nova, encoding="utf-8")

            return _ok({"status": "memoria_atualizada"})
        except Exception as exc:
            return _erro("MEM-002", f"Falha ao gravar memória: {exc}")
