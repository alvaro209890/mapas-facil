"""Pool de workers — um por projeto, com teto e ociosidade (W-04 §pool.py)."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..erros import ErroServidor
from . import allowlist, worker as worker_mod

ESPERA_VAGA_WORKER_S = 60.0


@dataclass
class Pool:
    """Guarda os workers vivos e decide quem sai quando o teto aperta.

    Regras (W-04):

    - reusa o worker do projeto; senão sobe um;
    - no teto, encerra o **ocioso há mais tempo** (nunca um ocupado);
    - se todos estão ocupados, espera até 60 s e devolve `SV-211`;
    - um turno de chat por projeto: segundo `chat.enviar` em curso → `SV-210`.
    """

    raiz_projetos: Path
    cmd_base: list[str]
    max_workers: int = 6
    timeout_req_s: float = 900.0
    worker_ocioso_s: float = 900.0
    env_por_projeto: Callable[[str, Path], dict[str, str]] | None = None
    _workers: dict[str, worker_mod.Worker] = field(default_factory=dict)
    _chat_em_curso: set[str] = field(default_factory=set)
    _travas: dict[str, asyncio.Lock] = field(default_factory=dict)
    _varredor: asyncio.Task | None = None

    # -- ciclo de vida ----------------------------------------------------
    def iniciar_varredura(self) -> None:
        if self._varredor is None or self._varredor.done():
            self._varredor = asyncio.create_task(self._varrer(), name="pool-varredura")

    async def encerrar_todos(self, *, motivo: str = "desligando") -> None:
        if self._varredor is not None:
            self._varredor.cancel()
            self._varredor = None
        self._chat_em_curso.clear()
        for w in list(self._workers.values()):
            with contextlib.suppress(Exception):
                await w.encerrar(motivo=motivo)
        self._workers.clear()

    async def _varrer(self) -> None:
        while True:
            await asyncio.sleep(60)
            limite = time.monotonic() - self.worker_ocioso_s
            for projeto_id, w in list(self._workers.items()):
                if w.estado == "pronto" and w.ultimo_uso < limite:
                    with contextlib.suppress(Exception):
                        await w.encerrar(motivo="ocioso")
                    self._workers.pop(projeto_id, None)

    # -- acesso -----------------------------------------------------------
    def _trava(self, projeto_id: str) -> asyncio.Lock:
        return self._travas.setdefault(projeto_id, asyncio.Lock())

    def obter_existente(self, projeto_id: str) -> worker_mod.Worker | None:
        w = self._workers.get(projeto_id)
        if w is not None and w.estado not in {"caido", "encerrando"}:
            return w
        return None

    async def obter(self, projeto_id: str) -> worker_mod.Worker:
        """Worker do projeto, subindo se preciso e respeitando o teto."""
        w = self.obter_existente(projeto_id)
        if w is not None:
            return w

        limite = time.monotonic() + ESPERA_VAGA_WORKER_S
        while len(self._workers) >= self.max_workers:
            ocioso = self._mais_ocioso()
            if ocioso is not None:
                chave, alvo = ocioso
                await alvo.encerrar(motivo="teto de workers")
                self._workers.pop(chave, None)
                break
            if time.monotonic() >= limite:
                raise ErroServidor(
                    "SV-211",
                    "Servidor cheio — todos os workers estão gerando.",
                    status_http=503,
                    porque=f"O teto é {self.max_workers} workers simultâneos.",
                    o_que_fazer="Tente em instantes; a geração em curso termina e libera.",
                    detalhes={"max_workers": self.max_workers},
                )
            await asyncio.sleep(1.0)

        raiz = self.raiz_projetos / projeto_id
        raiz.mkdir(parents=True, exist_ok=True)
        env = (
            self.env_por_projeto(projeto_id, raiz)
            if self.env_por_projeto is not None
            else worker_mod.montar_env(projeto_raiz=raiz, usuario_id="desconhecido")
        )
        w = worker_mod.Worker(
            projeto_id=projeto_id,
            raiz=raiz,
            cmd=list(self.cmd_base),
            env=env,
            timeout_req_s=self.timeout_req_s,
            log_path=self.raiz_projetos.parent / "logs" / "workers" / f"{projeto_id}.log",
        )
        await w.iniciar()
        self._workers[projeto_id] = w
        return w

    def _mais_ocioso(self) -> tuple[str, worker_mod.Worker] | None:
        candidatos = [
            (pid, w) for pid, w in self._workers.items() if w.estado == "pronto"
        ]
        if not candidatos:
            return None
        return min(candidatos, key=lambda par: par[1].ultimo_uso)

    async def chamar(
        self,
        projeto_id: str,
        metodo: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_s: float | None = None,
        ao_evento: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Verifica allowlist, garante o worker e chama. É a porta única da API."""
        allowlist.verificar(metodo)
        async with self._trava(projeto_id):
            w = await self.obter(projeto_id)
            if metodo == "chat.enviar":
                if projeto_id in self._chat_em_curso:
                    raise ErroServidor(
                        "SV-210",
                        "Já existe um turno de chat em andamento neste projeto.",
                        status_http=409,
                        porque="Um turno por projeto mantém a conversa coerente.",
                        o_que_fazer="Espere a resposta terminar — ou cancele.",
                        detalhes={"projeto_id": projeto_id},
                    )
                self._chat_em_curso.add(projeto_id)
                try:
                    return await w.chamar(
                        metodo, params, timeout_s=timeout_s, ao_evento=ao_evento
                    )
                finally:
                    self._chat_em_curso.discard(projeto_id)
            return await w.chamar(metodo, params, timeout_s=timeout_s, ao_evento=ao_evento)

    def estado(self) -> dict[str, Any]:
        return {
            "workers": len(self._workers),
            "max_workers": self.max_workers,
            "projetos": {
                pid: {"estado": w.estado, "ultimo_uso": w.ultimo_uso}
                for pid, w in self._workers.items()
            },
        }
