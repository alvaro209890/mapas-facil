"""Acervo local, compartilhado e endereçado por requisição para rasters WMS.

O arquivo materializado continua dentro de ``Mapas/recursos``. Este módulo só
mantém uma cópia local fora do workspace para evitar baixar novamente a mesma
cena em outro projeto. Chaves de autenticação e URLs assinadas nunca entram nos
metadados persistidos.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"


@dataclass(frozen=True, slots=True)
class EntradaRaster:
    imagem: bytes
    extensao: str
    metadados: dict[str, Any]


def diretorio_acervo(override: str | Path | None = None) -> Path:
    """Resolve o acervo sem colocá-lo no repositório ou no workspace."""
    if override is not None:
        return Path(override).expanduser().resolve()
    env_acervo = os.environ.get("MAPASFACIL_ACERVO_RASTERS")
    if env_acervo:
        return Path(env_acervo).expanduser().resolve()
    env_dados = os.environ.get("MAPASFACIL_DADOS")
    if env_dados:
        return Path(env_dados).expanduser().resolve() / "acervo" / "rasters"
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "MapasFacil" / "acervo" / "rasters"
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "MapasFacil" / "acervo" / "rasters"
    return Path.home() / ".cache" / "MapasFacil" / "acervo" / "rasters"


def _eh_imagem(imagem: bytes) -> bool:
    return imagem.startswith(MAGIC_PNG) or imagem.startswith(MAGIC_JPEG)


def _extensao(imagem: bytes) -> str:
    return ".png" if imagem.startswith(MAGIC_PNG) else ".jpg"


def _chave(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    largura: int,
    *,
    endpoint: str | None,
    camada: str | None,
) -> str:
    # O bbox não é arredondado: uma imagem de fundo é esticada exatamente sobre
    # o extent e, portanto, uma célula vizinha não pode compartilhar o raster.
    bbox_estavel = tuple(format(float(valor), ".10g") for valor in bbox)
    bruto = json.dumps(
        {
            "fonte": fonte,
            "bbox": bbox_estavel,
            "crs": crs.upper(),
            "largura": int(largura),
            "endpoint": endpoint or "",
            "camada": camada or "",
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _caminhos(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    largura: int,
    *,
    endpoint: str | None,
    camada: str | None,
    base: Path,
) -> tuple[Path, Path]:
    chave = _chave(fonte, bbox, crs, largura, endpoint=endpoint, camada=camada)
    prefixo = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in fonte)[:48]
    pasta = base / prefixo
    return pasta / f"{chave}.img", pasta / f"{chave}.json"


def obter(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    largura: int,
    *,
    endpoint: str | None = None,
    camada: str | None = None,
    base: Path | None = None,
) -> EntradaRaster | None:
    imagem_path, metadados_path = _caminhos(
        fonte,
        bbox,
        crs,
        largura,
        endpoint=endpoint,
        camada=camada,
        base=base or diretorio_acervo(),
    )
    try:
        imagem = imagem_path.read_bytes()
        metadados = json.loads(metadados_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not _eh_imagem(imagem) or not isinstance(metadados, dict):
        return None
    if metadados.get("sha256") != hashlib.sha256(imagem).hexdigest():
        return None
    return EntradaRaster(imagem=imagem, extensao=_extensao(imagem), metadados=metadados)


def salvar(
    fonte: str,
    bbox: tuple[float, float, float, float],
    crs: str,
    largura: int,
    imagem: bytes,
    *,
    endpoint: str | None = None,
    camada: str | None = None,
    base: Path | None = None,
) -> Path | None:
    """Salva de forma atômica; falha do acervo nunca derruba a geração."""
    if not _eh_imagem(imagem):
        return None
    imagem_path, metadados_path = _caminhos(
        fonte,
        bbox,
        crs,
        largura,
        endpoint=endpoint,
        camada=camada,
        base=base or diretorio_acervo(),
    )
    metadados = {
        "versao": 1,
        "fonte": fonte,
        "bbox": list(bbox),
        "crs": crs,
        "largura": largura,
        "camada": camada,
        "salvo_em": time.time(),
        "bytes": len(imagem),
        "sha256": hashlib.sha256(imagem).hexdigest(),
    }
    temporarios: tuple[Path, Path] | None = None
    try:
        imagem_path.parent.mkdir(parents=True, exist_ok=True)
        token = f"{os.getpid()}.{threading.get_ident()}.tmp"
        imagem_tmp = imagem_path.with_suffix(f".img.{token}")
        metadados_tmp = metadados_path.with_suffix(f".json.{token}")
        temporarios = (imagem_tmp, metadados_tmp)
        imagem_tmp.write_bytes(imagem)
        metadados_tmp.write_text(
            json.dumps(metadados, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(imagem_tmp, imagem_path)
        os.replace(metadados_tmp, metadados_path)
    except OSError:
        return None
    finally:
        for temporario in temporarios or ():
            try:
                temporario.unlink(missing_ok=True)
            except OSError:
                pass
    return imagem_path
