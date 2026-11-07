"""Carregador e resolvedor de LayoutSpecs para templates e modelos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.motores.perfil_pagina import (
    PAISAGEM,
    RETRATO,
    por_template,
)
from .conversor import de_perfil, perfil_do_layout
from .modelo import LayoutSpec
from .validar import validar


def _pasta_layouts() -> Path:
    return raiz_repositorio() / "shared" / "layouts"


def carregar(origem: dict[str, Any] | str | Path) -> LayoutSpec:
    """Carrega um LayoutSpec de dict, caminho de arquivo JSON ou ID em shared/layouts/."""
    if isinstance(origem, LayoutSpec):
        return carregar(origem.para_dict())

    if isinstance(origem, dict):
        resultado = validar(origem)
        if not resultado["valido"]:
            raise ValueError("LayoutSpec inválido: " + "; ".join(resultado["erros"]))
        return LayoutSpec.de_dict(origem)

    caminho = Path(origem)
    if not caminho.is_file():
        # Tenta buscar por ID na pasta shared/layouts/
        candidato = _pasta_layouts() / f"{origem}.json"
        if candidato.is_file():
            caminho = candidato
        else:
            candidato_sem_ext = _pasta_layouts() / str(origem)
            if candidato_sem_ext.is_file():
                caminho = candidato_sem_ext
            else:
                raise FileNotFoundError(f"LayoutSpec não encontrado: {origem}")

    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return carregar(dados)


def listar_layouts() -> list[dict[str, Any]]:
    """Lista metadados dos LayoutSpecs disponíveis em shared/layouts/."""
    pasta = _pasta_layouts()
    layouts: list[dict[str, Any]] = []
    if pasta.is_dir():
        for arq in sorted(pasta.glob("*.json")):
            try:
                dados = json.loads(arq.read_text(encoding="utf-8"))
                layouts.append({
                    "id": dados.get("id", arq.stem),
                    "nome": dados.get("nome", arq.stem),
                    "orientacao": dados.get("orientacao", "retrato"),
                    "perfil": dados.get("perfil", "harmonia"),
                    "arquivo": arq.name,
                })
            except Exception:
                continue
    return layouts


_MAPA_TEMPLATES_CONHECIDOS: dict[str, str] = {
    "dinamica_retrato": "harmonia_dinamica_retrato",
    "dinamica_quantitativos_retrato": "harmonia_dinamica_retrato",
    "dinamica_2008_spot_quadro": "serie_dinamica_2008_spot",
    "tipologia_paisagem": "harmonia_tematico_paisagem",
    "terras_indigenas_paisagem": "serie_terras_indigenas",
    "uc_paisagem": "serie_unidades_conservacao",
}


def _obter_mapa_manifesto() -> dict[str, str]:
    try:
        from mapasfacil_nucleo.motores.manifesto import carregar as carregar_manifesto

        manifesto = carregar_manifesto()
        return {
            str(t["id"]): str(t["layout_ref"])
            for t in manifesto.get("templates", [])
            if t.get("id") and t.get("layout_ref")
        }
    except Exception:
        return {}


def obter_layout(
    id_ou_template: str,
    folha: dict[str, Any] | None = None,
    _visitados: set[str] | None = None,
) -> LayoutSpec:
    """Resolve o LayoutSpec apropriado para um template, modelo ou preset.

    1. Tenta carregar arquivo JSON direto em shared/layouts/;
    2. Se for template da série (serie_*), usa perfil medido do modelo;
    3. Honra layout_ref do MANIFEST para os 26 templates (com detecção de ciclos);
    4. Mapeia templates conhecidos da galeria;
    5. Fallback por orientação (apenas quando documentado; não silencioso para layout explícito).
    """
    ident = str(id_ou_template).strip()

    if _visitados is None:
        _visitados = set()
    if ident in _visitados:
        raise ValueError(
            f"Ciclo detectado na resolução de layout: {ident} já foi visitado ({sorted(_visitados)})"
        )
    _visitados.add(ident)

    spec: LayoutSpec | None = None

    # 1. Preset em shared/layouts/
    arquivo_preset = _pasta_layouts() / f"{ident}.json"
    if arquivo_preset.is_file():
        spec = carregar(arquivo_preset)

    # 2. Template da série com anatomia medida
    if spec is None:
        medido = por_template(ident)
        if medido is not None:
            spec = de_perfil(medido, id=ident, nome=f"Layout {ident}")

    # 3. Referência no MANIFEST.json (26 templates)
    if spec is None:
        mapa_manifesto = _obter_mapa_manifesto()
        if ident in mapa_manifesto:
            alvo = mapa_manifesto[ident]
            if alvo != ident:
                return obter_layout(alvo, folha=folha, _visitados=_visitados)

    # 4. Mapeamento de alias/template conhecido
    if spec is None and ident in _MAPA_TEMPLATES_CONHECIDOS:
        alvo = _MAPA_TEMPLATES_CONHECIDOS[ident]
        if alvo != ident:
            return obter_layout(alvo, folha=folha, _visitados=_visitados)

    # 5. Fallback por orientação documentada
    if spec is None:
        ident_lower = ident.lower()
        if "paisagem" in ident_lower:
            spec = de_perfil(PAISAGEM, id=ident, nome=f"Layout {ident}")
        elif "retrato" in ident_lower or ident_lower in ("", "default", "padrao"):
            spec = de_perfil(RETRATO, id=ident, nome=f"Layout {ident}")
        else:
            raise ValueError(f"Layout ou template desconhecido: '{ident}'")

    if folha and str(folha.get("formato", "A4")).upper() != "A4":
        perfil = perfil_do_layout(spec, folha=folha)
        return de_perfil(perfil, id=spec.id, nome=spec.nome, descricao=spec.descricao)
    return spec
