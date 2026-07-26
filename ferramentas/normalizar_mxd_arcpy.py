# -*- coding: utf-8 -*-
"""Normalização automática (parcial) do .mxd para o contrato B1 — via arcpy.

Só usa operações seguras (ver `Referencias_IMAP/MXD/DOCUMENTACAO_MXD_HARMONIA.md` §5):
ListDataFrames/ListLayers/ListLayoutElements, ler/gravar `.name`, `mxd.relativePaths`,
`mxd.save()`. NUNCA usa Describe, replaceDataSource, Project ou cursores (trava nesta
máquina).

Trabalha sempre numa CÓPIA (nunca sobrescreve o `.mxd` de entrada). Renomeia o que dá para
inferir com confiança (data frames por CRS+escala, camadas por nome legado conhecido,
elementos de layout já existentes mas sem nome). O que não dá para inferir com segurança
fica listado em `pendencias` no relatório — precisa de confirmação visual no ArcMap.

Rodada 2026-07-25: comparando com outro template do acervo (`Divisão de talhões.mxd`, que
já tem título e rótulos como caixas de texto arredondadas), percebemos que o `Dinamica_2026`
JÁ TEM uma caixa de texto no estilo balão ("Ano: 2026") e rótulos soltos ("Vila Rica", "MT")
— não precisa criar elemento novo pra TITULO/ROTULO_IMOVEL, só reaproveitar (renomear +
reposicionar + trocar o texto) o que já existe. Isso é 100% dentro do que `arcpy.mapping`
permite (`.text`, `.elementPositionX/Y`, `.name` são graváveis em TextElement). Ainda **não
testado** neste ambiente (sem arcpy/Windows) — rodar no ArcMap e conferir o relatório.
"""
from __future__ import print_function

import argparse
import json
import os
import re
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

# TITULO no acervo Dinamica_2026 e' a caixa balao com o ano ("Ano: 2026") — mesmo estilo
# visual da caixa de titulo em `Divisão de talhões.mxd`. Repurposar em vez de criar nova.
_RE_TITULO_ANO = re.compile(r"^Ano:\s*\d{4}$", re.IGNORECASE)

# Logo padrao (variante "sem fundo, tom escuro" — confere com o logo ja usado nos PDFs
# renderizados do acervo, fundo branco da pagina). Caminho relativo a raiz do repo.
LOGO_PADRAO = os.path.join(
    u"Referencias_IMAP", u"Logos IMAP", u"LOGOTIPO SEM FUNDO", u"TOM ESCURO.png"
)


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


def _eh_grafico_fino(largura, altura):
    """Heuristica geometrica p/ distinguir linha-guia (fininha) de retangulo indicador."""
    maior = max(largura, altura)
    menor = min(largura, altura)
    if maior <= 0:
        return False
    # "fino": lado menor quase zero OU proporcao extrema (linha/diagonal, nao retangulo)
    return menor <= max(0.02 * maior, 0.3)


def _dentro_ou_perto(x, y, df, folga=5.0):
    dx = _safe(lambda: df.elementPositionX)
    dy = _safe(lambda: df.elementPositionY)
    dw = _safe(lambda: df.elementWidth)
    dh = _safe(lambda: df.elementHeight)
    if None in (dx, dy, dw, dh):
        return False
    return (dx - folga) <= x <= (dx + dw + folga) and (dy - folga) <= y <= (dy + dh + folga)


def normalizar(mxd_entrada, mxd_saida, dry_run=False, logo=None):
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

        # --- Textos: METADADOS (ja resolvido), TITULO (novo: reaproveita a caixa balao
        # "Ano: NNNN") e ROTULO_IMOVEL (novo: reaproveita o rotulo solto que sobrar). ---
        metadados_feito = False
        titulo_feito = False
        textos_sem_mapear = []  # lista de (elemento, texto) ainda sem nome canonico
        for el in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
            texto = el.text or ""
            nome_atual = _safe(lambda: el.name) or ""
            if not metadados_feito and texto.strip().startswith("<bol>METADADOS"):
                if nome_atual != "METADADOS":
                    el.name = "METADADOS"
                    aplicados.append("text_element (conteudo METADADOS IMAGEM) -> METADADOS")
                metadados_feito = True
            elif not titulo_feito and _RE_TITULO_ANO.match(texto.strip()):
                if nome_atual != "TITULO":
                    el.name = "TITULO"
                    aplicados.append(
                        u"text_element '{0}' (caixa balao existente, reaproveitada) -> TITULO "
                        u"— trocar .text por job em mapa.gerar, nao precisa GUI".format(texto.strip())
                    )
                titulo_feito = True
            elif not nome_atual:
                textos_sem_mapear.append((el, texto))

        if not titulo_feito:
            pendencias.append(
                u"Nenhum TEXT_ELEMENT no padrao 'Ano: NNNN' pra virar TITULO — confirmar no ArcMap "
                u"(pode ser que este .mxd nao tenha a caixa balao; nesse caso precisa criar na GUI)."
            )

        if len(textos_sem_mapear) == 1:
            el, texto = textos_sem_mapear[0]
            el.name = "ROTULO_IMOVEL"
            aplicados.append(
                u"text_element '{0}' (rotulo solto, unico sobrando) -> ROTULO_IMOVEL "
                u"— reposicionar sobre o poligono (elementPositionX/Y) e trocar .text por job, "
                u"nao precisa GUI".format(texto[:40])
            )
        elif len(textos_sem_mapear) > 1:
            pendencias.append(
                u"{0} TEXT_ELEMENT soltos sobrando para ROTULO_IMOVEL — escolher qual pelo "
                u"conteudo/posicao (decisao de codigo, nao precisa GUI): {1}".format(
                    len(textos_sem_mapear), [t[:40] for _, t in textos_sem_mapear]
                )
            )
        elif not titulo_feito:
            pendencias.append(
                u"Nenhum TEXT_ELEMENT solto sobrando para ROTULO_IMOVEL — confirmar no ArcMap."
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

        # --- LOGO: agora existe arquivo real (Referencias_IMAP/Logos IMAP/), antes o
        # sourceImage ficava vazio por falta de asset. Tenta gravar via script; arcpy.mapping
        # historicamente trata PictureElement.sourceImage como somente-leitura em algumas
        # versoes — por isso o try/except em vez de assumir que vai funcionar. ---
        pictures = arcpy.mapping.ListLayoutElements(mxd, "PICTURE_ELEMENT")
        if len(pictures) == 1:
            if _safe(lambda: pictures[0].name) != "LOGO":
                pictures[0].name = "LOGO"
                aplicados.append("picture_element unico -> LOGO")
            fonte = _safe(lambda: pictures[0].sourceImage) or ""
            if not fonte:
                caminho_logo = logo or LOGO_PADRAO
                if os.path.isfile(caminho_logo):
                    try:
                        pictures[0].sourceImage = caminho_logo
                        aplicados.append(
                            u"picture_element 'LOGO' sourceImage -> {0}".format(caminho_logo)
                        )
                    except Exception as exc:
                        pendencias.append(
                            u"PICTURE_ELEMENT 'LOGO' sem sourceImage — tentativa via script falhou "
                            u"({0}); apontar manualmente no ArcMap (Propriedades da Imagem) usando "
                            u"'{1}'.".format(exc, caminho_logo)
                        )
                else:
                    pendencias.append(
                        u"PICTURE_ELEMENT 'LOGO' sem sourceImage — arquivo padrao nao encontrado "
                        u"({0}); passe --logo apontando pro PNG certo.".format(caminho_logo)
                    )
        elif len(pictures) > 1:
            pendencias.append(u"{0} PICTURE_ELEMENT encontrados — LOGO ambiguo.".format(len(pictures)))

        # --- Graficos do minimapa: heuristica geometrica (fino = linha-guia) + heuristica
        # posicional (dentro do data frame MINIMAPA = retangulo indicador). Antes o script so
        # listava posicoes sem tentar classificar; agora tenta, mas so aplica em caso
        # inequivoco (1 candidato) — senao fica pendencia com os dados prontos pra decisao
        # rapida (nao precisa mais abrir o ArcMap so pra olhar posicao). ---
        graficos = arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT")
        if graficos:
            info = []
            for g in graficos:
                info.append(
                    {
                        "el": g,
                        "w": _safe(lambda: g.elementWidth) or 0,
                        "h": _safe(lambda: g.elementHeight) or 0,
                        "x": _safe(lambda: g.elementPositionX) or 0,
                        "y": _safe(lambda: g.elementPositionY) or 0,
                    }
                )

            linhas = [i for i in info if _eh_grafico_fino(i["w"], i["h"])]
            linhas_ids = set(id(i) for i in linhas)
            retangulos = [i for i in info if id(i) not in linhas_ids]

            if len(linhas) == 1:
                linhas[0]["el"].name = "MINIMAPA_GUIA"
                aplicados.append(
                    u"graphic_element fino (w={0:.2f} h={1:.2f}) -> MINIMAPA_GUIA "
                    u"(heuristica geometrica, confirmar visualmente)".format(linhas[0]["w"], linhas[0]["h"])
                )
            else:
                pendencias.append(
                    u"{0} candidato(s) a linha-guia (heuristica geometrica ambigua) — "
                    u"MINIMAPA_GUIA nao atribuido automaticamente: {1}".format(
                        len(linhas), [(round(i["w"], 2), round(i["h"], 2)) for i in linhas]
                    )
                )

            candidatos_retangulo = retangulos
            if df_minimapa is not None:
                dentro = [i for i in retangulos if _dentro_ou_perto(i["x"], i["y"], df_minimapa)]
                if dentro:
                    candidatos_retangulo = dentro

            if len(candidatos_retangulo) == 1:
                candidatos_retangulo[0]["el"].name = "MINIMAPA_RETANGULO"
                aplicados.append(
                    u"graphic_element dentro/perto do MINIMAPA (w={0:.2f} h={1:.2f}) -> "
                    u"MINIMAPA_RETANGULO (heuristica posicional, confirmar visualmente)".format(
                        candidatos_retangulo[0]["w"], candidatos_retangulo[0]["h"]
                    )
                )
            else:
                pendencias.append(
                    u"{0} candidato(s) a retangulo indicador — MINIMAPA_RETANGULO nao atribuido "
                    u"automaticamente. Posicoes/tamanhos: {1}".format(
                        len(candidatos_retangulo),
                        [
                            (round(i["x"], 2), round(i["y"], 2), round(i["w"], 2), round(i["h"], 2))
                            for i in candidatos_retangulo
                        ],
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
    parser.add_argument("--logo", help="Caminho do PNG do logo (default: acervo Logos IMAP, tom escuro sem fundo)")
    parser.add_argument("-o", "--relatorio", help="Gravar relatorio JSON neste arquivo")
    args = parser.parse_args()

    rel = normalizar(args.entrada, args.saida, dry_run=args.dry_run, logo=args.logo)

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
