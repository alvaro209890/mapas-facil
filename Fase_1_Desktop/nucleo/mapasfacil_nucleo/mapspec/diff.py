from __future__ import annotations

from typing import Any


def _caminho(partes: list[str | int]) -> str:
    return "/".join(str(p) for p in partes)


def _diff_valores(
    antes: Any,
    depois: Any,
    caminho: list[str | int],
    operacoes: list[dict[str, Any]],
) -> None:
    if antes == depois:
        return
    if isinstance(antes, dict) and isinstance(depois, dict):
        _diff_dict(antes, depois, caminho, operacoes)
        return
    if isinstance(antes, list) and isinstance(depois, list):
        _diff_lista(antes, depois, caminho, operacoes)
        return
    operacoes.append(
        {
            "op": "alterar",
            "caminho": _caminho(caminho),
            "antes": antes,
            "depois": depois,
        }
    )


def _diff_dict(
    antes: dict[str, Any],
    depois: dict[str, Any],
    caminho: list[str | int],
    operacoes: list[dict[str, Any]],
) -> None:
    chaves_antes = set(antes)
    chaves_depois = set(depois)
    for chave in sorted(chaves_antes - chaves_depois):
        operacoes.append(
            {"op": "remover", "caminho": _caminho(caminho + [chave]), "antes": antes[chave]}
        )
    for chave in sorted(chaves_depois - chaves_antes):
        operacoes.append(
            {"op": "adicionar", "caminho": _caminho(caminho + [chave]), "depois": depois[chave]}
        )
    for chave in sorted(chaves_antes & chaves_depois):
        _diff_valores(antes[chave], depois[chave], caminho + [chave], operacoes)


def _indice_camadas(itens: list[Any]) -> dict[str, dict[str, Any]]:
    indice: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(itens):
        if not isinstance(item, dict):
            continue
        chave = item.get("id") or item.get("fonte") or str(idx)
        indice[str(chave)] = item
    return indice


def _diff_lista(
    antes: list[Any],
    depois: list[Any],
    caminho: list[str | int],
    operacoes: list[dict[str, Any]],
) -> None:
    # Camadas do MapSpec: diff por id estável.
    if caminho == ["camadas"] or (len(caminho) >= 1 and caminho[-1] == "camadas"):
        idx_antes = _indice_camadas(antes)
        idx_depois = _indice_camadas(depois)
        for chave in sorted(set(idx_antes) - set(idx_depois)):
            operacoes.append(
                {
                    "op": "remover",
                    "caminho": _caminho(caminho + [chave]),
                    "antes": idx_antes[chave],
                }
            )
        for chave in sorted(set(idx_depois) - set(idx_antes)):
            operacoes.append(
                {
                    "op": "adicionar",
                    "caminho": _caminho(caminho + [chave]),
                    "depois": idx_depois[chave],
                }
            )
        for chave in sorted(set(idx_antes) & set(idx_depois)):
            _diff_valores(idx_antes[chave], idx_depois[chave], caminho + [chave], operacoes)
        return

    if len(antes) != len(depois):
        operacoes.append(
            {
                "op": "alterar",
                "caminho": _caminho(caminho),
                "antes": antes,
                "depois": depois,
                "nota": "lista com tamanho diferente",
            }
        )
        return

    for idx, (item_antes, item_depois) in enumerate(zip(antes, depois, strict=True)):
        _diff_valores(item_antes, item_depois, caminho + [idx], operacoes)


def diff(antes: dict[str, Any], depois: dict[str, Any]) -> dict[str, Any]:
    """Lista operações entre duas versões do MapSpec (anel 1)."""
    operacoes: list[dict[str, Any]] = []
    _diff_dict(antes, depois, [], operacoes)
    return {
        "operacoes": operacoes,
        "total": len(operacoes),
        "id_antes": antes.get("id"),
        "id_depois": depois.get("id"),
        "versao_antes": antes.get("versao"),
        "versao_depois": depois.get("versao"),
    }
