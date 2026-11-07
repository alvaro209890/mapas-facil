from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.estado import EstadoAgente, carregar_estado, salvar_estado
from mapasfacil_nucleo.agente.plano import PlanoAgente, registrar_tools_plano
from mapasfacil_nucleo.agente.provedor import MensagemLLM, ProvedorIA
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.protocolo import Emissor

_cancelados: set[str] = set()
_lock_cancelamento = threading.Lock()


def pedir_cancelamento(conversation_id: str) -> None:
    with _lock_cancelamento:
        _cancelados.add(conversation_id)


def _foi_cancelado(conversation_id: str) -> bool:
    with _lock_cancelamento:
        return conversation_id in _cancelados


def _limpar_cancelamento(conversation_id: str) -> None:
    with _lock_cancelamento:
        _cancelados.discard(conversation_id)


class EmissorInterceptador:
    """Encapsula o Emissor para sincronizar eventos reais com o EstadoAgente."""

    def __init__(self, emissor: Emissor | None, estado: EstadoAgente, ws_root: Path | None) -> None:
        self.emissor_real = emissor
        self.estado = estado
        self.ws_root = ws_root

    def emitir(self, evento: str, dados: dict[str, Any]) -> dict[str, Any]:
        agora = time.time()
        if evento == "agente.arquivo":
            self.estado.arquivos.append(
                {"caminho": dados.get("caminho"), "acao": dados.get("acao"), "ts": agora}
            )
        elif evento == "agente.preview":
            self.estado.previews.append(
                {"caminho": dados.get("caminho"), "pagina": dados.get("pagina"), "ts": agora}
            )
        elif evento == "agente.aprovacao":
            # Não expor ou persistir tokens criptográficos no estado público (.agente/estado.json)
            self.estado.aprovacao = {
                "acao": dados.get("acao"),
                "caminho": dados.get("caminho"),
                "motivo": dados.get("motivo"),
            }
            self.estado.status = "aguardando_aprovacao"
        elif evento == "agente.plano":
            # O plano do modelo nunca pode editar o estado de aprovação
            self.estado.passos = list(dados.get("passos") or [])
        elif evento == "agente.passo":
            pid = dados.get("id")
            for p in self.estado.passos:
                if p.get("id") == pid:
                    for k in ("titulo", "status", "resumo"):
                        if k in dados:
                            p[k] = dados[k]
                    break
        elif evento == "agente.fim":
            novo_status = dados.get("status")
            if novo_status:
                self.estado.status = novo_status
            if dados.get("resumo"):
                self.estado.resumo = dados.get("resumo")
            if dados.get("versao") is not None:
                self.estado.versao = dados.get("versao")

        if self.ws_root is not None:
            salvar_estado(self.ws_root, self.estado)

        if self.emissor_real is not None:
            return self.emissor_real.emitir(evento, dados)
        return {"evento": evento, "dados": dados}


class OrquestradorV2:
    """Orquestrador do Agente V2 com loop configurável (default 100),

    encerramento em falhas repetidas, eventos reais, suporte a aprovação e
    persistência de estado em .agente/estado.json.
    """

    def __init__(
        self,
        registro: RegistroFerramentas,
        provedor: ProvedorIA,
        max_rodadas: int = 100,
        limite_falhas_consecutivas: int = 3,
    ) -> None:
        self.registro = registro
        self.provedor = provedor
        self.max_rodadas = max_rodadas
        self.limite_falhas_consecutivas = limite_falhas_consecutivas

    def executar(
        self,
        conversation_id: str,
        mensagem: str,
        workspace: Path | str | None = None,
        emissor: Emissor | None = None,
        contexto_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ws_root = Path(workspace).resolve() if workspace else None

        # Carregar ou inicializar estado
        estado = (carregar_estado(ws_root) if ws_root else None) or EstadoAgente(
            conversation_id=conversation_id,
            status="em_andamento",
        )
        estado.status = "em_andamento"
        if ws_root:
            salvar_estado(ws_root, estado)

        emissor_sync = EmissorInterceptador(emissor, estado, ws_root)
        plano = PlanoAgente(emissor=emissor_sync)  # type: ignore[arg-type]
        registrar_tools_plano(self.registro, plano)

        ctx: dict[str, Any] = {
            "conversation_id": conversation_id,
            "workspace": ws_root,
            "emissor": emissor_sync,
            "plano": plano,
            "estado": estado,
        }
        if contexto_extra:
            ctx.update(contexto_extra)

        mensagens_llm = [
            MensagemLLM(
                papel="system",
                conteudo=(
                    "Você é o Agente Cartográfico V2 do Mapas Fácil. "
                    "Use as ferramentas disponíveis para inspecionar, recortar, medir, gerar "
                    "e validar mapas e arquivos. Defina o plano antes de agir e atualize cada passo."
                ),
            ),
            MensagemLLM(papel="user", conteudo=mensagem),
        ]

        tools_schemas = self.registro.schemas_openai()
        rodada = 0
        falhas_por_tool: dict[str, int] = {}
        texto_acumulado = ""

        while rodada < self.max_rodadas:
            if _foi_cancelado(conversation_id):
                estado.status = "cancelado"
                emissor_sync.emitir("agente.fim", {"status": "cancelado", "resumo": "Cancelado pelo usuário"})
                if ws_root:
                    salvar_estado(ws_root, estado)
                return {"status": "cancelado", "resumo": "Cancelado pelo usuário"}

            rodada += 1
            tool_calls = []
            texto_rodada = ""

            for delta in self.provedor.enviar_stream(mensagens_llm, tools=tools_schemas):
                if _foi_cancelado(conversation_id):
                    estado.status = "cancelado"
                    self.provedor.cancelar()
                    break
                if delta.texto:
                    texto_rodada += delta.texto
                    if emissor is not None:
                        emissor.emitir("chat.delta", {"texto": delta.texto})
                if delta.raciocinio and emissor is not None:
                    emissor.emitir("chat.raciocinio", {"texto": delta.raciocinio})
                if delta.tool_calls:
                    tool_calls = delta.tool_calls

            texto_acumulado = f"{texto_acumulado}\n{texto_rodada}".strip() if texto_acumulado else texto_rodada

            if estado.status == "cancelado":
                emissor_sync.emitir("agente.fim", {"status": "cancelado"})
                if ws_root:
                    salvar_estado(ws_root, estado)
                return {"status": "cancelado"}

            # Se a LLM não chamou nenhuma ferramenta, concluiu o turno
            if not tool_calls:
                estado.status = "concluido"
                estado.resumo = texto_acumulado or "Execução concluída."
                emissor_sync.emitir(
                    "agente.fim",
                    {"status": "concluido", "resumo": estado.resumo, "versao": estado.versao},
                )
                if ws_root:
                    salvar_estado(ws_root, estado)
                return {"status": "concluido", "resumo": estado.resumo, "rodadas": rodada}

            mensagens_llm.append(
                MensagemLLM(papel="assistant", conteudo=texto_rodada, tool_calls=tool_calls)
            )

            for call in tool_calls:
                fn = call.get("function") or {}
                nome = fn.get("name") or ""
                args = fn.get("arguments") or "{}"

                res = self.registro.executar(nome, args, ctx)

                # Rastrear falha repetida
                ok = bool(res.get("ok", True))
                if not ok:
                    falhas_por_tool[nome] = falhas_por_tool.get(nome, 0) + 1
                    if falhas_por_tool[nome] >= self.limite_falhas_consecutivas:
                        motivo = (
                            f"Loop encerrado após {falhas_por_tool[nome]} falhas consecutivas "
                            f"da ferramenta '{nome}': {res.get('mensagem', 'Erro desconhecido')}"
                        )
                        estado.status = "erro"
                        estado.resumo = motivo
                        emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": motivo})
                        if ws_root:
                            salvar_estado(ws_root, estado)
                        return {"status": "erro", "resumo": motivo, "codigo": "IA-035"}
                else:
                    falhas_por_tool[nome] = 0

                # Interrompe turno se exigir aprovação
                if res.get("aguardando_aprovacao"):
                    estado.status = "aguardando_aprovacao"
                    estado.resumo = res.get("mensagem", "Aguardando aprovação do usuário.")
                    if ws_root:
                        salvar_estado(ws_root, estado)
                    return {
                        "status": "aguardando_aprovacao",
                        "aprovacao": res,
                        "resumo": estado.resumo,
                        "rodadas": rodada,
                    }

                mensagens_llm.append(
                    MensagemLLM(
                        papel="tool",
                        conteudo=json.dumps(res, ensure_ascii=False, default=str),
                        tool_call_id=call.get("id"),
                        name=nome,
                    )
                )

        # Atingiu o teto de max_rodadas
        motivo_limite = f"Limite configurado de {self.max_rodadas} rodadas atingido."
        estado.status = "erro"
        estado.resumo = motivo_limite
        emissor_sync.emitir("agente.fim", {"status": "erro", "resumo": motivo_limite})
        if ws_root:
            salvar_estado(ws_root, estado)
        return {"status": "erro", "resumo": motivo_limite, "codigo": "IA-030"}
