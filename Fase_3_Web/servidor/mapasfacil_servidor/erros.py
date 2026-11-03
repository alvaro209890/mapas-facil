"""Erros do servidor — mesmo formato do `ErroNucleo`, mais o status HTTP.

O corpo sai como::

    {"erro": {"codigo": "SV-104", "mensagem": "...", "porque": "...",
              "o_que_fazer": "...", "detalhes": {...}}}

Prefixos (W-01):

- ``SV-0xx`` autenticação, sessão, permissão e boot
- ``SV-1xx`` upload e importação
- ``SV-2xx`` workers, fila, timeouts
- ``SV-3xx`` eventos/SSE
- ``SV-4xx`` arquivos e downloads
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErroServidor(Exception):
    codigo: str
    mensagem: str
    status_http: int = 500
    porque: str | None = None
    o_que_fazer: str | None = None
    detalhes: dict[str, Any] | None = None

    def para_dict(self) -> dict[str, Any]:
        erro: dict[str, Any] = {"codigo": self.codigo, "mensagem": self.mensagem}
        if self.porque:
            erro["porque"] = self.porque
        if self.o_que_fazer:
            erro["o_que_fazer"] = self.o_que_fazer
        if self.detalhes:
            erro["detalhes"] = self.detalhes
        return {"erro": erro}

    def __str__(self) -> str:  # pragma: no cover - só em log/terminal
        return f"{self.codigo}: {self.mensagem}"


class ConfiguracaoInvalida(ErroServidor):
    """Falta variável de ambiente obrigatória ou ela é inválida (boot)."""

    def __init__(
        self,
        mensagem: str,
        *,
        porque: str | None = None,
        o_que_fazer: str | None = None,
        detalhes: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "SV-000",
            mensagem,
            status_http=500,
            porque=porque,
            o_que_fazer=o_que_fazer,
            detalhes=detalhes,
        )


class HostInvalido(ErroServidor):
    """O bind não é loopback. O servidor nunca escuta no IP curinga (AW-06)."""

    def __init__(self, host: str) -> None:
        super().__init__(
            "SV-001",
            f"O servidor não pode escutar em {host!r}.",
            status_http=500,
            porque="Só o túnel da Cloudflare fala com o backend; porta aberta na rede é "
            "exposição desnecessária.",
            o_que_fazer="Use MF_HOST=127.0.0.1. Para testar de outra máquina, "
            "`ssh -L 3130:127.0.0.1:3130 sd`.",
            detalhes={"host": host},
        )


class SegredoAusente(ErroServidor):
    """Uma chave obrigatória falta **dentro** do arquivo de segredos (nome só, nunca o valor).

    Arquivo ausente ou com permissão frouxa é `SV-000` (falha de boot), não `SV-002`.
    """

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        super().__init__(
            "SV-002",
            mensagem,
            status_http=500,
            porque="O servidor precisa das chaves de IA e das APIs geo para trabalhar.",
            o_que_fazer="Peça ao Álvaro para montar/ajustar o arquivo de segredos "
            "(0600). O agente nunca lê nem imprime o valor.",
            detalhes=detalhes,
        )


class NaoImplementado(ErroServidor):
    """Comando da CLI que pertence a um marco ainda não implementado."""

    def __init__(self, comando: str, marco: str) -> None:
        super().__init__(
            "SV-098",
            f"O comando {comando!r} entra no marco {marco}.",
            status_http=501,
            porque="A CLI nasceu no W0 com a superfície completa, mas o corpo de cada "
            "comando chega no marco dono.",
            o_que_fazer=f"Implemente {marco} antes de usar este comando.",
            detalhes={"comando": comando, "marco": marco},
        )
