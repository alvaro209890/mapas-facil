# Loop de orquestração: contexto → provedor → tools → eventos (F1-06 / G7).
#
# Invariantes deste módulo:
#  · nada vai ao provedor sem passar por `contexto.montar_mensagens_llm` (AP-10);
#  · a 25ª rodada de tool no mesmo turno é `IA-030` — tool que erra conta rodada;
#  · cancelamento grava a mensagem parcial com `cancelada = 1` e fecha o HTTP;
#  · o turno só termina depois de gravar mensagem, traces e tokens — inclusive
#    quando falha, para o transcript nunca perder o que já foi produzido.

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.anexos import AnexoEntrada
from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.agente.contexto import (
    compactar_se_preciso,
    estimar_payload,
    montar_mensagens_llm,
)
from mapasfacil_nucleo.agente.deepseek import DeepSeekProvedor
from mapasfacil_nucleo.agente.estado import EstadoAgente, carregar_estado, salvar_estado
from mapasfacil_nucleo.agente.orquestrador_v2 import EmissorInterceptador
from mapasfacil_nucleo.agente.plano import PlanoAgente, registrar_tools_plano
from mapasfacil_nucleo.agente.provedor import MensagemLLM, ProvedorIA
from mapasfacil_nucleo.agente.registro import carregar_todas_ferramentas_v2, registro_padrao
from mapasfacil_nucleo.agente.resumo import gerar_compact_summary
from mapasfacil_nucleo.agente.tools import executar as executar_tool
from mapasfacil_nucleo.agente.tools import schemas_openai
from mapasfacil_nucleo.agente import mapspec_store
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import ContextoTurno
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
from mapasfacil_nucleo.protocolo import Emissor, novo_id
from mapasfacil_nucleo.workspace import servico as workspace_servico

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
    # Modo servidor: o provedor é o 9Router num formato OpenAI-compatível (W5-16 / D33).
    if (os.environ.get("MAPASFACIL_PROVEDOR") or "").strip() == "openai_compat":
        from mapasfacil_nucleo.agente import openai_compat

        return openai_compat.do_ambiente()
    chave = ler_chave_deepseek()
    if not chave:
        raise ErroNucleo(
            limites.CODIGO_SEM_CHAVE,
            "Chave DeepSeek ausente. Configure deepseek_api_key em secrets.local.json "
            "ou use a galeria de modelos (modo determinístico).",
        )
    return DeepSeekProvedor(chave)


def _resolver_workspace(
    workspace: Path | str | None,
    conversation_id: str,
    repo: Any,
) -> Path | None:
    if workspace is not None:
        return Path(workspace).resolve()
    estado_ws = workspace_servico.estado_atual()
    if estado_ws is not None:
        if hasattr(estado_ws, "guard") and hasattr(estado_ws.guard, "raiz"):
            return estado_ws.guard.raiz
        if hasattr(estado_ws, "pasta"):
            return Path(estado_ws.pasta).resolve()
    try:
        from mapasfacil_nucleo import projeto_servidor

        raiz_proj = projeto_servidor.raiz()
        if raiz_proj is not None:
            return Path(raiz_proj).resolve()
    except Exception:
        pass
    try:
        info = repo.abrir_conversa(conversation_id, limite=1)
        if info.get("workspace"):
            return Path(info["workspace"]).resolve()
    except Exception:
        pass
    return None


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
    anexos: list[AnexoEntrada] | None = None,
    workspace: Path | str | None = None,
    max_rodadas: int | None = None,
    limite_falhas_consecutivas: int | None = None,
    eventos_agente: bool | None = None,
) -> dict[str, Any]:
    _limpar_cancelamento(conversation_id)
    repo = conversas_servico.repositorio()
    msg_usuario = repo.adicionar_mensagem(conversation_id, papel="usuario", conteudo=mensagem)
    for indice, anexo in enumerate(anexos or [], start=1):
        repo.adicionar_anexo(
            conversation_id,
            message_id=msg_usuario["message_id"],
            indice=indice,
            nome_original=anexo.nome,
            mime=anexo.mime,
            dados=anexo.dados,
        )

    ctx_conversa = repo.contexto_para_turno(conversation_id)
    if limites.excede_conversa(ctx_conversa.tokens_entrada):
        raise ErroNucleo(
            limites.CODIGO_TETO_CONVERSA,
            "Esta conversa atingiu o teto de tokens. Abra um chat novo ou ramifique.",
            {"tokens_entrada": ctx_conversa.tokens_entrada},
        )

    deve_emitir_agente = eventos_agente
    if deve_emitir_agente is None:
        deve_emitir_agente = bool(workspace is not None or max_rodadas is not None or limite_falhas_consecutivas is not None)

    ws_root = _resolver_workspace(workspace, conversation_id, repo)
    estado = (carregar_estado(ws_root) if ws_root else None) or EstadoAgente(
        conversation_id=conversation_id,
        status="em_andamento",
    )
    estado.conversation_id = conversation_id
    estado.status = "em_andamento"
    if ws_root:
        salvar_estado(ws_root, estado)

    # Se deve_emitir_agente for False (ex.: testes legados de chat puro), o interceptador
    # sincroniza o estado interno mas não despacha agente.* para o emissor público legado
    class _EmissorFiltrado:
        def __init__(self, inner: EmissorInterceptador, repassar_agente: bool) -> None:
            self.inner = inner
            self.repassar_agente = repassar_agente

        def emitir(self, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
            if not self.repassar_agente and evento.startswith("agente."):
                # apenas sincroniza no estado, sem repassar para emissor_real
                emissor_salvo = self.inner.emissor_real
                self.inner.emissor_real = None
                try:
                    return self.inner.emitir(evento, dados)
                finally:
                    self.inner.emissor_real = emissor_salvo
            return self.inner.emitir(evento, dados)

    base_interceptador = EmissorInterceptador(emissor, estado, ws_root)
    emissor_sync = _EmissorFiltrado(base_interceptador, deve_emitir_agente)
    plano = PlanoAgente(emissor=emissor_sync)  # type: ignore[arg-type]
    registrar_tools_plano(registro_padrao, plano)

    mapspec_base = mapspec_da_conversa(conversation_id)
    ctx: dict[str, Any] = {
        "mapspec": mapspec_base,
        "emissor": emissor_sync,
        "workspace": ws_root,
        "conversation_id": conversation_id,
        "plano": plano,
        "estado": estado,
    }

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

    if not registro_padrao.nomes_tools():
        carregar_todas_ferramentas_v2(registro_padrao)

    provedor = _obter_provedor()
    tools = schemas_openai()
    turno = _Turno()
    erro_final: ErroNucleo | None = None
    falhas_por_tool: dict[str, int] = {}
    teto_rodadas = max_rodadas if max_rodadas is not None else limites.RODADAS_TOOL_MAX_POR_TURNO

    try:
        while True:
            if _foi_cancelado(conversation_id):
                turno.cancelada = True
                provedor.cancelar()
                emissor_sync.emitir("agente.fim", {"status": "cancelado", "resumo": "Cancelado pelo usuário"})
                break

            tool_calls: list[dict[str, Any]] = []
            texto_rodada = ""
            truncada = False
            for delta in provedor.enviar_stream(mensagens_llm, tools=tools):
                if _foi_cancelado(conversation_id):
                    turno.cancelada = True
                    provedor.cancelar()
                    emissor_sync.emitir("agente.fim", {"status": "cancelado", "resumo": "Cancelado pelo usuário"})
                    break
                if delta.texto:
                    texto_rodada += delta.texto
                    if emissor is not None:
                        emissor.emitir("chat.delta", {"texto": delta.texto})
                if delta.raciocinio and emissor is not None:
                    emissor.emitir("chat.raciocinio", {"texto": delta.raciocinio})
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
                motivo_trunc = "A resposta foi truncada pelo limite de tokens. Peça para continuar."
                emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": motivo_trunc})
                erro_final = ErroNucleo(
                    limites.CODIGO_RESPOSTA_TRUNCADA,
                    motivo_trunc,
                    {"tokens_saida_max": limites.SAIDA_MAX_TOKENS},
                )
                break
            if not tool_calls:
                estado.status = "concluido"
                estado.resumo = turno.texto or "Execução concluída."
                versao_num = (ctx.get("mapspec") or {}).get("versao")
                emissor_sync.emitir(
                    "agente.fim",
                    {"status": "concluido", "resumo": estado.resumo, "versao": versao_num},
                )
                break

            turno.rodadas_tool += 1
            if limites.rodada_tool_excedida(turno.rodadas_tool, max_rodadas=teto_rodadas):
                motivo_limite = (
                    f"Limite de {teto_rodadas} rodadas de tool neste turno. "
                    "Peça para continuar num turno novo."
                )
                emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": motivo_limite})
                erro_final = ErroNucleo(
                    limites.CODIGO_LIMITE_RODADAS,
                    motivo_limite,
                    {"rodada": turno.rodadas_tool, "tools": turno.tools_usadas[-5:]},
                )
                break

            mensagens_llm.append(
                MensagemLLM(papel="assistant", conteudo=texto_rodada or "", tool_calls=tool_calls)
            )
            interromper_loop = False
            for chamada in tool_calls:
                msg_tool, res_tool = _rodar_tool(chamada, ctx=ctx, turno=turno, emissor=emissor)
                mensagens_llm.append(msg_tool)

                fn = chamada.get("function") or {}
                nome_tool = fn.get("name") or ""
                ok_tool = bool(res_tool.get("ok", True))
                if not ok_tool and limite_falhas_consecutivas is not None:
                    falhas_por_tool[nome_tool] = falhas_por_tool.get(nome_tool, 0) + 1
                    if falhas_por_tool[nome_tool] >= limite_falhas_consecutivas:
                        motivo_falha = (
                            f"Loop encerrado após {falhas_por_tool[nome_tool]} falhas consecutivas "
                            f"da ferramenta '{nome_tool}': {res_tool.get('mensagem', 'Erro desconhecido')}"
                        )
                        emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": motivo_falha})
                        erro_final = ErroNucleo(
                            "IA-035",
                            motivo_falha,
                            {"tool": nome_tool, "falhas": falhas_por_tool[nome_tool]},
                        )
                        interromper_loop = True
                        break
                else:
                    falhas_por_tool[nome_tool] = 0

                if res_tool.get("aguardando_aprovacao"):
                    estado.status = "aguardando_aprovacao"
                    estado.resumo = res_tool.get("mensagem", "Aguardando aprovação do usuário.")
                    emissor_sync.emitir(
                        "agente.fim",
                        {"status": "aguardando_aprovacao", "resumo": estado.resumo},
                    )
                    ctx["aguardando_aprovacao"] = True
                    ctx["aprovacao_pendente"] = res_tool
                    interromper_loop = True
                    break

                if ctx.get("aguardando_pergunta"):
                    estado.status = "aguardando_pergunta"
                    perg_dict = ctx.get("pergunta_pendente") or {}
                    estado.resumo = str(perg_dict.get("pergunta") or "Aguardando resposta do usuário.")
                    emissor_sync.emitir(
                        "agente.fim",
                        {"status": "aguardando_pergunta", "resumo": estado.resumo},
                    )
                    interromper_loop = True
                    break

            if interromper_loop:
                break
    except Exception as exc:
        if erro_final is None and not isinstance(exc, ErroNucleo):
            estado.status = "erro"
            estado.resumo = str(exc)
            emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": str(exc)})
        raise

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
        pergunta_pendente=ctx.get("pergunta_pendente"),
        estado=estado,
        aprovacao_pendente=ctx.get("aprovacao_pendente"),
        ws_root=ws_root,
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
) -> tuple[MensagemLLM, dict[str, Any]]:
    """Executa uma tool, emite `chat.tool` (início/fim) e devolve a mensagem de tool e o resultado."""
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
    msg = MensagemLLM(
        papel="tool",
        conteudo=json.dumps(resultado, ensure_ascii=False, default=str),
        tool_call_id=tool_call.get("id"),
        name=nome,
    )
    return msg, resultado


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
    pergunta_pendente: dict[str, Any] | None = None,
    estado: EstadoAgente | None = None,
    aprovacao_pendente: dict[str, Any] | None = None,
    ws_root: Path | None = None,
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

    if estado is not None and ws_root is not None:
        salvar_estado(ws_root, estado)

    ret = {
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
    if estado is not None:
        ret["estado"] = estado.para_dict()
        ret["status"] = estado.status
    if aprovacao_pendente is not None:
        ret["aprovacao"] = aprovacao_pendente
        ret["status"] = "aguardando_aprovacao"
    if pergunta_pendente:
        ret["pergunta"] = pergunta_pendente
    return ret


__all__ = (
    "configurar_provedor",
    "esquecer_conversa",
    "executar_turno",
    "mapspec_da_conversa",
    "pedir_cancelamento",
)
