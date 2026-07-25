from __future__ import annotations

from typing import Any

# Classe declarada no recibo × campo calculado em quantitativos.calcular
PARES_CONFERENCIA: list[tuple[str, str, str]] = [
    ("Área total da propriedade", "area_total", "area_total_ha"),
    ("Área de vegetação nativa", "vegetacao_nativa_ha", "avn_ha"),
    ("Área consolidada", "consolidada_ha", "ac_ha"),
    ("Área Derivada de Desmate Após 2008", "auas_ha", "auas_ha"),
]


def _declarado_no_recibo(recibo: dict[str, Any] | None, chave: str) -> float | None:
    if not recibo:
        return None
    if chave == "area_total":
        valor = recibo.get("area_total_ha")
        return float(valor) if isinstance(valor, (int, float)) else None
    areas = recibo.get("areas") or {}
    valor = areas.get(chave)
    if isinstance(valor, (int, float)):
        return float(valor)
    # AUAS normalmente não vem no recibo
    if chave == "auas_ha":
        return None
    return None


def montar_conferencia(
    quantitativos: dict[str, Any],
    recibo: dict[str, Any] | None = None,
    *,
    tolerancia_ha: float = 0.01,
) -> dict[str, Any]:
    """Compara áreas do recibo CAR com as calculadas no workspace (F1-08)."""
    areas_calc = quantitativos.get("areas") or {}
    casas = int(quantitativos.get("casas_decimais") or 4)
    linhas: list[dict[str, Any]] = []
    avisos: list[str] = []

    for rotulo, chave_recibo, chave_calc in PARES_CONFERENCIA:
        declarado = _declarado_no_recibo(recibo, chave_recibo)
        calculado = areas_calc.get(chave_calc)
        if isinstance(calculado, (int, float)):
            calculado = round(float(calculado), casas)
        else:
            calculado = None

        if declarado is None and calculado is None:
            continue

        diff = None
        pct = None
        ok = True
        if declarado is not None and calculado is not None:
            diff = round(calculado - declarado, casas)
            if declarado != 0:
                pct = round(diff / declarado, 6)
            ok = abs(diff) <= tolerancia_ha
            if not ok:
                avisos.append(
                    f"{rotulo}: diferença {diff:.{casas}f} ha "
                    f"(recibo {declarado:.{casas}f} × calculado {calculado:.{casas}f})."
                )
        elif declarado is None and calculado is not None:
            avisos.append(f"{rotulo}: sem valor no recibo; calculado {calculado:.{casas}f} ha.")
        elif declarado is not None and calculado is None:
            avisos.append(f"{rotulo}: recibo {declarado:.{casas}f} ha; sem cálculo no workspace.")
            ok = False

        linhas.append(
            {
                "classe": rotulo,
                "declarado_ha": declarado,
                "calculado_ha": calculado,
                "diferenca_ha": diff,
                "diferenca_pct": pct,
                "ok": ok,
            }
        )

    return {
        "linhas": linhas,
        "tolerancia_ha": tolerancia_ha,
        "tem_recibo": recibo is not None,
        "ok": all(l["ok"] for l in linhas) if linhas else True,
        "avisos": avisos,
    }
