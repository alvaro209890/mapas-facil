"""Imagem de fundo do motor nativo — WMS do catálogo, com degradação declarada.

O basemap é a maior alavanca visual do mapa: é ele que ocupa o quadro inteiro
atrás das camadas. Também é a parte que pode faltar (sem rede, sem chave, tile
fora de cobertura), e por isso o contrato aqui é: **nunca derrubar a geração**.
Quando não dá, devolve o motivo e o mapa sai com fundo branco, com o
`validacao.json` declarando a degradação — o oposto de um mapa que finge ter
imagem.

Gotcha herdado de `planos/03-wfs-e-servicos-geo.md`: HTTP 200 mente. GeoServer
devolve XML de erro com status 200. Só os magic bytes decidem, e quem valida é
o cliente WMS.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.camadas import catalogo as catalogo_mod
from mapasfacil_nucleo.camadas import wms
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard

PASTA_RECURSOS = "recursos"
LARGURA_PADRAO = 1600
"""Pixels do GetMap. A 300 dpi o quadro do retrato tem ~2320 px de largura;
1600 é o meio-termo entre nitidez e peso do PDF."""

# Nomes amigáveis que o MapSpec (e o agente) podem usar sem conhecer o catálogo.
APELIDOS: dict[str, str] = {
    "wms_sema": "mosaico_spot_2008",
    "sema": "mosaico_spot_2008",
    "spot": "mosaico_spot_2008",
    "spot_2008": "mosaico_spot_2008",
    "prodes": "prodes_inpe",
}


def _resolver_id(tipo: str | None) -> str | None:
    if not tipo:
        return None
    chave = str(tipo).strip().lower()
    return APELIDOS.get(chave, chave)


def _candidatos(basemap: dict[str, Any] | None) -> list[str]:
    """Ordem de tentativa: o tipo pedido e depois os `fallback` declarados."""
    if not isinstance(basemap, dict):
        return []
    ordem: list[str] = []
    principal = _resolver_id(basemap.get("tipo"))
    if principal:
        ordem.append(principal)
    for alternativa in basemap.get("fallback") or []:
        resolvido = _resolver_id(alternativa)
        if resolvido and resolvido not in ordem:
            ordem.append(resolvido)
    return ordem


def _authkey(camada: dict[str, Any]) -> str | None:
    nome_segredo = camada.get("auth")
    if not nome_segredo:
        return None
    return cofre.usar(nome_segredo)


def buscar(
    basemap: dict[str, Any] | None,
    *,
    guard: WorkspaceGuard,
    extent: tuple[float, float, float, float],
    epsg: int,
    pasta_saida: str = "Mapas",
    largura: int = LARGURA_PADRAO,
) -> dict[str, Any]:
    """Baixa a imagem de fundo do extent. Sempre devolve envelope, nunca levanta.

    `{"ok": True, "caminho": Path, "camada": id, "fonte": nome}` no sucesso;
    `{"ok": False, "motivo": str, "tentativas": [...]}` quando degrada.
    """
    candidatos = _candidatos(basemap)
    if not candidatos:
        return {"ok": False, "motivo": "MapSpec sem basemap declarado", "tentativas": []}

    tentativas: list[dict[str, Any]] = []
    for camada_id in candidatos:
        try:
            camada = catalogo_mod.buscar(camada_id)
        except ErroNucleo as exc:
            tentativas.append({"camada": camada_id, "erro": exc.codigo, "detalhe": str(exc)})
            continue

        if camada.get("tipo") != "wms_raster":
            tentativas.append(
                {
                    "camada": camada_id,
                    "erro": "NU-210",
                    "detalhe": f"tipo {camada.get('tipo')} não serve de basemap",
                }
            )
            continue

        try:
            chave = _authkey(camada)
            if camada.get("auth") and not chave:
                tentativas.append(
                    {
                        "camada": camada_id,
                        "erro": "NU-102",
                        "detalhe": f"chave '{camada['auth']}' ausente no cofre",
                    }
                )
                continue

            resposta = wms.buscar_mapa(
                camada["endpoint"],
                camada["layer"],
                extent,
                f"EPSG:{epsg}",
                authkey=chave,
                largura=largura,
            )
        except Exception as exc:  # noqa: BLE001 — rede/serviço não derruba o mapa
            codigo = getattr(exc, "codigo", type(exc).__name__)
            tentativas.append({"camada": camada_id, "erro": codigo, "detalhe": str(exc)})
            continue

        imagem = resposta.get("imagem") or resposta.get("corpo")
        if not isinstance(imagem, (bytes, bytearray)) or not wms.eh_imagem(bytes(imagem)):
            tentativas.append(
                {"camada": camada_id, "erro": "NU-110", "detalhe": "resposta não é imagem"}
            )
            continue

        assinatura = hashlib.sha256(
            f"{camada_id}|{epsg}|{extent}|{largura}".encode()
        ).hexdigest()[:12]
        extensao = wms.extensao_da_imagem(bytes(imagem))
        destino = guard.resolver(
            f"{pasta_saida}/{PASTA_RECURSOS}/basemap_{camada_id}_{assinatura}{extensao}",
            escrita=True,
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(bytes(imagem))

        return {
            "ok": True,
            "caminho": destino,
            "camada": camada_id,
            "fonte": camada.get("nome") or camada_id,
            "endpoint": camada.get("endpoint"),
            "bytes": len(imagem),
            "tentativas": tentativas,
        }

    return {
        "ok": False,
        "motivo": "nenhum basemap do MapSpec pôde ser carregado",
        "tentativas": tentativas,
    }


def caminho_cacheado(
    guard: WorkspaceGuard,
    *,
    pasta_saida: str = "Mapas",
) -> list[Path]:
    """PNGs de basemap já materializados no projeto (para reuso offline)."""
    try:
        pasta = guard.resolver(f"{pasta_saida}/{PASTA_RECURSOS}")
    except ErroNucleo:
        return []
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.name.startswith("basemap_"))
