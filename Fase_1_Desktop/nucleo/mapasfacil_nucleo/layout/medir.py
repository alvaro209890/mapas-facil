"""Medição de layout a partir de PDFs de referência física."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mapasfacil_nucleo.motores.perfil_pagina import (
    Caixa,
    PAISAGEM,
    RETRATO,
    por_anatomia,
)
from mapasfacil_nucleo.validacao.anatomia import medir as medir_anatomia_pdf
from .conversor import de_perfil
from .modelo import CaixaMm, DimensoesMm, FolhaPadrao, LayoutSpec, Tipografia


def medir(
    caminho_pdf: Path | str,
    id: str = "medido",
    nome: str = "Layout Medido",
    pagina: int = 0,
) -> LayoutSpec:
    """Mede as caixas e geometria de um PDF de referência e gera um LayoutSpec."""
    caminho = Path(caminho_pdf)
    if not caminho.is_file():
        raise FileNotFoundError(f"PDF de referência não encontrado: {caminho}")

    medidas = medir_anatomia_pdf(caminho, pagina=pagina)
    orientacao = medidas.get("orientacao", "retrato")
    base = PAISAGEM if orientacao == "paisagem" else RETRATO

    # Dimensões da folha
    pag_dict = medidas.get("pagina_mm") or {}
    largura = float(pag_dict.get("largura", base.largura_mm))
    altura = float(pag_dict.get("altura", base.altura_mm))

    # Caixas medidas
    quadro = medidas.get("quadro_mapa")
    caixa_mapa = (
        CaixaMm(quadro["x0"], quadro["y0"], quadro["x1"], quadro["y1"])
        if quadro
        else CaixaMm(base.mapa.x0, base.mapa.y0, base.mapa.x1, base.mapa.y1)
    )

    titulo_dict = medidas.get("titulo") or {}
    titulo_cx = titulo_dict.get("caixa_mm")
    caixa_titulo = (
        CaixaMm(titulo_cx["x0"], titulo_cx["y0"], titulo_cx["x1"], titulo_cx["y1"])
        if titulo_cx
        else CaixaMm(base.titulo.x0, base.titulo.y0, base.titulo.x1, base.titulo.y1)
    )

    meta_cx = medidas.get("metadados")
    caixa_meta = (
        CaixaMm(meta_cx["x0"], meta_cx["y0"], meta_cx["x1"], meta_cx["y1"])
        if meta_cx
        else CaixaMm(base.metadados.x0, base.metadados.y0, base.metadados.x1, base.metadados.y1)
    )

    leg_cx = medidas.get("legenda")
    caixa_leg = (
        CaixaMm(leg_cx["x0"], leg_cx["y0"], leg_cx["x1"], leg_cx["y1"])
        if leg_cx
        else CaixaMm(base.legenda.x0, base.legenda.y0, base.legenda.x1, base.legenda.y1)
    )

    elementos = {
        "mapa": caixa_mapa,
        "titulo": caixa_titulo,
        "rosa": CaixaMm(base.rosa.x0, base.rosa.y0, base.rosa.x1, base.rosa.y1),
        "minimapa": CaixaMm(base.minimapa.x0, base.minimapa.y0, base.minimapa.x1, base.minimapa.y1),
        "metadados": caixa_meta,
        "legenda": caixa_leg,
        "logo": CaixaMm(base.logo.x0, base.logo.y0, base.logo.x1, base.logo.y1),
        "tabela": CaixaMm(base.tabela.x0, base.tabela.y0, base.tabela.x1, base.tabela.y1),
    }

    tipografia = Tipografia(
        pt_titulo=float(base.pt_titulo),
        pt_metadados=float(base.pt_metadados),
        pt_legenda=float(base.pt_legenda),
        pt_grade=float(base.pt_grade),
        pt_legenda_titulo=float(base.pt_legenda_titulo),
        titulo_legenda=base.titulo_legenda,
        titulo_metadados=base.titulo_metadados,
        fonte_grade=base.fonte_grade,
    )

    return LayoutSpec(
        contract_version=1,
        versao=1,
        id=id,
        nome=nome,
        descricao=f"Medido a partir do PDF {caminho.name}",
        perfil="harmonia",
        orientacao=orientacao,
        folha_padrao=FolhaPadrao(formato="A4", orientacao=orientacao),
        dimensoes_mm=DimensoesMm(largura=largura, altura=altura),
        elementos=elementos,
        tipografia=tipografia,
        crs_padrao=base.crs_padrao,
        metadados_medidos={
            "pdf_origem": caminho.name,
            "total_palavras": medidas.get("palavras", 0),
            "rotulos_dms": medidas.get("rotulos_dms", {}),
        },
    )
