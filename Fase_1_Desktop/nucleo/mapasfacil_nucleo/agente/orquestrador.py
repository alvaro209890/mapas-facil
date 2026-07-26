# Loop de orquestração: contexto → provedor → tools → eventos (F1-06 / G7).
#
# Invariantes deste módulo:
#  · nada vai ao provedor sem passar por `contexto.montar_mensagens_llm` (AP-10);
#  · a 13ª rodada de tool no mesmo turno é `IA-030` — tool que erra conta rodada;
#  · cancelamento grava a mensagem parcial com `cancelada = 1` e fecha o HTTP;
#  · o turno só termina depois de gravar mensagem, traces e tokens — inclusive
#    quando falha, para o transcript nunca perder o que já foi produzido.

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.agente.contexto import (
    compactar_se_preciso,
    estimar_payload,
    montar_mensagens_llm,
)
from mapasfacil_nucleo.agente.deepseek import DeepSeekProvedor
from mapasfacil_nucleo.agente.provedor import MensagemLLM, ProvedorIA
from mapasfacil_nucleo.agente.resumo import gerar_compact_summary
from mapasfacil_nucleo.agente.tools import executar as executar_tool
from mapasfacil_nucleo.agente.tools import schemas_openai
from mapasfacil_nucleo.agente import mapspec_store
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import ContextoTurno
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
from mapasfacil_nucleo.protocolo import Emissor, novo_id

_cancelados: set[str] = set()
_lock = threading.Lock()
_provedor_override: ProvedorIA | None = None

# MapSpec vivo por conversa e a versão que o modelo já viu — envio por diff (F1-06 §3).
# Memória é cache; o JSON completo também fica em disco (`mapspec_store`) para
# sobreviver ao reinício do sidecar.
_mapspec_por_conversa: dict[str, dict[str, Any]] = {}
_mapspec_enviado: dict[str, dict[str, Any]] = {}


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


def mapspec_da_conversa(conversation_id: str) -> dict[str, Any] | None:
    """MapSpec vivo da conversa (tools de edição + disco)."""
    vivo = _mapspec_por_conversa.get(conversation_id)
    if vivo is not None:
        return vivo
    disco = mapspec_store.carregar_mapspec(conversation_id)
    if disco is not None:
        _mapspec_por_conversa[conversation_id] = disco
    return disco


def esquecer_conversa(conversation_id: str) -> None:
    """Solta o estado em memória da conversa (fechamento e testes)."""
    _mapspec_por_conversa.pop(conversation_id, None)
    _mapspec_enviado.pop(conversation_id, None)
    _limpar_cancelamento(conversation_id)


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


@dataclass
class _Turno:
    """O que precisa ser gravado ao fim do turno, aconteça o que acontecer."""

    texto: str = ""
    tools_usadas: list[str] = field(default_factory=list)
    traces: list[dict[str, Any]] = field(default_factory=list)
    rodadas_tool: int = 0
    cancelada: bool = False


def executar_turno(
    *,
    conversation_id: str,
    mensagem: str,
    emissor: Emissor | None = None,
    anexos: list[Any] | None = None,
) -> dict[str, Any]:
    del anexos  # anexos entram com o fluxo de visão (F1-07)
    _limpar_cancelamento(conversation_id)
    repo = conversas_servico.repositorio()
    repo.adicionar_mensagem(conversation_id, papel="usuario", conteudo=mensagem)

    ctx_conversa = repo.contexto_para_turno(conversation_id)
    if limites.excede_conversa(ctx_conversa.tokens_entrada):
        raise ErroNucleo(
            limites.CODIGO_TETO_CONVERSA,
            "Esta conversa atingiu o teto de tokens. Abra um chat novo ou ramifique.",
            {"tokens_entrada": ctx_conversa.tokens_entrada},
        )

    mapspec_base = mapspec_da_conversa(conversation_id)
    ctx: dict[str, Any] = {"mapspec": mapspec_base, "emissor": emissor}

    mensagens_llm = montar_mensagens_llm(
        mensagens_db=ctx_conversa.mensagens,
        compact_summary=ctx_conversa.compact_summary,
        mapspec=mapspec_base,
        mapspec_diff=_diff_do_mapspec(conversation_id, mapspec_base),
    )
    mensagens_llm, compact_usado, _ = compactar_se_preciso(
        mensagens_llm,
        compact_summary=ctx_conversa.compact_summary,
        mensagens_db=ctx_conversa.mensagens,
        mapspec=mapspec_base,
    )
    if mapspec_base is not None:
        _mapspec_enviado[conversation_id] = mapspec_base

    provedor = _obter_provedor()
    tools = schemas_openai()
    turno = _Turno()
    erro_final: ErroNucleo | None = None

    while True:
        if _foi_cancelado(conversation_id):
            turno.cancelada = True
            provedor.cancelar()
            break

        tool_calls: list[dict[str, Any]] = []
        texto_rodada = ""
        truncada = False
        for delta in provedor.enviar_stream(mensagens_llm, tools=tools):
            if _foi_cancelado(conversation_id):
                turno.cancelada = True
                provedor.cancelar()
                break
            if delta.texto:
                texto_rodada += delta.texto
                if emissor is not None:
                    emissor.emitir("chat.delta", {"texto": delta.texto})
            if delta.tool_calls:
                tool_calls = delta.tool_calls
            if delta.truncado:
                truncada = True

        # O texto de todas as rodadas entra na resposta: o modelo costuma
        # explicar o que vai fazer antes de chamar a tool, e isso não some.
        turno.texto = f"{turno.texto}\n{texto_rodada}".strip() if turno.texto else texto_rodada

        if turno.cancelada:
            break
        if truncada:
            erro_final = ErroNucleo(
                limites.CODIGO_RESPOSTA_TRUNCADA,
                "A resposta foi truncada pelo limite de tokens. Peça para continuar.",
                {"tokens_saida_max": limites.SAIDA_MAX_TOKENS},
            )
            break
        if not tool_calls:
            break

        turno.rodadas_tool += 1
        if limites.rodada_tool_excedida(turno.rodadas_tool):
            erro_final = ErroNucleo(
                limites.CODIGO_LIMITE_RODADAS,
                f"Limite de {limites.RODADAS_TOOL_MAX_POR_TURNO} rodadas de tool neste turno. "
                "Peça para continuar num turno novo.",
                {"rodada": turno.rodadas_tool, "tools": turno.tools_usadas[-5:]},
            )
            break

        mensagens_llm.append(
            MensagemLLM(papel="assistant", conteudo=texto_rodada or "", tool_calls=tool_calls)
        )
        for chamada in tool_calls:
            mensagens_llm.append(_rodar_tool(chamada, ctx=ctx, turno=turno, emissor=emissor))

    mapspec = ctx.get("mapspec") if isinstance(ctx.get("mapspec"), dict) else None
    if mapspec is not None:
        _mapspec_por_conversa[conversation_id] = mapspec
        mapspec_store.gravar_mapspec(conversation_id, mapspec)

    resultado = _fechar_turno(
        repo=repo,
        conversation_id=conversation_id,
        turno=turno,
        mensagens_llm=mensagens_llm,
        ctx_conversa=ctx_conversa,
        compact_usado=compact_usado,
        mapspec=mapspec,
        modelo_id=ctx.get("modelo_id"),
    )
    _limpar_cancelamento(conversation_id)
    if erro_final is not None:
        raise erro_final
    return resultado


def _diff_do_mapspec(
    conversation_id: str,
    mapspec: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Diff contra a versão que o modelo já viu; `None` = manda o MapSpec inteiro.

    Regra F1-06 §3: no primeiro turno com MapSpec vai o JSON completo; depois só
    o diff — e se o diff passar de `MAPSPEC_DIFF_MAX`, volta a mandar completo e
    reinicia a base. Se o MapSpec não mudou (mesmo `id`), manda diff vazio.
    """
    if mapspec is None:
        return None
    base = _mapspec_enviado.get(conversation_id)
    if base is None:
        return None
    if base.get("id") == mapspec.get("id"):
        return {"operacoes": []}
    delta = mapspec_diff(base, mapspec)
    if not limites.mapspec_diff_cabe(limites.estimar_tokens_json(delta)):
        return None
    return delta


def _regenerar_resumo(
    *,
    ctx_conversa: ContextoTurno,
    seq_assistente: int,
    conteudo_assistente: str,
    compact_usado: str | None,
) -> tuple[str | None, int | None]:
    """Decide se o `compact_summary` é regenerado neste turno e o que ele cobre.

    Regras (F1-06 §2):

    1. só existe resumo do que está **fora** da janela verbatim — resumir o que
       já vai inteiro no payload é gasto puro;
    2. a primeira mensagem que sai da janela é resumida na hora, senão sumiria
       do contexto sem ninguém perceber (pior que recusar — ver AP "truncar em
       silêncio");
    3. depois disso, regenera a cada `COMPACT_SUMMARY_REGENERAR_CADA` mensagens
       novas cobertas — medido por `seq`, não por resto de divisão do total, que
       erra em conversa ramificada ou com mensagem de sistema no meio. Entre uma
       regeneração e outra, até 6 mensagens ficam cobertas só pela janela
       verbatim; é o custo aceito no plano para não pagar `flash` todo turno.

    Retorna `(resumo, compact_ate_seq)`; `(None, None)` quando não é a hora.
    """
    historico = ctx_conversa.mensagens + [
        {"seq": seq_assistente, "papel": "assistente", "conteudo": conteudo_assistente}
    ]
    cauda_verbatim = limites.TURNOS_VERBATIM * 2  # turno ≈ par usuário+assistente
    if len(historico) <= cauda_verbatim:
        return None, None

    a_resumir = historico[:-cauda_verbatim]
    seq_corte = int(a_resumir[-1]["seq"])
    ja_coberto = ctx_conversa.compact_ate_seq
    if seq_corte <= ja_coberto:
        return None, None
    primeira_vez = not ctx_conversa.compact_summary
    if not primeira_vez and not limites.deve_regenerar_compact_summary(seq_corte - ja_coberto):
        return None, None

    resumo = gerar_compact_summary(a_resumir, excluir_ultimas=0)
    if not resumo:
        return (compact_usado, None) if compact_usado else (None, None)
    return resumo, seq_corte


def _rodar_tool(
    tool_call: dict[str, Any],
    *,
    ctx: dict[str, Any],
    turno: _Turno,
    emissor: Emissor | None,
) -> MensagemLLM:
    """Executa uma tool, emite `chat.tool` (início/fim) e devolve a mensagem de tool."""
    fn = tool_call.get("function") or {}
    nome = fn.get("name") or ""
    args_brutos = fn.get("arguments") or "{}"
    if not isinstance(args_brutos, str):
        args_brutos = json.dumps(args_brutos, ensure_ascii=False, default=str)
    turno.tools_usadas.append(nome)
    trace_id = novo_id()
    args_resumo = args_brutos[:500]
    if emissor is not None:
        emissor.emitir(
            "chat.tool",
            {"trace_id": trace_id, "tool": nome, "fase": "inicio", "args_resumo": args_resumo},
        )
    t0 = time.perf_counter()
    resultado = executar_tool(nome, args_brutos, ctx)
    ms = int((time.perf_counter() - t0) * 1000)
    resumo = json.dumps(resultado, ensure_ascii=False, default=str)[:1000]
    ok = bool(resultado.get("ok", True))
    if emissor is not None:
        emissor.emitir(
            "chat.tool",
            {
                "trace_id": trace_id,
                "tool": nome,
                "fase": "fim",
                "resultado_resumo": resumo,
                "ms": ms,
                "ok": ok,
            },
        )
    turno.traces.append(
        {
            "tool": nome,
            "args_resumo": args_resumo,
            "resultado_resumo": resumo,
            "ms": ms,
            "ok": ok,
            "erro_codigo": None if ok else resultado.get("codigo"),
        }
    )
    return MensagemLLM(
        papel="tool",
        conteudo=json.dumps(resultado, ensure_ascii=False, default=str),
        tool_call_id=tool_call.get("id"),
        name=nome,
    )


def _fechar_turno(
    *,
    repo: Any,
    conversation_id: str,
    turno: _Turno,
    mensagens_llm: list[MensagemLLM],
    ctx_conversa: ContextoTurno,
    compact_usado: str | None,
    mapspec: dict[str, Any] | None,
    modelo_id: str | None,
) -> dict[str, Any]:
    """Grava mensagem do assistente, traces, tokens e (se for a hora) o resumo."""
    tokens_turno = estimar_payload(mensagens_llm)
    conteudo = turno.texto or ("(cancelado)" if turno.cancelada else "")
    msg_asst = repo.adicionar_mensagem(
        conversation_id,
        papel="assistente",
        conteudo=conteudo,
        cancelada=turno.cancelada,
        mapspec_id=mapspec.get("id") if mapspec else None,
        mapspec_versao=mapspec.get("versao") if mapspec else None,
    )
    for trace in turno.traces:
        repo.adicionar_tool_trace(
            conversation_id,
            message_id=msg_asst["message_id"],
            tool=trace["tool"],
            args_resumo=trace["args_resumo"],
            resultado_resumo=trace["resultado_resumo"],
            ms=trace["ms"],
            ok=trace["ok"],
            erro_codigo=trace["erro_codigo"],
        )

    resumo_novo, resumo_ate_seq = _regenerar_resumo(
        ctx_conversa=ctx_conversa,
        seq_assistente=msg_asst["seq"],
        conteudo_assistente=conteudo,
        compact_usado=compact_usado,
    )
    repo.atualizar_tokens_e_resumo(
        conversation_id,
        tokens_entrada_delta=tokens_turno,
        tokens_saida_delta=limites.estimar_tokens(turno.texto),
        compact_summary=resumo_novo,
        compact_ate_seq=resumo_ate_seq,
    )

    return {
        "conversation_id": conversation_id,
        "message_id": msg_asst["message_id"],
        "seq": msg_asst["seq"],
        "texto": turno.texto,
        "cancelada": turno.cancelada,
        "tools_usadas": turno.tools_usadas,
        "rodadas_tool": turno.rodadas_tool,
        "mapspec": mapspec,
        "mapspec_versao": mapspec.get("versao") if mapspec else None,
        "modelo_id": modelo_id,
        "tokens_entrada_turno": tokens_turno,
    }


__all__ = (
    "configurar_provedor",
    "esquecer_conversa",
    "executar_turno",
    "mapspec_da_conversa",
    "pedir_cancelamento",
)
