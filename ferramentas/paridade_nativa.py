#!/usr/bin/env python3
"""Paridade do motor **nativo** contra os PDFs-modelo do acervo — roda no Linux.

Complementa `smoke_m9_harmonia.py`, que mede o PDF do ArcMap (T1, Windows). Aqui
o alvo é o PDF que o motor nativo entrega em máquina sem ArcGIS nenhum: gera o
mapa, rasteriza modelo e gerado, mede o diff e escreve o material que um humano
(ou um agente) olha para decidir o próximo ajuste — máscara de diferença e
contact-sheet lado a lado.

Uso:

    Fase_1_Desktop/nucleo/.venv/bin/python ferramentas/paridade_nativa.py \
      --pasta /caminho/do/projeto \
      --modelo dinamica_2026_retrato \
      --baseline Referencias_IMAP/Mapas/01/Dinamica_2026.pdf \
      --imovel "Fazenda Harmonia" --municipio "Vila Rica" --uf MT \
      --car MT-5108451-XXXX --titulo "Ano: 2026"

Sem `--baseline` o modelo sai do `baseline_pdf` do MANIFEST do template.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NUCLEO = ROOT / "Fase_1_Desktop" / "nucleo"
sys.path.insert(0, str(NUCLEO))

from mapasfacil_nucleo.galeria.montar import montar_mapspec  # noqa: E402
from mapasfacil_nucleo.motores.gerar import gerar_mapa  # noqa: E402
from mapasfacil_nucleo.validacao import anatomia  # noqa: E402
from mapasfacil_nucleo.validacao.comparar_pdf import (  # noqa: E402
    medir_diferenca_raster,
    rasterizar_pdf,
    resolver_baseline_template,
)
from mapasfacil_nucleo.workspace import servico as ws  # noqa: E402

DPI_PADRAO = 110
"""Rasterização de trabalho: rápida e legível numa tela. A medição oficial de
paridade (0,3%) é a de `comparar_pdf`, a 150 dpi."""


def _fontes_preferidas(pasta: Path, fontes: dict[str, str]) -> None:
    """Aponta os papéis canônicos para a pasta do SIMCAR, quando ela existe."""
    for sub in ("Arquivo Processado (1)", "Arquivo Processado", "SHP"):
        base = pasta / sub
        if not base.is_dir():
            continue
        preferidos = {
            "ATP": "ATP.shp",
            "AVN": "AVN.shp",
            "AUAS": "AUAS.shp",
            "AC": "AREA_CONSOLIDADA.shp",
            "AREA_CONSOLIDADA": "AREA_CONSOLIDADA.shp",
            "APP": "APP.shp",
            "ARL": "ARL.shp",
        }
        for chave, arquivo in preferidos.items():
            if (base / arquivo).is_file():
                fontes[chave] = f"{sub}/{arquivo}"
        break


def _mascara_diferenca(ref: np.ndarray, ger: np.ndarray, limiar: int) -> np.ndarray:
    h = min(ref.shape[0], ger.shape[0])
    w = min(ref.shape[1], ger.shape[1])
    a = ref[:h, :w].astype(np.int16)
    b = ger[:h, :w].astype(np.int16)
    return np.any(np.abs(a - b) > limiar, axis=2)


def _contact_sheet(ref: np.ndarray, ger: np.ndarray, mascara: np.ndarray) -> Image.Image:
    """Modelo · gerado · máscara, na mesma altura, com faixa branca entre eles."""
    altura = max(ref.shape[0], ger.shape[0], mascara.shape[0])
    paineis = [
        Image.fromarray(ref),
        Image.fromarray(ger),
        Image.fromarray((mascara * 255).astype(np.uint8)).convert("RGB"),
    ]
    espaco = 12
    largura = sum(p.width for p in paineis) + espaco * (len(paineis) - 1)
    folha = Image.new("RGB", (largura, altura), "white")
    x = 0
    for painel in paineis:
        folha.paste(painel, (x, 0))
        x += painel.width + espaco
    return folha


def _montar(
    args: argparse.Namespace,
    pasta: Path,
) -> tuple[dict[str, Any], dict[str, str], Any]:
    ws.abrir(str(pasta))
    fontes = ws.fontes_idx()
    _fontes_preferidas(pasta, fontes)

    sobrescritas: dict[str, Any] = {"saidas": ["pdf", "png"]}
    if args.titulo:
        sobrescritas["titulo"] = args.titulo
    if args.escala:
        sobrescritas["escala"] = args.escala

    montado = montar_mapspec(args.modelo, sobrescritas=sobrescritas)
    mapspec = montado["mapspec"]

    imovel = mapspec["imovel"]
    if args.imovel:
        imovel["nome"] = args.imovel
    if args.car:
        imovel["car"] = args.car
    if imovel.get("car") is None:
        # O schema exige string; sem recibo não há CAR — declara a ausência.
        imovel["car"] = "SEM-RECIBO"
    if args.municipio:
        imovel["municipio"]["nome"] = args.municipio
    if args.uf:
        imovel["municipio"]["uf"] = args.uf[:2]

    # O rótulo do imóvel acompanha o nome informado.
    for camada in mapspec.get("camadas") or []:
        if camada.get("id") == "perimetro" and args.imovel:
            camada["rotulo_texto"] = args.imovel
            camada["nome_no_mxd"] = args.imovel
            camada["legenda"] = args.imovel

    if args.basemap:
        mapspec["basemap"] = {"tipo": args.basemap, "fallback": []}

    mapspec["saidas"] = ["pdf", "png"]
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
    return mapspec, fontes, estado


def main() -> int:
    parser = argparse.ArgumentParser(description="Paridade do motor nativo vs PDF-modelo")
    parser.add_argument("--pasta", required=True, help="Pasta do projeto (workspace)")
    parser.add_argument("--modelo", default="dinamica_2026_retrato")
    parser.add_argument("--nome-base", default="Paridade_Nativa")
    parser.add_argument("--baseline", default=None, help="PDF-modelo; default = MANIFEST")
    parser.add_argument("--imovel", default=None)
    parser.add_argument("--municipio", default=None)
    parser.add_argument("--uf", default=None)
    parser.add_argument("--car", default=None)
    parser.add_argument("--titulo", default=None)
    parser.add_argument("--escala", default=None, type=int)
    parser.add_argument(
        "--basemap",
        default=None,
        help="id/apelido do basemap (ex.: wms_sema, mosaico_spot_2008). Vazio = sem fundo.",
    )
    parser.add_argument("--dpi", type=int, default=DPI_PADRAO)
    parser.add_argument("--limiar-rgb", type=int, default=16)
    parser.add_argument(
        "--saida",
        default=None,
        help="Pasta dos artefatos de comparação (default: output/paridade/<nome_base>)",
    )
    args = parser.parse_args()

    pasta = Path(args.pasta).expanduser().resolve()
    if not pasta.is_dir():
        print(f"ERRO: pasta inexistente: {pasta}", file=sys.stderr)
        return 2

    mapspec, fontes, estado = _montar(args, pasta)

    resultado = gerar_mapa(mapspec, estado.guard, fontes, recibo=estado.recibo)

    pdf_rel = resultado.get("pdf")
    if not pdf_rel:
        print("ERRO: geração não devolveu PDF", file=sys.stderr)
        return 3
    pdf_gerado = pasta / pdf_rel

    if args.baseline:
        baseline = Path(args.baseline)
        if not baseline.is_absolute():
            baseline = ROOT / baseline
    else:
        baseline = resolver_baseline_template(str(mapspec.get("template")))
    if baseline is None or not baseline.is_file():
        print(f"ERRO: PDF-modelo ausente: {baseline}", file=sys.stderr)
        return 4

    ref = rasterizar_pdf(baseline, dpi=args.dpi)
    ger = rasterizar_pdf(pdf_gerado, dpi=args.dpi)
    medidas = medir_diferenca_raster(ref, ger, limiar_rgb=args.limiar_rgb)
    mascara = _mascara_diferenca(ref, ger, args.limiar_rgb)

    saida = Path(args.saida) if args.saida else ROOT / "output" / "paridade" / args.nome_base
    saida.mkdir(parents=True, exist_ok=True)
    Image.fromarray(ref).save(saida / "modelo.png")
    Image.fromarray(ger).save(saida / "gerado.png")
    Image.fromarray((mascara * 255).astype(np.uint8)).save(saida / "diff_mascara.png")
    _contact_sheet(ref, ger, mascara).save(saida / "lado_a_lado.png")

    # Anatomia: a comparação que faz sentido quando o dado é outro — o diff
    # raster contra um imóvel diferente mede a paisagem, não o layout.
    anat_modelo = anatomia.medir(baseline)
    anat_gerado = anatomia.medir(pdf_gerado)
    comparacao_anatomia = anatomia.comparar(anat_modelo, anat_gerado)

    relatorio = {
        "quando": datetime.now(timezone.utc).isoformat(),
        "motor": "nativo",
        "anatomia": {
            "modelo": anat_modelo,
            "gerado": anat_gerado,
            "comparacao": comparacao_anatomia,
        },
        "pasta": str(pasta),
        "modelo": args.modelo,
        "template": mapspec.get("template"),
        "baseline_pdf": str(baseline),
        "pdf_gerado": str(pdf_gerado),
        "dpi": args.dpi,
        "limiar_rgb": args.limiar_rgb,
        "medidas": medidas,
        "validacao": resultado.get("validacao_dados"),
        "artefatos": {
            "modelo": str(saida / "modelo.png"),
            "gerado": str(saida / "gerado.png"),
            "mascara": str(saida / "diff_mascara.png"),
            "lado_a_lado": str(saida / "lado_a_lado.png"),
        },
    }
    (saida / "relatorio.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    print(json.dumps({k: relatorio[k] for k in ("medidas", "artefatos")}, ensure_ascii=False, indent=2))
    print("== anatomia vs modelo ==")
    for item in comparacao_anatomia["itens"]:
        print(f"  [{'ok' if item['ok'] else '--'}] {item['id']} {item['mensagem']}")
    print(f"== diff {medidas['diferenca_pct']}% · artefatos em {saida} ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
