#!/usr/bin/env python3
"""Gera a série Análise de área com MXD + PDF e consolida a evidência W5."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUCLEO = ROOT / "Fase_1_Desktop" / "nucleo"
sys.path.insert(0, str(NUCLEO))

from mapasfacil_nucleo.analise.executar import executar  # noqa: E402
from mapasfacil_nucleo.fsguard import WorkspaceGuard  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke da série MXD/ArcMap")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--atp-rel", default="SHP/analise/ATP.shp")
    parser.add_argument(
        "--apenas",
        help="IDs de receitas separados por vírgula; sem valor roda os 20.",
    )
    parser.add_argument(
        "--preparar-camadas",
        action="store_true",
        help="Busca/materializa fontes oficiais; sem a flag reusa SHP/analise.",
    )
    parser.add_argument(
        "--modelos",
        type=Path,
        help="Pasta dos PDFs-modelo para medir anatomia.",
    )
    parser.add_argument(
        "--saida-relatorio",
        type=Path,
        default=ROOT / "output" / "w5_serie_mxd.json",
    )
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error(f"workspace inexistente: {workspace}")
    apenas = (
        tuple(item.strip() for item in args.apenas.split(",") if item.strip())
        if args.apenas
        else None
    )
    guard = WorkspaceGuard(workspace)

    def progresso(fase: str, item: str, indice: int, total: int) -> None:
        sufixo = f" [{indice}/{total}]" if total else ""
        print(f"{fase}: {item}{sufixo}", flush=True)

    resultado = executar(
        guard=guard,
        atp_rel=args.atp_rel,
        apenas=apenas,
        modelos=args.modelos.expanduser().resolve() if args.modelos else None,
        ao_progresso=progresso,
        preparar_camadas=args.preparar_camadas,
        saidas=("mxd", "pdf"),
    )

    mapas = resultado.get("mapas") or []
    hard = {
        "total": len(mapas),
        "gerados": sum(1 for mapa in mapas if mapa.get("ok")),
        "mxd": sum(1 for mapa in mapas if mapa.get("mxd")),
        "pdf": sum(1 for mapa in mapas if mapa.get("pdf")),
        "pdf_arcmap": sum(1 for mapa in mapas if mapa.get("pdf_arcmap")),
        "falhas": [
            {"mapa": mapa.get("mapa"), "erro": mapa.get("erro")}
            for mapa in mapas
            if not mapa.get("ok")
        ],
    }
    evidencia = {
        "ok": (
            hard["total"] > 0
            and hard["gerados"] == hard["total"]
            and hard["mxd"] == hard["total"]
            and hard["pdf_arcmap"] == hard["total"]
        ),
        "workspace": str(workspace),
        "saidas": ["mxd", "pdf"],
        "resumo_w5": hard,
        "resultado": resultado,
    }
    args.saida_relatorio.parent.mkdir(parents=True, exist_ok=True)
    args.saida_relatorio.write_text(
        json.dumps(evidencia, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(hard, ensure_ascii=False, indent=2))
    print(f"Relatório: {args.saida_relatorio}")
    return 0 if evidencia["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
