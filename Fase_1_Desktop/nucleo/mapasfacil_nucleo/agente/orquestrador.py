# Loop de orquestração: contexto → provedor → tools → eventos (F1-06 / G7).

from __future__ import annotations

import json
import threading
import time
from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.agente.contexto import compactar_se_preciso, estimar_payload, montar_mensagens_llm
from mapasfacil_nucleo.agente.deepseek import DeepSeekProvedor
from mapasfacil_nucleo.agente.provedor import MensagemLLM, ProvedorIA
from mapasfacil_nucleo.agente.resumo import gerar_compact_summary
from mapasfacil_nucleo.agente.tools import executar as executar_tool
from mapasfacil_nucleo.agente.tools import schemas_openai
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import Emissor, novo_id

_cancelados: set[str] = set()
_lock = threading.Lock()
_provedor_override: ProvedorIA | None = None


def configurar_provedor(provedor: ProvedorIA | None) -> None:
    """Testes injetam FakeProvedor; produção usa None (DeepSeek com chave)."""
    global _provedor_override
    _provedor_override = provedor


def pedir_cancelamento(conversation_id: str) -> None:
    with _lock:
        _cancelados.add(conversation_id)


def _foi_cancelado(conversation_id: str) -> bool:
    with _lock:
        return conversation_id in _cancelados


def _limpar_cancelamento(conversation_id: str) -> None:
    with _lock:
        _cancelados.discard(conversation_id)


def _obter_provedor() -> ProvedorIA:
    if _provedor_override is not None:
        return _provedor_override
    chave = ler_chave_deepseek()
    if not chave:
        raise ErroNucleo(
            limites.CODIGO_SEM_CHAVE,
            "Chave DeepSeek ausente. Configure deepseek_api_key em secrets.local.json "
            "ou use a galeria de modelos (modo determinístico).",
        )
    return DeepSeekProvedor(chave)


def executar_turno(
    *,
    conversation_id: str,
    mensagem: str,
    emissor: Emissor | None = None,
    anexos: list[Any] | None = None,
) -> dict[str, Any]:
    del anexos
    _limpar_cancelamento(conversation_id)
    repo = conversas_servico.repositorio()
    repo.adicionar_mensagem(conversation_id, papel="usuario", conteudo=mensagem)

    aberto = repo.abrir_conversa(conversation_id, limite=500)
    mensagens_db = [
        {"seq": m["seq"], "papel": m["papel"], "conteudo": m["conteudo"]}
        for m in aberto["mensagens"]
    ]
    compact = aberto.get("compact_summary")
    ctx: dict[str, Any] = {"mapspec": None}

    tokens_entrada = int(aberto["conversa"].get("tokens_entrada") or 0)
    if limites.excede_conversa(tokens_entrada):
        raise ErroNucleo(
            limites.CODIGO_TETO_CONVERSA,
            "Esta conversa atingiu o teto de tokens. Abra um chat novo ou ramifique.",
            {"tokens_entrada": tokens_entrada},
        )

    mensagens_llm = montar_mensagens_llm(
        mensagens_db=mensagens_db,
        compact_summary=compact,
        mapspec=ctx.get("mapspec"),
    )
    mensagens_llm, compact, _ = compactar_se_preciso(
        mensagens_llm,
        compact_summary=compact,
        mensagens_db=mensagens_db,
        mapspec=ctx.get("mapspec"),
    )

    provedor = _obter_provedor()
    tools = schemas_openai()
    texto_final = ""
    tools_usadas: list[str] = []
    cancelada = False
    truncada = False
    rodadas_tool = 0

    while True:
        if _foi_cancelado(conversation_id):
            cancelada = True
            provedor.cancelar()
            break

        tool_calls: list[dict[str, Any]] = []
        texto_turno = ""
        for delta in provedor.enviar_stream(mensagens_llm, tools=tools):
            if _foi_cancelado(conversation_id):
                cancelada = True
                provedor.cancelar()
                break
            if delta.texto:
                texto_turno += delta.texto
                if emissor is not None:
                    emissor.emitir("chat.delta", {"texto": delta.texto})
            if delta.tool_calls:
                tool_calls = delta.tool_calls
            if delta.truncado:
                truncada = True
        if cancelada:
            texto_final = texto_turno
            break
        if truncada:
            raise ErroNucleo(
                limites.CODIGO_RESPOSTA_TRUNCADA,
                "A resposta foi truncada pelo limite de tokens. Peça para continuar.",
            )
        if not tool_calls:
            texto_final = texto_turno
            break

        rodadas_tool += 1
        if limites.rodada_tool_excedida(rodadas_tool):
            raise ErroNucleo(
                limites.CODIGO_LIMITE_RODADAS,
                "Limite de 12 rodadas de tool neste turno. Peça para continuar num turno novo.",
                {"rodada": rodadas_tool},
            )

        mensagens_llm.append(
            MensagemLLM(papel="assistant", conteudo=texto_turno or "", tool_calls=tool_calls)
        )
        for tc in tool_calls:
            fn = tc.get("function") or {}
            nome = fn.get("name") or ""
            args_brutos = fn.get("arguments") or "{}"
            tools_usadas.append(nome)
            trace_id = novo_id()
            if emissor is not None:
                emissor.emitir(
                    "chat.tool",
                    {
                        "trace_id": trace_id,
                        "tool": nome,
                        "fase": "inicio",
                        "args_resumo": (
                            args_brutos[:500] if isinstance(args_brutos, str) else str(args_brutos)[:500]
                        ),
                    },
                )
            t0 = time.perf_counter()
            resultado = executar_tool(nome, args_brutos, ctx)
            ms = int((time.perf_counter() - t0) * 1000)
            resumo = json.dumps(resultado, ensure_ascii=False)[:1000]
            if emissor is not None:
                emissor.emitir(
                    "chat.tool",
                    {
                        "trace_id": trace_id,
                        "tool": nome,
                        "fase": "fim",
                        "resultado_resumo": resumo,
                        "ms": ms,
                        "ok": bool(resultado.get("ok", True)),
                    },
                )
            mensagens_llm.append(
                MensagemLLM(
                    papel="tool",
                    conteudo=json.dumps(resultado, ensure_ascii=False),
                    tool_call_id=tc.get("id"),
                    name=nome,
                )
            )

    tokens_turno = estimar_payload(mensagens_llm)
    mapspec = ctx.get("mapspec") if isinstance(ctx.get("mapspec"), dict) else None
    msg_asst = repo.adicionar_mensagem(
        conversation_id,
        papel="assistente",
        conteudo=texto_final or ("(cancelado)" if cancelada else ""),
        cancelada=cancelada,
        mapspec_id=mapspec.get("id") if mapspec else None,
        mapspec_versao=mapspec.get("versao") if mapspec else None,
    )
    for nome in tools_usadas:
        repo.adicionar_tool_trace(
            conversation_id,
            message_id=msg_asst["message_id"],
            tool=nome,
            args_resumo="{}",
            resultado_resumo="ok",
            ok=True,
        )

    total = aberto["total"] + 2
    if total >= limites.COMPACT_SUMMARY_REGENERAR_CADA and (
        total % limites.COMPACT_SUMMARY_REGENERAR_CADA == 0
    ):
        novo_resumo = gerar_compact_summary(
            mensagens_db
            + [
                {"seq": 0, "papel": "usuario", "conteudo": mensagem},
                {"seq": 0, "papel": "assistente", "conteudo": texto_final},
            ]
        )
        repo.atualizar_tokens_e_resumo(
            conversation_id,
            tokens_entrada_delta=tokens_turno,
            tokens_saida_delta=limites.estimar_tokens(texto_final),
            compact_summary=novo_resumo,
            compact_ate_seq=msg_asst["seq"],
        )
    else:
        repo.atualizar_tokens_e_resumo(
            conversation_id,
            tokens_entrada_delta=tokens_turno,
            tokens_saida_delta=limites.estimar_tokens(texto_final),
        )

    _limpar_cancelamento(conversation_id)
    return {
        "conversation_id": conversation_id,
        "message_id": msg_asst["message_id"],
        "texto": texto_final,
        "cancelada": cancelada,
        "tools_usadas": tools_usadas,
        "mapspec": mapspec,
        "modelo_id": ctx.get("modelo_id"),
    }
