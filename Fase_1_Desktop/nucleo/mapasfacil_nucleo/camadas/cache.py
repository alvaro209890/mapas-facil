# A13 — cache de camadas externas, TTL por tema (F1-01 §Estado e armazenamento local,
# planos/03-wfs-e-servicos-geo.md §Cache no agente).
#
# Fica em `%LOCALAPPDATA%\MapasFacil\cache\` (ou XDG/env em dev/Linux) — **fora**
# do workspace e do fsguard, igual a `contas.sqlite`/`chats.sqlite`. Nunca versiona
# download (não é o repositório que guarda isso).

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# TTL em segundos, por tema do catálogo (planos/03-wfs-e-servicos-geo.md §Cache).
TTL_POR_TEMA: dict[str, int] = {
    "car": 7 * 24 * 3600,
    "embargos": 24 * 3600,
    "desmatamento": 6 * 3600,
    "malhas": 180 * 24 * 3600,
    "basemap": 30 * 24 * 3600,
}
TTL_PADRAO = 24 * 3600  # temas sem regra específica (areas_protegidas, tipologia, uso_solo…)


def ttl_do_tema(tema: str | None) -> int:
    return TTL_POR_TEMA.get(tema or "", TTL_PADRAO)


def diretorio_cache(override: str | Path | None = None) -> Path:
    """Prioridade: `override` → `MAPASFACIL_CACHE_DIR` → `MAPASFACIL_DADOS`/cache →
    `%LOCALAPPDATA%`/XDG_CACHE_HOME → `~/.cache`."""
    if override is not None:
        return Path(override).expanduser().resolve()
    env_cache = os.environ.get("MAPASFACIL_CACHE_DIR")
    if env_cache:
        return Path(env_cache).expanduser().resolve()
    env_dados = os.environ.get("MAPASFACIL_DADOS")
    if env_dados:
        return Path(env_dados).expanduser().resolve() / "cache"
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "MapasFacil" / "cache"
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "MapasFacil"
    return Path.home() / ".cache" / "MapasFacil"


@dataclass(frozen=True, slots=True)
class EntradaCache:
    dados: dict[str, Any]
    idade_s: float
    expirada: bool


def _chave_arquivo(fonte: str, bbox: tuple[float, float, float, float], crs: str) -> str:
    # bbox arredondado a ~100 m (≈0,001° perto do equador) — mesma célula de cache
    # para requisições vizinhas, igual à receita do GeoForest.
    bbox_arred = tuple(round(v, 3) for v in bbox)
    bruto = f"{fonte}|{bbox_arred}|{crs}"
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:32]


def _caminho(fonte: str, bbox: tuple[float, float, float, float], crs: str, *, base: Path) -> Path:
    return base / f"{fonte}_{_chave_arquivo(fonte, bbox, crs)}.json"


def obter(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    *,
    tema: str | None,
    base: Path | None = None,
) -> EntradaCache | None:
    caminho = _caminho(fonte, bbox, crs, base=base or diretorio_cache())
    if not caminho.exists():
        return None
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    salvo_em = bruto.get("salvo_em")
    if not isinstance(salvo_em, (int, float)):
        return None
    idade = time.time() - salvo_em
    return EntradaCache(
        dados=bruto.get("dados") or {},
        idade_s=idade,
        expirada=idade > ttl_do_tema(tema),
    )


def salvar(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    dados: dict[str, Any],
    *,
    base: Path | None = None,
) -> None:
    destino = base or diretorio_cache()
    destino.mkdir(parents=True, exist_ok=True)
    caminho = _caminho(fonte, bbox, crs, base=destino)
    payload = {"salvo_em": time.time(), "dados": dados}
    caminho.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
