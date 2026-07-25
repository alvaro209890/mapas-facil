from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.workspace.shapefile import inspecionar

# Colunas padrão da tabela Harmonia (F1-08) quando o MapSpec não declara tabela.
COLUNAS_PADRAO = [
    "Propriedade",
    "Área total da propriedade (ha)",
    "Área de vegetação nativa (ha)",
    "Área consolidada (ha)",
    "Área Derivada de Desmate Após 2008 (ha)",
]

ESTILO_PARA_CAMPO = {
    "perimetro_imovel": "area_total_ha",
    "avn": "avn_ha",
    "ac": "ac_ha",
    "auas": "auas_ha",
}


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> str | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    return fontes_idx.get(chave) or fontes_idx.get(chave.upper())


def _arredondar(valor: float | None, casas: int) -> float | None:
    if valor is None:
        return None
    return round(float(valor), casas)


def calcular(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> dict[str, Any]:
    """Calcula quantitativos a partir das camadas locais do workspace (anel 1)."""
    imovel = mapspec.get("imovel") or {}
    nome_imovel = imovel.get("nome") or imovel.get("rotulo") or "Imóvel"

    tabela_cfg = mapspec.get("tabela") or {}
    casas = int(tabela_cfg.get("casas_decimais") or 4)
    colunas = list(tabela_cfg.get("colunas") or COLUNAS_PADRAO)

    areas: dict[str, float | None] = {
        "area_total_ha": None,
        "avn_ha": None,
        "ac_ha": None,
        "auas_ha": None,
    }
    detalhe: list[dict[str, Any]] = []
    avisos: list[str] = []

    for camada in mapspec.get("camadas", []):
        fonte = camada.get("fonte", "")
        rel = _resolver_fonte_local(fonte, fontes_idx)
        if not rel:
            continue

        estilo = camada.get("estilo")
        campo = ESTILO_PARA_CAMPO.get(estilo or "")
        if not campo:
            continue

        try:
            meta = inspecionar(guard.resolver(rel))
        except ErroNucleo as exc:
            avisos.append(f"{fonte}: {exc.mensagem}")
            continue

        if meta.vazia or meta.area_ha is None:
            avisos.append(f"{fonte}: sem área calculável.")
            continue

        valor = _arredondar(meta.area_ha, casas)
        areas[campo] = valor
        detalhe.append(
            {
                "fonte": fonte,
                "estilo": estilo,
                "area_ha": valor,
                "geometrias_corrigidas": meta.geometrias_corrigidas,
                "feicoes": meta.feicoes,
                "arquivo": rel,
                "crs": meta.crs.get("epsg") or meta.crs.get("wkt_resumo"),
            }
        )

    linha = [
        nome_imovel,
        areas["area_total_ha"],
        areas["avn_ha"],
        areas["ac_ha"],
        areas["auas_ha"],
    ]

    # Ajusta largura da linha ao número de colunas declarado.
    if len(colunas) > len(linha):
        linha.extend([None] * (len(colunas) - len(linha)))
    elif len(colunas) < len(linha):
        linha = linha[: len(colunas)]

    soma_classes = sum(
        v for k, v in areas.items() if k != "area_total_ha" and isinstance(v, (int, float))
    )
    soma_arredondada = _arredondar(soma_classes, casas)
    total_geral = soma_arredondada if tabela_cfg.get("total_geral", True) else None

    fechamento_ok = True
    if areas["area_total_ha"] is not None and soma_arredondada is not None:
        diff = abs(areas["area_total_ha"] - soma_arredondada)
        if diff > 10 ** (-casas):
            fechamento_ok = False
            avisos.append(
                f"Soma das classes ({soma_arredondada} ha) difere da ATP "
                f"({areas['area_total_ha']} ha) em {diff:.{casas}f} ha."
            )

    conferencia_mapspec = None
    linhas_declaradas = tabela_cfg.get("linhas") or []
    if linhas_declaradas:
        declarada = linhas_declaradas[0]
        if isinstance(declarada, list) and len(declarada) >= 2:
            conferencia_mapspec = {
                "linha_declarada": declarada,
                "linha_calculada": linha,
                "bate": declarada == linha,
            }
            if not conferencia_mapspec["bate"]:
                avisos.append("Linha da tabela do MapSpec difere dos valores calculados no workspace.")

    return {
        "colunas": colunas,
        "linhas": [linha],
        "total_geral": total_geral,
        "casas_decimais": casas,
        "areas": areas,
        "detalhe": detalhe,
        "fechamento_ok": fechamento_ok,
        "conferencia_mapspec": conferencia_mapspec,
        "avisos": avisos,
    }
