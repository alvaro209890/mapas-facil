"""Roda a série inteira: identidade → camadas → 20 mapas → PDF compilado → validação.

Regra de ouro do fluxo: **um mapa que falha não derruba a série**. A SEMA cai, um
mosaico de um ano some, uma camada volta vazia — o mapa correspondente sai com o
que dá (ou não sai), o motivo entra no relatório, e os outros 19 seguem. É o
comportamento que o GOAL pede e o oposto do que um `for` ingênuo faria.

A validação não é "abriu sem erro": cada PDF é medido em milímetros contra o seu
PDF-modelo (`validacao/anatomia.py`), e o relatório diz mapa a mapa o que ficou
fora de tolerância.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapasfacil_nucleo.analise import preparar as preparar_mod
from mapasfacil_nucleo.analise import serie as serie_mod
from mapasfacil_nucleo.analise.identidade import IdentidadeImovel, identificar
from mapasfacil_nucleo.analise.progresso import RastreadorProgressoSerie
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.workspace.shapefile import (
    _abrir_reader,
    _shapes_para_geometrias,
    inspecionar,
)

PASTA_SAIDA = "Mapas"
NOME_COMPILADO = "Analise_de_area"


@dataclass
class ResultadoMapa:
    """O que aconteceu com um mapa da série."""

    id: str
    ordem: int
    nome: str
    ok: bool
    pdf: str | None = None
    pdf_nativo: str | None = None
    pdf_arcmap: str | None = None
    mxd: str | None = None
    segundos: float = 0.0
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)
    basemap: dict[str, Any] = field(default_factory=dict)
    anatomia: dict[str, Any] | None = None
    camadas: list[str] = field(default_factory=list)

    def para_ndjson(self) -> dict[str, Any]:
        return {
            "mapa": self.id,
            "ordem": self.ordem,
            "nome": self.nome,
            "ok": self.ok,
            "pdf": self.pdf,
            "pdf_nativo": self.pdf_nativo,
            "pdf_arcmap": self.pdf_arcmap,
            "mxd": self.mxd,
            "segundos": round(self.segundos, 1),
            "erro": self.erro,
            "avisos": self.avisos,
            "basemap": self.basemap,
            "camadas": self.camadas,
            "anatomia_ok": (self.anatomia or {}).get("ok"),
            "anatomia_falhas": (self.anatomia or {}).get("falhas"),
        }


def _geometria_do_atp(guard: WorkspaceGuard, atp_rel: str) -> BaseGeometry:
    caminho = guard.resolver(atp_rel)
    reader, _enc = _abrir_reader(caminho)
    geoms = [g for g in _shapes_para_geometrias(reader) if not g.is_empty]
    if not geoms:
        raise ErroNucleo("NU-240", f"Polígono do imóvel vazio: {atp_rel}")
    uniao = unary_union(geoms)
    return uniao if uniao.is_valid else uniao.buffer(0)


def _extent_com_folga(
    bbox: tuple[float, float, float, float], folga: float
) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = bbox
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    largura = max(xmax - xmin, 1.0) * folga
    altura = max(ymax - ymin, 1.0) * folga
    return (cx - largura / 2, cy - altura / 2, cx + largura / 2, cy + altura / 2)


def executar(
    *,
    guard: WorkspaceGuard,
    atp_rel: str = "SHP/ATP.shp",
    epsg: int = 31982,
    apenas: tuple[str, ...] | None = None,
    modelos: Path | None = None,
    ao_progresso: Callable[[str, str, int, int], None] | None = None,
    progresso: RastreadorProgressoSerie | None = None,
    preparar_camadas: bool = True,
    saidas: tuple[str, ...] = ("pdf",),
) -> dict[str, Any]:
    """Executa a série e devolve o relatório completo.

    `apenas` roda um subconjunto (útil no loop de ajuste de um mapa só).
    `modelos` aponta a pasta dos PDFs-modelo para a validação de anatomia.
    """
    inicio = time.time()
    imovel = _geometria_do_atp(guard, atp_rel)
    bbox = tuple(imovel.bounds)  # type: ignore[assignment]
    meta_atp = inspecionar(guard.resolver(atp_rel))
    epsg_efetivo = int(meta_atp.crs.get("epsg") or epsg)

    if progresso:
        progresso.iniciar_identidade()
    identidade = identificar(imovel, guard=guard, epsg=epsg_efetivo)
    if progresso:
        progresso.concluir_identidade(identidade.rotulo)
    if ao_progresso:
        ao_progresso("identidade", identidade.rotulo, 0, 0)

    receitas = [r for r in serie_mod.ordenadas() if not apenas or r.id in apenas]
    folga_maxima = max((r.folga_extent for r in receitas), default=1.12)

    if preparar_camadas:
        if progresso:
            progresso.iniciar_camadas()

        def _camada_pronta(papel: str, i: int, t: int) -> None:
            if ao_progresso:
                ao_progresso("camada", papel, i, t)
            if progresso:
                progresso.camada(papel, i, t)

        preparacao = preparar_mod.preparar(
            guard=guard,
            atp_rel=atp_rel,
            extent=_extent_com_folga(bbox, folga_maxima),
            epsg=epsg_efetivo,
            ao_progresso=_camada_pronta if (ao_progresso or progresso) else None,
        )
    else:
        preparacao = _preparacao_do_disco(guard)

    resultados: list[ResultadoMapa] = []
    for indice, receita in enumerate(receitas, start=1):
        if ao_progresso:
            ao_progresso("mapa", receita.nome, indice, len(receitas))
        if progresso:
            progresso.iniciar_mapa(receita, indice)
        resultado_mapa = _gerar_um(
            receita,
            identidade=identidade,
            preparacao=preparacao,
            guard=guard,
            epsg=epsg,
            modelos=modelos,
            saidas=saidas,
            rastreador=(
                progresso.rastreador_do_mapa(receita, indice) if progresso else None
            ),
        )
        resultados.append(resultado_mapa)
        if progresso:
            progresso.concluir_mapa(
                receita,
                indice,
                ok=resultado_mapa.ok,
                erro=resultado_mapa.erro,
            )

    compilado = None
    pdfs_ok = [r for r in resultados if r.ok and r.pdf]
    if len(pdfs_ok) > 1:
        if ao_progresso:
            ao_progresso("compilando", NOME_COMPILADO, len(pdfs_ok), len(pdfs_ok))
        if progresso:
            progresso.iniciar_compilacao(len(pdfs_ok))
        compilado = _compilar(guard, [r.pdf for r in pdfs_ok if r.pdf])
        if progresso and compilado:
            progresso.artefato_compilado(compilado["pdf"], compilado["paginas"])

    relatorio = {
        "imovel": identidade.para_ndjson(),
        "preparacao": preparacao.para_ndjson(),
        "mapas": [r.para_ndjson() for r in resultados],
        "compilado": compilado,
        "resumo": {
            "total": len(resultados),
            "gerados": sum(1 for r in resultados if r.ok),
            "falhas": sum(1 for r in resultados if not r.ok),
            "anatomia_verde": sum(1 for r in resultados if (r.anatomia or {}).get("ok")),
            "anatomia_medida": sum(1 for r in resultados if r.anatomia),
            "segundos": round(time.time() - inicio, 1),
        },
    }

    destino = guard.resolver(f"{PASTA_SAIDA}/analise_de_area_relatorio.json", escrita=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1), encoding="utf-8")
    relatorio["relatorio"] = str(destino.relative_to(guard.raiz))
    if progresso:
        progresso.concluir(
            gerados=relatorio["resumo"]["gerados"],
            total=relatorio["resumo"]["total"],
            relatorio=relatorio["relatorio"],
        )
    return relatorio


def _preparacao_do_disco(guard: WorkspaceGuard) -> preparar_mod.ResultadoPreparacao:
    """Reusa camadas já materializadas — o loop de ajuste não repete a rede."""
    resultado = preparar_mod.ResultadoPreparacao()
    pasta = guard.resolver(preparar_mod.PASTA_PADRAO)
    for caminho in sorted(pasta.glob("*.shp")):
        papel = caminho.stem
        reader, _enc = _abrir_reader(caminho)
        try:
            total = len(reader.shapes())
        except Exception:  # noqa: BLE001
            total = 0
        resultado.fontes_idx[papel] = str(caminho.relative_to(guard.raiz))
        resultado.feicoes[papel] = total
    return resultado


def _gerar_um(
    receita: serie_mod.ReceitaMapa,
    *,
    identidade: IdentidadeImovel,
    preparacao: preparar_mod.ResultadoPreparacao,
    guard: WorkspaceGuard,
    epsg: int,
    modelos: Path | None,
    saidas: tuple[str, ...] = ("pdf",),
    rastreador: Any = None,
) -> ResultadoMapa:
    t0 = time.time()
    resultado = ResultadoMapa(id=receita.id, ordem=receita.ordem, nome=receita.nome, ok=False)
    try:
        mapspec = serie_mod.montar_mapspec(
            receita,
            identidade,
            fontes_disponiveis=preparacao.feicoes,
            pasta_saida=PASTA_SAIDA,
            crs=f"EPSG:{epsg}",
            saidas=saidas,
        )
        resultado.camadas = [c["id"] for c in mapspec["camadas"]]
        saida = gerar_mapa(
            mapspec,
            guard,
            dict(preparacao.fontes_idx),
            progresso=rastreador,
        )
        resultado.pdf_nativo = saida.get("pdf")
        resultado.pdf_arcmap = saida.get("pdf_arcmap")
        resultado.pdf = resultado.pdf_arcmap or resultado.pdf_nativo
        resultado.mxd = saida.get("mxd")
        resultado.avisos = list(saida.get("avisos") or [])
        artefatos = saida.get("artefatos") or {}
        resultado.basemap = (artefatos.get("basemap") or {}) if isinstance(artefatos, dict) else {}
        resultado.ok = (
            ("pdf" not in saidas or bool(resultado.pdf))
            and ("mxd" not in saidas or bool(resultado.mxd))
        )
    except Exception as exc:  # noqa: BLE001 — um mapa não derruba a série
        if getattr(exc, "codigo", None) == "NU-050":
            raise
        resultado.erro = f"{getattr(exc, 'codigo', type(exc).__name__)}: {getattr(exc, 'mensagem', exc)}"
    resultado.segundos = time.time() - t0

    if resultado.ok and modelos is not None and resultado.pdf:
        resultado.anatomia = _validar_anatomia(
            guard.resolver(resultado.pdf), modelos / receita.modelo_pdf
        )
    return resultado


def _validar_anatomia(gerado: Path, modelo: Path) -> dict[str, Any] | None:
    """Compara a anatomia do PDF gerado com a do modelo. Sem modelo, sem medida."""
    if not modelo.is_file() or not gerado.is_file():
        return None
    from mapasfacil_nucleo.validacao import anatomia as anatomia_mod

    try:
        medida_modelo = anatomia_mod.medir(modelo)
        medida_gerado = anatomia_mod.medir(gerado)
        comparacao = anatomia_mod.comparar(medida_modelo, medida_gerado)
        comparacao["modelo"] = modelo.name
        return comparacao
    except Exception as exc:  # noqa: BLE001 — medir é diagnóstico, não entrega
        return {"ok": False, "erro": str(exc), "falhas": ["medicao"]}


def _compilar(guard: WorkspaceGuard, pdfs: list[str]) -> dict[str, Any] | None:
    """Junta os PDFs na ordem da série — o equivalente ao `Mapas_unidos.pdf`."""
    try:
        import fitz
    except ImportError:  # pragma: no cover — PyMuPDF é dependência do núcleo
        return None

    destino = guard.resolver(f"{PASTA_SAIDA}/{NOME_COMPILADO}.pdf", escrita=True)
    documento = fitz.open()
    try:
        for rel in pdfs:
            caminho = guard.resolver(rel)
            if not caminho.is_file():
                continue
            with fitz.open(caminho) as parte:
                documento.insert_pdf(parte)
        if documento.page_count == 0:
            return None
        documento.save(destino)
        return {
            "pdf": str(destino.relative_to(guard.raiz)),
            "paginas": documento.page_count,
        }
    finally:
        documento.close()
