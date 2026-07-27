# Regressão: stdio do sidecar tem de forçar UTF-8 no Windows.
#
# Sem isto, `sys.stdin`/`sys.stdout` abrem no codepage do console (cp1252/cp850)
# em vez de UTF-8, e qualquer nome de pasta com acento (ex.: "Área") chega
# corrompido ao `workspace.abrir` — o núcleo então devolve NU-010 achando que a
# pasta não existe, quando na verdade ela existe e o problema é a decodificação.

from __future__ import annotations

from mapasfacil_nucleo.__main__ import _forcar_utf8_stdio


class _FluxoFalso:
    def __init__(self) -> None:
        self.encoding_pedido: str | None = None

    def reconfigure(self, *, encoding: str) -> None:
        self.encoding_pedido = encoding


def test_forcar_utf8_stdio_reconfigura_stdin_stdout_stderr(monkeypatch) -> None:
    entrada, saida, erro = _FluxoFalso(), _FluxoFalso(), _FluxoFalso()
    monkeypatch.setattr("sys.stdin", entrada)
    monkeypatch.setattr("sys.stdout", saida)
    monkeypatch.setattr("sys.stderr", erro)

    _forcar_utf8_stdio()

    assert entrada.encoding_pedido == "utf-8"
    assert saida.encoding_pedido == "utf-8"
    assert erro.encoding_pedido == "utf-8"


def test_forcar_utf8_stdio_nao_quebra_sem_reconfigure(monkeypatch) -> None:
    """Fluxo sem `.reconfigure` (ex.: capturado por outra ferramenta de teste) é ignorado."""

    class _SemReconfigure:
        pass

    monkeypatch.setattr("sys.stdin", _SemReconfigure())
    _forcar_utf8_stdio()  # não deve levantar exceção
