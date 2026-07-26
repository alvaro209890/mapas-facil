# F1-17 — persistência local de conversas (M6).
#
# `banco` diz onde mora e como migra; `repositorio` é o CRUD; `servico` são os
# handlers NDJSON `chat.*` de histórico; `redator`, `titulo` e `fingerprint` são as
# regras que valem antes de qualquer INSERT.
#
# Este pacote é local-only por decisão (D20/AP-12): nenhum módulo aqui abre socket.

from mapasfacil_nucleo.conversas import (  # noqa: F401
    banco,
    fingerprint,
    redator,
    repositorio,
    titulo,
)
