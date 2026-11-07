from __future__ import annotations

from pathlib import Path
from typing import Any

import pyproj
import shapefile
from shapely.geometry import MultiPolygon, Polygon, mapping, shape
from shapely.ops import transform as shapely_transform, unary_union

from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace, _resolver_caminho_seguro, _resolver_saida_nova
from mapasfacil_nucleo.protocolo import Emissor


def _ler_epsg_prj(caminho_shp: Path) -> int | None:
    prj = caminho_shp.with_suffix(".prj")
    if not prj.exists():
        return None
    try:
        wkt = prj.read_text(encoding="utf-8", errors="ignore").strip()
        if not wkt:
            return None
        crs = pyproj.CRS.from_user_input(wkt)
        return crs.to_epsg()
    except Exception:
        return None


def _garantir_prj(caminho_shp: Path, epsg: int) -> None:
    prj = caminho_shp.with_suffix(".prj")
    try:
        crs = pyproj.CRS.from_epsg(epsg)
        prj.write_text(crs.to_wkt(), encoding="utf-8")
    except Exception:
        pass


def registrar_tools_geo(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="geo_inspecionar",
        descricao="Inspeciona informações estruturais de uma camada vetorial (EPSG, bbox, campos, feições).",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo do arquivo .shp."}
            },
            "required": ["caminho"],
            "additionalProperties": False,
        },
    )
    def tool_geo_inspecionar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            alvo = _resolver_caminho_seguro(args.get("caminho", ""), ws_root)
            if not alvo.exists():
                return _erro("NU-040", f"Arquivo '{alvo.name}' não existe.")

            with shapefile.Reader(str(alvo)) as r:
                total_feicoes = len(r)
                tipo_geom = r.shapeTypeName
                bbox = list(r.bbox) if total_feicoes > 0 else []
                campos = [
                    {"nome": f[0], "tipo": f[1], "tamanho": f[2], "decimais": f[3]}
                    for f in r.fields[1:]  # primeiro é campo de deleção do dbf
                ]
                amostra = []
                for rec in r.iterRecords():
                    amostra.append(rec.as_dict())
                    if len(amostra) >= 3:
                        break

            epsg = _ler_epsg_prj(alvo)
            return _ok(
                {
                    "caminho": alvo.relative_to(ws_root).as_posix(),
                    "epsg": epsg,
                    "total_feicoes": total_feicoes,
                    "tipo_geometria": tipo_geom,
                    "bbox": bbox,
                    "campos": campos,
                    "amostra": amostra,
                }
            )
        except Exception as exc:
            return _erro("GEO-001", f"Falha ao inspecionar shapefile: {exc}")

    @registro.ferramenta(
        nome="geo_area",
        descricao="Calcula a área total e por feição de polígonos em hectares (ha), m² ou km².",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo do arquivo .shp."},
                "unidade": {
                    "type": "string",
                    "enum": ["ha", "m2", "km2"],
                    "description": "Unidade de saída (padrão: 'ha').",
                },
            },
            "required": ["caminho"],
            "additionalProperties": False,
        },
    )
    def tool_geo_area(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            alvo = _resolver_caminho_seguro(args.get("caminho", ""), ws_root)
            unidade = args.get("unidade", "ha").lower()

            epsg = _ler_epsg_prj(alvo)
            transformer = None
            if epsg is not None:
                crs = pyproj.CRS.from_epsg(epsg)
                if crs.is_geographic:
                    # Projetar para UTM ou Albers/SIRGAS2000
                    # Para MT/Brasil Centro-Oeste, SIRGAS UTM 21S (31981) como referência métrica
                    transformer = pyproj.Transformer.from_crs(crs, pyproj.CRS.from_epsg(31981), always_xy=True)

            with shapefile.Reader(str(alvo)) as r:
                poligonos = []
                for s in r.shapes():
                    if s.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM):
                        geom = shape(s.__geo_interface__)
                        if transformer is not None:
                            geom = shapely_transform(transformer.transform, geom)
                        poligonos.append(geom)

            if not poligonos:
                return _ok({"area_total": 0.0, "unidade": unidade, "total_poligonos": 0})

            area_m2_total = sum(p.area for p in poligonos)
            if unidade == "ha":
                fator = 10_000.0
            elif unidade == "km2":
                fator = 1_000_000.0
            else:
                fator = 1.0

            area_calculada = round(area_m2_total / fator, 4)
            return _ok(
                {
                    "caminho": alvo.relative_to(ws_root).as_posix(),
                    "area_total": area_calculada,
                    "unidade": unidade,
                    "total_poligonos": len(poligonos),
                }
            )
        except Exception as exc:
            return _erro("GEO-002", f"Falha ao calcular área: {exc}")

    @registro.ferramenta(
        nome="geo_recortar",
        descricao="Recorta uma camada vetorial pelos limites de uma camada máscara (clip).",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "camada_entrada": {"type": "string", "description": "Shapefile a recortar."},
                "camada_mascara": {"type": "string", "description": "Shapefile delimitador."},
                "camada_saida": {"type": "string", "description": "Shapefile de destino."},
            },
            "required": ["camada_entrada", "camada_mascara", "camada_saida"],
            "additionalProperties": False,
        },
    )
    def tool_geo_recortar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            p_entrada = _resolver_caminho_seguro(args["camada_entrada"], ws_root)
            p_mascara = _resolver_caminho_seguro(args["camada_mascara"], ws_root)
            p_saida = _resolver_saida_nova(args["camada_saida"], ws_root)

            # Carregar máscara
            with shapefile.Reader(str(p_mascara)) as r_m:
                geoms_m = [shape(s.__geo_interface__) for s in r_m.shapes() if s.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM)]
            if not geoms_m:
                return _erro("GEO-003", "Camada máscara não contém polígonos válidos.")
            mascara_uniao = unary_union(geoms_m)

            # Processar entrada
            p_saida.parent.mkdir(parents=True, exist_ok=True)
            with shapefile.Reader(str(p_entrada)) as r_e:
                w = shapefile.Writer(str(p_saida.with_suffix("")), shapeType=shapefile.POLYGON)
                for f in r_e.fields[1:]:
                    w.field(f[0], f[1], size=f[2], decimal=f[3])

                feicoes_recortadas = 0
                for s_rec in r_e.shapeRecords():
                    geom = shape(s_rec.shape.__geo_interface__)
                    intersecao = geom.intersection(mascara_uniao)
                    if not intersecao.is_empty:
                        if isinstance(intersecao, (Polygon, MultiPolygon)):
                            w.shape(intersecao)
                            w.record(*s_rec.record)
                            feicoes_recortadas += 1
                w.close()

            # Copiar .prj
            epsg = _ler_epsg_prj(p_entrada)
            if epsg is not None:
                _garantir_prj(p_saida, epsg)

            rel_saida = p_saida.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel_saida, "acao": "criacao"})

            return _ok(
                {
                    "camada_saida": rel_saida,
                    "feicoes_recortadas": feicoes_recortadas,
                }
            )
        except Exception as exc:
            return _erro("GEO-004", f"Falha ao recortar camada: {exc}")

    @registro.ferramenta(
        nome="geo_dissolver",
        descricao="Dissolve (une) geometrias de uma camada vetorial em uma única feição.",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "camada_entrada": {"type": "string", "description": "Shapefile de entrada."},
                "camada_saida": {"type": "string", "description": "Shapefile de destino."},
            },
            "required": ["camada_entrada", "camada_saida"],
            "additionalProperties": False,
        },
    )
    def tool_geo_dissolver(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            p_entrada = _resolver_caminho_seguro(args["camada_entrada"], ws_root)
            p_saida = _resolver_saida_nova(args["camada_saida"], ws_root)

            with shapefile.Reader(str(p_entrada)) as r_e:
                geoms = [shape(s.__geo_interface__) for s in r_e.shapes() if s.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM)]

            if not geoms:
                return _erro("GEO-005", "Nenhum polígono encontrado para dissolver.")

            uniao = unary_union(geoms)
            p_saida.parent.mkdir(parents=True, exist_ok=True)
            with shapefile.Writer(str(p_saida.with_suffix("")), shapeType=shapefile.POLYGON) as w:
                w.field("ID", "N")
                w.shape(uniao)
                w.record(1)

            epsg = _ler_epsg_prj(p_entrada)
            if epsg is not None:
                _garantir_prj(p_saida, epsg)

            rel_saida = p_saida.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel_saida, "acao": "criacao"})

            return _ok({"camada_saida": rel_saida, "feicoes_dissolvidas": 1})
        except Exception as exc:
            return _erro("GEO-006", f"Falha ao dissolver camada: {exc}")

    @registro.ferramenta(
        nome="geo_intersectar",
        descricao="Calcula a interseção espacial entre duas camadas vetoriais.",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "camada_a": {"type": "string", "description": "Primeira camada."},
                "camada_b": {"type": "string", "description": "Segunda camada."},
                "camada_saida": {"type": "string", "description": "Shapefile de destino."},
            },
            "required": ["camada_a", "camada_b", "camada_saida"],
            "additionalProperties": False,
        },
    )
    def tool_geo_intersectar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            p_a = _resolver_caminho_seguro(args["camada_a"], ws_root)
            p_b = _resolver_caminho_seguro(args["camada_b"], ws_root)
            p_saida = _resolver_saida_nova(args["camada_saida"], ws_root)

            with shapefile.Reader(str(p_b)) as r_b:
                geoms_b = [shape(s.__geo_interface__) for s in r_b.shapes() if s.shapeType in (shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM)]
            uniao_b = unary_union(geoms_b)

            p_saida.parent.mkdir(parents=True, exist_ok=True)
            with shapefile.Reader(str(p_a)) as r_a:
                w = shapefile.Writer(str(p_saida.with_suffix("")), shapeType=shapefile.POLYGON)
                for f in r_a.fields[1:]:
                    w.field(f[0], f[1], size=f[2], decimal=f[3])

                feicoes = 0
                for s_rec in r_a.shapeRecords():
                    geom = shape(s_rec.shape.__geo_interface__)
                    inter = geom.intersection(uniao_b)
                    if not inter.is_empty and isinstance(inter, (Polygon, MultiPolygon)):
                        w.shape(inter)
                        w.record(*s_rec.record)
                        feicoes += 1
                w.close()

            epsg = _ler_epsg_prj(p_a)
            if epsg is not None:
                _garantir_prj(p_saida, epsg)

            rel_saida = p_saida.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel_saida, "acao": "criacao"})

            return _ok({"camada_saida": rel_saida, "feicoes_intersecao": feicoes})
        except Exception as exc:
            return _erro("GEO-007", f"Falha ao intersectar camadas: {exc}")

    @registro.ferramenta(
        nome="geo_reprojetar",
        descricao="Reprojeta as geometrias de um shapefile para outro CRS/EPSG.",
        categoria="geo",
        parametros={
            "type": "object",
            "properties": {
                "camada_entrada": {"type": "string", "description": "Shapefile de origem."},
                "camada_saida": {"type": "string", "description": "Shapefile reprojetado."},
                "epsg_destino": {
                    "type": "integer",
                    "description": "Código EPSG do CRS de destino (ex.: 4674, 31981).",
                },
            },
            "required": ["camada_entrada", "camada_saida", "epsg_destino"],
            "additionalProperties": False,
        },
    )
    def tool_geo_reprojetar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            p_entrada = _resolver_caminho_seguro(args["camada_entrada"], ws_root)
            p_saida = _resolver_saida_nova(args["camada_saida"], ws_root)
            epsg_dest = int(args["epsg_destino"])

            epsg_orig = _ler_epsg_prj(p_entrada)
            if epsg_orig is None:
                return _erro("GEO-008", "Não foi possível determinar o EPSG de origem (.prj ausente ou inválido).")

            transformer = pyproj.Transformer.from_crs(
                pyproj.CRS.from_epsg(epsg_orig),
                pyproj.CRS.from_epsg(epsg_dest),
                always_xy=True,
            )

            p_saida.parent.mkdir(parents=True, exist_ok=True)
            with shapefile.Reader(str(p_entrada)) as r_e:
                w = shapefile.Writer(str(p_saida.with_suffix("")), shapeType=r_e.shapeType)
                for f in r_e.fields[1:]:
                    w.field(f[0], f[1], size=f[2], decimal=f[3])

                for s_rec in r_e.shapeRecords():
                    geom = shape(s_rec.shape.__geo_interface__)
                    geom_reproj = shapely_transform(transformer.transform, geom)
                    if isinstance(geom_reproj, Polygon):
                        from shapely.geometry.polygon import orient
                        geom_reproj = orient(geom_reproj, sign=-1.0)
                    elif isinstance(geom_reproj, MultiPolygon):
                        from shapely.geometry.polygon import orient
                        geom_reproj = MultiPolygon([orient(p, sign=-1.0) for p in geom_reproj.geoms])
                    w.shape(geom_reproj)
                    w.record(*s_rec.record)
                w.close()

            _garantir_prj(p_saida, epsg_dest)

            rel_saida = p_saida.relative_to(ws_root).as_posix()
            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel_saida, "acao": "criacao"})

            return _ok(
                {
                    "camada_saida": rel_saida,
                    "epsg_origem": epsg_orig,
                    "epsg_destino": epsg_dest,
                }
            )
        except Exception as exc:
            return _erro("GEO-009", f"Falha ao reprojetar camada: {exc}")
