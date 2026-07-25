from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Paleta F1-08 (mesma do .xlsx)
COR_CABECALHO = (46, 117, 182)  # #2E75B6
COR_TOTAL = (112, 173, 71)  # #70AD47
COR_TEXTO = (0, 0, 0)
COR_TEXTO_CLARO = (255, 255, 255)
COR_BORDA = (180, 180, 180)
COR_FUNDO = (255, 255, 255)

# Modelo Harmonia: ~3210 × 472 px para 13,59 × 2,00 cm → ≥ 600 dpi efetivos
DPI_ALVO = 600
LARGURA_CM = 13.59
ALTURA_LINHA_PX = 72
PADDING = 12


def _fonte(tamanho: int, *, negrito: bool = False) -> ImageFont.ImageFont:
    candidatos = []
    if negrito:
        candidatos.extend(
            [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ]
        )
    candidatos.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )
    for caminho in candidatos:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def _formatar_valor(valor: Any, casas: int) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, (int, float)):
        texto = f"{valor:.{casas}f}"
        # pt-BR: milhar com ponto, decimal com vírgula
        if "." in texto:
            inteiro, frac = texto.split(".", 1)
        else:
            inteiro, frac = texto, ""
        inteiro = f"{int(inteiro):,}".replace(",", ".")
        return f"{inteiro},{frac}" if frac else inteiro
    return str(valor)


def _quebrar_cabecalho(texto: str, max_chars: int = 18) -> str:
    if len(texto) <= max_chars:
        return texto
    # Quebra preferencial em espaço próximo do meio
    meio = len(texto) // 2
    espaco = texto.rfind(" ", 0, meio + 8)
    if espaco <= 0:
        espaco = texto.find(" ", meio)
    if espaco <= 0:
        return texto
    return texto[:espaco].strip() + "\n" + texto[espaco:].strip()


def _medir_texto(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.ImageFont) -> tuple[int, int]:
    caixa = draw.multiline_textbbox((0, 0), texto, font=fonte, spacing=4)
    return caixa[2] - caixa[0], caixa[3] - caixa[1]


def renderizar_png_tabela(
    dados: dict[str, Any],
    destino: Path,
    *,
    dpi: int = DPI_ALVO,
) -> dict[str, Any]:
    """Gera PNG da tabela de quantitativos (≥ 600 dpi efetivos) — F1-08."""
    colunas = list(dados.get("colunas") or [])
    linhas = list(dados.get("linhas") or [])
    if not colunas:
        raise ValueError("dados sem colunas")

    casas = int(dados.get("casas_decimais") or 4)
    total_geral = dados.get("total_geral")
    tem_total = total_geral is not None

    n_linhas_dados = len(linhas) + (1 if tem_total else 0)
    n_linhas_visuais = 1 + n_linhas_dados  # cabeçalho + dados

    largura_px = max(math.ceil(LARGURA_CM / 2.54 * dpi), 3210)
    altura_px = max(ALTURA_LINHA_PX * n_linhas_visuais + PADDING * 2, 200)

    img = Image.new("RGB", (largura_px, altura_px), COR_FUNDO)
    draw = ImageDraw.Draw(img)

    fonte_cab = _fonte(22, negrito=True)
    fonte_cel = _fonte(20)
    fonte_total = _fonte(20, negrito=True)

    pesos = [2.0] + [1.5] + [1.0] * max(0, len(colunas) - 2)
    pesos = pesos[: len(colunas)]
    soma_pesos = sum(pesos)
    larguras = [int(largura_px * p / soma_pesos) for p in pesos]
    # Ajuste residual na última coluna
    larguras[-1] += largura_px - sum(larguras)

    y = 0
    # Cabeçalho
    x = 0
    for col_idx, nome in enumerate(colunas):
        w = larguras[col_idx]
        draw.rectangle([x, y, x + w, y + ALTURA_LINHA_PX], fill=COR_CABECALHO, outline=COR_BORDA)
        texto = _quebrar_cabecalho(str(nome))
        tw, th = _medir_texto(draw, texto, fonte_cab)
        draw.multiline_text(
            (x + (w - tw) / 2, y + (ALTURA_LINHA_PX - th) / 2),
            texto,
            fill=COR_TEXTO_CLARO,
            font=fonte_cab,
            align="center",
            spacing=4,
        )
        x += w
    y += ALTURA_LINHA_PX

    # Linhas de dados
    for linha in linhas:
        x = 0
        for col_idx in range(len(colunas)):
            w = larguras[col_idx]
            valor = linha[col_idx] if col_idx < len(linha) else None
            texto = _formatar_valor(valor, casas) if col_idx > 0 else str(valor or "—")
            draw.rectangle([x, y, x + w, y + ALTURA_LINHA_PX], fill=COR_FUNDO, outline=COR_BORDA)
            fonte = fonte_cel
            tw, th = _medir_texto(draw, texto, fonte)
            if col_idx == 0:
                tx = x + PADDING
            else:
                tx = x + w - tw - PADDING
            draw.text((tx, y + (ALTURA_LINHA_PX - th) / 2), texto, fill=COR_TEXTO, font=fonte)
            x += w
        y += ALTURA_LINHA_PX

    # TOTAL GERAL
    if tem_total:
        x = 0
        for col_idx in range(len(colunas)):
            w = larguras[col_idx]
            draw.rectangle([x, y, x + w, y + ALTURA_LINHA_PX], fill=COR_TOTAL, outline=COR_BORDA)
            if col_idx == 0:
                texto = "TOTAL GERAL"
            elif col_idx == 1:
                # Soma das classes já arredondadas, ou o total_geral informado
                texto = _formatar_valor(total_geral, casas)
            else:
                # Soma da coluna entre as linhas de dados
                soma = 0.0
                tem_num = False
                for linha in linhas:
                    if col_idx < len(linha) and isinstance(linha[col_idx], (int, float)):
                        soma += float(linha[col_idx])
                        tem_num = True
                texto = _formatar_valor(round(soma, casas) if tem_num else None, casas)
            tw, th = _medir_texto(draw, texto, fonte_total)
            tx = x + PADDING if col_idx == 0 else x + w - tw - PADDING
            draw.text((tx, y + (ALTURA_LINHA_PX - th) / 2), texto, fill=COR_TEXTO_CLARO, font=fonte_total)
            x += w

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, format="PNG", dpi=(dpi, dpi))

    dpi_efetivo = largura_px / (LARGURA_CM / 2.54)
    return {
        "png": str(destino),
        "largura_px": largura_px,
        "altura_px": altura_px,
        "dpi": dpi,
        "dpi_efetivo": round(dpi_efetivo, 1),
        "ok_dpi": dpi_efetivo >= 600,
    }
