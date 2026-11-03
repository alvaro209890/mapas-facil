"""Limitador de tentativas de login (W-11: `429 SV-005`).

Em memória e por processo: o servidor é um processo só atrás do túnel, então não há
estado compartilhado a sincronizar. Reinício zera o contador — aceitável, porque o
alvo é frear força bruta contínua, não contabilidade.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

JANELA_S = 15 * 60
MAX_FALHAS = 5


@dataclass
class Limitador:
    janela_s: float = JANELA_S
    max_falhas: int = MAX_FALHAS
    _falhas: dict[str, list[float]] = field(default_factory=dict)

    def _limpar(self, chave: str, agora: float) -> list[float]:
        marcas = [t for t in self._falhas.get(chave, []) if agora - t < self.janela_s]
        if marcas:
            self._falhas[chave] = marcas
        else:
            self._falhas.pop(chave, None)
        return marcas

    def bloqueado(self, chave: str) -> bool:
        return len(self._limpar(chave, time.monotonic())) >= self.max_falhas

    def registrar_falha(self, chave: str) -> int:
        agora = time.monotonic()
        marcas = self._limpar(chave, agora)
        marcas.append(agora)
        self._falhas[chave] = marcas
        return len(marcas)

    def registrar_sucesso(self, chave: str) -> None:
        self._falhas.pop(chave, None)

    def segundos_para_liberar(self, chave: str) -> int:
        marcas = self._limpar(chave, time.monotonic())
        if len(marcas) < self.max_falhas:
            return 0
        restante = self.janela_s - (time.monotonic() - marcas[0])
        return max(0, int(restante))

    def limpar(self) -> None:
        self._falhas.clear()


def chave(email: str, ip: str | None) -> str:
    return f"{email.strip().lower()}|{ip or '-'}"
