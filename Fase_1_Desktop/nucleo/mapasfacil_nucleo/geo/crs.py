from __future__ import annotations


def zona_utm_por_longitude(longitude: float) -> int:
    """Zona UTM SIRGAS 2000 para o centro-oeste brasileiro.

    Regra do acervo Harmonia (meridiano 54°W):
    - longitude < -54° → zona 21S
    - longitude >= -54° → zona 22S
    """
    return 21 if longitude < -54.0 else 22


def epsg_utm_sirgas(longitude: float) -> int:
    zona = zona_utm_por_longitude(longitude)
    return 31960 + zona  # 31981 = 21S, 31982 = 22S
