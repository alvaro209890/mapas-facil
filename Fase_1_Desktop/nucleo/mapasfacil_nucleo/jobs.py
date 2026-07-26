"""A10 — registro de jobs de `mapa.gerar` e `mapa.cancelar`.

Um job vive enquanto `mapa.gerar` roda. Cancelar:
1. marca o flag cooperativo (etapas do motor nativo/T2 checam entre si);
2. se houver subprocesso ArcPy, mata a árvore (`taskkill /T /F` no Windows;
   `killpg`/`terminate` nos demais).

O loop NDJSON precisa despachar `mapa.gerar` em thread (ver `__main__.py`)
para `mapa.cancelar` poder chegar enquanto o job ainda corre.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import novo_id

# Job cancelado pelo usuário — F1-01 §mapa.cancelar.
CODIGO_JOB_CANCELADO = "NU-050"


@dataclass
class Job:
    id: str
    cancelado: bool = False
    processo: subprocess.Popen[Any] | None = None
    pid: int | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_job_atual: str | None = None


def registrar() -> str:
    """Cria um job e o torna o 'atual'. Devolve o `job_id` (ULID)."""
    global _job_atual
    job_id = novo_id()
    with _jobs_lock:
        _jobs[job_id] = Job(id=job_id)
        _job_atual = job_id
    return job_id


def obter(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def atual() -> Job | None:
    with _jobs_lock:
        if _job_atual is None:
            return None
        return _jobs.get(_job_atual)


def anexar_processo(job_id: str, processo: subprocess.Popen[Any]) -> None:
    job = obter(job_id)
    if job is None:
        return
    with job.lock:
        job.processo = processo
        job.pid = processo.pid


def liberar(job_id: str) -> None:
    global _job_atual
    with _jobs_lock:
        _jobs.pop(job_id, None)
        if _job_atual == job_id:
            _job_atual = None


def pedir_cancelamento(job_id: str | None = None) -> dict[str, Any]:
    """Marca cancelamento e tenta matar o subprocesso. Idempotente."""
    with _jobs_lock:
        alvo_id = job_id or _job_atual
        job = _jobs.get(alvo_id) if alvo_id else None

    if job is None or alvo_id is None:
        raise ErroNucleo(
            "NU-001",
            "Nenhum job em andamento para cancelar."
            if not job_id
            else f"Job desconhecido: {job_id}",
            {"job_id": job_id},
        )

    with job.lock:
        job.cancelado = True
        processo = job.processo
        pid = job.pid

    morto = False
    if processo is not None and processo.poll() is None:
        morto = _matar_arvore(processo, pid)
    elif pid is not None:
        morto = _matar_pid(pid)

    return {"ok": True, "job_id": alvo_id, "processo_encerrado": morto}


def verificar_nao_cancelado(job_id: str | None) -> None:
    """Levanta `NU-050` se o job foi cancelado — pontos de checagem do motor."""
    if not job_id:
        return
    job = obter(job_id)
    if job is not None and job.cancelado:
        raise ErroNucleo(
            CODIGO_JOB_CANCELADO,
            "Geração de mapa cancelada.",
            {"job_id": job_id},
        )


def _matar_arvore(processo: subprocess.Popen[Any], pid: int | None) -> bool:
    """Mata o processo e filhos. Windows: `taskkill /T /F`. Demais: group/kill."""
    pid = pid or processo.pid
    if pid is None:
        return False
    if sys.platform.startswith("win"):
        return _taskkill(pid)
    try:
        # Se o filho foi criado com start_new_session, mata o grupo.
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            processo.terminate()
        except OSError:
            pass
    try:
        processo.wait(timeout=3)
        return True
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                processo.kill()
            except OSError:
                return False
        try:
            processo.wait(timeout=2)
        except subprocess.TimeoutExpired:
            return False
        return True


def _matar_pid(pid: int) -> bool:
    if sys.platform.startswith("win"):
        return _taskkill(pid)
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _taskkill(pid: int) -> bool:
    """`taskkill /T /F` — mata a árvore (F1-03 armadilha #4)."""
    try:
        concl = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return concl.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


# --- handlers NDJSON -------------------------------------------------------


def handler_cancelar(params: dict[str, Any]) -> dict[str, Any]:
    job_id = params.get("job_id")
    if job_id is not None and not isinstance(job_id, str):
        raise ErroNucleo("NU-001", "Parâmetro 'job_id' inválido.")
    if isinstance(job_id, str) and not job_id.strip():
        job_id = None
    return pedir_cancelamento(job_id)
