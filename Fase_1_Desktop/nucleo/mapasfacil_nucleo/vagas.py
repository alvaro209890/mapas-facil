"""Vagas de geração entre processos (W1-09).

No servidor, cada projeto é um processo `mapasfacil_nucleo` diferente. Sem um lock entre
processos, `MF_MAX_JOBS=2` não significaria nada: três abas do site gerariam três mapas ao
mesmo tempo e o servidor (15 GB, 4 núcleos) engasgaria.

O lock é um **flock** (POSIX) / `msvcrt.locking` (Windows) em
`$MAPASFACIL_VAGAS_DIR/vaga-{0..N-1}.lock`. O próprio SO libera o lock se o processo morrer,
então não existe vaga fantasma — é a razão de não usar um arquivo "em uso" com PID dentro.

Fora do modo servidor isto é um no-op: o desktop continua com um job por vez, sem lock.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from mapasfacil_nucleo.config import modo_servidor
from mapasfacil_nucleo.erros import ErroNucleo

ENV_DIR = "MAPASFACIL_VAGAS_DIR"
ENV_MAX = "MAPASFACIL_MAX_JOBS"
ESPERA_PADRAO_S = 10.0

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]


def diretorio() -> Path | None:
    """Pasta das vagas. `None` = sem limite (nenhum env definido).

    Sem `MAPASFACIL_VAGAS_DIR` (ou sem `MAPASFACIL_DADOS`) o núcleo não bloqueia a
    geração: travar o trabalho por falta de configuração de lock seria pior que rodar
    uma geração a mais. A ponte sempre define as duas.
    """
    bruto = (os.environ.get(ENV_DIR) or "").strip()
    if bruto:
        return Path(bruto)
    dados = (os.environ.get("MAPASFACIL_DADOS") or "").strip()
    if dados:
        return Path(dados).parent / "vagas"
    return None


def maximo() -> int:
    bruto = (os.environ.get(ENV_MAX) or "").strip()
    if not bruto:
        return 2
    try:
        return max(int(bruto), 1)
    except ValueError:
        return 2


def _travar(arquivo) -> bool:
    """Tenta travar sem bloquear. `True` = vaga obtida."""
    try:
        if fcntl is not None:
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        if msvcrt is not None:  # pragma: no cover - exercitado só no Windows
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            return True
    except OSError:
        return False
    return False


def _destravar(arquivo) -> None:  # pragma: no cover - caminho de saída
    try:
        if fcntl is not None:
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        elif msvcrt is not None:
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def tentar_agora() -> tuple[object, int] | None:
    """Uma tentativa, sem esperar. Devolve `(arquivo_travado, indice)` ou `None`."""
    pasta = diretorio()
    if pasta is None:
        return None
    pasta.mkdir(parents=True, exist_ok=True)
    for indice in range(maximo()):
        caminho = pasta / f"vaga-{indice}.lock"
        arquivo = caminho.open("a+b")
        if _travar(arquivo):
            return arquivo, indice
        arquivo.close()
    return None


class _Vaga:
    """Context manager de vaga — classe, não gerador.

    `@contextmanager` propaga a exceção pelo `throw()` do gerador, e o Python tenta
    gravar `__traceback__` no `ErroNucleo` (dataclass frozen) → `FrozenInstanceError`.
    Com uma classe o `raise` acontece na pilha normal.
    """

    def __init__(
        self,
        *,
        espera_s: float,
        ao_esperar: Callable[[float], None] | None,
        cancelado: Callable[[], bool] | None,
        dormir: Callable[[float], None],
    ) -> None:
        self.espera_s = espera_s
        self.ao_esperar = ao_esperar
        self.cancelado = cancelado
        self.dormir = dormir
        self._arquivo: object | None = None
        self._indice: int | None = None

    def __enter__(self) -> int | None:
        if not modo_servidor() or diretorio() is None:
            return None
        while True:
            obtida = tentar_agora()
            if obtida is not None:
                self._arquivo, self._indice = obtida
                return self._indice

            if self.cancelado is not None and self.cancelado():
                raise ErroNucleo(
                    "NU-050",
                    "Geração cancelada enquanto esperava vaga.",
                    {"operacao": "vaga"},
                )
            if self.ao_esperar is not None:
                self.ao_esperar(self.espera_s)
            self.dormir(self.espera_s)

    def __exit__(self, tipo, valor, tb) -> bool:
        if self._arquivo is not None:
            _destravar(self._arquivo)
            self._arquivo.close()  # type: ignore[attr-defined]
            self._arquivo = None
        return False


def vaga(
    *,
    espera_s: float = ESPERA_PADRAO_S,
    ao_esperar: Callable[[float], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> _Vaga:
    """Segura uma vaga durante o bloco. Fora do modo servidor, não faz nada.

    Espera em ciclos de `espera_s`, avisando a cada ciclo (`job.log` no chamador). Se
    `cancelado()` virar verdadeiro, solta a espera com `NU-050`.
    """
    return _Vaga(
        espera_s=espera_s,
        ao_esperar=ao_esperar,
        cancelado=cancelado,
        dormir=dormir,
    )


def livres() -> int:
    """Quantas vagas estão livres agora — usado pelo `/admin/saude` e por testes."""
    if not modo_servidor() or diretorio() is None:
        return 1
    obtidas: list[object] = []
    try:
        while True:
            resultado = tentar_agora()
            if resultado is None:
                break
            obtidas.append(resultado[0])
            if len(obtidas) >= maximo():
                break
    finally:
        for arquivo in obtidas:
            _destravar(arquivo)  # type: ignore[arg-type]
            arquivo.close()  # type: ignore[attr-defined]
    return max(maximo() - len(obtidas), 0)
