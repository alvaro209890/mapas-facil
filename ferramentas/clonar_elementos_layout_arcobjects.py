# -*- coding: utf-8 -*-
"""Clona elementos de layout nomeados entre MXDs usando ArcObjects.

`arcpy.mapping` lista e altera elementos, mas não cria um TextElement novo.
ArcObjects expõe `IGraphicsContainer` + `IClone`, permitindo herdar o elemento
pronto de outro MXD sem copiar o layout inteiro nem trocar o raster anual.

Use sempre sobre cópias, com o ArcMap fechado:

    C:\Python27\ArcGIS10.8\python.exe ferramentas\clonar_elementos_layout_arcobjects.py ^
      --origem shared\templates\Dinamica_retrato.mxd ^
      --destino shared\templates\Dinamica_2023.mxd ^
      --elemento ROTULO_IMOVEL
"""
from __future__ import print_function

import argparse
import json
import os
import sys

import comtypes.client

COM = r"C:\Program Files (x86)\ArcGIS\Desktop10.8\com"
esri_carto = comtypes.client.GetModule(os.path.join(COM, "esriCarto.olb"))
esri_system = comtypes.client.GetModule(os.path.join(COM, "esriSystem.olb"))


def _inicializar_licenca():
    inicializador = comtypes.client.CreateObject(
        esri_system.AoInitialize,
        interface=esri_system.IAoInitialize,
    )
    status = inicializador.Initialize(esri_system.esriLicenseProductCodeAdvanced)
    return inicializador, status


def _u(valor):
    if isinstance(valor, unicode):  # noqa: F821 - Python 2.7 do ArcMap
        return valor
    for encoding in ("mbcs", "utf-8", "cp1252", "latin-1"):
        try:
            return valor.decode(encoding)
        except UnicodeDecodeError:
            continue
    return unicode(valor, "latin-1", "replace")  # noqa: F821


def _abrir(caminho):
    documento = comtypes.client.CreateObject(
        esri_carto.MapDocument,
        interface=esri_carto.IMapDocument,
    )
    documento.Open(_u(os.path.abspath(caminho)), u"")
    return documento


def _graphics(documento):
    return documento.PageLayout.QueryInterface(esri_carto.IGraphicsContainer)


def _por_nome(container, nome):
    container.Reset()
    elemento = container.Next()
    while elemento:
        try:
            props = elemento.QueryInterface(esri_carto.IElementProperties)
            if (props.Name or u"").upper() == nome.upper():
                return elemento
        except Exception:
            pass
        elemento = container.Next()
    return None


def clonar(origem, destino, nomes):
    if not os.path.isfile(origem):
        raise IOError("MXD de origem ausente: {0}".format(origem))
    if not os.path.isfile(destino):
        raise IOError("MXD de destino ausente: {0}".format(destino))

    inicializador, _status = _inicializar_licenca()
    doc_origem = _abrir(origem)
    clones = {}
    faltantes = []
    try:
        gc_origem = _graphics(doc_origem)
        for nome in nomes:
            nome_u = _u(nome)
            elemento = _por_nome(gc_origem, nome_u)
            if elemento is None:
                faltantes.append(nome_u)
                continue
            clones[nome_u] = elemento.QueryInterface(esri_system.IClone).Clone()
    finally:
        try:
            doc_origem.Close()
        except Exception:
            pass

    # O coclass MapDocument do Desktop 10.8 não abre dois documentos ao mesmo
    # tempo no mesmo processo. Clone primeiro, feche a origem e só então abra o
    # destino.
    doc_destino = _abrir(destino)
    adicionados = []
    existentes = []
    try:
        gc_destino = _graphics(doc_destino)
        for nome in nomes:
            nome_u = _u(nome)
            if _por_nome(gc_destino, nome_u) is not None:
                existentes.append(nome_u)
                continue
            clone = clones.get(nome_u)
            if clone is None:
                continue
            gc_destino.AddElement(clone, 0)
            adicionados.append(nome_u)
        if adicionados:
            doc_destino.Save(True, True)
    finally:
        try:
            doc_destino.Close()
        except Exception:
            pass
        try:
            inicializador.Shutdown()
        except Exception:
            pass

    return {
        "origem": os.path.abspath(origem),
        "destino": os.path.abspath(destino),
        "adicionados": adicionados,
        "existentes": existentes,
        "faltantes_na_origem": faltantes,
    }


def _json_safe(valor):
    if isinstance(valor, dict):
        return {_json_safe(k): _json_safe(v) for k, v in valor.iteritems()}
    if isinstance(valor, (list, tuple)):
        return [_json_safe(v) for v in valor]
    if isinstance(valor, str):
        return _u(valor)
    return valor


def main():
    parser = argparse.ArgumentParser(description="Clona elementos nomeados entre layouts MXD")
    parser.add_argument("--origem", required=True)
    parser.add_argument("--destino", action="append", required=True)
    parser.add_argument("--elemento", action="append", required=True)
    parser.add_argument("-o", "--saida-json")
    args = parser.parse_args()

    resultados = [clonar(args.origem, destino, args.elemento) for destino in args.destino]
    resultado = resultados[0] if len(resultados) == 1 else {"resultados": resultados}
    payload = json.dumps(_json_safe(resultado), ensure_ascii=False, indent=2).encode("utf-8")
    if args.saida_json:
        with open(args.saida_json, "wb") as arquivo:
            arquivo.write(payload)
        print("Relatorio: {0}".format(args.saida_json))
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
    return (
        0
        if all(not item["faltantes_na_origem"] for item in resultados)
        else 2
    )


if __name__ == "__main__":
    sys.exit(main())
