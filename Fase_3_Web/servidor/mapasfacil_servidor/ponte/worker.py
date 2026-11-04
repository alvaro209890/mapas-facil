"""Um processo do núcleo por projeto (W-04 §worker.py).

Responsabilidades:

- subir o núcleo com **ambiente mínimo** (nunca `os.environ` inteiro);
- falar NDJSON por stdio, casando `res` com `req` por `id` e entregando `evt` ao
  dono da requisição (ou ao callback de projeto, quando o evento não tem req);
- transformar morte do processo, linha inválida e timeout em erros tipados
  (`SV-220`, `SV-221`, `SV-230`) — o chamador nunca vê `ProcessLookupError`;
- redigir CPF e chave antes de gravar `stderr` em log.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..erros import ErroServidor
from . import protocolo

LIMITE_LINHA = 16 * 1024 * 1024

# Plomería do SO que o filho precisa e que **não** é configuração: sem estas, o
# Python no Windows nem inicializa o Winsock (`OSError 10106` em `_overlapped`).
_PASS_THROUGH = (
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS",
    "SYSTEMDRIVE",
)
ESPERA_ENCERRAR_S = 10.0
ESPERA_CANCELAR_S = 30.0

# Redação obrigatória nos logs de stderr (W-04, critério de aceite): a regra vive em
# `logs_redigidos` (W3-24) para valer em todo log do servidor, não só no do worker.
from ..logs_redigidos import redigir as _redigir_compartilhado


def redigir(texto: str) -> str:
    """Mascara CPF e chaves em texto de log. Nunca logar o valor original."""
    return _redigir_compartilhado(texto)


def montar_env(
    *,
    projeto_raiz: Path,
    usuario_id: str,
    segredos: dict[str, str] | None = None,
    vagas_dir: Path | None = None,
    max_jobs: int | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Ambiente do worker: o mínimo para o núcleo rodar em modo servidor.

    Não herda `os.environ` (W-04 §worker): o servidor tem variáveis que o núcleo não
    deve ver e a ponte não pode vazar configuração para o filho.
    """
    env: dict[str, str] = {
        "MAPASFACIL_MODO": "servidor",
        "MAPASFACIL_SESSAO_SERVIDOR": usuario_id,
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "HOME": os.environ.get("HOME", str(projeto_raiz)),
        "TMPDIR": str(projeto_raiz / ".tmp"),
        # Estado do projeto (chats, mapspecs, índice) fica DENTRO da pasta dele:
        # nada de APPDATA/XDG no servidor e um projeto não enxerga o outro.
        "MAPASFACIL_DADOS": str(projeto_raiz / ".estado"),
        "MAPASFACIL_CHATS_DIR": str(projeto_raiz / ".estado" / "chats"),
    }
    for nome in _PASS_THROUGH:
        valor = os.environ.get(nome)
        if valor:
            env[nome] = valor
    if vagas_dir is not None:
        env["MAPASFACIL_VAGAS_DIR"] = str(vagas_dir)
    if max_jobs is not None:
        env["MAPASFACIL_MAX_JOBS"] = str(max_jobs)
    for nome, valor in (segredos or {}).items():
        if valor:
            env[nome] = valor
    if extra:
        env.update({k: v for k, v in extra.items() if v})
    return env


@dataclass
class _Pendente:
    futuro: asyncio.Future
    ao_evento: Callable[[dict[str, Any]], Awaitable[None]] | None = None


@dataclass
class Worker:
    projeto_id: str
    raiz: Path
    cmd: list[str]
    env: dict[str, str]
    timeout_req_s: float = 900.0
    ao_evento_projeto: Callable[[dict[str, Any]], Awaitable[None]] | None = None
    log_path: Path | None = None
    estado: str = "iniciando"
    ultimo_uso: float = 0.0
    _proc: asyncio.subprocess.Process | None = None
    _pendentes: dict[str, _Pendente] = field(default_factory=dict)
    _tarefas: list[asyncio.Task] = field(default_factory=list)
    _morto: asyncio.Event = field(default_factory=asyncio.Event)
    _motivo_morte: str = ""
    _log: Any = None

    # -- ciclo de vida ----------------------------------------------------
    async def iniciar(self, *, timeout_handshake_s: float = 120.0) -> None:
        if self._proc is not None and self._proc.returncode is None:
            return
        (self.raiz / ".tmp").mkdir(parents=True, exist_ok=True)
        self.estado = "iniciando"
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self.cmd,
                cwd=str(self.raiz),
                env=self.env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=LIMITE_LINHA,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            self.estado = "caido"
            raise ErroServidor(
                "SV-222",
                f"Não foi possível subir o núcleo: {self.cmd[0]!r} não existe.",
                status_http=500,
                porque="O servidor hospeda o núcleo como processo filho (D23).",
                o_que_fazer="Confira MF_PYTHON_NUCLEO e se o pacote do núcleo está "
                "instalado nesse interpretador.",
                detalhes={"comando": self.cmd[0]},
            ) from exc

        self._morto.clear()
        self._tarefas = [
            asyncio.create_task(self._ler_stdout(), name=f"stdout-{self.projeto_id}"),
            asyncio.create_task(self._ler_stderr(), name=f"stderr-{self.projeto_id}"),
            asyncio.create_task(self._vigiar(), name=f"vigia-{self.projeto_id}"),
        ]
        await self._handshake(timeout_s=timeout_handshake_s)

    async def _handshake(self, *, timeout_s: float) -> None:
        """Uma chamada barata (`ping`) prova que o filho fala o protocolo."""
        try:
            await self.chamar("ping", {}, timeout_s=timeout_s)
        except ErroServidor:
            # O filho respondeu (mesmo que com erro): o canal está vivo.
            if self._proc is None or self._proc.returncode is not None:
                raise
        self.estado = "pronto"

    async def chamar(
        self,
        metodo: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
        ao_evento: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Envia `req` e devolve o `resultado` do `res` (ou levanta erro tipado)."""
        if self._proc is None or self._proc.returncode is not None:
            raise ErroServidor(
                "SV-221",
                "O worker deste projeto não está vivo.",
                status_http=503,
                porque="O processo do núcleo morreu (ou nunca subiu).",
                o_que_fazer="A próxima mensagem sobe um worker novo.",
                detalhes={"projeto_id": self.projeto_id},
            )

        envelope = protocolo.envelope_req(metodo, params)
        futuro: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pendentes[envelope["id"]] = _Pendente(futuro=futuro, ao_evento=ao_evento)
        self.estado = "ocupado"
        self.ultimo_uso = asyncio.get_running_loop().time()

        try:
            assert self._proc.stdin is not None
            linha = protocolo.serializar_linha(envelope) + "\n"
            self._proc.stdin.write(linha.encode("utf-8"))
            await self._proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            self._pendentes.pop(envelope["id"], None)
            self.estado = "caido"
            raise ErroServidor(
                "SV-221",
                "O worker morreu antes de receber a requisição.",
                status_http=503,
                detalhes={"projeto_id": self.projeto_id, "metodo": metodo},
            ) from exc

        limite = timeout_s if timeout_s is not None else self.timeout_req_s
        try:
            resposta = await asyncio.wait_for(futuro, timeout=limite)
        except asyncio.TimeoutError as exc:
            self._pendentes.pop(envelope["id"], None)
            await self.cancelar(envelope["id"])
            raise ErroServidor(
                "SV-220",
                f"O núcleo não respondeu {metodo!r} em {int(limite)} s.",
                status_http=504,
                porque="Requisição estourou o tempo; o worker foi cancelado e "
                "encerrado se não voltar.",
                o_que_fazer="Tente de novo; se repetir, veja o log do worker.",
                detalhes={"projeto_id": self.projeto_id, "metodo": metodo},
            ) from exc
        finally:
            # Com pedidos em paralelo (o chat corre enquanto a tela lê o histórico), o worker
            # só fica "pronto" quando o último pendente acaba — senão a varredura de ociosos
            # podia matá-lo no meio de uma geração.
            if self.estado == "ocupado" and not self._pendentes:
                self.estado = "pronto"
            self.ultimo_uso = asyncio.get_running_loop().time()

        if resposta.get("ok") is False:
            erro = resposta.get("erro") or {}
            raise ErroServidor(
                f"NUCLEO:{erro.get('codigo', 'NU-000')}",
                erro.get("mensagem", "O núcleo recusou a requisição."),
                status_http=400,
                porque=erro.get("porque"),
                o_que_fazer=erro.get("o_que_fazer"),
                detalhes=erro.get("detalhes"),
            )
        return resposta.get("resultado") or {}

    async def cancelar(self, req_id: str) -> None:
        """Pede cancelamento do job daquela requisição (melhor esforço)."""
        futuro = self._pendentes.pop(req_id, None)
        if futuro is not None and not futuro.futuro.done():
            futuro.futuro.set_exception(
                ErroServidor("SV-223", "Requisição cancelada.", status_http=409)
            )
        envelope = protocolo.envelope_req("mapa.cancelar", {"req_id": req_id})
        if self._proc is not None and self._proc.returncode is None and self._proc.stdin:
            with contextlib.suppress(Exception):
                self._proc.stdin.write(
                    (protocolo.serializar_linha(envelope) + "\n").encode("utf-8")
                )
                await self._proc.stdin.drain()

    async def encerrar(self, *, motivo: str = "encerrando") -> None:
        self.estado = "encerrando"
        self._motivo_morte = motivo
        proc = self._proc
        for tarefa in self._tarefas:
            tarefa.cancel()
        self._tarefas = []
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=ESPERA_ENCERRAR_S)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                with contextlib.suppress(Exception):
                    await proc.wait()
        self._proc = None
        self.estado = "caido"
        self._falhar_pendentes(motivo)
        if self._log is not None:
            self._log.close()
            self._log = None

    def _falhar_pendentes(self, motivo: str) -> None:
        pendentes, self._pendentes = self._pendentes, {}
        for _id, pendente in pendentes.items():
            if not pendente.futuro.done():
                pendente.futuro.set_exception(
                    ErroServidor(
                        "SV-221",
                        f"O worker caiu durante a requisição ({motivo}).",
                        status_http=503,
                        detalhes={"projeto_id": self.projeto_id},
                    )
                )

    # -- leitura ----------------------------------------------------------
    async def _ler_stdout(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            try:
                linha = await self._proc.stdout.readline()
            except (asyncio.LimitOverrunError, ValueError):
                await self._abortar("SV-230", "linha acima de 16 MiB")
                return
            if not linha:
                break
            try:
                mensagem = protocolo.parsear_linha(linha.decode("utf-8", "replace"))
            except protocolo.ProtocoloInvalido as exc:
                await self._abortar("SV-230", f"linha fora do protocolo: {exc}")
                return
            await self._despachar(mensagem)

    async def _despachar(self, mensagem: dict[str, Any]) -> None:
        tipo = mensagem.get("tipo")
        if tipo == "res":
            pendente = self._pendentes.pop(mensagem.get("id", ""), None)
            if pendente is not None and not pendente.futuro.done():
                pendente.futuro.set_result(mensagem)
            return
        if tipo != "evt":
            return
        id_req = mensagem.get("id", "")
        pendente = self._pendentes.get(id_req)
        if pendente is not None and pendente.ao_evento is not None:
            await pendente.ao_evento(mensagem)
            return
        if self.ao_evento_projeto is not None:
            await self.ao_evento_projeto(mensagem)

    async def _ler_stderr(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        while True:
            linha = await self._proc.stderr.readline()
            if not linha:
                break
            self._gravar_log(linha.decode("utf-8", "replace").rstrip("\n"))

    def _gravar_log(self, linha: str) -> None:
        # stdout do núcleo é protocolo; diagnóstico vai para cá, redigido.
        if self.log_path is None:
            print(redigir(linha), file=sys.stderr)
            return
        if self._log is None:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log = self.log_path.open("a", encoding="utf-8")
        self._log.write(redigir(linha) + "\n")
        self._log.flush()

    async def _vigiar(self) -> None:
        assert self._proc is not None
        returncode = await self._proc.wait()
        self.estado = "caido"
        self._falhar_pendentes(f"saiu com código {returncode}")
        self._morto.set()

    async def _abortar(self, codigo: str, motivo: str) -> None:
        self._motivo_morte = f"{codigo}: {motivo}"
        self._gravar_log(f"[ponte] {codigo} — {motivo}; encerrando worker")
        await self.encerrar(motivo=motivo)
