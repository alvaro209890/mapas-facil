# compact_summary — preferencialmente deepseek-v4-flash; fallback heurístico (G4).

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.contexto import _resumo_heuristico
from mapasfacil_nucleo.agente.provedor import MensagemLLM, ProvedorIA


def gerar_compact_summary(
    mensagens_db: list[dict[str, Any]],
    *,
    provedor: ProvedorIA | None = None,
    ate_seq: int | None = None,
) -> str:
    """Gera resumo ≤ COMPACT_SUMMARY_MAX tokens.

    Com ``provedor``: um turno flash. Sem provedor: heurística local (CI).
    """
    subset = mensagens_db
    if ate_seq is not None:
        subset = [m for m in mensagens_db if int(m.get("seq") or 0) <= ate_seq]
    if not subset:
        return ""
    if provedor is None:
        return _resumo_heuristico(subset)

    prompt = (
        "Resuma em português, no máximo 800 tokens, o histórico abaixo para continuidade "
        "de um agente de cartografia florestal. Preserve decisões de mapa, modelos usados "
        "e avisos numéricos. Não inclua CPF, caminhos absolutos nem chaves.\n\n"
    )
    corpo = "\n".join(
        f"{m.get('papel')}: {(m.get('conteudo') or '')[:400]}" for m in subset[-40:]
    )
    mensagens = [
        MensagemLLM(papel="system", conteudo="Você resume transcripts de forma factual."),
        MensagemLLM(papel="user", conteudo=prompt + corpo),
    ]
    texto = ""
    for delta in provedor.enviar_stream(mensagens, max_tokens=limites.COMPACT_SUMMARY_MAX, modelo=None):
        texto += delta.texto
    cortado, _ = limites.truncar_ate_tokens(texto.strip(), limites.COMPACT_SUMMARY_MAX)
    return cortado or _resumo_heuristico(subset)
