"""Cliente das malhas IBGE (API v3) + shapefiles versionados no repo.

Shapefiles: `shared/bases/ibge/` (ver `ferramentas/materializar_malhas_ibge.py`).
Campo da definition query nos MXDs: `nome` (município) / `nome` (UF por extenso).
"""

from __future__ import annotations

import gzip
import json
import time
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

import shapefile
from shapely.geometry import shape
from shapely.ops import unary_union

from mapasfacil_nucleo.camadas.cache import TTL_POR_TEMA, diretorio_cache

UA = "mapas-facil/1.0 (ibge-malhas)"
TTL_MALHAS = TTL_POR_TEMA["malhas"]

# Sigla → nome por extenso (campo `nome` de lml_uf_a.shp)
UF_SIGLA_PARA_NOME: dict[str, str] = {
    "AC": "Acre",
    "AL": "Alagoas",
    "AP": "Amapá",
    "AM": "Amazonas",
    "BA": "Bahia",
    "CE": "Ceará",
    "DF": "Distrito Federal",
    "ES": "Espírito Santo",
    "GO": "Goiás",
    "MA": "Maranhão",
    "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul",
    "MG": "Minas Gerais",
    "PA": "Pará",
    "PB": "Paraíba",
    "PR": "Paraná",
    "PE": "Pernambuco",
    "PI": "Piauí",
    "RJ": "Rio de Janeiro",
    "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul",
    "RO": "Rondônia",
    "RR": "Roraima",
    "SC": "Santa Catarina",
    "SP": "São Paulo",
    "SE": "Sergipe",
    "TO": "Tocantins",
}


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
        root = Path(__file__).resolve().parents[4]
    return root / "shared" / "bases" / "ibge"


def shapefile_municipios(root: Path | None = None) -> Path:
    return pasta_shapefile_repo(root) / "lml_municipio_a.shp"


def shapefile_ufs(root: Path | None = None) -> Path:
    return pasta_shapefile_repo(root) / "lml_uf_a.shp"


def uf_sigla_para_nome(sigla: str | None) -> str:
    """`MT` → `Mato Grosso` (campo `nome` da definition query da UF)."""
    if not sigla:
        return "Mato Grosso"
    return UF_SIGLA_PARA_NOME.get(str(sigla).strip().upper(), str(sigla).strip())


@lru_cache(maxsize=1)
def _indice_municipios(shp_path: str) -> dict[str, dict[str, str]]:
    """nome_normalizado → {nome, cod_ibge, sigla_uf, uf}."""
    reader = shapefile.Reader(shp_path)
    fields = [f[0] for f in reader.fields[1:]]
    idx: dict[str, dict[str, str]] = {}
    for rec in reader.iterRecords():
        row = {fields[i]: str(rec[i] or "") for i in range(len(fields))}
        nome = row.get("nome") or ""
        if not nome:
            continue
        chave = nome.casefold().strip()
        idx[chave] = {
            "nome": nome,
            "cod_ibge": row.get("cod_ibge") or "",
            "sigla_uf": row.get("sigla_uf") or "",
            "uf": row.get("uf") or "",
        }
        # também indexa por código
        cod = row.get("cod_ibge") or ""
        if cod:
            idx[cod] = idx[chave]
    return idx


def resolver_municipio(
    *,
    nome: str | None = None,
    ibge: str | None = None,
    root: Path | None = None,
) -> dict[str, str] | None:
    """Resolve município na base local (nome ou código IBGE)."""
    shp = shapefile_municipios(root)
    if not shp.is_file():
        return None
    indice = _indice_municipios(str(shp))
    if ibge:
        hit = indice.get(str(ibge).strip())
        if hit:
            return dict(hit)
    if nome:
        hit = indice.get(str(nome).casefold().strip())
        if hit:
            return dict(hit)
    return None


def extent_municipio(
    *,
    nome: str | None = None,
    ibge: str | None = None,
    root: Path | None = None,
    padding: float = 1.25,
) -> tuple[float, float, float, float] | None:
    """BBox WGS84 (xmin, ymin, xmax, ymax) do município, com padding."""
    info = resolver_municipio(nome=nome, ibge=ibge, root=root)
    if not info:
        return None
    shp = shapefile_municipios(root)
    reader = shapefile.Reader(str(shp))
    fields = [f[0] for f in reader.fields[1:]]
    nome_i = fields.index("nome") if "nome" in fields else 0
    geoms = []
    alvo = info["nome"]
    for sr in reader.iterShapeRecords():
        if str(sr.record[nome_i]) != alvo:
            continue
        try:
            geoms.append(shape(sr.shape.__geo_interface__))
        except Exception:
            continue
    if not geoms:
        return None
    union = unary_union(geoms)
    minx, miny, maxx, maxy = union.bounds
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    half_w = (maxx - minx) / 2.0 * padding
    half_h = (maxy - miny) / 2.0 * padding
    return cx - half_w, cy - half_h, cx + half_w, cy + half_h
