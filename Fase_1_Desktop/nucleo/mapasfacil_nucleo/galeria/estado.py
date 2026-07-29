# Status derivado MANIFEST × índice do workspace (F1-15 D4). Nunca grava no JSON.

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.motores import manifesto

PAPEIS = frozenset({"ATP", "AVN", "AC", "AUAS", "APP", "ARL", "SIGEF", "RESERVA_LEGAL"})
SAIDAS_NATIVAS = frozenset({"pdf", "png", "xlsx"})
SAIDAS_VALIDAS = SAIDAS_NATIVAS | {"mxd"}


def fontes_do_indice(indice: dict[str, Any] | None) -> set[str]:
    if not indice:
        return set()
    fontes = set(indice.get("fontes_locais") or [])
    for shp in indice.get("shapefiles") or []:
        papel = shp.get("papel")
        if isinstance(papel, str) and papel:
            fontes.add(papel)
        id_local = shp.get("id_local")
        if isinstance(id_local, str) and id_local:
            fontes.add(id_local)
    return fontes


def papéis_presentes(indice: dict[str, Any] | None) -> set[str]:
    fontes = fontes_do_indice(indice)
    return {p for p in PAPEIS if p in fontes}


def _template_info(template_id: str) -> dict[str, Any]:
    tpl = next(
        (t for t in manifesto.carregar().get("templates", []) if t.get("id") == template_id),
        None,
    )
    if tpl is None:
        return {"status": "a_preparar", "sha256_ok": False, "sha256": None}
    try:
        return manifesto.verificar_template(template_id)
    except Exception:
        return {
            "status": tpl.get("status"),
            "sha256_ok": False,
            "sha256": tpl.get("sha256"),
        }


def avaliar_status(
    modelo: dict[str, Any],
    indice: dict[str, Any] | None,
    saidas_pedidas: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    """Devolve `{status, motivo?, requisitos_faltando}`.

    O arquivo ``.mxd`` é a única saída que depende do binário preparado no
    ArcMap. PDF/PNG/XLSX usam o motor nativo e só precisam dos metadados do
    template no MANIFEST. Esse detalhe é a diferença entre um card útil numa
    máquina sem ArcMap e um falso ``indisponivel`` (GOAL §6.1).
    """
    saidas = set(saidas_pedidas or modelo.get("saidas_padrao") or ())
    saidas &= SAIDAS_VALIDAS
    exige_template_mxd = "mxd" in saidas

    info = _template_info(modelo["template"])
    status_tpl = info.get("status")
    sha_ok = bool(info.get("sha256_ok"))
    sha_esperado = info.get("sha256")

    if exige_template_mxd and (status_tpl == "a_preparar" or sha_esperado is None):
        return {
            "status": "indisponivel",
            "motivo": "template ainda não preparado no ArcMap",
            "requisitos_faltando": [],
        }

    if exige_template_mxd and not sha_ok:
        return {
            "status": "indisponivel",
            "motivo": "sha256 do template diverge do MANIFEST",
            "requisitos_faltando": [],
        }

    presentes = papéis_presentes(indice)
    faltando_obrig: list[str] = []
    faltando_opc: list[str] = []
    for req in modelo.get("requisitos_camadas") or []:
        papel = req["papel"]
        if papel in presentes:
            continue
        if req.get("obrigatorio"):
            faltando_obrig.append(papel)
        else:
            faltando_opc.append(papel)

    if faltando_obrig:
        return {
            "status": "faltam_dados",
            "motivo": f"falta {', '.join(p + '.shp' for p in faltando_obrig)} na pasta",
            "requisitos_faltando": faltando_obrig,
        }

    if (exige_template_mxd and status_tpl == "parcial") or faltando_opc:
        partes: list[str] = []
        if exige_template_mxd and status_tpl == "parcial":
            partes.append("template parcial (offsets pendentes)")
        if faltando_opc:
            partes.append("opcional ausente: " + ", ".join(faltando_opc))
        return {
            "status": "parcial",
            "motivo": "; ".join(partes),
            "requisitos_faltando": faltando_opc,
        }

    if not exige_template_mxd or status_tpl == "pronto":
        return {"status": "pronto", "motivo": None, "requisitos_faltando": []}

    return {
        "status": "parcial",
        "motivo": f"template com status {status_tpl}",
        "requisitos_faltando": [],
    }
