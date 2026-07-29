"""Cores e estilos oficiais do perfil Harmonia (planos/01 §Cores e estilos).

Valores **vinculantes**, extraídos das legendas dos PDFs-modelo e dos `.mxd`.
Duas regras estruturais estão codificadas aqui:

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
        "cor_linha": "#00E64D",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "ac": {
        "cor_linha": "#FF00FF",
        "cor_preenchimento": None,
        "hachura": "xx",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "auas": {
        "cor_linha": "#FF8000",
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
    "arl": {
        "cor_linha": "#00B050",
        "cor_preenchimento": None,
        "hachura": "..",
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    # — limites administrativos —
    "limite_municipal": {
        "cor_linha": "#E8722C",
        "cor_preenchimento": None,
        "hachura": None,
        "largura": 1.0,
        "legenda": "poligono_vazado",
    },
    "limite_estadual": {
        "cor_linha": "#C5E0B4",
        "cor_preenchimento": "#C5E0B4",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    # — temáticas (sólidas) —
    "terra_indigena": {
        "cor_linha": "#5E1900",
        "cor_preenchimento": "#8B2500",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "zona_amortecimento": {
        "cor_linha": "#FF00FF",
        "cor_preenchimento": None,
        "hachura": None,
        "largura": 1.2,
        "legenda": "poligono_vazado",
    },
    "embargo_ibama": {
        "cor_linha": "#595959",
        "cor_preenchimento": "#BFBFBF",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "unidade_conservacao": {
        "cor_linha": "#38761D",
        "cor_preenchimento": "#93C47D",
        "hachura": None,
        "largura": 0.8,
        "legenda": "poligono_solido",
    },
    "tipologia_floresta": {
        "cor_linha": "#00A854",
        "cor_preenchimento": "#00D26A",
        "hachura": None,
        "largura": 0.6,
        "legenda": "poligono_solido",
    },
    "tipologia_cerrado": {
        "cor_linha": "#A89A3A",
        "cor_preenchimento": "#C9B94A",
        "hachura": None,
        "largura": 0.6,
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
