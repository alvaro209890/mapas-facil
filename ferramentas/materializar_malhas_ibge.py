# -*- coding: utf-8 -*-
"""Materializa shapefiles IBGE (municipios + UFs) em shared/bases/ibge/.

Fonte: API Malhas v3 + Localidades v1 do IBGE.
Campos alinhados ao contrato dos MXDs IMAP (`nome` na definition query).

Uso::

    python ferramentas/materializar_malhas_ibge.py
    python ferramentas/materializar_malhas_ibge.py --baixar
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import shapefile
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shared" / "bases" / "ibge"
RAW = OUT / "_raw"

URLS = {
    "br_municipios.geojson": (
        "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
        "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
    ),
    "mt_municipios.geojson": (
        "https://servicodados.ibge.gov.br/api/v3/malhas/estados/51"
        "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
    ),
    "br_ufs.geojson": (
        "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
        "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF"
    ),
    "br_localidades.json": "https://servicodados.ibge.gov.br/api/v1/localidades/municipios",
    "br_estados.json": "https://servicodados.ibge.gov.br/api/v1/localidades/estados",
    "mt_localidades.json": (
        "https://servicodados.ibge.gov.br/api/v1/localidades/estados/51/municipios"
    ),
}

PRJ_WGS84 = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def _baixar(forcar: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for nome, url in URLS.items():
        dest = RAW / nome
        if dest.exists() and not forcar:
            print(f"já existe {dest.name} ({dest.stat().st_size} bytes)")
            continue
        print(f"baixando {nome}…")
        req = urllib.request.Request(url, headers={"User-Agent": "mapas-facil/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        # API às vezes devolve gzip; urllib descomprime se Content-Encoding, senão detecta
        if data[:2] == b"\x1f\x8b":
            import gzip

            data = gzip.decompress(data)
        dest.write_bytes(data)
        print(f"  OK {len(data)} bytes")


def _uf_de_municipio(m: dict) -> dict:
    uf = (m.get("microrregiao") or {}).get("mesorregiao", {}).get("UF") or {}
    if not uf:
        uf = (
            ((m.get("regiao-imediata") or {}).get("regiao-intermediaria") or {}).get("UF")
            or {}
        )
    return uf


def _write_poly_shp(path_stem: Path, features: list, fields_fn) -> int:
    w = shapefile.Writer(str(path_stem), shapeType=shapefile.POLYGON)
    w.field("nome", "C", size=80)
    w.field("cod_ibge", "C", size=10)
    w.field("sigla_uf", "C", size=2)
    w.field("uf", "C", size=40)
    n = 0
    for feat in features:
        props = feat.get("properties") or {}
        cod = str(props.get("codarea") or "")
        vals = fields_fn(cod, props)
        if vals is None:
            continue
        geom = shape(feat["geometry"])
        if geom.is_empty:
            continue
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            if poly.geom_type != "Polygon":
                continue
            parts = [list(poly.exterior.coords)]
            for ring in poly.interiors:
                parts.append(list(ring.coords))
            w.poly(parts)
            w.record(*vals)
            n += 1
    w.close()
    path_stem.with_suffix(".prj").write_text(PRJ_WGS84, encoding="ascii")
    path_stem.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
    print(f"escreveu {path_stem.name}.shp ({n} partes)")
    return n


def materializar() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    munis = {
        str(m["id"]): m
        for m in json.loads((RAW / "br_localidades.json").read_text(encoding="utf-8"))
    }
    estados = {
        str(e["id"]): e
        for e in json.loads((RAW / "br_estados.json").read_text(encoding="utf-8"))
    }

    def mun_fields(cod: str, _props: dict):
        m = munis.get(cod)
        if not m:
            return None
        uf = _uf_de_municipio(m)
        return [
            m["nome"][:80],
            cod,
            (uf.get("sigla") or "")[:2],
            (uf.get("nome") or "")[:40],
        ]

    def uf_fields(cod: str, _props: dict):
        e = estados.get(cod)
        if not e:
            return None
        return [e["nome"][:80], cod, (e.get("sigla") or "")[:2], e["nome"][:40]]

    gj = json.loads((RAW / "br_municipios.geojson").read_text(encoding="utf-8"))
    _write_poly_shp(OUT / "lml_municipio_a", gj["features"], mun_fields)

    gj_mt = json.loads((RAW / "mt_municipios.geojson").read_text(encoding="utf-8"))
    _write_poly_shp(OUT / "lml_municipio_mt", gj_mt["features"], mun_fields)

    gj_uf = json.loads((RAW / "br_ufs.geojson").read_text(encoding="utf-8"))
    _write_poly_shp(OUT / "lml_uf_a", gj_uf["features"], uf_fields)

    meta = {
        "fonte": "IBGE Malhas API v3 + Localidades v1",
        "qualidade": "minima",
        "crs": "EPSG:4326",
        "campos": ["nome", "cod_ibge", "sigla_uf", "uf"],
        "arquivos": {
            "lml_municipio_a": "todos os municipios do Brasil (campo nome p/ definition query)",
            "lml_municipio_mt": "somente MT (mais leve)",
            "lml_uf_a": "UFs do Brasil (campo nome = nome por extenso, ex. Mato Grosso)",
        },
        "definition_query_exemplos": {
            "municipio": "\"nome\" = 'Vila Rica'",
            "uf": "\"nome\" = 'Mato Grosso'",
        },
    }
    (OUT / "README.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baixar", action="store_true", help="Baixa/atualiza JSON bruto da API")
    ap.add_argument("--forcar-download", action="store_true")
    args = ap.parse_args()
    if args.baixar or args.forcar_download or not (RAW / "br_municipios.geojson").exists():
        _baixar(forcar=args.forcar_download)
    materializar()


if __name__ == "__main__":
    main()
