"""Cliente das malhas IBGE (API v3) com cache em disco.

A resposta pode vir gzip — descomprimir antes do JSON.
Shapefiles versionados: `shared/bases/ibge/` (ver `ferramentas/materializar_malhas_ibge.py`).
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.camadas.cache import TTL_POR_TEMA, diretorio_cache

UA = "mapas-facil/1.0 (ibge-malhas)"
TTL_MALHAS = TTL_POR_TEMA["malhas"]


def _get_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def _cache_path(chave: str) -> Path:
    return diretorio_cache() / "malhas" / f"{chave}.json"


def _ler(chave: str) -> dict[str, Any] | None:
    caminho = _cache_path(chave)
    if not caminho.exists():
        return None
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - float(bruto.get("salvo_em") or 0) > TTL_MALHAS:
        return None
    dados = bruto.get("dados")
    return dados if isinstance(dados, dict) else None


def _gravar(chave: str, dados: dict[str, Any]) -> None:
    caminho = _cache_path(chave)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps({"salvo_em": time.time(), "dados": dados}, ensure_ascii=False),
        encoding="utf-8",
    )


def malha_municipios_uf(cod_uf: str | int = 51) -> dict[str, Any]:
    """GeoJSON minimo dos municipios de uma UF (cod IBGE 2 digitos)."""
    chave = f"municipios_uf_{cod_uf}"
    cached = _ler(chave)
    if cached is not None:
        return cached
    url = (
        f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{cod_uf}"
        "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
    )
    data = json.loads(_get_bytes(url).decode("utf-8"))
    _gravar(chave, data)
    return data


def malha_ufs_br() -> dict[str, Any]:
    chave = "ufs_br"
    cached = _ler(chave)
    if cached is not None:
        return cached
    url = (
        "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
        "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF"
    )
    data = json.loads(_get_bytes(url).decode("utf-8"))
    _gravar(chave, data)
    return data


def pasta_shapefile_repo(root: Path | None = None) -> Path:
    """Pasta dos .shp versionados no monorepo."""
    if root is None:
        # .../Fase_1_Desktop/nucleo/mapasfacil_nucleo/camadas/ibge.py → repo root
        root = Path(__file__).resolve().parents[4]
    return root / "shared" / "bases" / "ibge"


def shapefile_municipios(root: Path | None = None) -> Path:
    return pasta_shapefile_repo(root) / "lml_municipio_a.shp"


def shapefile_ufs(root: Path | None = None) -> Path:
    return pasta_shapefile_repo(root) / "lml_uf_a.shp"
