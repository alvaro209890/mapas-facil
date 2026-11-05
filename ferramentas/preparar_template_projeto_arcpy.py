# -*- coding: utf-8 -*-
"""Prepara um MXD-modelo para o motor binário: links em ..\\SHP, sentinelas longas.

Roda com o Python 2.7 do ArcMap:

    C:\\Python27\\ArcGIS10.8\\python.exe ferramentas\\preparar_template_projeto_arcpy.py ^
        ferramentas\\templates_projeto\\dinamica_2008_spot.json <pasta-projeto> <saida.mxd>

`<pasta-projeto>` só precisa ter `MXD\\` (o .mxd é salvo ali para os caminhos relativos
saírem `..\\SHP\\...`); os dados **não** são lidos.

Por que sem ler dados: nesta máquina qualquer acesso a dado pelo arcpy (`Describe`,
`replaceDataSource`, `MakeRasterLayer`) trava indefinidamente (04/11/2026), mas trocar
só a **pasta** de uma camada (`findAndReplaceWorkspacePath(..., validate=False)`) é
instantâneo. Por isso cada camada mantém o **nome do arquivo** do modelo (AIR.shp,
lml_municipio_a.shp, ...) e só a pasta muda; o `.slots.json` lista esses arquivos com o
papel de cada um, e o núcleo grava as cópias com esses nomes (`arquivos` no manifesto).

O que faz:
  1. renomeia os data frames (MAPA / MINIMAPA / UF_INSET);
  2. remove camadas que não fazem parte da entrega (conexões de rede, shapes de outros
     projetos) e reaponta as demais para SHP/, SHP/limites/ ou SHP/imagens/;
  3. opcionalmente copia uma camada raster de outro MXD para servir de imagem de fundo;
  4. troca textos por sentinelas longas (o motor binário só troca texto pelo mesmo
     número de letras: a sentinela é o limite do que cabe);
  5. grava extensão/escala sentinelas;
  6. salva com caminhos relativos e escreve `<saida>.sentinelas.json`.

Motivo (04/11/2026): trocar texto mudando o tamanho corrompia o PageLayout (o .mxd do
teste_22 não abria), e os links apontavam para pastas do repositório e da máquina da
Aline — no projeto do usuário, tudo ficava vermelho.
"""
from __future__ import print_function

import io
import json
import os
import shutil
import sys

import arcpy


def u(texto):
    if isinstance(texto, str):
        try:
            return texto.decode("utf-8")
        except UnicodeDecodeError:
            return texto.decode("cp1252")
    return texto


def passo(msg):
    print(msg.encode("utf-8") if isinstance(msg, unicode) else msg)  # noqa: F821
    sys.stdout.flush()


def sentinela(prefixo, tamanho):
    base = u"MF" + prefixo.upper()
    return base + u"X" * (tamanho - len(base))


def _abs(cfg_path, caminho):
    if os.path.isabs(caminho):
        return caminho
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(cfg_path)), caminho))


def main():
    # Abrir um MapDocument muda o diretório atual: tudo vira caminho absoluto já aqui.
    cfg_path, projeto, saida = (os.path.abspath(a) for a in sys.argv[1:4])
    cfg = json.load(io.open(cfg_path, encoding="utf-8"))
    pasta_mxd = os.path.join(projeto, "MXD")
    if not os.path.isdir(pasta_mxd):
        os.makedirs(pasta_mxd)
    tmp = os.path.join(pasta_mxd, "_origem.mxd")
    shutil.copy2(_abs(cfg_path, cfg["origem"]), tmp)
    mxd = arcpy.mapping.MapDocument(tmp)
    passo("aberto")

    sentinelas = dict((k, sentinela(k, t)) for k, t in cfg.get("textos_tamanho", {}).items())

    # 1. data frames
    dfs = {}
    for df in arcpy.mapping.ListDataFrames(mxd):
        novo = cfg["data_frames"].get(u(df.name))
        if novo:
            df.name = novo
        dfs[u(df.name)] = df

    # 3 (antes do 2, para a camada copiada também ser reapontada). raster de outro MXD
    extra = cfg.get("raster_de")
    if extra:
        caminho_outro = _abs(cfg_path, extra["mxd"])
        passo(u"raster de {0} ({1})".format(caminho_outro, os.path.isfile(caminho_outro)))
        outro = arcpy.mapping.MapDocument(caminho_outro)
        camada = [l for l in arcpy.mapping.ListLayers(outro) if u(l.longName) == extra["camada"]][0]
        arcpy.mapping.AddLayer(dfs[extra["df"]], camada, "BOTTOM")
        del outro

    # 2. camadas
    arquivos = []
    for df_nome, regras in cfg["camadas"].items():
        df = dfs[df_nome]
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            nome = u(lyr.longName)
            regra = regras.get(nome)
            if regra is None:
                raise RuntimeError(u"Camada sem regra: {0} / {1}".format(df_nome, nome).encode("utf-8"))
            if regra == "remover":
                try:
                    arcpy.mapping.RemoveLayer(df, lyr)
                except Exception:  # noqa: BLE001 — filho de grupo já removido junto
                    pass
                continue
            if regra == "manter":
                continue
            pasta = os.path.join(projeto, *regra["pasta"].split("/"))
            lyr.findAndReplaceWorkspacePath(lyr.workspacePath, pasta, False)
            dataset = os.path.basename(lyr.dataSource)
            arquivos.append({"arquivo": regra["pasta"] + "/" + dataset, "papel": regra["papel"]})
            if "nome" in regra:
                lyr.name = regra["nome"]
            if "visivel" in regra:
                lyr.visible = bool(regra["visivel"])
            if "consulta" in regra:
                lyr.definitionQuery = regra["consulta"].replace(u"{municipio}", sentinelas.get("municipio", u""))
            if regra.get("mover") == "BOTTOM":
                camadas_df = arcpy.mapping.ListLayers(mxd, "", df)
                arcpy.mapping.MoveLayer(df, camadas_df[-1], lyr, "AFTER")
            passo(u"camada {0} -> {1}".format(nome, lyr.dataSource))

    # 4. textos
    feitos = set()
    for el in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
        texto = u(el.text).strip()
        for regra in cfg["textos"]:
            if regra["id"] in feitos or not texto.startswith(regra["comeca_com"]):
                continue
            el.name = regra["nome"]
            if regra.get("slot"):
                el.text = sentinelas[regra["slot"]]
            if regra.get("centralizar_no_df"):
                df = dfs[regra["centralizar_no_df"]]
                el.elementPositionX = df.elementPositionX + df.elementWidth / 2 - el.elementWidth / 2
                el.elementPositionY = df.elementPositionY + df.elementHeight / 2 - el.elementHeight / 2
            feitos.add(regra["id"])
            break
    faltam = [r["id"] for r in cfg["textos"] if r["id"] not in feitos]
    if faltam:
        raise RuntimeError("Textos nao encontrados: {0}".format(faltam))

    # gráficos presos ao projeto original (retângulo/guia fixos na página): fora da folha
    for el in arcpy.mapping.ListLayoutElements(mxd, "GRAPHIC_ELEMENT"):
        pos = [round(el.elementPositionX, 2), round(el.elementPositionY, 2)]
        for alvo in cfg.get("graficos_fora", []):
            if pos == alvo or u(el.name) == alvo:
                el.elementPositionX = 60.0

    # 5. extensões e escala sentinelas
    for df_nome, ext in cfg.get("extensoes", {}).items():
        dfs[df_nome].extent = arcpy.Extent(*ext)
    if cfg.get("escala_sentinela"):
        dfs["MAPA"].scale = cfg["escala_sentinela"]

    # 6. salvar com caminhos relativos ao lado de SHP/
    mxd.relativePaths = True
    final = os.path.join(pasta_mxd, os.path.basename(saida))
    mxd.saveACopy(final)
    del mxd
    os.remove(tmp)
    shutil.copy2(final, saida)

    pronto = arcpy.mapping.MapDocument(final)
    reais = {}
    for df in arcpy.mapping.ListDataFrames(pronto):
        e = df.extent
        reais[u(df.name)] = {
            "extent": [e.XMin, e.YMin, e.XMax, e.YMax],
            "escala": df.scale,
            "quadro_cm": [df.elementWidth, df.elementHeight],
            "epsg": df.spatialReference.factoryCode,
        }
    del pronto
    with open(saida + ".sentinelas.json", "wb") as fh:
        fh.write(json.dumps({"textos": sentinelas, "data_frames": reais, "arquivos": arquivos},
                            ensure_ascii=True, indent=2))
    passo("ok " + saida)


if __name__ == "__main__":
    main()
