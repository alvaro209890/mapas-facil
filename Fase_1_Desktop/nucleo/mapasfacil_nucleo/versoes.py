"""Persistência do MapSpec por versão de saída (W5-15) — `versoes.py`.

⚠️ Não confundir com `agente/mapspec_store.py`, que guarda o MapSpec **vivo da conversa**
(`chats/mapspecs/<conversation_id>.json`). Este aqui guarda o MapSpec de cada versão
**gerada**, ao lado dos artefatos.

Por que existe: a web precisa responder "volta pra versão 1" sem depender de a
conversa ainda estar na memória de um worker. Cada versão gerada deixa o seu
`mapspec.json` ao lado dos artefatos, e é dele que `listar_versoes` e
`restaurar_versao` leem.

Onde fica:

| modo | pasta |
|---|---|
| servidor | `Mapas/vNNN/mapspec.json` (uma pasta por versão, criada por `config.pasta_saida_versao`) |
| desktop | `Mapas/_versoes/vNNN/mapspec.json` — no desktop a saída é `Mapas/` com sufixo `_vN` no nome do arquivo, então a versão precisa de um lugar próprio |

Regra dura: **restaurar nunca apaga artefato**. A restauração cria uma versão
nova com o conteúdo antigo; `Mapas/v001/` continua lá, intacta.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import config

ARQUIVO = "mapspec.json"
PASTA_DESKTOP = "_versoes"


def raiz_versoes() -> Path:
    """Raiz onde as versões moram, conforme o modo de execução."""
    base = Path(config.pasta_saida())
    if config.modo_servidor():
        return base
    return base / PASTA_DESKTOP


def pasta_da_versao(versao: int) -> Path:
    """`Mapas/vNNN` no servidor, `Mapas/_versoes/vNNN` no desktop."""
    numero = max(int(versao), 1)
    if config.modo_servidor():
        return Path(config.pasta_saida_versao(numero))
    return raiz_versoes() / f"v{numero:03d}"


def _agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def salvar(mapspec: dict[str, Any], *, versao: int | None = None) -> Path:
    """Grava o MapSpec na pasta da versão e devolve o caminho do arquivo."""
    numero = int(versao or mapspec.get("versao") or 1)
    pasta = pasta_da_versao(numero)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / ARQUIVO
    payload = {
        "versao": numero,
        "salvo_em": _agora(),
        "mapspec": mapspec,
    }
    temporario = destino.with_suffix(".json.tmp")
    temporario.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)
    return destino


def salvar_na_pasta(mapspec: dict[str, Any], pasta: str | Path) -> Path:
    """Grava ao lado dos artefatos de uma geração já feita.

    `tool_gerar_mapa` recebe o caminho do PDF; a versão é a pasta dele. Assim o
    MapSpec fica gravado mesmo que o worker morra logo depois de gerar.
    """
    destino_dir = Path(pasta)
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / ARQUIVO
    payload = {
        "versao": int(mapspec.get("versao") or 1),
        "salvo_em": _agora(),
        "mapspec": mapspec,
    }
    temporario = destino.with_suffix(".json.tmp")
    temporario.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporario.replace(destino)
    return destino


def _ler(pasta: Path) -> dict[str, Any] | None:
    arquivo = pasta / ARQUIVO
    if not arquivo.is_file():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    mapspec = dados.get("mapspec")
    if not isinstance(mapspec, dict):
        return None
    return dados


def carregar(versao: int) -> dict[str, Any] | None:
    """MapSpec de uma versão, ou `None` se ela nunca foi gerada."""
    dados = _ler(pasta_da_versao(versao))
    return dados["mapspec"] if dados else None


def _artefatos(pasta: Path) -> list[str]:
    if not pasta.is_dir():
        return []
    extensoes = {".pdf", ".mxd", ".xlsx", ".png", ".geojson", ".zip"}
    return sorted(
        p.suffix.lstrip(".")
        for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in extensoes
    )


def _valor_escala(bruto: Any) -> Any:
    """`escala` é string no MapSpec v3, mas versões antigas guardavam objeto."""
    if isinstance(bruto, dict):
        return bruto.get("valor")
    return bruto


def listar() -> list[dict[str, Any]]:
    """Versões existentes, da mais nova para a mais antiga — sem geometria."""
    raiz = raiz_versoes()
    if not raiz.is_dir():
        return []
    versoes: list[dict[str, Any]] = []
    for pasta in raiz.iterdir():
        if not pasta.is_dir() or not pasta.name.startswith("v"):
            continue
        try:
            numero = int(pasta.name[1:])
        except ValueError:
            continue
        dados = _ler(pasta)
        if dados is None:
            continue
        mapspec = dados["mapspec"]
        folha = mapspec.get("folha") or {}
        versoes.append(
            {
                "versao": int(mapspec.get("versao") or numero),
                "salvo_em": dados.get("salvo_em"),
                "titulo": mapspec.get("titulo"),
                "folha": folha.get("formato"),
                "orientacao": folha.get("orientacao"),
                "escala": _valor_escala(mapspec.get("escala")),
                "parent_id": mapspec.get("parent_id"),
                "artefatos": _artefatos(pasta),
            }
        )
    versoes.sort(key=lambda v: v["versao"], reverse=True)
    return versoes


def ultima() -> int | None:
    """Número da maior versão registrada."""
    versoes = listar()
    return versoes[0]["versao"] if versoes else None
