# A13 — catálogo de camadas externas (WFS/WMS/REST).
#
# Lê `shared/catalog/camadas.json` (fonte da verdade, 41 camadas — F1-03 §Estrutura,
# planos/03-wfs-e-servicos-geo.md). Não inventa camada: quem não está no arquivo não
# existe para o núcleo (AP-04). Segredo nunca mora aqui — `auth` é só o *nome* da
# chave no cofre (`cofre.usar`).

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mapasfacil_nucleo.config import caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo

# Tipos de serviço com cliente implementado nesta versão (A13). Os demais
# (arcgis_rest, wfs_gml, wms_raster) ainda não têm cliente — `camada.resolver`
# degrada com NU-140 em vez de fingir que funciona.
TIPOS_SUPORTADOS: frozenset[str] = frozenset({"wms_wfs"})

CAMPOS_OBRIGATORIOS = ("id", "nome", "tema", "tipo", "endpoint", "layer")


@lru_cache(maxsize=1)
def _bruto() -> dict[str, Any]:
    caminho = caminho_shared("catalog", "camadas.json")
    try:
        with caminho.open(encoding="utf-8") as fh:
            dados = json.load(fh)
    except FileNotFoundError as exc:
        raise ErroNucleo("NU-130", f"Catálogo de camadas ausente: {caminho}") from exc
    except json.JSONDecodeError as exc:
        raise ErroNucleo("NU-130", f"Catálogo de camadas com JSON inválido: {exc}") from exc
    if not isinstance(dados, dict) or not isinstance(dados.get("camadas"), list):
        raise ErroNucleo("NU-130", "Catálogo de camadas em formato inesperado.")
    for item in dados["camadas"]:
        faltando = [c for c in CAMPOS_OBRIGATORIOS if not item.get(c)]
        if faltando:
            raise ErroNucleo(
                "NU-130",
                f"Camada do catálogo sem campo obrigatório: {faltando}",
                {"id": item.get("id")},
            )
    return dados


def limpar_cache() -> None:
    """Só para testes — o catálogo real não muda em runtime."""
    _bruto.cache_clear()


def camadas() -> tuple[dict[str, Any], ...]:
    return tuple(_bruto()["camadas"])


def ids() -> frozenset[str]:
    return frozenset(str(c["id"]) for c in camadas())


def temas() -> tuple[str, ...]:
    return tuple(sorted({str(c["tema"]) for c in camadas() if c.get("tema")}))


def normalizar_id(fonte: str) -> str:
    """`catalogo.<id>` (formato usado no `MapSpec.camadas[].fonte`) ou `<id>` puro."""
    texto = str(fonte or "").strip()
    if texto.startswith("catalogo."):
        return texto.split(".", 1)[1]
    return texto


def buscar(fonte: str) -> dict[str, Any]:
    """Camada do catálogo por `id` (aceita prefixo `catalogo.`). NU-130 se não existir."""
    alvo = normalizar_id(fonte)
    if not alvo:
        raise ErroNucleo("NU-001", "Parâmetro 'fonte' é obrigatório.")
    for item in camadas():
        if item["id"] == alvo:
            return item
    raise ErroNucleo(
        "NU-130",
        f"Camada fora do catálogo: {alvo}",
        {"fonte": alvo},
    )


def listar(tema: str | None = None) -> dict[str, Any]:
    if tema is not None and not isinstance(tema, str):
        raise ErroNucleo("NU-001", "Parâmetro 'tema' inválido.")
    itens = [c for c in camadas() if not tema or c.get("tema") == tema]
    resumo = [
        {
            "id": c["id"],
            "nome": c.get("nome"),
            "tema": c.get("tema"),
            "tipo": c.get("tipo"),
            "auth": c.get("auth"),
            "suportada": c.get("tipo") in TIPOS_SUPORTADOS,
            "descricao": c.get("descricao"),
        }
        for c in itens
    ]
    return {
        "camadas": resumo,
        "total": len(resumo),
        "temas": list(temas()),
        "tema_filtrado": tema,
    }
