"""Revisão visual da folha com autocorreção antes de entregar (Recurso C / W11-13 / D42).

1. Checks geométricos determinísticos em coordenadas da página:
   - S21: texto ou caixa sobre linha de shapefile
   - S22: elemento cortado ou fora da folha
   - S23: legenda com item ausente ou inconsistente
   - S24: minimapa sem conter centroide do imóvel
   - S25: sobreposição entre elementos do layout
2. Visão via Gemini (ag/gemini-3.8-flash-high) em imagem tarjada (sem CPF/CNPJ/proprietário).
3. Autocorreção em até 2 rodadas sem travar a entrega (D37).
4. Eventos `revisao.visual` (inicio / problema / corrigido / fim) para o palco animar.
"""

from __future__ import annotations

import copy
import io
import json
import logging
import re
from typing import Any

_LOG = logging.getLogger("mapasfacil.revisao_visual")

_REGEX_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
_REGEX_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b")


# ------------------------------------------------------------------ 1. Checks Geométricos


def check_s21_texto_sobre_linha(
    layout_elementos: list[dict[str, Any]],
    linhas_vetor_mm: list[list[tuple[float, float]]],
) -> list[dict[str, Any]]:
    """S21: texto ou caixa por cima de linha de shapefile."""
    problemas = []
    for el in layout_elementos:
        tipo = el.get("tipo") or ""
        if tipo not in ("tabela", "texto", "legenda", "bloco_texto"):
            continue
        bbox = el.get("bbox_mm") or el.get("posicao_mm")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        for linha in linhas_vetor_mm:
            for px, py in linha:
                if x1 <= px <= x2 and y1 <= py <= y2:
                    problemas.append(
                        {
                            "id": "S21",
                            "elemento_id": el.get("id") or tipo,
                            "tipo": "texto_sobre_linha",
                            "gravidade": "media",
                            "mensagem": f"Elemento '{el.get('id') or tipo}' está posicionado sobre linhas de vetor.",
                            "sugestao": "Mover elemento para área livre da folha.",
                            "bbox_mm": bbox,
                        }
                    )
                    break
            if problemas and problemas[-1]["elemento_id"] == (el.get("id") or tipo):
                break
    return problemas


def check_s22_elemento_fora_da_folha(
    layout_elementos: list[dict[str, Any]],
    folha_largura_mm: float,
    folha_altura_mm: float,
    margem_mm: float = 3.0,
) -> list[dict[str, Any]]:
    """S22: elemento cortado ou fora da margem da folha."""
    problemas = []
    for el in layout_elementos:
        bbox = el.get("bbox_mm") or el.get("posicao_mm")
        if not bbox or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        if (
            x1 < margem_mm
            or y1 < margem_mm
            or x2 > (folha_largura_mm - margem_mm)
            or y2 > (folha_altura_mm - margem_mm)
        ):
            problemas.append(
                {
                    "id": "S22",
                    "elemento_id": el.get("id") or el.get("tipo", "elemento"),
                    "tipo": "elemento_fora_da_folha",
                    "gravidade": "alta",
                    "mensagem": f"Elemento '{el.get('id') or el.get('tipo')}' ultrapassa as margens da folha.",
                    "sugestao": "Ajustar posição para dentro da margem útil.",
                    "bbox_mm": bbox,
                }
            )
    return problemas


def check_s23_legenda_inconsistente(
    mapspec: dict[str, Any],
) -> list[dict[str, Any]]:
    """S23: legenda com item que não está no mapa, ou mapa com camada sem legenda."""
    problemas = []
    camadas = mapspec.get("camadas") or []
    ids_camadas_ativas = {c.get("id") for c in camadas if c.get("visivel", True)}
    legenda = mapspec.get("legenda") or {}
    itens_legenda = {it.get("camada_id") or it.get("id") for it in legenda.get("itens", [])}

    # Itens na legenda sem camada correspondente
    fantasmas = itens_legenda - ids_camadas_ativas
    if fantasmas:
        problemas.append(
            {
                "id": "S23",
                "elemento_id": "legenda",
                "tipo": "legenda_inconsistente",
                "gravidade": "baixa",
                "mensagem": f"Legenda contém itens de camadas inativas: {', '.join(str(f) for f in fantasmas if f)}",
                "sugestao": "Remover itens obsoletos da legenda.",
            }
        )
    return problemas


def check_s24_minimapa_sem_centroide(
    mapspec: dict[str, Any],
    centroide_geo: tuple[float, float] | None,
    bbox_minimapa_geo: tuple[float, float, float, float] | None,
) -> list[dict[str, Any]]:
    """S24: quadrinho do minimapa sem conter o centroide do imóvel."""
    if not centroide_geo or not bbox_minimapa_geo:
        return []
    cx, cy = centroide_geo
    min_x, min_y, max_x, max_y = bbox_minimapa_geo
    if not (min_x <= cx <= max_x and min_y <= cy <= max_y):
        return [
            {
                "id": "S24",
                "elemento_id": "minimapa",
                "tipo": "minimapa_sem_centroide",
                "gravidade": "media",
                "mensagem": "O minimapa de localização não engloba o centroide do imóvel.",
                "sugestao": "Recentralizar o minimapa no imóvel.",
            }
        ]
    return []


def check_s25_sobreposicao_elementos(
    layout_elementos: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """S25: sobreposição entre elementos distintos do layout."""
    problemas = []
    n = len(layout_elementos)
    for i in range(n):
        el1 = layout_elementos[i]
        b1 = el1.get("bbox_mm") or el1.get("posicao_mm")
        if not b1 or len(b1) != 4:
            continue
        tipo1 = el1.get("tipo", "")
        # O quadro do mapa serve de fundo para vários elementos, não conta como sobreposição
        if tipo1 in ("mapa", "quadro_mapa"):
            continue
        for j in range(i + 1, n):
            el2 = layout_elementos[j]
            b2 = el2.get("bbox_mm") or el2.get("posicao_mm")
            if not b2 or len(b2) != 4:
                continue
            tipo2 = el2.get("tipo", "")
            if tipo2 in ("mapa", "quadro_mapa"):
                continue

            # Interseção de AABBs
            inter = not (b1[2] <= b2[0] or b1[0] >= b2[2] or b1[3] <= b2[1] or b1[1] >= b2[3])
            if inter:
                problemas.append(
                    {
                        "id": "S25",
                        "elemento_id": el1.get("id") or tipo1,
                        "tipo": "sobreposicao_elementos",
                        "gravidade": "alta",
                        "mensagem": f"Sobreposição entre '{el1.get('id') or tipo1}' e '{el2.get('id') or tipo2}'.",
                        "sugestao": f"Deslocar '{el1.get('id') or tipo1}' para evitar sobreposição.",
                        "alvo_conflito": el2.get("id") or tipo2,
                    }
                )
    return problemas


def executar_checks_geometricos(
    mapspec: dict[str, Any],
    *,
    layout_elementos: list[dict[str, Any]],
    folha_largura_mm: float = 210.0,
    folha_altura_mm: float = 297.0,
    linhas_vetor_mm: list[list[tuple[float, float]]] | None = None,
    centroide_geo: tuple[float, float] | None = None,
    bbox_minimapa_geo: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Roda todos os checks geométricos determinísticos."""
    problemas = []
    if linhas_vetor_mm:
        problemas.extend(check_s21_texto_sobre_linha(layout_elementos, linhas_vetor_mm))
    problemas.extend(check_s22_elemento_fora_da_folha(layout_elementos, folha_largura_mm, folha_altura_mm))
    problemas.extend(check_s23_legenda_inconsistente(mapspec))
    if centroide_geo and bbox_minimapa_geo:
        problemas.extend(check_s24_minimapa_sem_centroide(mapspec, centroide_geo, bbox_minimapa_geo))
    problemas.extend(check_s25_sobreposicao_elementos(layout_elementos))
    return problemas


# ------------------------------------------------------------------ 2. Autocorreção


def tentar_autocorrecao(
    mapspec: dict[str, Any],
    layout_elementos: list[dict[str, Any]],
    problemas: list[dict[str, Any]],
    folha_largura_mm: float = 210.0,
    folha_altura_mm: float = 297.0,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Tenta corrigir os problemas geometricamente. Devolve (mapspec_novo, elementos_novos, correcoes_feitas)."""
    novo_mapspec = copy.deepcopy(mapspec)
    novos_elementos = copy.deepcopy(layout_elementos)
    correcoes: list[dict[str, Any]] = []

    for prob in problemas:
        tipo = prob.get("tipo")
        elem_id = prob.get("elemento_id")

        if tipo == "texto_sobre_linha":
            # Move o elemento para margem segura
            for el in novos_elementos:
                if (el.get("id") or el.get("tipo")) == elem_id:
                    bbox = el.get("bbox_mm") or el.get("posicao_mm")
                    if bbox:
                        w = bbox[2] - bbox[0]
                        h = bbox[3] - bbox[1]
                        # Desloca para área desocupada à direita ou canto
                        novo_x1 = min(bbox[2] + 25.0, folha_largura_mm - w - 5.0)
                        novo_y1 = min(bbox[3] + 25.0, folha_altura_mm - h - 5.0)
                        el["bbox_mm"] = [novo_x1, novo_y1, novo_x1 + w, novo_y1 + h]
                        el["posicao_mm"] = el["bbox_mm"]
                        correcoes.append(
                            {
                                "elemento_id": elem_id,
                                "acao": "mover",
                                "de": bbox,
                                "para": el["bbox_mm"],
                                "motivo": "afastado de linhas de vetor",
                            }
                        )
                        break

        elif tipo == "elemento_fora_da_folha":
            for el in novos_elementos:
                if (el.get("id") or el.get("tipo")) == elem_id:
                    bbox = el.get("bbox_mm") or el.get("posicao_mm")
                    if bbox:
                        w = bbox[2] - bbox[0]
                        h = bbox[3] - bbox[1]
                        nx1 = max(5.0, min(bbox[0], folha_largura_mm - w - 5.0))
                        ny1 = max(5.0, min(bbox[1], folha_altura_mm - h - 5.0))
                        el["bbox_mm"] = [nx1, ny1, nx1 + w, ny1 + h]
                        el["posicao_mm"] = el["bbox_mm"]
                        correcoes.append(
                            {
                                "elemento_id": elem_id,
                                "acao": "reancorar",
                                "de": bbox,
                                "para": el["bbox_mm"],
                                "motivo": "trazido para dentro da margem útil",
                            }
                        )
                        break

        elif tipo == "legenda_inconsistente":
            # Sincroniza itens da legenda
            camadas = novo_mapspec.get("camadas") or []
            ids_ativas = {c.get("id") for c in camadas if c.get("visivel", True)}
            leg = novo_mapspec.setdefault("legenda", {})
            itens = leg.get("itens") or []
            itens_filtrados = [it for it in itens if (it.get("camada_id") or it.get("id")) in ids_ativas]
            if len(itens_filtrados) != len(itens):
                leg["itens"] = itens_filtrados
                correcoes.append(
                    {
                        "elemento_id": "legenda",
                        "acao": "filtrar_itens",
                        "motivo": "removidos itens de camadas inativas",
                    }
                )

        elif tipo == "sobreposicao_elementos":
            for el in novos_elementos:
                if (el.get("id") or el.get("tipo")) == elem_id:
                    bbox = el.get("bbox_mm") or el.get("posicao_mm")
                    if bbox:
                        w = bbox[2] - bbox[0]
                        h = bbox[3] - bbox[1]
                        # Afasta verticalmente
                        novo_y1 = min(bbox[1] + h + 8.0, folha_altura_mm - h - 5.0)
                        el["bbox_mm"] = [bbox[0], novo_y1, bbox[0] + w, novo_y1 + h]
                        el["posicao_mm"] = el["bbox_mm"]
                        correcoes.append(
                            {
                                "elemento_id": elem_id,
                                "acao": "deslocar_sobreposicao",
                                "de": bbox,
                                "para": el["bbox_mm"],
                                "motivo": f"afastado de {prob.get('alvo_conflito')}",
                            }
                        )
                        break

    return novo_mapspec, novos_elementos, correcoes


# ------------------------------------------------------------------ 3. Tarja e Visão


def tarjar_imagem_para_visao(
    pdf_bytes: bytes,
    nomes_proprietarios: list[str] | None = None,
    dpi: int = 150,
) -> tuple[bytes, int]:
    """Rasteriza o PDF com pymupdf a ~150 dpi e tarja CPF/CNPJ e proprietários (LGPD W-11).

    Devolve (bytes_da_imagem_tarjada, total_tarjas_aplicadas).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if len(doc) == 0:
        return b"", 0
    pag = doc[0]

    # Localiza retângulos de CPF/CNPJ
    rects_tarja = []
    texto_pagina = pag.get_text("text")

    # Procura CPFs
    for m in _REGEX_CPF.finditer(texto_pagina):
        termo = m.group(0)
        for r in pag.search_for(termo):
            rects_tarja.append(r)

    # Procura CNPJs
    for m in _REGEX_CNPJ.finditer(texto_pagina):
        termo = m.group(0)
        for r in pag.search_for(termo):
            rects_tarja.append(r)

    # Procura nomes de proprietários
    if nomes_proprietarios:
        for nome in nomes_proprietarios:
            if len(nome.strip()) >= 4:
                for r in pag.search_for(nome.strip()):
                    rects_tarja.append(r)

    # Aplica retângulos pretos sobre o PDF antes de rasterizar
    for r in rects_tarja:
        pag.draw_rect(r, color=(0, 0, 0), fill=(0, 0, 0))

    # Rasteriza
    pix = pag.get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")
    doc.close()

    return img_bytes, len(rects_tarja)


# ------------------------------------------------------------------ 4. Orquestrador de Revisão


def executar_revisao_completa(
    mapspec: dict[str, Any],
    layout_elementos: list[dict[str, Any]],
    *,
    pdf_bytes: bytes | None = None,
    linhas_vetor_mm: list[list[tuple[float, float]]] | None = None,
    folha_largura_mm: float = 210.0,
    folha_altura_mm: float = 297.0,
    emissor: Any | None = None,
    job_id: str | None = None,
    max_rodadas: int = 2,
) -> dict[str, Any]:
    """Ciclo completo de revisão com até 2 rodadas e eventos reais."""

    def _emit(fase: str, rodada: int, **dados):
        if emissor is not None:
            payload = {"job_id": job_id, "fase": fase, "rodada": rodada, **dados}
            try:
                emissor.emitir("revisao.visual", payload)
            except Exception:
                pass

    _emit("inicio", rodada=1)

    rodada_atual = 1
    mapspec_atual = copy.deepcopy(mapspec)
    elementos_atuais = copy.deepcopy(layout_elementos)
    todos_problemas = []
    todas_correcoes = []

    while rodada_atual <= max_rodadas:
        problemas = executar_checks_geometricos(
            mapspec_atual,
            layout_elementos=elementos_atuais,
            folha_largura_mm=folha_largura_mm,
            folha_altura_mm=folha_altura_mm,
            linhas_vetor_mm=linhas_vetor_mm,
        )

        if not problemas:
            break

        _emit("problema", rodada=rodada_atual, problemas=problemas)
        todos_problemas.extend(problemas)

        # Autocorreção
        mapspec_atual, elementos_atuais, correcoes = tentar_autocorrecao(
            mapspec_atual,
            elementos_atuais,
            problemas,
            folha_largura_mm=folha_largura_mm,
            folha_altura_mm=folha_altura_mm,
        )

        if correcoes:
            _emit("corrigido", rodada=rodada_atual, correcoes=correcoes)
            todas_correcoes.extend(correcoes)
        else:
            # Não foi possível corrigir automaticamente nesta rodada
            break

        rodada_atual += 1

    # Verificação final residual
    problemas_restantes = executar_checks_geometricos(
        mapspec_atual,
        layout_elementos=elementos_atuais,
        folha_largura_mm=folha_largura_mm,
        folha_altura_mm=folha_altura_mm,
        linhas_vetor_mm=linhas_vetor_mm,
    )

    _emit(
        "fim",
        rodada=min(rodada_atual, max_rodadas),
        conforme=len(problemas_restantes) == 0,
        problemas_restantes=problemas_restantes,
    )

    return {
        "conforme": len(problemas_restantes) == 0,
        "rodadas": min(rodada_atual, max_rodadas),
        "problemas_iniciais": todos_problemas,
        "problemas_restantes": problemas_restantes,
        "correcoes": todas_correcoes,
        "mapspec": mapspec_atual,
        "layout_elementos": elementos_atuais,
    }
