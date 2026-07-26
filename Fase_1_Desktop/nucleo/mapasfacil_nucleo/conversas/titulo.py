# Título de conversa: automático, galeria ou manual (F1-17).

from __future__ import annotations

TITULO_PADRAO = "Conversa sem título"
LIMITE_TITULO = 48


def titulo_da_mensagem(conteudo: str) -> str:
    """Fallback sem IA: primeiros 48 caracteres da primeira mensagem do usuário."""
    limpo = " ".join((conteudo or "").split())
    if not limpo:
        return TITULO_PADRAO
    if len(limpo) <= LIMITE_TITULO:
        return limpo
    return limpo[: LIMITE_TITULO - 1].rstrip() + "…"


def titulo_da_galeria(nome_modelo: str, nome_workspace: str | None) -> str:
    """Sem chave DeepSeek: título a partir do modelo da galeria + pasta."""
    base = (nome_modelo or "").strip() or TITULO_PADRAO
    if nome_workspace:
        candidato = f"{base} · {nome_workspace}"
    else:
        candidato = base
    if len(candidato) <= LIMITE_TITULO:
        return candidato
    return candidato[: LIMITE_TITULO - 1].rstrip() + "…"


def pode_atualizar_automatico(title_manual: bool | int) -> bool:
    """Uma vez renomeado pelo usuário, a IA/galeria nunca sobrescreve."""
    return not bool(title_manual)
