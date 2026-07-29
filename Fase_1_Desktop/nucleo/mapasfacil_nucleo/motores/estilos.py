"""Cores e estilos oficiais do perfil Harmonia (planos/01 §Cores e estilos).

Valores **vinculantes**. Desde 2026-07-29 eles não são mais transcritos de olho:
saíram da amostragem dos próprios PDFs-modelo do acervo — para cada item de
legenda, a cor dominante do quadradinho à esquerda do rótulo, a 300 dpi
(`ferramentas/amostrar_cores_modelo.py`). Onde a amostra discordou do palpite
anterior, ganhou a amostra: `ac` era `#FF00FF` e é `#C500FF`; `auas` era
`#FF8000` e é `#E59800`; terra indígena era `#8B2500` e é `#A73800`.

Duas regras estruturais continuam codificadas aqui:

1. camadas do imóvel são **vazadas** (sem preenchimento), porque o que importa
   embaixo delas é a imagem de satélite;
2. camadas temáticas de contexto (TI, embargo, tipologia) são **sólidas**,
   porque nelas o fundo não importa.

O perímetro é **amarelo**. Vermelho é o perfil Trevisol, descartado em
2026-07-25 — não "corrija" de volta.
"""

from __future__ import annotations

from typing import Any

# `hatch` segue a notação do matplotlib: "xx" = cruzada, "///" = diagonal.
ESTILOS: dict[str, dict[str, Any]] = {
    # — camadas do imóvel (vazadas) —
    "perimetro_imovel": {
        "cor_linha": "#FFFF00",
        "cor_preenchimento": None,
        "hachura": None,
        "largura": 2.2,
        "legenda": "poligono_vazado",
    },
    "avn": {
        "cor_linha": "#4CE500",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "ac": {
        "cor_linha": "#C500FF",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "auas": {
        "cor_linha": "#E59800",
        "cor_preenchimento": None,
        "hachura": "///",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "app": {
        "cor_linha": "#00B0F0",
        "cor_preenchimento": None,
        "hachura": "\\\\\\",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "appd": {
        "cor_linha": "#E59800",
        "cor_preenchimento": None,
        "hachura": "\\\\\\",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "arl": {
        "cor_linha": "#00B050",
        "cor_preenchimento": None,
        "hachura": "..",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    # — limites administrativos —
    # `cor_preenchimento_legenda` existe para os limites administrativos: no
    # mapa eles são só a linha divisória (preencher esconde a imagem de
    # satélite), mas o item de legenda do modelo é um quadrado preenchido.
    "limite_municipal": {
        "cor_linha": "#FF5400",
        "cor_preenchimento": None,
        "cor_preenchimento_legenda": "#FFD27F",
        "hachura": None,
        "largura": 1.0,
        "legenda": "poligono_solido",
    },
    "limite_estadual": {
        "cor_linha": "#6D6D6D",
        "cor_preenchimento": None,
        "cor_preenchimento_legenda": "#E2F2C4",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    # — temáticas (sólidas) —
    "terra_indigena": {
        "cor_linha": "#7A2900",
        "cor_preenchimento": "#A73800",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "zona_amortecimento": {
        "cor_linha": "#E500A9",
        "cor_preenchimento": None,
        "hachura": None,
        "largura": 1.2,
        "legenda": "poligono_vazado",
    },
    "embargo_ibama": {
        "cor_linha": "#333333",
        "cor_preenchimento": "#CCCCCC",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "embargo_sema": {
        "cor_linha": "#E3191B",
        "cor_preenchimento": None,
        "hachura": "///",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "embargo_siga": {
        "cor_linha": "#E3191B",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "unidade_conservacao": {
        "cor_linha": "#00FF00",
        "cor_preenchimento": None,
        "hachura": None,
        "largura": 1.4,
        "legenda": "poligono_vazado",
    },
    "uc_amortecimento": {
        "cor_linha": "#9A9A9A",
        "cor_preenchimento": "#E5E5E5",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "tipologia_floresta": {
        "cor_linha": "#6FA84F",
        "cor_preenchimento": "#89CC66",
        "hachura": None,
        "largura": 0.6,
        "legenda": "poligono_solido",
    },
    "tipologia_cerrado": {
        "cor_linha": "#AEA53F",
        "cor_preenchimento": "#D0C64B",
        "hachura": None,
        "largura": 0.6,
        "legenda": "poligono_solido",
    },
    "alerta_mapbiomas": {
        "cor_linha": "#333333",
        "cor_preenchimento": "#CCCCCC",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "alerta_prodes": {
        "cor_linha": "#D6D64A",
        "cor_preenchimento": "#FFFF72",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "dla": {
        "cor_linha": "#000000",
        "cor_preenchimento": "#E5E5E5",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "desmate_licenciado": {
        "cor_linha": "#4CE500",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "area_precisa_dla": {
        "cor_linha": "#FF0000",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "tcr_pontos": {
        "cor_linha": "#FF0000",
        "cor_preenchimento": "#FF0000",
        "hachura": None,
        "largura": 1.4,
        "legenda": "poligono_solido",
    },
}

PADRAO: dict[str, Any] = {
    "cor_linha": "#666666",
    "cor_preenchimento": None,
    "hachura": None,
    "largura": 1.0,
    "legenda": "poligono_vazado",
}


def obter(estilo_id: str | None) -> dict[str, Any]:
    """Estilo pelo id do MapSpec; desconhecido cai no cinza neutro."""
    if not estilo_id:
        return dict(PADRAO)
    return dict(ESTILOS.get(str(estilo_id), PADRAO))
