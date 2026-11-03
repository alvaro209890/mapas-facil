# Cliente OpenAI-compatível — é o que fala com o 9Router da VPS (W5-16 / D33).
#
# O 9Router expõe `/v1/chat/completions` no formato OpenAI (SSE, tool calling,
# `reasoning_content` no delta), então o cliente herda o parser já provado do DeepSeek e
# só acrescenta o que é dele: `base_url`, `reasoning_effort` no corpo e o nome do modelo
# (`ag/gemini-3.8-flash-high`).
#
# Regra do vault (`02-projetos/9router.md`): o 9Router **ignora `max` em silêncio** — por
# isso o padrão é `high` e não existe "escalar" o raciocínio aqui.

from __future__ import annotations

import os
from typing import Any

from mapasfacil_nucleo.agente.deepseek import DeepSeekProvedor

ENV_PROVEDOR = "MAPASFACIL_PROVEDOR"
ENV_URL = "MAPASFACIL_PROVEDOR_URL"
ENV_CHAVE = "MAPASFACIL_PROVEDOR_CHAVE"
ENV_MODELO_CHAT = "MAPASFACIL_MODELO_CHAT"
ENV_MODELO_RAPIDO = "MAPASFACIL_MODELO_RAPIDO"
ENV_RACIOCINIO = "MAPASFACIL_RACIOCINIO"
ENV_CONTEXTO_MAX = "MAPASFACIL_CONTEXTO_MAX"
# Visão (W5-20): o mesmo Gemini do chat, por decisão do Álvaro em 2026-11-03.
ENV_MODELO_VISAO = "MAPASFACIL_MODELO_VISAO"

URL_PADRAO = "http://100.104.255.35:20128/v1"
MODELO_PADRAO = "ag/gemini-3.8-flash-high"
RACIOCINIO_PADRAO = "high"


def endpoint_de(base_url: str) -> str:
    """`http://host/v1` → `http://host/v1/chat/completions` (sem duplicar a barra)."""
    return base_url.rstrip("/") + "/chat/completions"


class OpenAICompatProvedor(DeepSeekProvedor):
    """Mesmo protocolo do DeepSeek, com `base_url` e `reasoning_effort` configuráveis."""

    def __init__(
        self,
        chave: str,
        *,
        base_url: str = URL_PADRAO,
        modelo: str = MODELO_PADRAO,
        reasoning_effort: str | None = RACIOCINIO_PADRAO,
        timeout: float = 180.0,
        urlopen: Any | None = None,
    ) -> None:
        super().__init__(
            chave,
            endpoint=endpoint_de(base_url),
            modelo=modelo,
            timeout=timeout,
            urlopen=urlopen,
        )
        self.base_url = base_url
        self.reasoning_effort = reasoning_effort

    def _extras_do_corpo(self) -> dict[str, Any]:
        if not self.reasoning_effort:
            return {}
        return {"reasoning_effort": self.reasoning_effort}


def do_ambiente(ambiente: dict[str, str] | None = None) -> OpenAICompatProvedor:
    """Monta o cliente a partir das variáveis do `servidor.env`.

    Chave ausente é erro de configuração, não falha de rede: quem chama (o servidor) já
    validou `MAPASFACIL_PROVEDOR_CHAVE` no boot.
    """
    env = ambiente if ambiente is not None else os.environ
    chave = (env.get(ENV_CHAVE) or "").strip()
    if not chave:
        from mapasfacil_nucleo.erros import ErroNucleo

        raise ErroNucleo(
            "IA-001",
            "MAPASFACIL_PROVEDOR_CHAVE não está configurada — sem ela o chat não fala com o 9Router.",
        )
    return OpenAICompatProvedor(
        chave,
        base_url=(env.get(ENV_URL) or URL_PADRAO).strip(),
        modelo=(env.get(ENV_MODELO_CHAT) or MODELO_PADRAO).strip(),
        reasoning_effort=(env.get(ENV_RACIOCINIO) or RACIOCINIO_PADRAO).strip(),
    )


def modelo_visao(ambiente: dict[str, str] | None = None) -> str:
    """Modelo que interpreta print/PDF de referência (`MAPASFACIL_MODELO_VISAO`).

    O default é o **mesmo** modelo do chat: o 9Router repassa imagem ao
    `ag/gemini-3.8-flash-high` (medido no W5-20), então não existe modelo de visão separado.
    """
    env = ambiente if ambiente is not None else os.environ
    return (env.get(ENV_MODELO_VISAO) or env.get(ENV_MODELO_CHAT) or MODELO_PADRAO).strip()


def modelo_rapido(ambiente: dict[str, str] | None = None) -> str:
    """Modelo de título de conversa e `compact_summary` (mesmo do chat, por decisão)."""
    env = ambiente if ambiente is not None else os.environ
    return (env.get(ENV_MODELO_RAPIDO) or env.get(ENV_MODELO_CHAT) or MODELO_PADRAO).strip()


def contexto_max(ambiente: dict[str, str] | None = None) -> int | None:
    """Teto de contexto **medido** no W5-16; sem medição, `None` (vale o do `limites`)."""
    env = ambiente if ambiente is not None else os.environ
    bruto = (env.get(ENV_CONTEXTO_MAX) or "").strip()
    if not bruto.isdigit():
        return None
    return int(bruto)
