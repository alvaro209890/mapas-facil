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


MAXIMO_SEM_DADO = 0.12
"""Acima disto a cena está furada demais para servir de fundo (12% da imagem)."""


def _fracao_sem_dado(imagem: bytes) -> float | None:
    """Fração de pixels brancos/transparentes — o buraco de mosaico da SEMA.

    `None` quando não dá para inspecionar (formato exótico): nesse caso a imagem
    passa, porque recusar por não conseguir medir seria pior que aceitar.
    """
    try:
        import io

        import numpy as np
        from PIL import Image

        with Image.open(io.BytesIO(imagem)) as img:
            if img.mode in ("RGBA", "LA"):
                alfa = np.array(img.getchannel("A"))
                if alfa.size and (alfa == 0).mean() > 0.01:
                    return float((alfa == 0).mean())
            arr = np.array(img.convert("RGB"))
        if arr.size == 0:
            return None
        branco = np.all(arr >= 250, axis=2)
        return float(branco.mean())
    except Exception:  # noqa: BLE001 — medir é opcional; imagem segue válida
        return None


PREFERENCIA_SENSOR = ("sentinel2", "landsat8", "landsat7", "landsat5", "resourcesat", "spot")
"""Desempate quando um ano tem mais de um mosaico: o mais nítido primeiro."""


def _resolver_id(tipo: str | None) -> str | None:
    if not tipo:
        return None
    chave = str(tipo).strip().lower()
    return APELIDOS.get(chave, chave)


def _tabela_mosaicos() -> dict[str, Any]:
    """`shared/catalog/mosaicos_sema.json` — 43 mosaicos WMS por sensor e ano."""
    import json

    from mapasfacil_nucleo.config import raiz_repositorio

    caminho = raiz_repositorio() / "shared" / "catalog" / "mosaicos_sema.json"
    if not caminho.is_file():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _nome_amigavel(mosaico: dict[str, Any]) -> str:
    sensor = str(mosaico.get("sensor") or "").strip()
    ano = mosaico.get("ano")
    return f"{sensor} {ano}".strip() if sensor else str(mosaico.get("layer") or "")


def camada_de_mosaico(chave: str) -> dict[str, Any] | None:
    """Resolve um mosaico da SEMA como se fosse camada de catálogo.

    Existe porque os 43 mosaicos por ano viviam num JSON que ninguém lia: o
    basemap só sabia o SPOT 2008 (lacuna C2 do GOAL). Aceita o id do mosaico
    (`landsat5_2000`) ou só o ano (`2013`) — e, no ano, escolhe o sensor mais
    nítido disponível.
    """
    tabela = _tabela_mosaicos()
    mosaicos = tabela.get("mosaicos") or []
    if not mosaicos:
        return None

    texto = str(chave).strip().lower()
    escolhido: dict[str, Any] | None = None
    exato = True

    direto = next((m for m in mosaicos if str(m.get("id", "")).lower() == texto), None)
    if direto is not None:
        escolhido = direto
    elif texto.isdigit() and len(texto) == 4:
        ano = int(texto)
        do_ano = [m for m in mosaicos if m.get("ano") == ano]
        if not do_ano:
            # Ano sem mosaico (2025/2026 não existem na SEMA): usa o mais
            # recente **anterior** e declara que não é o ano pedido.
            anteriores = [m for m in mosaicos if isinstance(m.get("ano"), int) and m["ano"] < ano]
            if not anteriores:
                return None
            melhor_ano = max(m["ano"] for m in anteriores)
            do_ano = [m for m in anteriores if m["ano"] == melhor_ano]
            exato = False
        do_ano.sort(
            key=lambda m: next(
                (i for i, s in enumerate(PREFERENCIA_SENSOR) if str(m.get("id", "")).startswith(s)),
                len(PREFERENCIA_SENSOR),
            )
        )
        escolhido = do_ano[0]

    if escolhido is None:
        return None

    return {
        "id": f"mosaico:{escolhido['id']}",
        "nome": _nome_amigavel(escolhido),
        "tipo": "wms_raster",
        "endpoint": tabela.get("endpoint_wms", "https://geo.sema.mt.gov.br/geoserver/ows"),
        "layer": escolhido["layer"],
        "auth": tabela.get("auth", "sema_authkey"),
        "ano": escolhido.get("ano"),
        "sensor": escolhido.get("sensor"),
        "ano_exato": exato,
    }


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
        camada: dict[str, Any] | None = None
        try:
            camada = catalogo_mod.buscar(camada_id)
        except ErroNucleo as exc:
            # Não está no catálogo: pode ser mosaico da SEMA por id ou por ano.
            camada = camada_de_mosaico(camada_id)
            if camada is None:
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

        vazio = _fracao_sem_dado(bytes(imagem))
        if vazio is not None and vazio > MAXIMO_SEM_DADO:
            # Mosaico com buraco: a SEMA devolve 200 com a cena furada, e o mapa
            # sai com retângulos brancos no meio da imagem. Vale mais a imagem
            # de outro ano inteira do que a do ano certo pela metade.
            tentativas.append(
                {
                    "camada": camada_id,
                    "erro": "NU-113",
                    "detalhe": f"{vazio:.0%} da cena sem dado",
                }
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
            "ano": camada.get("ano"),
            "sensor": camada.get("sensor"),
            # False quando o ano pedido não existe na SEMA e caiu no anterior —
            # quem escreve o metadado precisa saber para não mentir a data.
            "ano_exato": camada.get("ano_exato", True),
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
