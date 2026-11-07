from __future__ import annotations

import os
from typing import Any

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro


def verificar_isolamento_os() -> bool:
    """Verifica se há isolamento comprovado de SO (container, gVisor, jail sem rede).

    Por padrão no processo hospedeiro (Windows/Linux sem sandbox formal), retorna False.
    Não confiar em simples audit hooks de Python ou variáveis de ambiente sem prova de container.
    """
    # Mesmo com flags de ambiente, se estiver rodando direto no SO do usuário sem sandbox verificado,
    # retorna False por segurança estrita (fail-closed).
    return False


def registrar_tools_exec(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="python_exec",
        descricao="Execução de código Python (DESLIGADO por padrão em modo fail-closed).",
        categoria="execucao",
        parametros={
            "type": "object",
            "properties": {
                "codigo": {"type": "string", "description": "Código Python para execução."},
                "permitir": {
                    "type": "boolean",
                    "description": "Flag de solicitação de permissão.",
                },
                "forcar": {"type": "boolean", "description": "Tentativa de forçar execução."},
                "sandbox": {"type": "boolean", "description": "Flag de sandbox."},
            },
            "required": ["codigo"],
            "additionalProperties": False,
        },
    )
    def tool_python_exec(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        if not verificar_isolamento_os():
            return _erro(
                "SEC-001",
                "python_exec explicitamente DESLIGADO: isolamento de sistema operacional "
                "não comprovado (fail-closed). Não é permitida a execução de código "
                "arbitrário no processo hospedeiro.",
            )
        # Caminho inalcançável sem isolamento real comprovado
        return _erro("SEC-002", "Ambiente com isolamento de SO não configurado.")
