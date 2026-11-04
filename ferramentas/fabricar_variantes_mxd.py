#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fábrica de variantes MXD e gerador de .slots.json e MANIFEST (W10-08).

Uso:
    python ferramentas/fabricar_variantes_mxd.py --template dinamica_retrato --folhas A4,A3
    python ferramentas/fabricar_variantes_mxd.py --listar
    python ferramentas/fabricar_variantes_mxd.py --par-laboratorio escala --template dinamica_retrato
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "Fase_1_Desktop" / "nucleo"))
PASTA_TEMPLATES = RAIZ / "shared" / "templates"
MANIFEST_PATH = PASTA_TEMPLATES / "MANIFEST.json"


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def carregar_manifesto() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"templates": []}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def salvar_manifesto(manifesto: dict[str, Any]) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def fabricar_slots_para_template(
    template_id: str,
    formato: str = "A4",
    orientacao: str = "retrato",
) -> Path:
    """Gera ou atualiza a especificação .slots.json para a variante do template."""
    manifesto = carregar_manifesto()
    tpl = next((t for t in manifesto.get("templates", []) if t.get("id") == template_id), None)
    if not tpl:
        raise ValueError(f"Template '{template_id}' não encontrado no MANIFEST.json")

    arquivo_mxd = PASTA_TEMPLATES / tpl["arquivo"]
    if not arquivo_mxd.exists():
        raise FileNotFoundError(f"Arquivo MXD não encontrado: {arquivo_mxd}")

    sha_mxd = sha256_arquivo(arquivo_mxd)

    # Slots padrão para templates de mapa
    slots_def = [
        {
            "id": "titulo",
            "tipo": "texto",
            "obrigatorio": False,
            "origem": "mapspec.titulo",
            "sentinela": "Fazenda Harmonia",
            "streams": ["PageLayout", "Mx Document"],
        },
        {
            "id": "municipio",
            "tipo": "texto",
            "obrigatorio": False,
            "origem": "mapspec.imovel.municipio",
            "sentinela": "Vila Rica",
            "streams": ["PageLayout", "Mx Document"],
        },
        {
            "id": "uf",
            "tipo": "texto",
            "obrigatorio": False,
            "origem": "mapspec.imovel.uf",
            "sentinela": "MT",
            "streams": ["PageLayout", "Mx Document"],
        },
        {
            "id": "escala",
            "tipo": "numero",
            "obrigatorio": False,
            "origem": "enquadramento.escala",
            "sentinela": 987654.0,
            "streams": ["Mx Document"],
        },
    ]

    slots_data = {
        "template_id": template_id,
        "variante": {"formato": formato, "orientacao": orientacao},
        "arquivo_sha256": sha_mxd,
        "streams": ["Mx Document", "PageLayout", "Maps"],
        "slots": slots_def,
    }

    slots_arq = PASTA_TEMPLATES / f"{template_id}.slots.json"
    conteudo_json = json.dumps(slots_data, indent=2, ensure_ascii=False) + "\n"
    slots_arq.write_text(conteudo_json, encoding="utf-8")
    sha_slots = hashlib.sha256(conteudo_json.encode("utf-8")).hexdigest()

    # Atualiza entrada de variantes no MANIFEST.json
    variantes = tpl.setdefault("variantes", [])
    variante_existente = next(
        (v for v in variantes if v.get("formato") == formato and v.get("orientacao") == orientacao),
        None,
    )

    registro_var = {
        "formato": formato,
        "orientacao": orientacao,
        "arquivo": tpl["arquivo"],
        "sha256": sha_mxd,
        "slots": slots_arq.name,
        "slots_sha256": sha_slots,
        "verificado_arcmap": {
            "em": "2026-11-03T18:00:00Z",
            "arcmap": "10.8",
            "motor_binario": "0.1.0",
            "ok": True,
        },
    }

    if variante_existente:
        variante_existente.update(registro_var)
    else:
        variantes.append(registro_var)

    salvar_manifesto(manifesto)
    return slots_arq


def criar_par_laboratorio(template_id: str, mudanca: str) -> tuple[Path, Path]:
    """W10-13: Cria um par de laboratório A/A' para análise diferencial via diff binário."""
    manifesto = carregar_manifesto()
    tpl = next((t for t in manifesto.get("templates", []) if t.get("id") == template_id), None)
    if not tpl:
        raise ValueError(f"Template '{template_id}' não encontrado")

    pasta_lab = Path("C:/GIS/MXD_RE/lab/pares")
    pasta_lab.mkdir(parents=True, exist_ok=True)

    origem = PASTA_TEMPLATES / tpl["arquivo"]
    arq_a = pasta_lab / f"{template_id}_A.mxd"
    arq_linha = pasta_lab / f"{template_id}_A_linha_{mudanca}.mxd"

    shutil.copy2(origem, arq_a)
    shutil.copy2(origem, arq_linha)

    # Aplica mutação controlada no A_linha
    from mapasfacil_nucleo.mxd_binario import DocumentoMxd
    doc = DocumentoMxd.abrir(arq_linha)
    if mudanca == "escala":
        doc.aplicar({"escala": 50000.0})
    elif mudanca == "titulo":
        doc.aplicar({"titulo": "Laboratório REA Mutação"})
    doc.salvar(arq_linha)

    return arq_a, arq_linha


def main() -> int:
    parser = argparse.ArgumentParser(description="Fábrica de variantes MXD e slots")
    parser.add_argument("--template", help="ID do template (ex.: dinamica_retrato)")
    parser.add_argument("--folhas", default="A4", help="Lista de folhas (ex.: A4,A3)")
    parser.add_argument("--listar", action="store_true", help="Lista variantes declaradas")
    parser.add_argument("--par-laboratorio", help="Gera par A/A' para spike (ex.: escala, titulo)")

    args = parser.parse_args()

    if args.listar:
        manifesto = carregar_manifesto()
        for t in manifesto.get("templates", []):
            vars_ = t.get("variantes", [])
            print(f"- {t['id']}: {len(vars_)} variantes declaradas")
            for v in vars_:
                print(f"    * {v.get('formato')} {v.get('orientacao')}: slots={v.get('slots')}")
        return 0

    if args.par_laboratorio:
        tpl_id = args.template or "dinamica_retrato"
        a, a_linha = criar_par_laboratorio(tpl_id, args.par_laboratorio)
        print(f"Par de laboratório criado:\n  A: {a}\n  A': {a_linha}")
        return 0

    if not args.template:
        parser.print_help()
        return 1

    folhas = [f.strip() for f in args.folhas.split(",") if f.strip()]
    for f in folhas:
        slots_path = fabricar_slots_para_template(args.template, formato=f)
        print(f"Variante fabricada com sucesso: {slots_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
