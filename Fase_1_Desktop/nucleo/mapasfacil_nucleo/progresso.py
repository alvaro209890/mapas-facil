"""Progresso de job (`job.progresso`) — as 10 etapas de `mapa.gerar`.

Contrato: [F1-01 §Etapas reportadas em `job.progresso`](../../planos/01-arquitetura.md).

Semântica do evento, fixada aqui e espelhada na UI:

* o evento é emitido **ao concluir** uma etapa; `etapa` é a que acabou de terminar e
  `pct` é o acumulado do job (soma dos pesos das etapas concluídas);
* nas etapas de camada (`resolvendo_camadas_locais`, `baixando_externas`) há eventos
  intermediários com `item` = `camadas[].id` e `pct` dentro da faixa da etapa;
* `pct` é **monotônico**: nunca anda para trás (AP de F1-01).

Nenhuma etapa é simulada por timer: quem chama emite quando o trabalho aconteceu.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

EVENTO = "job.progresso"


@dataclass(frozen=True)
class Etapa:
    """Uma das 10 etapas do contrato. `peso` é a fatia de `pct` que ela vale."""

    id: str
    peso: int
    emite_item: bool = False


ETAPAS: tuple[Etapa, ...] = (
    Etapa("validando_spec", 3),
    Etapa("resolvendo_camadas_locais", 7, emite_item=True),
    Etapa("baixando_externas", 20, emite_item=True),
    Etapa("calculando_quantitativos", 10),
    Etapa("gerando_tabela", 5),
    Etapa("preparando_template", 10),
    Etapa("aplicando_layout", 15),
    Etapa("salvando_mxd", 5),
    Etapa("exportando_pdf", 15),
    Etapa("validando_saida", 10),
)

IDS_ETAPAS: tuple[str, ...] = tuple(etapa.id for etapa in ETAPAS)

assert sum(etapa.peso for etapa in ETAPAS) == 100, "os pesos das etapas têm de somar 100"

_INDICE: dict[str, int] = {etapa.id: i for i, etapa in enumerate(ETAPAS)}
# pct acumulado ao concluir cada etapa: 3, 10, 30, 40, 45, 55, 70, 75, 90, 100.
_ACUMULADO: tuple[int, ...] = tuple(
    sum(e.peso for e in ETAPAS[: i + 1]) for i in range(len(ETAPAS))
)


def indice_da_etapa(etapa: str) -> int:
    try:
        return _INDICE[etapa]
    except KeyError:  # pragma: no cover - erro de programação, não de entrada
        raise ValueError(f"Etapa fora do contrato de job.progresso: {etapa}") from None


def pct_ao_concluir(etapa: str) -> int:
    """`pct` acumulado quando `etapa` termina."""
    return _ACUMULADO[indice_da_etapa(etapa)]


class RastreadorProgresso:
    """Traduz o andamento de `mapa.gerar` em eventos `job.progresso`.

    Sem `emitir`, funciona como no-op: `gerar_mapa` chamado direto (testes, CLI)
    não precisa de canal de eventos.
    """

    def __init__(self, emitir: Callable[[str, dict[str, Any]], Any] | None = None) -> None:
        self._emitir = emitir
        self._pct = 0
        self._concluidas = -1

    @property
    def emite_eventos(self) -> bool:
        """Há canal de eventos? Quem produz artefato caro (rasterizar preview)
        checa isto antes de trabalhar — sem UI ouvindo, o trabalho é lixo."""
        return self._emitir is not None

    @property
    def pct(self) -> int:
        return self._pct

    @property
    def etapas_concluidas(self) -> int:
        return self._concluidas + 1

    def concluir(self, etapa: str, *, item: str | None = None) -> dict[str, Any]:
        """Fecha uma etapa: `pct` vai ao acumulado dela."""
        indice = indice_da_etapa(etapa)
        if indice <= self._concluidas:
            raise ValueError(
                f"Etapa '{etapa}' já foi concluída — job.progresso não anda para trás."
            )
        self._concluidas = indice
        return self._despachar(etapa, _ACUMULADO[indice], item)

    def concluir_se_pendente(self, etapa: str, *, item: str | None = None) -> dict[str, Any] | None:
        """Fecha a etapa se ela ainda não foi fechada por um `item` final."""
        if indice_da_etapa(etapa) <= self._concluidas:
            return None
        return self.concluir(etapa, item=item)

    def item(self, etapa: str, item: str, *, indice: int, total: int) -> dict[str, Any]:
        """Item pronto dentro de uma etapa de camada (`indice` é 1-based)."""
        i_etapa = indice_da_etapa(etapa)
        etapa_def = ETAPAS[i_etapa]
        if not etapa_def.emite_item:
            raise ValueError(f"Etapa '{etapa}' não reporta 'item' no contrato.")
        inicio = _ACUMULADO[i_etapa] - etapa_def.peso
        fracao = 0.0 if total <= 0 else max(0.0, min(1.0, indice / total))
        pct = int(inicio + round(etapa_def.peso * fracao))
        if indice >= total:
            # O último item da etapa também a conclui — evita evento duplicado.
            self._concluidas = i_etapa
            pct = _ACUMULADO[i_etapa]
        return self._despachar(etapa, pct, item)

    def artefato(
        self,
        tipo: str,
        *,
        caminho: Any,
        etapa: str,
        raiz: Any = None,
        camada_id: str | None = None,
        ordem: int | None = None,
        com_pct: bool = False,
    ) -> dict[str, Any]:
        """Emite `job.artefato_parcial` (M8 / F1-16 §A5 fase 2).

        Mora aqui porque o rastreador já é o canal de eventos do job: passar um
        segundo objeto por `gerar_mapa` → `materializar` → `nativo` só para isso
        seria encanamento sem ganho. A validação do contrato fica em
        `artefatos.py`; este método só despacha.

        `com_pct=True` carimba o `pct` corrente do job no evento — útil no
        `preview_png`, em que a UI quer saber de que altura do job veio a imagem.
        """
        from mapasfacil_nucleo.artefatos import EVENTO as EVENTO_ARTEFATO
        from mapasfacil_nucleo.artefatos import montar_dados

        dados = montar_dados(
            tipo,
            caminho=caminho,
            etapa=etapa,
            raiz=raiz,
            camada_id=camada_id,
            ordem=ordem,
            pct=self._pct if com_pct else None,
        )
        if self._emitir is not None:
            self._emitir(EVENTO_ARTEFATO, dados)
        return dados

    def _despachar(self, etapa: str, pct: int, item: str | None) -> dict[str, Any]:
        pct = max(0, min(100, pct))
        if pct < self._pct:
            pct = self._pct
        self._pct = pct
        dados: dict[str, Any] = {"etapa": etapa, "pct": pct}
        if item is not None:
            dados["item"] = item
        if self._emitir is not None:
            self._emitir(EVENTO, dados)
        return dados
