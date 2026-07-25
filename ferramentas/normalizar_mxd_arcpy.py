# -*- coding: utf-8 -*-
"""Normalização automática (parcial) do .mxd para o contrato B1 — via arcpy.

Só usa operações seguras (ver `Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md` §5):
ListDataFrames/ListLayers/ListLayoutElements, ler/gravar `.name`, `mxd.relativePaths`,
`mxd.save()`. NUNCA usa Describe, replaceDataSource, Project ou cursores (trava nesta
máquina).

Trabalha sempre numa CÓPIA (nunca sobrescreve o `.mxd` de entrada). Renomeia o que dá para
inferir com confiança (data frames por CRS+escala, camadas por nome legado conhecido,
elementos de layout já existentes mas sem nome). O que não dá para inferir com segurança
(qual dos 2 legend/quais dos 5 graphics são MINIMAPA_RETANGULO/GUIA, título do imóvel que
não existe como elemento próprio) fica listado em `pendencias` no relatório — precisa de
confirmação visual no ArcMap.
"""
from __future__ import print_function

import argparse
import json
import shutil
import sys

try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel — execute com Python 2.7 do ArcMap\n")
    sys.exit(1)

RENOMEAR_CAMADAS = {
    u"Fazenda Harmonia": u"PERIMETRO",
    u"Uso Consolidado": u"AC",
    u"Limite municipal": u"MUNICIPIOS",
    u"Limite estadual": u"UF",
}


def _safe(getter, default=None):
    try:
        return getter()
    except (NameError, AttributeError, ValueError):
        return default


def _classificar_data_frames(dfs):
    """Escolhe MAPA (UTM, escala pequena) e MINIMAPA (o próximo por área de extent)."""
    candidatos = []
    for df in dfs:
        sr = _safe(lambda: df.spatialReference.factoryCode)
        ext = df.extent
        area = abs((ext.XMax - ext.XMin) * (ext.YMax - ext.YMin))
        candidatos.append({"df": df, "sr": sr, "scale": df.scale, "area": area})

    utm = [c for c in candidatos if c["sr"] == 31982]
    mapa = min(utm, key=lambda c: c["area"]) if utm else min(candidatos, key=lambda c: c["area"])

    restantes = [c for c in candidatos if c["df"] is not mapa["df"]]
    webmerc = [c for c in restantes if c["sr"] == 3857]
    minimapa = min(webmerc, key=lambda c: c["area"]) if webmerc else (
        min(restantes, key=lambda c: c["area"]) if restantes else None
    )

    extras = [c for c in restantes if minimapa is None or c["df"] is not minimapa["df"]]
    return mapa["df"], (minimapa["df"] if minimapa else None), [c["df"] for c in extras]


def normalizar(mxd_entrada, mxd_saida, dry_run=False):
    shutil.copy2(mxd_entrada, mxd_saida)
    mxd = arcpy.mapping.MapDocument(mxd_saida)
    aplicados = []
    pendencias = []

    try:
        if not mxd.relativePaths:
            mxd.relativePaths = True
            aplicados.append("relativePaths = True")

        dfs = arcpy.mapping.ListDataFrames(mxd)
        df_mapa, df_minimapa, df_extras = _classificar_data_frames(dfs)

        if df_mapa.name != u"MAPA":
            antigo = df_mapa.name
            df_mapa.name = u"MAPA"
            aplicados.append(u"data frame '{0}' -> MAPA".format(antigo))

        if df_minimapa is not None and df_minimapa.name != u"MINIMAPA":
            antigo = df_minimapa.name
            df_minimapa.name = u"MINIMAPA"
            aplicados.append(u"data frame '{0}' -> MINIMAPA".format(antigo))
        elif df_minimapa is None:
            pendencias.append(u"Nenhum 2o data frame candidato a MINIMAPA — confirmar no ArcMap.")

        for df in df_extras:
            pendencias.append(
                u"Data frame extra nao classificado: '{0}' (sr={1}, scale={2}) — mantido sem renomear.".format(
                    df.name, _safe(lambda: df.spatialReference.factoryCode), df.scale
                )
            )

        for df in arcpy.mapping.ListDataFrames(mxd):
            for lyr in arcpy.mapping.ListLayers(mxd, "", df):
                novo = RENOMEAR_CAMADAS.get(lyr.name)
                if novo and lyr.name != novo:
                    antigo = lyr.name
                    lyr.name = novo
                    aplicados.append(u"camada '{0}' -> {1} (df {2})".format(antigo, novo, df.name))

        metadados_feito = False
        textos_sem_mapear = []
        for el in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
            texto = el.text or ""
            nome_atual = _safe(lambda: el.name) or ""
            if not metadados_feito and texto.strip().startswith("<bol>METADADOS"):
                if nome_atual != "METADADOS":
                    el.name = "METADADOS"
                    aplicados.append("text_element (conteudo METADADOS IMAGEM) -> METADADOS")
                metadados_feito = True
            elif not nome_atual:
                textos_sem_mapear.append(texto[:60])
        if textos_sem_mapear:
            pendencias.append(
                u"TEXT_ELEMENT sem nome canonico (TITULO/ROTULO_IMOVEL) — conteudo: {0}".format(
                    textos_sem_mapear
                )
            )

        legendas = arcpy.mapping.ListLayoutElements(mxd, "LEGEND_ELEMENT")
        if len(legendas) == 1:
            if _safe(lambda: legendas[0].name) != "LEGENDA":
                legendas[0].name = "LEGENDA"
                aplicados.append("legend_element unico -> LEGENDA")
        elif len(legendas) > 1:
            def _area_legenda(el):
                w = _safe(lambda: el.elementWidth) or 0
                h = _safe(lambda: el.elementHeight) or 0
                return w * h

            maior = max(legendas, key=_area_legenda)
            if _safe(lambda: maior.name) != "LEGENDA":
                maior.name = "LEGENDA"
                aplicados.append(
                    "legend_element maior (w={0:.2f} h={1:.2f}) -> LEGENDA".format(
                        _safe(lambda: maior.elementWidth) or 0, _safe(lambda: maior.elementHeight) or 0
                    )
                )
            pendencias.append(
                u"{0} LEGEND_ELEMENT encontrados — escolhida a maior como LEGENDA por heuristica de "
                u"tamanho; confirmar visualmente no ArcMap que e a legenda do MAPA (nao da MINIMAPA).".format(
                    len(legendas)
                )
            )

        for el in arcpy.mapping.ListLayoutElements(mxd, "MAPSURROUND_ELEMENT"):
            nome_atual = _safe(lambda: el.name) or ""
            if "North Arrow" in nome_atual or nome_atual == "":
                if nome_atual != "NORTE":
                    el.name = "NORTE"
                    aplicados.append(u"mapsurround '{0}' -> NORTE".format(nome_atual))
                break

        pictures = arcpy.mapping.ListLayoutElements(mxd, "PICTURE_ELEMENT")
        if len(pictures) == 1:
            if _safe(lambda: pictures[0].name) != "LOGO":
                pictures[0].name = "LOGO"
                aplicados.append("picture_element unico -> LOGO")
            fonte = _safe(lambda: pictures[0].sourceImage) or ""
            if not fonte:
                pendencias.append(u"PICTURE_ELEMENT 'LOGO' sem sourceImage — precisa apontar logo no ArcMap.")
        elif len(pictures) > 1:
            pendencias.append(u"{0} PICTURE_ELEMENT encontrados — LOGO ambiguo.".format(len(pictures)))

        graficos = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT")
        pendencias.append(
            u"{0} GRAPHIC_ELEMENT sem classificacao segura (MINIMAPA_RETANGULO/MINIMAPA_GUIA) "
            u"— posicoes: {1}".format(
                len(graficos),
                [(round(_safe(lambda: g.elementPositionX, 0), 3), round(_safe(lambda: g.elementPositionY, 0), 3)) for g in graficos],
            )
        )

        if not dry_run and aplicados:
            mxd.save()
    finally:
        del mxd

    return {"aplicados": aplicados, "pendencias": pendencias, "arquivo": mxd_saida}


def main():
    parser = argparse.ArgumentParser(description="Normaliza .mxd (parcial, seguro) via arcpy")
    parser.add_argument("entrada", help="MXD de origem (nunca modificado)")
    parser.add_argument("saida", help="MXD de destino (sera criado/sobrescrito)")
    parser.add_argument("--dry-run", action="store_true", help="Nao salva, so relata")
    parser.add_argument("-o", "--relatorio", help="Gravar relatorio JSON neste arquivo")
    args = parser.parse_args()

    rel = normalizar(args.entrada, args.saida, dry_run=args.dry_run)

    def _out(prefixo, item):
        linha = u"  {0} {1}".format(prefixo, item)
        sys.stdout.write(linha.encode("utf-8", "replace"))
        sys.stdout.write("\n")

    print("Aplicados ({0}):".format(len(rel["aplicados"])))
    for item in rel["aplicados"]:
        _out("+", item)
    print("Pendencias ({0}):".format(len(rel["pendencias"])))
    for item in rel["pendencias"]:
        _out("!", item)

    if args.relatorio:
        import codecs

        with codecs.open(args.relatorio, "w", "utf-8") as fh:
            fh.write(json.dumps(rel, ensure_ascii=False, indent=2))
        print("Relatorio:", args.relatorio)

    return 0


if __name__ == "__main__":
    sys.exit(main())
