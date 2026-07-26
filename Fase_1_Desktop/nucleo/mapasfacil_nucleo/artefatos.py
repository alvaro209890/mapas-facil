"""Artefatos intermediários (`job.artefato_parcial`) — contrato novo do M8.

Contrato: [F1-16 §Contrato NOVO](../../planos/16-design-system-dark.md), consumido
pelo `painel-preview` (A5 fase 2).

Regras que este módulo garante — todas testadas:

* `tipo` só pode ser um dos quatro do contrato (`camada`, `tabela_png`,
  `preview_png`, `pdf`); nome novo exige alterar o plano junto;
* `etapa` tem de ser uma das 10 etapas de `job.progresso` — o artefato sempre
  pertence a uma etapa observável, senão a UI não sabe onde encaixá-lo;
* `caminho` é **sempre relativo à pasta do projeto**, com `/` como separador.
  Caminho absoluto vaza o disco do usuário (`C:\\Users\\...`) e é recusado aqui,
  não "filtrado na exibição".

Este módulo não emite nada sozinho: quem emite é o `RastreadorProgresso`, que já
carrega o canal de eventos da requisição.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Final

from mapasfacil_nucleo.progresso import IDS_ETAPAS

EVENTO: Final = "job.artefato_parcial"

TIPOS: Final[tuple[str, ...]] = ("camada", "tabela_png", "preview_png", "pdf")

# Pasta (relativa) onde as rasterizações intermediárias do preview são gravadas.
# Fica sob `Mapas/` porque é a única pasta de saída que o fsguard autoriza para
# escrita e que o usuário já reconhece como "coisa gerada".
PASTA_PREVIEW: Final = "Mapas/.preview"


class ArtefatoInvalido(ValueError):
    """Erro de programação: artefato fora do contrato de F1-16."""


def normalizar_caminho(caminho: str | Path, *, raiz: Path | None = None) -> str:
    """Caminho relativo à pasta do projeto, com `/`, pronto para ir ao evento.

    Com `raiz`, aceita caminho absoluto **dentro** dela e o relativiza; fora dela
    (ou absoluto sem `raiz`) é `ArtefatoInvalido` — o renderer nunca deve receber
    caminho de disco.
    """
    if isinstance(caminho, Path) or raiz is not None:
        alvo = Path(caminho)
        if alvo.is_absolute():
            if raiz is None:
                raise ArtefatoInvalido(f"Caminho absoluto no artefato: {caminho}")
            try:
                alvo = alvo.resolve().relative_to(Path(raiz).resolve())
            except ValueError as exc:
                raise ArtefatoInvalido(
                    f"Artefato fora da pasta do projeto: {caminho}"
                ) from exc
        texto = alvo.as_posix()
    else:
        texto = str(caminho).replace("\\", "/")

    if PureWindowsPath(texto).is_absolute() or texto.startswith("/"):
        raise ArtefatoInvalido(f"Caminho absoluto no artefato: {caminho}")
    partes = PurePosixPath(texto).parts
    if not partes or ".." in partes:
        raise ArtefatoInvalido(f"Caminho relativo inválido no artefato: {caminho}")
    return PurePosixPath(*partes).as_posix()


def montar_dados(
    tipo: str,
    *,
    caminho: str | Path,
    etapa: str,
    raiz: Path | None = None,
    camada_id: str | None = None,
    ordem: int | None = None,
    pct: int | None = None,
) -> dict[str, Any]:
    """Valida e monta o `dados` do evento. Função pura — é o que o teste exercita."""
    if tipo not in TIPOS:
        raise ArtefatoInvalido(f"Tipo de artefato fora do contrato: {tipo}")
    if etapa not in IDS_ETAPAS:
        raise ArtefatoInvalido(f"Etapa fora do contrato de job.progresso: {etapa}")

    dados: dict[str, Any] = {
        "tipo": tipo,
        "caminho": normalizar_caminho(caminho, raiz=raiz),
        "etapa": etapa,
    }
    if camada_id is not None:
        dados["camada_id"] = camada_id
    if ordem is not None:
        dados["ordem"] = int(ordem)
    if pct is not None:
        dados["pct"] = max(0, min(100, int(pct)))
    return dados
