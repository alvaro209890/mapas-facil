"""Progresso real da série de Análise de área sobre o contrato de jobs.

Cada mapa continua usando as dez etapas oficiais de ``mapa.gerar``. Este
adaptador converte o percentual local de cada mapa em um percentual global da
série e acrescenta metadados estruturados para o renderer mostrar imóvel,
camada, mapa atual e compilação sem inventar timers (AP-07).
"""

from __future__ import annotations

from typing import Any, Callable

from mapasfacil_nucleo.artefatos import EVENTO as EVENTO_ARTEFATO
from mapasfacil_nucleo.artefatos import montar_dados
from mapasfacil_nucleo.progresso import (
    EVENTO,
    EVENTO_AVISO,
    EVENTO_LOG,
    RastreadorProgresso,
)

Emitir = Callable[[str, dict[str, Any]], Any]


class RastreadorProgressoSerie:
    """Traduz identidade → camadas → 20 mapas → compilado em eventos do job."""

    INICIO_MAPAS = 30
    FIM_MAPAS = 94

    def __init__(self, emitir: Emitir, *, job_id: str, total_mapas: int) -> None:
        self._emitir = emitir
        self.job_id = job_id
        self.total_mapas = max(1, total_mapas)
        self._pct = 0

    def _dados_serie(
        self,
        *,
        fase: str,
        mensagem: str,
        indice: int | None = None,
        total: int | None = None,
        mapa_id: str | None = None,
        mapa_nome: str | None = None,
        compilado: bool = False,
    ) -> dict[str, Any]:
        dados: dict[str, Any] = {"fase": fase, "mensagem": mensagem}
        if indice is not None:
            dados["indice"] = indice
        if total is not None:
            dados["total"] = total
        if mapa_id is not None:
            dados["mapa_id"] = mapa_id
        if mapa_nome is not None:
            dados["mapa_nome"] = mapa_nome
        if compilado:
            dados["compilado"] = True
        return dados

    def _progresso(
        self,
        etapa: str,
        pct: int,
        *,
        item: str | None,
        serie: dict[str, Any],
    ) -> None:
        self._pct = max(self._pct, min(100, max(0, round(pct))))
        dados: dict[str, Any] = {
            "etapa": etapa,
            "pct": self._pct,
            "job_id": self.job_id,
            "serie": serie,
        }
        if item:
            dados["item"] = item
        self._emitir(EVENTO, dados)

    def log(self, linha: str) -> None:
        self._emitir(EVENTO_LOG, {"linha": str(linha)[:500], "job_id": self.job_id})

    def aviso(self, codigo: str, mensagem: str) -> None:
        self._emitir(
            EVENTO_AVISO,
            {"codigo": codigo, "mensagem": str(mensagem)[:500], "job_id": self.job_id},
        )

    def iniciar_identidade(self) -> None:
        mensagem = "buscando CAR e identificando o imóvel"
        self._progresso(
            "validando_spec",
            1,
            item="CAR",
            serie=self._dados_serie(fase="identidade", mensagem=mensagem),
        )
        self.log(mensagem)

    def concluir_identidade(self, rotulo: str) -> None:
        mensagem = f"imóvel identificado · {rotulo}"
        self._progresso(
            "validando_spec",
            5,
            item=rotulo,
            serie=self._dados_serie(fase="identidade", mensagem=mensagem),
        )
        self.log(mensagem)

    def iniciar_camadas(self) -> None:
        mensagem = "preparando camadas oficiais e derivadas"
        self._progresso(
            "baixando_externas",
            6,
            item=None,
            serie=self._dados_serie(fase="camada", mensagem=mensagem),
        )
        self.log(mensagem)

    def camada(self, papel: str, indice: int, total: int) -> None:
        total_seguro = max(1, total)
        pct = 6 + round(24 * max(0, min(indice, total_seguro)) / total_seguro)
        mensagem = f"camada pronta · {papel}"
        self._progresso(
            "baixando_externas",
            pct,
            item=papel,
            serie=self._dados_serie(
                fase="camada",
                mensagem=mensagem,
                indice=indice,
                total=total,
            ),
        )

    def iniciar_mapa(self, receita: Any, indice: int) -> None:
        pct = self._pct_mapa(indice, 0)
        mensagem = f"montando mapa {indice} de {self.total_mapas} · {receita.nome}"
        self._progresso(
            "preparando_template",
            pct,
            item=receita.id,
            serie=self._dados_serie(
                fase="mapa",
                mensagem=mensagem,
                indice=indice,
                total=self.total_mapas,
                mapa_id=receita.id,
                mapa_nome=receita.nome,
            ),
        )
        self.log(mensagem)

    def rastreador_do_mapa(self, receita: Any, indice: int) -> RastreadorProgresso:
        def _adaptar(evento: str, dados: dict[str, Any]) -> None:
            serie = self._dados_serie(
                fase="mapa",
                mensagem=self._mensagem_mapa(receita, indice, dados),
                indice=indice,
                total=self.total_mapas,
                mapa_id=receita.id,
                mapa_nome=receita.nome,
            )
            if evento == EVENTO:
                pct_local = int(dados.get("pct") or 0)
                self._progresso(
                    str(dados.get("etapa") or "aplicando_layout"),
                    self._pct_mapa(indice, pct_local),
                    item=str(dados["item"]) if dados.get("item") is not None else receita.id,
                    serie=serie,
                )
                return
            if evento == EVENTO_ARTEFATO:
                enriquecido = {**dados, "job_id": self.job_id, "serie": serie}
                self._emitir(evento, enriquecido)
                return
            if evento == EVENTO_LOG:
                self.log(
                    f"mapa {indice}/{self.total_mapas} · {receita.nome} · "
                    f"{dados.get('linha', '')}"
                )
                return
            if evento == EVENTO_AVISO:
                self.aviso(
                    str(dados.get("codigo") or "NU-000"),
                    f"{receita.nome}: {dados.get('mensagem', '')}",
                )

        return RastreadorProgresso(_adaptar, job_id=self.job_id)

    def concluir_mapa(self, receita: Any, indice: int, *, ok: bool, erro: str | None) -> None:
        estado = "pronto" if ok else "pendente"
        mensagem = f"mapa {indice} de {self.total_mapas} {estado} · {receita.nome}"
        self._progresso(
            "validando_saida",
            self._pct_mapa(indice, 100),
            item=receita.id,
            serie=self._dados_serie(
                fase="mapa",
                mensagem=mensagem,
                indice=indice,
                total=self.total_mapas,
                mapa_id=receita.id,
                mapa_nome=receita.nome,
            ),
        )
        if not ok:
            self.aviso("NU-241", f"{receita.nome}: {erro or 'mapa não gerado'}; a série continua.")

    def iniciar_compilacao(self, total_pdfs: int) -> None:
        mensagem = f"compilando {total_pdfs} PDFs na ordem de entrega"
        self._progresso(
            "exportando_pdf",
            96,
            item="Analise_de_area.pdf",
            serie=self._dados_serie(fase="compilando", mensagem=mensagem),
        )
        self.log(mensagem)

    def artefato_compilado(self, caminho: str, paginas: int) -> None:
        serie = self._dados_serie(
            fase="compilando",
            mensagem=f"PDF compilado pronto · {paginas} páginas",
            compilado=True,
        )
        dados = montar_dados(
            "pdf",
            caminho=caminho,
            etapa="exportando_pdf",
            pct=98,
        )
        self._emitir(
            EVENTO_ARTEFATO,
            {**dados, "job_id": self.job_id, "serie": serie},
        )
        self._progresso("exportando_pdf", 98, item=caminho, serie=serie)

    def concluir(self, *, gerados: int, total: int, relatorio: str) -> None:
        mensagem = f"série concluída · {gerados}/{total} mapas gerados"
        self._progresso(
            "validando_saida",
            100,
            item=relatorio,
            serie=self._dados_serie(fase="concluido", mensagem=mensagem, compilado=True),
        )
        self.log(f"{mensagem} · relatório={relatorio}")

    def _pct_mapa(self, indice: int, pct_local: int) -> int:
        amplitude = self.FIM_MAPAS - self.INICIO_MAPAS
        fracao = ((max(1, indice) - 1) + min(100, max(0, pct_local)) / 100) / self.total_mapas
        return self.INICIO_MAPAS + round(amplitude * fracao)

    def _mensagem_mapa(self, receita: Any, indice: int, dados: dict[str, Any]) -> str:
        etapa = str(dados.get("etapa") or "")
        item = dados.get("item")
        rotulos = {
            "validando_spec": "validando especificação",
            "resolvendo_camadas_locais": "resolvendo camada",
            "baixando_externas": "buscando camada externa ou mosaico",
            "calculando_quantitativos": "calculando quantitativos",
            "gerando_tabela": "gerando tabela",
            "preparando_template": "preparando página",
            "aplicando_layout": "aplicando anatomia Harmonia",
            "salvando_mxd": "finalizando saídas",
            "exportando_pdf": "exportando PDF",
            "validando_saida": "validando PDF",
        }
        acao = rotulos.get(etapa, etapa or "processando")
        sufixo = f" · {item}" if item else ""
        return f"mapa {indice} de {self.total_mapas} · {receita.nome} · {acao}{sufixo}"
