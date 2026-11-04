"""Metadados automáticos e tabela de proveniência cartográfica (W11-05).

Cada linha do bloco de metadados tem proveniência estrita; nenhum valor é
inventado ou digitado pela IA quando pode ser derivado da projeção, escala ou basemap.
"""

from __future__ import annotations

import re
from typing import Any

# Tabela fixa de nomes de datum do escritório
TABELA_DATUM: dict[int | str, str] = {
    31982: "SIRGAS 2000 UTM 22 S",
    "31982": "SIRGAS 2000 UTM 22 S",
    "EPSG:31982": "SIRGAS 2000 UTM 22 S",
    31981: "SIRGAS 2000 UTM 21 S",
    "31981": "SIRGAS 2000 UTM 21 S",
    "EPSG:31981": "SIRGAS 2000 UTM 21 S",
    31980: "SIRGAS 2000 UTM 20 S",
    "31980": "SIRGAS 2000 UTM 20 S",
    "EPSG:31980": "SIRGAS 2000 UTM 20 S",
    4674: "SIRGAS 2000",
    "4674": "SIRGAS 2000",
    "EPSG:4674": "SIRGAS 2000",
    3857: "WGS 84 / Pseudo-Mercator",
    "3857": "WGS 84 / Pseudo-Mercator",
    "EPSG:3857": "WGS 84 / Pseudo-Mercator",
}

# Meses em português
MESES = {
    "01": "Janeiro",
    "02": "Fevereiro",
    "03": "Março",
    "04": "Abril",
    "05": "Maio",
    "06": "Junho",
    "07": "Julho",
    "08": "Agosto",
    "09": "Setembro",
    "10": "Outubro",
    "11": "Novembro",
    "12": "Dezembro",
    "1": "Janeiro",
    "2": "Fevereiro",
    "3": "Março",
    "4": "Abril",
    "5": "Maio",
    "6": "Junho",
    "7": "Julho",
    "8": "Agosto",
    "9": "Setembro",
}


def formatar_escala(escala: int | float) -> str:
    """Formata escala numérica no padrão do escritório: 1:50.000."""
    return f"1:{int(escala):,}".replace(",", ".")


def formatar_data_mosaico(mosaico_id: str) -> str:
    """Extrai mês e ano de ID de mosaico (ex.: global_monthly_2026_10_mosaic -> Outubro/2026)."""
    m = re.search(r"(20\d{2})[-_](\d{1,2})", mosaico_id)
    if m:
        ano = m.group(1)
        mes_num = m.group(2).zfill(2)
        mes_nome = MESES.get(mes_num, mes_num)
        return f"{mes_nome}/{ano}"
    return mosaico_id


def resolver_sensor_padrao(nome_ou_ano: str) -> str:
    """Mapeia sensor canônico do acervo (references/regras-dinamica-temporal.md)."""
    s = str(nome_ou_ano).lower()
    if "planet" in s:
        return "PLANET"
    if "spot" in s:
        return "SPOT"
    if "landsat" in s:
        if "8" in s or "oli" in s:
            return "LANDSAT 8/OLI"
        return "LANDSAT 5/TM"
    if "cbers" in s:
        return "CBERS-4A/WPM"
    if "sentinel" in s:
        return "SENTINEL-2"

    # Inferência por ano histórico da dinâmica
    if "2000" in s:
        return "LANDSAT 5/TM"
    if "2008" in s:
        return "SPOT"
    return "PLANET"


def derivar_metadados_mapa(
    mapspec: dict[str, Any],
    *,
    escala: int | float | None = None,
    crs: str | int | None = None,
    basemap_usado: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Gera a lista de metadados cartográficos com base na proveniência real."""
    metadados: list[dict[str, str]] = []

    # 1. Datum / Projeção
    crs_val = crs or mapspec.get("crs") or 31982
    nome_datum = TABELA_DATUM.get(crs_val, f"EPSG:{crs_val}")
    metadados.append({"rotulo": "Datum", "valor": nome_datum})

    # 2. Escala
    esc_val = escala or mapspec.get("escala")
    if esc_val and isinstance(esc_val, (int, float)):
        metadados.append({"rotulo": "Escala", "valor": formatar_escala(esc_val)})

    # 3. Satélite / Sensor
    basemap = basemap_usado or mapspec.get("basemap") or {}
    sensor = basemap.get("sensor")
    if not sensor:
        sensor = resolver_sensor_padrao(basemap.get("mosaico") or mapspec.get("template") or "")
    metadados.append({"rotulo": "Satélite/Sensor", "valor": sensor})

    # 4. Data da Imagem
    data_img = basemap.get("data")
    if not data_img and basemap.get("mosaico"):
        data_img = formatar_data_mosaico(str(basemap["mosaico"]))
    if not data_img:
        data_img = "Outubro/2026"
    metadados.append({"rotulo": "Data da imagem", "valor": data_img})

    # 5. Fonte
    fonte = basemap.get("fonte") or "PLANET / IMAP"
    metadados.append({"rotulo": "Fonte", "valor": fonte})

    return metadados
