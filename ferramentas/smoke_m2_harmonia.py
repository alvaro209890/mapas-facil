#!/usr/bin/env python3
"""Smoke M2 — gera Dinâmica 2026 na pasta Harmonia real (T1 se ArcMap, senão T2).

NÃO toca em Fase_1_Desktop/app/. Só núcleo + pasta do projeto do cliente.

Uso:
  Fase_1_Desktop\\nucleo\\.venv\\Scripts\\python.exe ferramentas\\smoke_m2_harmonia.py ^
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

from mapasfacil_nucleo.doctor import rodar as doctor_rodar  # noqa: E402
from mapasfacil_nucleo.galeria.montar import montar_mapspec  # noqa: E402
from mapasfacil_nucleo.motores.gerar import gerar_mapa  # noqa: E402
from mapasfacil_nucleo.workspace import servico as ws  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke M2 Harmonia")
    parser.add_argument("--pasta", required=True, help="Pasta do projeto Harmonia")
    parser.add_argument(
        "--modelo",
        default="dinamica_2026_retrato",
        help="ID do modelo na galeria (default: dinamica_2026_retrato)",
    )
    parser.add_argument(
        "--nome-base",
        default="Dinamica_2026_MapasFacil_M2",
        help="Nome base dos artefatos em Mapas/",
    )
    parser.add_argument(
        "--forcar-t2",
        action="store_true",
        help="Esconde ArcMap (MAPASFACIL_ARCPY_PYTHON=inexistente) para provar T2",
    )
    args = parser.parse_args()

    pasta = Path(args.pasta).expanduser().resolve()
    if not pasta.is_dir():
        print(f"ERRO: pasta inexistente: {pasta}", file=sys.stderr)
        return 2

    if args.forcar_t2:
        # Esconde todos os Pythons do ArcMap (env sozinho não basta — há fallbacks).
        import mapasfacil_nucleo.motores.arcpy_ponte as arcpy_ponte

        arcpy_ponte._python_arcmap_padrao = lambda: None  # type: ignore[method-assign]
        print("== forcar-t2: ArcMap oculto ==")

    print(f"== doctor ==")
    doc = doctor_rodar(sondar_arcpy=True)
    print(
        json.dumps(
            {
                "arcmap": doc.get("arcmap"),
                "pronto_para_mxd": doc.get("pronto_para_mxd"),
                "motor_preferido": doc.get("motor_preferido"),
                "templates": [
                    {
                        "id": t.get("id"),
                        "status": t.get("status"),
                        "sha256_ok": t.get("sha256_ok"),
                        "patch_ok": t.get("patch_ok"),
                    }
                    for t in (doc.get("templates") or [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    print(f"== workspace.abrir {pasta} ==")
    aberto = ws.abrir(str(pasta))
    idx = aberto["workspace"]
    fontes = ws.fontes_idx()

    # Preferir CAR processado da Harmonia (evita AVN/AUAS de outra fazenda no mesmo SHP/).
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

    print(
        f"shapefiles={len(idx.get('shapefiles') or [])} "
        f"ATP={fontes.get('ATP')} AVN={fontes.get('AVN')} AUAS={fontes.get('AUAS')} "
        f"AC={fontes.get('AC')}"
    )

    print(f"== galeria.montar {args.modelo} ==")
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
        # Só Mapas/, MXD/, SHP/, _extraido/ aceitam escrita (fsguard).
        "materializar_camadas_em": "SHP",
    }
    # Locais + catálogo (municípios); evita fontes remotas que quebram offline.
    mapspec["camadas"] = [
        c
        for c in (mapspec.get("camadas") or [])
        if isinstance(c.get("fonte"), str)
        and (c["fonte"].startswith("local.") or c["fonte"].startswith("catalogo."))
    ]

    estado = ws.estado_atual()
    assert estado is not None
    guard = estado.guard

    print("== mapa.gerar ==")
    resultado = gerar_mapa(mapspec, guard, fontes, recibo=estado.recibo)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))

    relatorio = {
        "quando": datetime.now(timezone.utc).isoformat(),
        "pasta": str(pasta),
        "modelo": args.modelo,
        "forcar_t2": bool(args.forcar_t2),
        "doctor": {
            "arcmap_encontrado": bool((doc.get("arcmap") or {}).get("encontrado")),
            "arcmap_versao": (doc.get("arcmap") or {}).get("versao"),
            "motor_preferido": doc.get("motor_preferido"),
        },
        "resultado": resultado,
    }
    out = pasta / "Mapas" / f"{args.nome_base}_relatorio_m2.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"== relatorio {out} ==")

    ws.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
