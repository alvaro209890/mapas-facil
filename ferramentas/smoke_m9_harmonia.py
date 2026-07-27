#!/usr/bin/env python3
"""Smoke M9 — conformidade Harmonia: gera mapa, mede checks e diff raster.

Complementa o smoke M2 com `comparar_baseline` e relatório JSON consolidado.

Uso:
  Fase_1_Desktop\\nucleo\\.venv\\Scripts\\python.exe ferramentas\\smoke_m9_harmonia.py ^
    --pasta \"C:\\Users\\...\\Analise_de_área-Julio Barbosa_ 4_Harmonia\"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUCLEO = ROOT / "Fase_1_Desktop" / "nucleo"
sys.path.insert(0, str(NUCLEO))

from mapasfacil_nucleo.config import raiz_repositorio  # noqa: E402
from mapasfacil_nucleo.doctor import rodar as doctor_rodar  # noqa: E402
from mapasfacil_nucleo.galeria.montar import montar_mapspec  # noqa: E402
from mapasfacil_nucleo.motores.gerar import gerar_mapa  # noqa: E402
from mapasfacil_nucleo.motores.manifesto import obter_template  # noqa: E402
from mapasfacil_nucleo.validacao.comparar_pdf import comparar_pdf, resolver_baseline_template  # noqa: E402
from mapasfacil_nucleo.workspace import servico as ws  # noqa: E402


def _preferir_fontes_harmonia(pasta: Path, fontes: dict[str, str]) -> None:
    preferidos = {
        "ATP": "Arquivo Processado (1)/ATP.shp",
        "AVN": "Arquivo Processado (1)/AVN.shp",
        "AUAS": "Arquivo Processado (1)/AUAS.shp",
        "AC": "Arquivo Processado (1)/AREA_CONSOLIDADA.shp",
        "AREA_CONSOLIDADA": "Arquivo Processado (1)/AREA_CONSOLIDADA.shp",
        "APP": "Arquivo Processado (1)/APP.shp",
        "ARL": "Arquivo Processado (1)/ARL.shp",
    }
    for chave, rel in preferidos.items():
        if (pasta / rel).is_file():
            fontes[chave] = rel.replace("\\", "/")


def _resumo_checks(validacao: dict) -> dict:
    checks = validacao.get("checks") or {}
    hard = checks.get("hard") or []
    soft = checks.get("soft") or []
    return {
        "hard_total": len(hard),
        "hard_ok": sum(1 for c in hard if c.get("ok")),
        "soft_total": len(soft),
        "soft_ok": sum(1 for c in soft if c.get("ok")),
        "hard_falhas": [c["id"] for c in hard if not c.get("ok")],
        "soft_falhas": [c["id"] for c in soft if not c.get("ok")],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke M9 Harmonia")
    parser.add_argument("--pasta", required=True, help="Pasta do projeto Harmonia")
    parser.add_argument("--modelo", default="dinamica_2026_retrato")
    parser.add_argument("--nome-base", default="Dinamica_2026_MapasFacil_M9")
    parser.add_argument(
        "--tolerancia-pct",
        type=float,
        default=0.3,
        help="Tolerância do diff raster (default 0,3%%)",
    )
    args = parser.parse_args()

    pasta = Path(args.pasta).expanduser().resolve()
    if not pasta.is_dir():
        print(f"ERRO: pasta inexistente: {pasta}", file=sys.stderr)
        return 2

    print("== doctor ==")
    doc = doctor_rodar(sondar_arcpy=True)
    arcmap = bool((doc.get("arcmap") or {}).get("encontrado"))
    print(json.dumps({"arcmap": doc.get("arcmap"), "motor_preferido": doc.get("motor_preferido")}, indent=2))

    print(f"== workspace.abrir {pasta} ==")
    ws.abrir(str(pasta))
    fontes = ws.fontes_idx()
    _preferir_fontes_harmonia(pasta, fontes)

    montado = montar_mapspec(
        args.modelo,
        sobrescritas={
            "saidas": ["mxd", "pdf"],
            "titulo": "Dinâmica 2026",
        },
    )
    mapspec = montado["mapspec"]
    mapspec["saidas"] = ["mxd", "pdf"]
    mapspec["saida"] = {
        "pasta": "Mapas",
        "nome_base": args.nome_base,
        "materializar_camadas_em": "SHP",
    }
    mapspec["camadas"] = [
        c
        for c in (mapspec.get("camadas") or [])
        if isinstance(c.get("fonte"), str)
        and (c["fonte"].startswith("local.") or c["fonte"].startswith("catalogo."))
    ]

    estado = ws.estado_atual()
    assert estado is not None
    guard = estado.guard

    print("== mapa.gerar (comparar_baseline=true) ==")
    resultado = gerar_mapa(
        mapspec,
        guard,
        fontes,
        recibo=estado.recibo,
        comparar_baseline=True,
    )

    template_id = mapspec.get("template")
    tpl = obter_template(str(template_id)) if template_id else {}
    baseline = resolver_baseline_template(str(template_id)) if template_id else None

    comp = resultado.get("comparacao_baseline") or {}
    # Comparação explícita nativo vs ArcMap quando ambos existem.
    comparacoes_extra: dict[str, dict] = {}
    pasta_mapas = pasta / "Mapas"
    pdf_nativo = pasta_mapas / f"{args.nome_base}.pdf"
    pdf_arcmap = pasta_mapas / f"{args.nome_base}_arcmap.pdf"
    if baseline and baseline.is_file():
        if pdf_nativo.is_file():
            comparacoes_extra["nativo"] = comparar_pdf(
                pdf_nativo, baseline, tolerancia_pct=args.tolerancia_pct
            )
        if pdf_arcmap.is_file():
            comparacoes_extra["arcmap"] = comparar_pdf(
                pdf_arcmap, baseline, tolerancia_pct=args.tolerancia_pct
            )

    validacao = resultado.get("validacao_dados") or {}
    resumo = _resumo_checks(validacao)
    diff_ok = bool(comp.get("ok"))
    hard_ok = resumo["hard_total"] == 0 or resumo["hard_ok"] == resumo["hard_total"]

    relatorio = {
        "quando": datetime.now(timezone.utc).isoformat(),
        "marco": "M9",
        "repo": str(raiz_repositorio()),
        "pasta": str(pasta),
        "modelo": args.modelo,
        "template": template_id,
        "baseline_pdf": str(baseline) if baseline else None,
        "arcmap_disponivel": arcmap,
        "resultado": {
            "mxd": resultado.get("mxd"),
            "pdf": resultado.get("pdf"),
            "pdf_arcmap": resultado.get("pdf_arcmap"),
            "comparacao_baseline": comp,
            "comparacoes_extra": comparacoes_extra,
            "validacao": validacao,
            "resumo_checks": resumo,
        },
        "criterios_m9": {
            "diff_raster_ok": diff_ok,
            "hard_checks_ok": hard_ok,
            "template_pronto": tpl.get("status") == "pronto",
            "serie_completa": False,
            "nota": (
                "M9 infra entregue; paridade <0,3% e série de 19 mapas dependem de templates "
                "adicionais e ajuste cartográfico."
            ),
        },
        "passou": diff_ok and hard_ok,
    }

    out_repo = raiz_repositorio() / "output" / "m9_smoke_relatorio.json"
    out_repo.parent.mkdir(parents=True, exist_ok=True)
    out_repo.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    out_pasta = pasta / "Mapas" / f"{args.nome_base}_relatorio_m9.json"
    out_pasta.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str))
    print(f"== relatorio {out_repo} ==")
    print(f"== relatorio {out_pasta} ==")

    ws.fechar()
    return 0 if relatorio["passou"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
