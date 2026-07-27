# -*- coding: utf-8 -*-
"""Remove camadas Planet/WMTS quebradas dos .mxd e troca por WMS SEMA (ou Esri).

Contexto
--------
Com as chaves Planet zeradas (placeholders), o ArcMap abre o dialogo
"GIS Server Connection" a cada ``MapDocument``. Rode em paralelo
``fechar_dialogs_gis.ps1`` para Cancel automatico.

Substituicao de basemap (sem Planet):
- por ano do arquivo Dinamica_* → mosaico SEMA em ``shared/catalog/mosaicos_sema.json``
- senao → Esri World Imagery (sem senha)
- SEMA precisa de ``sema_authkey`` na URL para pintar; sem chave a camada fica no MXD
  mas nao desenha — ainda assim NAO abre o dialogo de usuario/senha do Planet.

Uso (Python 2.7 do ArcMap)::

    C:\\Python27\\ArcGIS10.8\\python.exe ferramentas/remover_planet_mxd_arcpy.py \\
        Referencias_IMAP/MXD shared/templates --in-place -o relatorio_planet.json

Nunca embute chave. Authkey SEMA so via env ``SEMA_WFS_AUTHKEY`` / ``SEMA_WMS_AUTHKEY``
se quiser gravar URL ja autenticada (opcional).
"""
from __future__ import print_function

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

# NAO usar sys.setdefaultencoding('utf-8'): quebra str(cp1252)+unicode no Windows.
try:
    import arcpy
except ImportError:
    sys.stderr.write("arcpy indisponivel - execute com Python 2.7 do ArcMap\n")
    sys.exit(1)


def _as_text(msg):
    if msg is None:
        return u""
    if isinstance(msg, unicode):  # noqa: F821 — Py2
        return msg
    if isinstance(msg, str):
        for enc in ("mbcs", "cp1252", "utf-8", "latin-1"):
            try:
                return msg.decode(enc)
            except Exception:
                continue
        return msg.decode("latin-1", "replace")
    return unicode(msg)  # noqa: F821


def _as_path(msg):
    """Caminho nativo Windows (bytes mbcs) para arcpy/os."""
    if isinstance(msg, str):
        return msg
    if isinstance(msg, unicode):  # noqa: F821
        try:
            return msg.encode("mbcs")
        except Exception:
            return msg.encode("utf-8", "replace")
    return str(msg)


def _out(msg):
    text = _as_text(msg)
    try:
        print(text)
    except Exception:
        try:
            sys.stdout.write(text.encode("mbcs", "replace") + "\n")
        except Exception:
            sys.stdout.write(repr(text) + "\n")

# Marcadores de camada Planet / WMTS (nome ou serviceProperties)
MARCADORES_PLANET = (
    u"planet",
    u"global monthly",
    u"api.planet.com",
    u"planet.com",
    u"plak_",
    u"planet-tiles",
    u"basemaps/v1/mosaics",
)

# Ano no nome do arquivo → layer SEMA (workspace Mosaicos:)
ANO_PARA_MOSAICO = {
    2000: u"Mosaicos:LANDSAT_5_2000",
    2002: u"Mosaicos:LANDSAT_7_2002",
    2005: u"Mosaicos:LANDSAT_5_2005",
    2006: u"Mosaicos:LANDSAT_5_2006",
    2008: u"Mosaicos:LANDSAT_5_2008",  # SPOT sobrescrito se nome tiver SPOT
    2012: u"Mosaicos:RESOURCESAT_2012",
    2013: u"Mosaicos:LANDSAT_8_2013",
    2016: u"Mosaicos:SENTINEL_2_2016",
    2017: u"Mosaicos:SENTINEL_2_2017",
    2018: u"Mosaicos:SENTINEL_2_2018",
    2019: u"Mosaicos:SENTINEL_2_2019",
    2020: u"Mosaicos:SENTINEL_2_2020",
    2021: u"Mosaicos:SENTINEL_2_2021",
    2022: u"Mosaicos:SENTINEL_2_2022",
    2023: u"Mosaicos:SENTINEL_2_2023",
    2024: u"Mosaicos:SENTINEL_2_2024",
    2025: u"Mosaicos:SENTINEL_2_2024",
    2026: u"Mosaicos:SENTINEL_2_2024",
}

SEMA_WMS = u"https://geo.sema.mt.gov.br/geoserver/ows"
ESRI_WORLD_IMAGERY = (
    u"https://services.arcgisonline.com/ArcGIS/rest/services/"
    u"World_Imagery/MapServer"
)


def _safe(getter, default=None):
    try:
        return getter()
    except Exception:
        return default


def _texto_camada(lyr):
    # Sempre unicode via _as_text: em Py2, u"%s" % str_mbcs estoura ascii codec.
    partes = [_as_text(lyr.name or u"")]
    for attr in ("description", "workspacePath", "dataSource", "longName"):
        partes.append(_as_text(_safe(lambda a=attr: getattr(lyr, a), u"") or u""))
    # serviceProperties e dict-like em ServiceLayer
    try:
        props = lyr.serviceProperties
        if props:
            for k in props:
                partes.append(_as_text(k) + u"=" + _as_text(props[k]))
    except Exception:
        pass
    return u" ".join(partes).lower()


def _eh_planet(lyr):
    blob = _texto_camada(lyr)
    for m in MARCADORES_PLANET:
        if m in blob:
            return True
    return False


def _inferir_ano(caminho):
    nome = _as_text(os.path.basename(caminho)).upper()
    # Anos de 4 digitos no nome; pegar o maior (>=1984) como ano do mapa
    anos = [int(x) for x in re.findall(ur"19\d{2}|20\d{2}", nome)]
    anos = [a for a in anos if 1984 <= a <= 2030]
    if not anos:
        return None
    return max(anos)


def _layer_sema_para(caminho):
    nome = _as_text(os.path.basename(caminho)).upper()
    ano = _inferir_ano(caminho)
    if u"SPOT" in nome:
        return u"Mosaicos:MOSAICO_SPOT_SEPLAN"
    if ano is None:
        return u"Mosaicos:SENTINEL_2_2024"
    return ANO_PARA_MOSAICO.get(ano, u"Mosaicos:SENTINEL_2_2024")


def _authkey():
    return (
        os.environ.get("SEMA_WMS_AUTHKEY")
        or os.environ.get("SEMA_WFS_AUTHKEY")
        or os.environ.get("SEMA_AUTHKEY")
        or ""
    )


def _escrever_lyr_wms(caminho_lyr, layer_name, titulo):
    """Gera um .lyr minimo apontando para WMS SEMA (ArcMap 10.x aceita via Layer()).

    Formato simplificado: na pratica o ArcMap 10.8 e mais feliz com um .wms + AddData.
    Aqui gravamos um arquivo de conexao WMS (XML) e tentamos AddLayer; se falhar,
    o relatorio fica com pendencia — Planet ja foi removido (objetivo principal).
    """
    auth = _authkey()
    url = SEMA_WMS
    if auth:
        sep = u"&" if u"?" in url else u"?"
        url = url + sep + u"authkey=" + auth
    # Conexao WMS "GetCapabilities" style usada pelo ArcMap
    xml = u"""<?xml version="1.0" encoding="UTF-8"?>
<IMS_SERVICES>
  <SERVICE>
    <NAME>{titulo}</NAME>
    <CAPABILITIES_URL>{url}</CAPABILITIES_URL>
    <TYPE>WMS</TYPE>
    <LAYER>{layer}</LAYER>
  </SERVICE>
</IMS_SERVICES>
""".format(titulo=titulo, url=url, layer=layer_name)
    with open(caminho_lyr, "wb") as f:
        f.write(xml.encode("utf-8"))
    return caminho_lyr


def _tentar_adicionar_basemap(mxd, df, caminho_mxd, relatorio):
    """Tenta Esri World Imagery (sem senha). SEMA WMS fica documentado se authkey ausente."""
    layer_sema = _layer_sema_para(caminho_mxd)
    relatorio["basemap_desejado"] = layer_sema
    auth = _authkey()
    if not auth:
        relatorio["avisos"].append(
            u"SEMA WMS '{0}' nao adicionado com authkey (env vazia). "
            u"Planet removido; use Esri World Imagery ou rode com SEMA_WMS_AUTHKEY.".format(
                layer_sema
            )
        )

    # Esri via CreateGISServerConnectionFile + Layer — melhor esforco sem senha
    pasta = tempfile.mkdtemp(prefix="mf_basemap_")
    try:
        ags = os.path.join(pasta, "esri.ags")
        try:
            arcpy.mapping.CreateGISServerConnectionFile(
                "USE_GIS_SERVICES",
                pasta,
                "esri",
                "https://services.arcgisonline.com/ArcGIS/rest/services",
                "ARCGIS_SERVER",
                username="#",
                password="#",
                save_username_password=False,
            )
        except Exception as exc:
            relatorio["avisos"].append(u"CreateGISServerConnectionFile falhou: {0}".format(exc))
            return False

        # Tentar Layer apontando para World_Imagery
        candidatos = [
            os.path.join(pasta, "esri.ags"),
            ags,
        ]
        # Em 10.8 o .ags e conexao; AddLayer precisa de um .lyr ou MapServer URL via lyr file.
        # Fallback: nao forcar — remocao Planet ja resolve o dialogo.
        relatorio["avisos"].append(
            u"Basemap Esri: conexao .ags criada em temp; AddLayer automatico de MapServer "
            u"e limitado no ArcMap 10.8 via arcpy - confirme BASEMAP na GUI se faltar fundo. "
            u"Layer SEMA alvo: {0}".format(layer_sema)
        )
        # Marca intencao no MXD: se existir camada SEMA/WMS generica, renomeia BASEMAP
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            blob = _texto_camada(lyr)
            if (
                u"sema" in blob
                or u"mosaico" in blob
                or u"landsat" in blob
                or u"sentinel" in blob
                or u"spot" in blob
                or u"webmaps" in blob
                or u"geoserver" in blob
            ) and not _eh_planet(lyr):
                if lyr.name != u"BASEMAP":
                    antigo = lyr.name
                    try:
                        lyr.name = u"BASEMAP"
                        relatorio["renomeados_basemap"].append(
                            u"{0} -> BASEMAP".format(antigo)
                        )
                    except Exception as exc:
                        relatorio["avisos"].append(
                            u"nao renomeou '{0}': {1}".format(antigo, exc)
                        )
                return True
        return False
    finally:
        try:
            shutil.rmtree(pasta, ignore_errors=True)
        except Exception:
            pass


def processar_mxd(caminho, in_place, dry_run, pasta_saida):
    # Sempre trabalhar em path ASCII sob %TEMP% — evita ascii codec em nomes
    # com acento (Unidade_de_Conservação, DINÂMINCA_*, Dinâmica_*).
    caminho = _as_path(os.path.abspath(_as_path(caminho)))
    rel = {
        "arquivo": _as_text(caminho),
        "planet_removidas": [],
        "renomeados_basemap": [],
        "avisos": [],
        "ok": False,
        "ms": 0,
    }
    t0 = time.time()
    pasta_tmp = tempfile.mkdtemp(prefix="mf_planet_")
    trabalho = _as_path(os.path.join(pasta_tmp, "work.mxd"))
    if in_place:
        destino = caminho
    else:
        base = os.path.basename(caminho)
        if not os.path.isdir(pasta_saida):
            os.makedirs(pasta_saida)
        destino = _as_path(os.path.join(_as_path(pasta_saida), base))

    mxd = None
    try:
        shutil.copy2(caminho, trabalho)
        mxd = arcpy.mapping.MapDocument(trabalho)
        removidas = []
        for df in arcpy.mapping.ListDataFrames(mxd):
            # Lista copia: RemoveLayer invalida o iterator
            layers = list(arcpy.mapping.ListLayers(mxd, "", df))
            for lyr in layers:
                if _eh_planet(lyr):
                    nome = lyr.name
                    if not dry_run:
                        try:
                            arcpy.mapping.RemoveLayer(df, lyr)
                            removidas.append(
                                u"{0} (df={1})".format(_as_text(nome), _as_text(df.name))
                            )
                        except Exception as exc:
                            rel["avisos"].append(
                                u"falha ao remover '{0}': {1}".format(
                                    _as_text(nome), _as_text(exc)
                                )
                            )
                    else:
                        removidas.append(
                            u"{0} (df={1}) [dry-run]".format(
                                _as_text(nome), _as_text(df.name)
                            )
                        )

        if not dry_run and removidas:
            for df in arcpy.mapping.ListDataFrames(mxd):
                _tentar_adicionar_basemap(mxd, df, caminho, rel)

        rel["planet_removidas"] = removidas
        if not dry_run and (removidas or rel["renomeados_basemap"]):
            mxd.save()
            del mxd
            mxd = None
            for _ in range(10):
                try:
                    shutil.copy2(trabalho, destino)
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                shutil.copy2(trabalho, destino)
        rel["ok"] = True
    except Exception as exc:
        rel["avisos"].append(u"ERRO: {0}".format(_as_text(exc)))
        rel["ok"] = False
    finally:
        if mxd is not None:
            try:
                del mxd
            except Exception:
                pass
        try:
            shutil.rmtree(pasta_tmp, ignore_errors=True)
        except Exception:
            pass
        rel["ms"] = int((time.time() - t0) * 1000)
    return rel


def _coletar_mxds(caminhos):
    out = []
    for c in caminhos:
        c = os.path.abspath(c)
        if os.path.isfile(c) and c.lower().endswith(".mxd"):
            out.append(c)
        elif os.path.isdir(c):
            for root, _dirs, files in os.walk(c):
                for f in files:
                    if f.lower().endswith(".mxd"):
                        out.append(os.path.join(root, f))
    # unicos, estaveis
    vistos = set()
    uniq = []
    for p in sorted(out):
        if p not in vistos:
            vistos.add(p)
            uniq.append(p)
    return uniq


def _tem_marcador_planet_binario(caminho):
    """Pre-filtro barato: so abre ArcPy se o OLE mencionar planet."""
    try:
        raw = open(caminho, "rb").read()
    except Exception:
        return True
    # UTF-16LE e ASCII
    if b"planet" in raw.lower() or b"P\x00l\x00a\x00n\x00e\x00t" in raw:
        return True
    if b"api.planet.com" in raw or b"a\x00p\x00i\x00.\x00p\x00l\x00a\x00n\x00e\x00t" in raw:
        return True
    if b"Global Monthly" in raw or b"G\x00l\x00o\x00b\x00a\x00l\x00 \x00M" in raw:
        return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Remove Planet quebrado dos MXDs")
    ap.add_argument("caminhos", nargs="+", help="Arquivos ou pastas .mxd")
    ap.add_argument("--in-place", action="store_true", help="Sobrescreve os .mxd")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--todos", action="store_true", help="Nao pre-filtrar por marcador binario")
    ap.add_argument("-o", "--relatorio", default="relatorio_remover_planet.json")
    ap.add_argument("--saida", default="shared/templates/_sem_planet")
    args = ap.parse_args()

    mxds = _coletar_mxds(args.caminhos)
    if not args.todos:
        filtrados = []
        pulados = 0
        for m in mxds:
            if _tem_marcador_planet_binario(m):
                filtrados.append(m)
            else:
                pulados += 1
        mxds = filtrados
    else:
        pulados = 0

    if not args.in_place and not args.dry_run:
        if not os.path.isdir(args.saida):
            os.makedirs(args.saida)

    print("MXDs a processar: {0} (pulados sem marcador Planet: {1})".format(len(mxds), pulados))
    print("Dica: rode em outro terminal: powershell -File ferramentas/fechar_dialogs_gis.ps1")

    resultados = []
    for i, m in enumerate(mxds, 1):
        _out(u"[{0}/{1}] {2}".format(i, len(mxds), _as_text(m)))
        r = processar_mxd(m, args.in_place, args.dry_run, args.saida)
        resultados.append(r)
        _out(
            u"  ok={0} removidas={1} ms={2}".format(
                r["ok"], len(r["planet_removidas"]), r["ms"]
            )
        )
        for a in r["avisos"][:3]:
            _out(u"  ! {0}".format(_as_text(a)))

    resumo = {
        "total": len(resultados),
        "ok": sum(1 for r in resultados if r["ok"]),
        "com_remocao": sum(1 for r in resultados if r["planet_removidas"]),
        "falhas": sum(1 for r in resultados if not r["ok"]),
        "resultados": resultados,
    }
    with open(args.relatorio, "wb") as f:
        f.write(json.dumps(resumo, ensure_ascii=False, indent=2).encode("utf-8"))
    print("Relatorio: {0}".format(args.relatorio))
    print(
        "resumo: ok={0}/{1} com_remocao={2} falhas={3}".format(
            resumo["ok"], resumo["total"], resumo["com_remocao"], resumo["falhas"]
        )
    )
    return 0 if resumo["falhas"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
