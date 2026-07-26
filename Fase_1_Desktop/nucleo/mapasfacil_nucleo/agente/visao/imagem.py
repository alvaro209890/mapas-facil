# F1-07 §"O que é medido, não perguntado" — geometria pura, sem modelo nenhum.
#
# MVP deliberado (mission explicita "pode ser MVP simples"): moldura e faixa
# inferior são heurísticas de luminância, não segmentação real. `cores_dominantes`
# é a paleta quantizada da imagem inteira, não amostragem nos swatches exatos da
# legenda — o modelo de visão recebe essas medidas e faz a interpretação fina
# (qual cor é qual camada).

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from mapasfacil_nucleo.erros import ErroNucleo

FORMATOS_CONHECIDOS: dict[str, float] = {
    "A4_retrato": 210 / 297,
    "A4_paisagem": 297 / 210,
}
TOLERANCIA_FORMATO = 0.06

LIMIAR_QUASE_BRANCO = 240.0
LIMIAR_QUASE_PRETO = 15.0
FRACAO_ESPESSURA_BORDA = 0.015
LIMIAR_LUMINANCIA_MOLDURA = 90.0
DELTA_MINIMO_MOLDURA_INTERIOR = 40.0


def _abrir(origem: bytes | bytearray | str | Path) -> Image.Image:
    try:
        if isinstance(origem, (bytes, bytearray)):
            return Image.open(io.BytesIO(origem)).convert("RGB")
        return Image.open(origem).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ErroNucleo("NU-001", f"Não consegui abrir a imagem: {exc}") from exc


def _orientacao(largura: int, altura: int) -> str:
    if largura == altura:
        return "quadrado"
    return "paisagem" if largura > altura else "retrato"


def _formato_sugerido(proporcao: float) -> str:
    for nome, alvo in FORMATOS_CONHECIDOS.items():
        if abs(proporcao - alvo) <= TOLERANCIA_FORMATO * alvo:
            return nome
    return "personalizado"


def _luminancia(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cores_dominantes(imagem: Image.Image, *, maximo: int = 5) -> list[dict[str, Any]]:
    """Paleta quantizada (16 cores), excluindo quase-branco/quase-preto (fundo/moldura)."""
    pequena = imagem.copy()
    pequena.thumbnail((200, 200))
    total_px = pequena.width * pequena.height
    if total_px == 0:
        return []
    quantizada = pequena.quantize(colors=16)
    paleta = quantizada.getpalette() or []
    contagem = quantizada.getcolors() or []

    candidatos: list[tuple[int, tuple[int, int, int]]] = []
    for count, indice in contagem:
        base = indice * 3
        if base + 2 >= len(paleta):
            continue
        rgb = (paleta[base], paleta[base + 1], paleta[base + 2])
        lum = _luminancia(rgb)
        if lum >= LIMIAR_QUASE_BRANCO or lum <= LIMIAR_QUASE_PRETO:
            continue
        candidatos.append((count, rgb))

    candidatos.sort(key=lambda item: -item[0])
    return [
        {"hex": "#{:02X}{:02X}{:02X}".format(*rgb), "fracao": round(count / total_px, 3)}
        for count, rgb in candidatos[:maximo]
    ]


def detectar_moldura(imagem: Image.Image) -> dict[str, Any]:
    """Heurística: borda uniformemente escura + interior bem mais claro (MVP)."""
    largura, altura = imagem.size
    if largura < 10 or altura < 10:
        return {
            "moldura_detectada": False,
            "luminancia_borda": None,
            "luminancia_interior": None,
        }
    espessura = max(2, int(min(largura, altura) * FRACAO_ESPESSURA_BORDA))
    px = imagem.load()

    def _media(pontos: list[tuple[int, int]]) -> float:
        if not pontos:
            return 0.0
        return sum(_luminancia(px[x, y]) for x, y in pontos) / len(pontos)

    passo_x = max(1, largura // 100)
    passo_y = max(1, altura // 100)
    borda: list[tuple[int, int]] = []
    for x in range(0, largura, passo_x):
        borda.extend((x, y) for y in range(0, espessura))
        borda.extend((x, y) for y in range(altura - espessura, altura))
    for y in range(0, altura, passo_y):
        borda.extend((x, y) for x in range(0, espessura))
        borda.extend((x, y) for x in range(largura - espessura, largura))

    cx0, cy0 = int(largura * 0.3), int(altura * 0.3)
    cx1, cy1 = max(cx0 + 1, int(largura * 0.7)), max(cy0 + 1, int(altura * 0.7))
    passo_ix = max(1, (cx1 - cx0) // 30)
    passo_iy = max(1, (cy1 - cy0) // 30)
    interior = [(x, y) for x in range(cx0, cx1, passo_ix) for y in range(cy0, cy1, passo_iy)]

    lum_borda = _media(borda)
    lum_interior = _media(interior)
    detectada = (
        lum_borda <= LIMIAR_LUMINANCIA_MOLDURA
        and (lum_interior - lum_borda) >= DELTA_MINIMO_MOLDURA_INTERIOR
    )
    return {
        "moldura_detectada": detectada,
        "luminancia_borda": round(lum_borda, 1),
        "luminancia_interior": round(lum_interior, 1),
    }


def medir_imagem(origem: bytes | bytearray | str | Path) -> dict[str, Any]:
    """Medidas determinísticas de um print/raster — nunca chama modelo nenhum."""
    imagem = _abrir(origem)
    largura, altura = imagem.size
    proporcao = round(largura / altura, 4) if altura else 0.0
    dados: dict[str, Any] = {
        "largura_px": largura,
        "altura_px": altura,
        "orientacao": _orientacao(largura, altura),
        "proporcao": proporcao,
        "formato_sugerido": _formato_sugerido(proporcao) if altura else "desconhecido",
        "cores_dominantes": cores_dominantes(imagem),
    }
    dados.update(detectar_moldura(imagem))
    return dados
