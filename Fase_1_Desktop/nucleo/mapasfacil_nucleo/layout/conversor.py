"""Conversão bidirecional entre PerfilPagina e LayoutSpec."""

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.motores.perfil_pagina import (
    Caixa,
    PerfilPagina,
    escalar_perfil,
)
from .modelo import CaixaMm, DimensoesMm, FolhaPadrao, LayoutSpec, Tipografia


def de_perfil(
    perfil: PerfilPagina,
    id: str | None = None,
    nome: str | None = None,
    descricao: str = "",
) -> LayoutSpec:
    """Converte um PerfilPagina medido em um LayoutSpec declarativo."""
    layout_id = id or f"layout_{perfil.id.replace(':', '_')}"
    layout_nome = nome or f"Layout {perfil.orientacao.capitalize()} ({perfil.formato})"

    elementos = {
        "mapa": CaixaMm(perfil.mapa.x0, perfil.mapa.y0, perfil.mapa.x1, perfil.mapa.y1),
        "titulo": CaixaMm(perfil.titulo.x0, perfil.titulo.y0, perfil.titulo.x1, perfil.titulo.y1),
        "rosa": CaixaMm(perfil.rosa.x0, perfil.rosa.y0, perfil.rosa.x1, perfil.rosa.y1),
        "minimapa": CaixaMm(perfil.minimapa.x0, perfil.minimapa.y0, perfil.minimapa.x1, perfil.minimapa.y1),
        "metadados": CaixaMm(perfil.metadados.x0, perfil.metadados.y0, perfil.metadados.x1, perfil.metadados.y1),
        "legenda": CaixaMm(perfil.legenda.x0, perfil.legenda.y0, perfil.legenda.x1, perfil.legenda.y1),
        "logo": CaixaMm(perfil.logo.x0, perfil.logo.y0, perfil.logo.x1, perfil.logo.y1),
        "tabela": CaixaMm(perfil.tabela.x0, perfil.tabela.y0, perfil.tabela.x1, perfil.tabela.y1),
    }

    tipografia = Tipografia(
        pt_titulo=float(perfil.pt_titulo),
        pt_metadados=float(perfil.pt_metadados),
        pt_legenda=float(perfil.pt_legenda),
        pt_grade=float(perfil.pt_grade),
        pt_legenda_titulo=float(perfil.pt_legenda_titulo),
        titulo_legenda=str(perfil.titulo_legenda),
        titulo_metadados=str(perfil.titulo_metadados),
        fonte_grade=tuple(perfil.fonte_grade),
    )

    return LayoutSpec(
        contract_version=1,
        versao=1,
        id=layout_id,
        nome=layout_nome,
        descricao=descricao,
        perfil="harmonia",
        orientacao=perfil.orientacao,
        folha_padrao=FolhaPadrao(formato=perfil.formato, orientacao=perfil.orientacao),
        dimensoes_mm=DimensoesMm(largura=perfil.largura_mm, altura=perfil.altura_mm),
        elementos=elementos,
        tipografia=tipografia,
        crs_padrao=perfil.crs_padrao,
    )


def perfil_do_layout(
    layout: LayoutSpec | dict[str, Any],
    folha: dict[str, Any] | None = None,
) -> PerfilPagina:
    """Converte um LayoutSpec em um PerfilPagina para consumo pelo motor nativo."""
    spec = layout if isinstance(layout, LayoutSpec) else LayoutSpec.de_dict(layout)

    def _obter_caixa(nome: str, padrao: Caixa) -> Caixa:
        c = spec.elementos.get(nome)
        if c is not None:
            return Caixa(c.x0, c.y0, c.x1, c.y1)
        return padrao

    padrao_vazio = Caixa(0.0, 0.0, 0.0, 0.0)
    mapa = _obter_caixa("mapa", padrao_vazio)
    titulo = _obter_caixa("titulo", padrao_vazio)
    rosa = _obter_caixa("rosa", padrao_vazio)
    minimapa = _obter_caixa("minimapa", padrao_vazio)
    metadados = _obter_caixa("metadados", padrao_vazio)
    legenda = _obter_caixa("legenda", padrao_vazio)
    logo = _obter_caixa("logo", padrao_vazio)
    tabela = _obter_caixa("tabela", padrao_vazio)

    formato_origem = (spec.folha_padrao.formato if spec.folha_padrao else "A4").upper()
    from mapasfacil_nucleo.motores import folhas as folhas_mod
    fator_origem = (
        folhas_mod.fator_k(formato_origem)
        if formato_origem in folhas_mod.FORMATOS
        else 1.0
    )

    base = PerfilPagina(
        id=spec.id,
        orientacao=spec.orientacao,
        largura_mm=spec.dimensoes_mm.largura,
        altura_mm=spec.dimensoes_mm.altura,
        mapa=mapa,
        titulo=titulo,
        rosa=rosa,
        minimapa=minimapa,
        metadados=metadados,
        legenda=legenda,
        logo=logo,
        tabela=tabela,
        crs_padrao=spec.crs_padrao,
        titulo_legenda=spec.tipografia.titulo_legenda,
        pt_titulo=spec.tipografia.pt_titulo,
        pt_metadados=spec.tipografia.pt_metadados,
        pt_legenda=spec.tipografia.pt_legenda,
        pt_grade=spec.tipografia.pt_grade,
        pt_legenda_titulo=spec.tipografia.pt_legenda_titulo,
        titulo_metadados=spec.tipografia.titulo_metadados,
        fonte_grade=spec.tipografia.fonte_grade,
        fator=fator_origem,
        formato=formato_origem,
    )

    if folha:
        dados = folha if isinstance(folha, dict) else {}
        formato_alvo = str(dados.get("formato") or folhas_mod.FORMATO_PADRAO).upper()
        if formato_alvo in folhas_mod.FORMATOS:
            largura_alvo, altura_alvo = folhas_mod.folha_mm(formato_alvo, base.orientacao)
            dimensoes_iguais = (
                abs(spec.dimensoes_mm.largura - largura_alvo) <= 1.0
                and abs(spec.dimensoes_mm.altura - altura_alvo) <= 1.0
            )
            formato_igual = formato_origem == formato_alvo
            if dimensoes_iguais or (formato_igual and abs(spec.dimensoes_mm.largura - largura_alvo) <= 1.0):
                fator_alvo = folhas_mod.fator_k(formato_alvo)
                if base.formato == formato_alvo and abs(base.fator - fator_alvo) < 1e-9:
                    return base
                from dataclasses import replace
                return replace(base, formato=formato_alvo, fator=fator_alvo)
        return escalar_perfil(base, folha)
    return base
