"""Vocabulário de eventos do SSE (W-03 §Vocabulário).

Duas origens: `nucleo` (repassados do worker) e `servidor` (nascidos aqui). O conjunto
é fechado; evento fora dele é bug (`SV-300`), não "só mais um campo".
"""

from __future__ import annotations

# Espelho do `protocolo.py::EVENTOS` do núcleo. Copiado de propósito: o servidor não
# importa o núcleo (AW-01) e o teste `test_vocabulario.py` compara os dois quando o
# pacote está instalado.
EVENTOS_NUCLEO: frozenset[str] = frozenset(
    {
        "job.progresso",
        "job.log",
        "job.artefato_parcial",
        "workspace.mudou",
        "chat.delta",
        "chat.raciocinio",
        "chat.tool",
        "chat.pergunta",
        "mapspec.atualizado",
        "aviso",
        # W7 — eventos do palco
        "viewport.foco",
        "camada.renderizada",
        "layout.elemento",
        "revisao.visual",
        # Agente PDF-first
        "agente.plano",
        "agente.passo",
        "agente.arquivo",
        "agente.preview",
        "agente.aprovacao",
        "agente.fim",
    }
)

EVENTOS_SERVIDOR: frozenset[str] = frozenset(
    {
        "projeto.estado",
        "importacao.progresso",
        "worker.estado",
        "mensagem.criada",
        "chat.turno",
        "versao.criada",
        "nucleo.res",
        "sse.heartbeat",
    }
)

EVENTOS: frozenset[str] = EVENTOS_NUCLEO | EVENTOS_SERVIDOR

ORIGENS = frozenset({"nucleo", "servidor"})

# Eventos que pertencem a um job de geração (carregam `job_id` quando existir).
EVENTOS_DE_JOB: frozenset[str] = frozenset(
    {
        "job.progresso",
        "job.log",
        "job.artefato_parcial",
        "viewport.foco",
        "camada.renderizada",
        "layout.elemento",
        "nucleo.res",
        "revisao.visual",
    }
)


def valido(evento: str) -> bool:
    return evento in EVENTOS


def exigir(evento: str) -> str:
    """Devolve o nome ou levanta `ValueError` — erro de programação, não de usuário."""
    if evento not in EVENTOS:
        raise ValueError(
            f"Evento fora do vocabulário: {evento!r}. "
            f"Válidos: {', '.join(sorted(EVENTOS))}"
        )
    return evento
