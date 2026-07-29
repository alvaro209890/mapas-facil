#!/usr/bin/env python3
"""Valida `planos/GOAL_analise_de_area.md` contra o disco.

A meta "Análise de área" descreve um inventário (20 mapas), um catálogo de camadas e um
conjunto de âncoras do repositório. Este script confere se o documento continua verdadeiro —
é o que impede o plano de envelhecer mentindo (regra zero do `AGENT_BRIEF.md`).

Roda com Python 3 puro. O que depende de `Testes/` (134 MB, gitignored) e de `fitz` é
conferido quando disponível e **pulado** — com aviso — quando não.

    python3 ferramentas/validar_goal_analise.py
    python3 ferramentas/validar_goal_analise.py --json

Saída: linhas `[ok] / [pular] / [FALHA]` e código 0 (nenhuma falha) ou 1.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GOAL = RAIZ / "planos" / "GOAL_analise_de_area.md"
MODELO = RAIZ / "Testes" / "01_analise_04_Julio" / "Modelo"
ATP = RAIZ / "Testes" / "01_analise_04_Julio" / "ATP_Teste" / "Aruana_l_MAT_4242.shp"

# Ordem oficial da série (§3.1 do GOAL) — PDF ↔ MXD.
SERIE = [
    ("Alertas_MAPBIOMAS_2", "Alertas_MAPBIOMAS_2"),
    ("Alertas_PRODES_VF", "Alertas_PRODES_VF"),
    ("DLA", "DLA"),
    ("Unidade_de_Conservação", "Unidade_de_Conservação"),
    ("Tipologia", "Tipologia"),
    ("Terras_Indigenas", "Terras_Indigenas"),
    ("TCR", "TCR"),
    ("PEF", "PEF"),
    ("Embargos_SEMA_SIGA_Poligono", "Embargos_SEMA_SIGA_Poligono"),
    ("Embargos_IBAMA", "Embargos_IBAMA"),
    ("Areas_Cultivaveis_VF", "Areas_Cultivaveis_VF"),
    ("Dinamica_2026_quantitativos", "Dinamica_2026_quantitativos"),
    ("Dinamica_2026", "Dinamica_2026"),
    ("Dinamica_2023", "Dinamica_2023"),
    ("Dinamica_2019", "Dinamica_2019"),
    ("Dinamica_2017", "Dinamica_2017"),
    ("Dinamica_2013", "Dinamica_2013"),
    ("Dinamica_2008_SPOT", "Dinamica_2008_SPOT"),
    ("Dinamica_2008_LANDSAT", "Dinamica_2008_LANDSAT"),
    ("Dinamica_2000", "Dinamica_2000"),
]

# Âncoras da §9 — caminhos que a meta promete que existem.
ANCORAS = [
    "AGENT_BRIEF.md",
    "docs/motor-nativo-harmonia.md",
    "docs/estado-2026-07-27.md",
    "docs/handoff-windows-fase1.md",
    "docs/provisao-deepseek-instalador.md",
    "Fase_1_Desktop/GUIA_WINDOWS.md",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/gerar.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/nativo.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/basemap.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/basemap_planet.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/acervo/rasters.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/blocos.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/estilos.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/grade_dms.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/perfil_pagina.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/patch_mxd.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/motores/arcpy_ponte.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/anatomia.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/analise/progresso.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/saida.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/comparar_pdf.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/validacao/relatorio.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/galeria/estado.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/galeria/montar.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/agente/tools.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/agente/prompt.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/agente/provisao.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/contas/banco.py",
    "Fase_1_Desktop/nucleo/mapasfacil_nucleo/conversas/banco.py",
    "shared/galeria/modelos.json",
    "Fase_1_Desktop/nucleo/tests/golden/anatomia_dinamica_retrato.png",
    "shared/templates/MANIFEST.json",
    "shared/catalog/camadas.json",
    "shared/catalog/mosaicos_sema.json",
    "shared/catalog/sema_layers_live.json",
    "shared/catalog/servicos_geo.json",
    "shared/bases/ibge/lml_municipio_mt.shp",
    "ferramentas/paridade_nativa.py",
    "ferramentas/chaves_mxd.py",
    "ferramentas/normalizar_mxd_arcpy.py",
    "ferramentas/corrigir_template_b1_arcpy.py",
    "ferramentas/preparar_sentinelas_arcpy.py",
    "ferramentas/registrar_template.py",
    "ferramentas/inspecionar_mxd_arcpy.py",
    "ferramentas/conectar_minimapa_ibge_arcpy.py",
    "ferramentas/salvar_mxd_gui.ps1",
    "ferramentas/fechar_dialogs_gis.ps1",
    "ferramentas/fechar_m2_windows.ps1",
    "ferramentas/fechar_m9_windows.ps1",
    "ferramentas/smoke_m2_harmonia.py",
    "ferramentas/smoke_m9_harmonia.py",
]

# Camadas do catálogo que a série usa (§5, "já resolvido").
CAMADAS_USADAS = [
    "car_atp",
    "car_avn",
    "car_auas",
    "car_app",
    "car_appd",
    "car_arl",
    "area_consolidada_simcar",
    "embargos_sema",
    "embargos_siga",
    "embargos_ibama",
    "embargos_ibama_siscom",
    "terras_indigenas_funai",
    "terras_indigenas_sema",
    "unidades_conservacao",
    "alertas_mapbiomas",
    "prodes_inpe",
    "prodes_yearly",
    "tipologia_sema",
    "vegetacao_radam",
    "dla",
    "lim_municipios_mt",
    "sigef_particular_mt",
    "mosaico_spot_2008",
    "autorizacao_desmate_sema",
]

# Mosaicos citados na matriz de imagem (§4).
MOSAICOS_CITADOS = [
    "Mosaicos:LANDSAT_5_2000",
    "Mosaicos:LANDSAT_5_2008",
    "Mosaicos:MOSAICO_SPOT_SEPLAN",
    "Mosaicos:LANDSAT_8_2013",
    "Mosaicos:LANDSAT_8_2017",
    "Mosaicos:SENTINEL_2_2017",
    "Mosaicos:SENTINEL_2_2019",
    "Mosaicos:SENTINEL_2_2023",
    "Mosaicos:SENTINEL_2_2024",
]

# Padrões de segredo que não podem aparecer no documento (AP-03).
SEGREDOS = [
    (r"PLAK[0-9a-f]{20,}", "chave Planet"),
    (r"authkey=[0-9a-f]{8}-[0-9a-f]{4}", "authkey SEMA"),
    (r"api_key=[0-9a-f]{16,}", "api_key em querystring"),
    (r"\bsk-[A-Za-z0-9]{16,}", "chave estilo sk-"),
    (r"gsk_[A-Za-z0-9]{20,}", "chave Groq"),
]


class Resultado:
    def __init__(self) -> None:
        self.itens: list[dict] = []

    def ok(self, titulo: str, detalhe: str = "") -> None:
        self.itens.append({"estado": "ok", "titulo": titulo, "detalhe": detalhe})

    def pular(self, titulo: str, detalhe: str = "") -> None:
        self.itens.append({"estado": "pular", "titulo": titulo, "detalhe": detalhe})

    def falha(self, titulo: str, detalhe: str = "") -> None:
        self.itens.append({"estado": "FALHA", "titulo": titulo, "detalhe": detalhe})

    @property
    def falhas(self) -> int:
        return sum(1 for i in self.itens if i["estado"] == "FALHA")

    def imprimir(self) -> None:
        for i in self.itens:
            marca = {"ok": "[ok]   ", "pular": "[pular]", "FALHA": "[FALHA]"}[i["estado"]]
            linha = f"{marca} {i['titulo']}"
            if i["detalhe"]:
                linha += f" — {i['detalhe']}"
            print(linha)


def _carregar_json(caminho: Path):
    with caminho.open(encoding="utf-8") as fp:
        return json.load(fp)


def checar_goal_existe(r: Resultado) -> str:
    if not GOAL.exists():
        r.falha("GOAL presente", f"{GOAL} não existe")
        return ""
    texto = GOAL.read_text(encoding="utf-8")
    r.ok("GOAL presente", f"{len(texto.splitlines())} linhas")
    return texto


def checar_segredos(r: Resultado, texto: str) -> None:
    achados = [nome for padrao, nome in SEGREDOS if re.search(padrao, texto)]
    if achados:
        r.falha("Sem segredo no documento", ", ".join(achados))
    else:
        r.ok("Sem segredo no documento", f"{len(SEGREDOS)} padrões conferidos")


def checar_ancoras(r: Resultado) -> None:
    faltando = [a for a in ANCORAS if not (RAIZ / a).exists()]
    if faltando:
        r.falha("Âncoras da §9", f"{len(faltando)} ausentes: {', '.join(faltando[:5])}")
    else:
        r.ok("Âncoras da §9", f"{len(ANCORAS)} caminhos conferidos")


def checar_serie(r: Resultado) -> None:
    if not MODELO.exists():
        r.pular("Inventário da série", "Testes/ ausente (gitignored) — nada a conferir")
        return

    mapas = MODELO / "Mapas"
    mxds = MODELO / "MXD"
    faltando: list[str] = []
    for pdf, mxd in SERIE:
        if not (mapas / f"{pdf}.pdf").exists():
            faltando.append(f"{pdf}.pdf")
        if not (mxds / f"{mxd}.mxd").exists():
            faltando.append(f"{mxd}.mxd")
    if faltando:
        r.falha("Pares PDF↔MXD da §3.1", f"{len(faltando)} ausentes: {', '.join(faltando[:6])}")
    else:
        r.ok("Pares PDF↔MXD da §3.1", f"{len(SERIE)} pares no disco")

    n_pdf = len(list(mapas.glob("*.pdf")))
    n_mxd = len(list(mxds.glob("*.mxd")))
    if n_pdf == 21 and n_mxd == 24:
        r.ok("Contagem do acervo-modelo", "21 PDFs (20 + compilado) e 24 MXDs")
    else:
        r.falha("Contagem do acervo-modelo", f"achei {n_pdf} PDFs e {n_mxd} MXDs (esperado 21/24)")

    unidos = mapas / "Mapas_unidos.pdf"
    try:
        import fitz  # type: ignore
    except ImportError:
        r.pular("Compilado com 20 páginas", "PyMuPDF ausente neste interpretador")
        return
    if not unidos.exists():
        r.falha("Compilado com 20 páginas", "Mapas_unidos.pdf ausente")
        return
    with fitz.open(unidos) as doc:
        n = doc.page_count
    if n == 20:
        r.ok("Compilado com 20 páginas", "ordem oficial da série")
    else:
        r.falha("Compilado com 20 páginas", f"tem {n}")


def checar_atp(r: Resultado) -> None:
    if not ATP.exists():
        r.pular("ATP de teste", "Testes/ ausente (gitignored)")
        return
    prj = ATP.with_suffix(".prj")
    texto = prj.read_text(encoding="latin-1") if prj.exists() else ""
    if "UTM_Zone_22S" in texto and "SIRGAS" in texto:
        r.ok("ATP de teste", "SIRGAS 2000 / UTM 22S (EPSG:31982)")
    else:
        r.falha("ATP de teste", "CRS do .prj não bate com EPSG:31982")


def checar_catalogo(r: Resultado) -> None:
    camadas = _carregar_json(RAIZ / "shared" / "catalog" / "camadas.json")
    lista = camadas["camadas"] if isinstance(camadas, dict) else camadas
    ids = {c.get("id") for c in lista}
    if len(lista) == 43:
        r.ok("Catálogo de camadas", "43 camadas (41 + as 2 autorizações da SEMA)")
    else:
        r.falha("Catálogo de camadas", f"{len(lista)} camadas (o GOAL diz 43)")

    faltando = [c for c in CAMADAS_USADAS if c not in ids]
    if faltando:
        r.falha("Camadas usadas pela série", f"ausentes: {', '.join(faltando)}")
    else:
        r.ok("Camadas usadas pela série", f"{len(CAMADAS_USADAS)} conferidas")

    # C1: a lacuna declarada no GOAL tem de continuar sendo uma lacuna real.
    vivo = (RAIZ / "shared" / "catalog" / "sema_layers_live.json").read_text(encoding="utf-8")
    tem_no_vivo = "AUTORIZACAO_DESMATE_SEMA" in vivo.upper()
    tem_no_catalogo = "autorizacao_desmate_sema" in ids
    if tem_no_catalogo and tem_no_vivo:
        r.ok("Lacuna C1 (PEF)", "fechada — a camada está no catálogo e no WFS vivo")
    elif tem_no_catalogo:
        r.ok("Lacuna C1 (PEF)", "no catálogo; inventário vivo não confirma o nome")
    else:
        r.falha("Lacuna C1 (PEF)", "AUTORIZACAO_DESMATE_SEMA saiu do catálogo")

    mosaicos = _carregar_json(RAIZ / "shared" / "catalog" / "mosaicos_sema.json")
    layers = {m.get("layer") for m in mosaicos.get("mosaicos", [])}
    ausentes = [m for m in MOSAICOS_CITADOS if m not in layers]
    if ausentes:
        r.falha("Mosaicos citados na §4", f"ausentes: {', '.join(ausentes)}")
    else:
        r.ok("Mosaicos citados na §4", f"{len(MOSAICOS_CITADOS)} de {len(layers)} disponíveis")

    anos = {m.get("ano") for m in mosaicos.get("mosaicos", [])}
    maior = max(a for a in anos if isinstance(a, int))
    if maior == 2024:
        r.ok("Cobertura temporal da SEMA", "vai até 2024 — 2025/2026 dependem de Planet ou STAC")
    else:
        r.falha("Cobertura temporal da SEMA", f"maior ano agora é {maior}; a §4 diz 2024")


def checar_serie_implementada(r_: Resultado) -> None:
    """A série existe em código, com anatomia medida e 20 templates.

    Importa o núcleo, que tem dependências pesadas (shapely, pyproj): rodando
    com o Python do sistema elas não existem, e aí o check se pula em vez de
    reprovar — quem valida de verdade é o CI, que instala o pacote.
    """
    import sys

    sys.path.insert(0, str(RAIZ / "Fase_1_Desktop" / "nucleo"))
    try:
        from mapasfacil_nucleo.analise import serie as serie_mod
    except ModuleNotFoundError as exc:
        if (exc.name or "").startswith("mapasfacil"):
            r_.falha("Série Análise de área", f"módulo ausente: {exc.name}")
        else:
            r_.pular("Série Análise de área", f"dependência do núcleo ausente ({exc.name})")
        return
    except Exception as exc:  # noqa: BLE001
        r_.falha("Série Análise de área", f"não importa: {exc}")
        return

    if len(serie_mod.RECEITAS) == 20:
        r_.ok("Série Análise de área", "20 receitas, uma por PDF-modelo")
    else:
        r_.falha("Série Análise de área", f"{len(serie_mod.RECEITAS)} receitas (esperado 20)")

    anat = RAIZ / "shared" / "padrao-imap" / "anatomia_serie.json"
    if not anat.is_file():
        r_.falha("Anatomia medida", "shared/padrao-imap/anatomia_serie.json ausente")
        return
    mapas = _carregar_json(anat).get("mapas") or {}
    faltando = [rc.id for rc in serie_mod.RECEITAS if rc.id not in mapas]
    if faltando:
        r_.falha("Anatomia medida", f"sem medida: {', '.join(faltando)}")
    else:
        r_.ok("Anatomia medida", f"{len(mapas)} mapas medidos dos modelos")

    manifest = _carregar_json(RAIZ / "shared" / "templates" / "MANIFEST.json")
    ids = {t["id"] for t in manifest["templates"]}
    sem_template = [rc.template for rc in serie_mod.RECEITAS if rc.template not in ids]
    if sem_template:
        r_.falha("Templates da série", f"fora do MANIFEST: {', '.join(sem_template)}")
    else:
        r_.ok("Templates da série", "20 templates serie_* registrados")


def checar_galeria(r: Resultado) -> None:
    galeria = _carregar_json(RAIZ / "shared" / "galeria" / "modelos.json")
    modelos = galeria["modelos"]
    manifest = _carregar_json(RAIZ / "shared" / "templates" / "MANIFEST.json")
    status = {t["id"]: t.get("status") for t in manifest["templates"]}

    por_id = {m["id"]: m for m in modelos}
    card = por_id.get("analise_de_area")
    if (
        galeria.get("galeria_version") == 2
        and card
        and card.get("tipo_execucao") == "analise_de_area"
        and "mxd" not in card.get("saidas_padrao", [])
    ):
        r.ok("Card analise_de_area", "schema v2, executor de série e saída nativa")
    else:
        r.falha("Card analise_de_area", "ausente ou sem contrato nativo da série")

    prontos = [m["id"] for m in modelos if status.get(m["template"]) == "pronto"]
    bloqueados = [m["id"] for m in modelos if status.get(m["template"]) == "a_preparar"]
    tipos_mapspec = [m["id"] for m in modelos if m.get("tipo_execucao") == "mapspec"]
    if (
        len(modelos) == 6
        and len(tipos_mapspec) == 5
        and prontos == ["dinamica_2026_retrato", "analise_de_area"]
        and len(bloqueados) == 4
    ):
        r.ok("Galeria e templates", "6 cards; gate ArcMap preservado só para saída mxd (§6.1)")
    else:
        r.falha(
            "Galeria e templates",
            f"{len(modelos)} cards, prontos={prontos}, a_preparar={len(bloqueados)}",
        )


def checar_gitignore(r: Resultado) -> None:
    alvos = ["Testes/01_analise_04_Julio/Modelo/Mapas/DLA.pdf", "output/", "secrets.local.json"]
    fora: list[str] = []
    for alvo in alvos:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", alvo],
            cwd=RAIZ,
            capture_output=True,
        )
        if proc.returncode != 0:
            fora.append(alvo)
    if fora:
        r.falha("Material sensível ignorado pelo Git", f"não ignorado: {', '.join(fora)}")
    else:
        r.ok("Material sensível ignorado pelo Git", "Testes/, output/ e secrets.local.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="saída em JSON")
    args = parser.parse_args()

    r = Resultado()
    texto = checar_goal_existe(r)
    if texto:
        checar_segredos(r, texto)
    checar_ancoras(r)
    checar_serie(r)
    checar_atp(r)
    checar_catalogo(r)
    checar_serie_implementada(r)
    checar_galeria(r)
    checar_gitignore(r)

    if args.json:
        print(json.dumps({"itens": r.itens, "falhas": r.falhas}, ensure_ascii=False, indent=1))
    else:
        r.imprimir()
        print()
        if r.falhas:
            print(f"{r.falhas} verificação(ões) falharam — o GOAL divergiu do disco.")
        else:
            print("GOAL_analise_de_area.md coerente com o repositório.")
    return 1 if r.falhas else 0


if __name__ == "__main__":
    sys.exit(main())
