# F1-17 §Título automático — as três origens do título e a regra de `title_manual`.
#
# Regra 2 do plano (título gerado por `deepseek-v4-flash`) é do M7: exige rede, e
# este pacote não fala com rede. O que existe aqui é o contrato que o M7 vai usar —
# `pode_sobrescrever` + `TETO_TITULO` — e as origens determinísticas (regras 3 e 4),
# que já funcionam hoje, sem chave de IA:
#
#   1. ao criar                → TITULO_PADRAO
#   3. sem chave de IA         → nome do modelo da galeria, ou 1ª mensagem do usuário
#   4. renomeado pelo usuário  → `title_manual = 1`, e ninguém sobrescreve mais

from __future__ import annotations

TITULO_PADRAO = "Conversa sem título"
TETO_TITULO = 48


def encurtar(texto: str, teto: int = TETO_TITULO) -> str:
    """Uma linha, com no máximo `teto` caracteres contando o `…` do corte.

    Corta na última fronteira de palavra que couber; se a primeira palavra já não
    couber, corta no caractere.
    """
    limpo = " ".join(texto.split())
    if len(limpo) <= teto:
        return limpo
    fatia = limpo[: teto - 1]
    espaco = fatia.rfind(" ")
    if espaco >= teto // 2:
        fatia = fatia[:espaco]
    return f"{fatia.rstrip()}…"


def sugerir(
    *,
    modelo_galeria: str | None = None,
    primeira_mensagem: str | None = None,
) -> str:
    """Título determinístico, sem IA. O modelo da galeria vence a mensagem do usuário.

    Vence porque é mais informativo e já vem curado ("Dinâmica de uso do solo ·
    Harmonia"), enquanto a primeira mensagem costuma ser "boa tarde, preciso de".
    """
    if modelo_galeria and modelo_galeria.strip():
        return encurtar(modelo_galeria)
    if primeira_mensagem and primeira_mensagem.strip():
        return encurtar(primeira_mensagem)
    return TITULO_PADRAO


def pode_sobrescrever(title_manual: int | bool) -> bool:
    """A IA só titula conversa que o usuário nunca renomeou (regra 4)."""
    return not bool(title_manual)
