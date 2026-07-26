from __future__ import annotations

from pathlib import Path
from typing import Any

from pyproj import Transformer

from mapasfacil_nucleo.camadas.materializar import materializar_camadas_locais
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo.bbox_shp import ler_bbox_header_shp
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores.manifesto import obter_template
from mapasfacil_nucleo.motores.nativo import gerar_pdf_minimo
from mapasfacil_nucleo.motores.patch_mxd import gerar_mxd_t2
from mapasfacil_nucleo.progresso import RastreadorProgresso
from mapasfacil_nucleo.quantitativos.calcular import calcular as calcular_quantitativos
from mapasfacil_nucleo.quantitativos.png_tabela import renderizar_png_tabela
from mapasfacil_nucleo.quantitativos.xlsx import exportar_xlsx
from mapasfacil_nucleo.validacao.comparar_pdf import comparar_pdf, resolver_baseline_template
from mapasfacil_nucleo.validacao.relatorio import gerar as gerar_validacao
from mapasfacil_nucleo.validacao.relatorio import salvar as salvar_validacao
from mapasfacil_nucleo.workspace.shapefile import inspecionar


def _resolver_fonte_local(fonte: str, fontes_idx: dict[str, str]) -> str | None:
    if not fonte.startswith("local."):
        return None
    chave = fonte.split(".", 1)[1]
    return fontes_idx.get(chave) or fontes_idx.get(chave.upper())


def _resolver_bbox_utm(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
) -> tuple[float, float, float, float] | None:
    extent = mapspec.get("extent")
    if isinstance(extent, dict):
        return (
            float(extent["xmin"]),
            float(extent["ymin"]),
            float(extent["xmax"]),
            float(extent["ymax"]),
        )

    geometria = (mapspec.get("imovel") or {}).get("geometria", "local.ATP")
    rel = _resolver_fonte_local(geometria, fontes_idx)
    if not rel:
        for camada in mapspec.get("camadas", []):
            rel = _resolver_fonte_local(camada.get("fonte", ""), fontes_idx)
            if rel:
                break
    if not rel:
        return None

    caminho = guard.resolver(rel)
    meta = inspecionar(caminho)
    bbox = meta.bbox
    xmin, ymin, xmax, ymax = bbox["xmin"], bbox["ymin"], bbox["xmax"], bbox["ymax"]

    template_id = mapspec.get("template")
    if not template_id:
        return xmin, ymin, xmax, ymax

    tpl = obter_template(str(template_id))
    crs_dest = tpl.get("crs_data_frame", mapspec.get("crs", "EPSG:31982"))
    epsg_dest = int(str(crs_dest).replace("EPSG:", ""))
    epsg_orig = meta.crs.get("epsg") or 31982
    if epsg_orig == epsg_dest:
        return xmin, ymin, xmax, ymax

    transformer = Transformer.from_crs(
        f"EPSG:{epsg_orig}",
        f"EPSG:{epsg_dest}",
        always_xy=True,
    )
    xs = [xmin, xmin, xmax, xmax]
    ys = [ymin, ymax, ymin, ymax]
    tx, ty = transformer.transform(xs, ys)
    return min(tx), min(ty), max(tx), max(ty)


def _recibo_do_guard(guard: WorkspaceGuard) -> dict[str, Any] | None:
    """Lê o recibo CAR do workspace, se o índice o apontar."""
    from mapasfacil_nucleo.workspace import indice as indice_mod
    from mapasfacil_nucleo.workspace.recibo_car import parsear

    try:
        idx = indice_mod.varrer(guard.raiz, guard)
    except Exception:
        return None
    rel = idx.get("recibo_car")
    if not rel:
        return None
    try:
        return parsear(guard.resolver(rel)).para_dict()
    except ErroNucleo:
        return None


def gerar_mapa(
    mapspec: dict[str, Any],
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    *,
    comparar_baseline: bool = False,
    recibo: dict[str, Any] | None = None,
    progresso: RastreadorProgresso | None = None,
) -> dict[str, Any]:
    """Gera os artefatos do MapSpec, reportando as 10 etapas de `job.progresso`.

    A ordem de execução segue a ordem das etapas do contrato (F1-01): sem
    `progresso`, nada é emitido — o trabalho é o mesmo.
    """
    prog = progresso or RastreadorProgresso()

    resultado_val = validar(mapspec, fontes_locais=frozenset(fontes_idx))
    if not resultado_val["valido"]:
        primeiro = resultado_val["erros"][0]
        raise ErroNucleo(primeiro["codigo"], primeiro["mensagem"], {"erros": resultado_val["erros"]})
    prog.concluir("validando_spec")

    saidas = mapspec.get("saidas") or ["pdf"]
    saida_cfg = mapspec.get("saida") or {}
    pasta_shp = saida_cfg.get("materializar_camadas_em", "SHP")

    artefatos: dict[str, Any] = {}
    avisos: list[str] = []
    resultado: dict[str, Any] = {"artefatos": artefatos, "avisos": avisos}

    precisa_shp = bool(saida_cfg.get("materializar_camadas_em")) or "mxd" in saidas
    if precisa_shp:
        materializacao = materializar_camadas_locais(
            mapspec,
            guard=guard,
            fontes_idx=fontes_idx,
            pasta_shp=pasta_shp,
            ao_materializar=lambda camada_id, i, total: prog.item(
                "resolvendo_camadas_locais", camada_id, indice=i, total=total
            ),
        )
        artefatos["materializacao"] = materializacao
        avisos.extend(materializacao.get("avisos", []))
    prog.concluir_se_pendente("resolvendo_camadas_locais")

    # Camadas externas (WFS/WMS) ainda não são resolvidas em runtime — `camada.resolver`
    # é R21/A13. A etapa existe no contrato e fecha sem `item` enquanto não há download.
    prog.concluir_se_pendente("baixando_externas")

    # Quantitativos cedo: alimentam .xlsx, PNG e overlay no PDF nativo (F1-08).
    precisa_quant = (
        "xlsx" in saidas
        or "png" in saidas
        or bool(mapspec.get("tabela"))
        or bool((mapspec.get("elementos_layout") or {}).get("tabela"))
    )
    if precisa_quant:
        quant = calcular_quantitativos(mapspec, guard=guard, fontes_idx=fontes_idx)
        artefatos["quantitativos"] = quant
        resultado["quantitativos"] = quant
        avisos.extend(quant.get("avisos", []))
    prog.concluir("calculando_quantitativos")

    # PNG antes do PDF para permitir overlay (F1-05 / F1-08).
    precisa_png = "png" in saidas or bool((mapspec.get("elementos_layout") or {}).get("tabela"))
    png_path: Path | None = None
    if precisa_png:
        quant = artefatos.get("quantitativos") or calcular_quantitativos(
            mapspec, guard=guard, fontes_idx=fontes_idx
        )
        artefatos["quantitativos"] = quant
        pasta_saida = guard.resolver((mapspec.get("saida") or {}).get("pasta", "Mapas"), escrita=True)
        nome_base = (mapspec.get("saida") or {}).get("nome_base", "mapa")
        png_path = pasta_saida / "recursos" / "tabela_quantitativos.png"
        meta_png = renderizar_png_tabela(quant, png_path)
        rel_png = str(png_path.relative_to(guard.raiz))
        resultado["png_tabela"] = rel_png
        artefatos["png_tabela"] = {**meta_png, "png": rel_png}
        if not meta_png.get("ok_dpi"):
            avisos.append(
                f"PNG da tabela com dpi efetivo {meta_png.get('dpi_efetivo')} "
                "(alvo ≥ 600)."
            )
    prog.concluir("gerando_tabela")

    # O `.mxd` vem depois da tabela para a execução seguir a ordem das etapas do
    # contrato (preparando_template → aplicando_layout → salvando_mxd).
    if "mxd" in saidas:
        if not mapspec.get("template"):
            raise ErroNucleo("NU-205", "MapSpec pede .mxd mas não informa template.")
        bbox = _resolver_bbox_utm(mapspec, guard=guard, fontes_idx=fontes_idx)
        escala = mapspec.get("escala")
        mxd_info = gerar_mxd_t2(
            mapspec,
            guard=guard,
            bbox=bbox,
            escala=float(escala) if escala is not None else None,
            ao_etapa=prog.concluir,
        )
        artefatos["mxd"] = mxd_info
        resultado["mxd"] = mxd_info["mxd"]
        avisos.extend(mxd_info.get("patch", {}).get("avisos", []))
    prog.concluir_se_pendente("preparando_template")
    prog.concluir_se_pendente("aplicando_layout")
    prog.concluir_se_pendente("salvando_mxd")

    if "pdf" in saidas:
        pdf_path, pdf_artefatos = gerar_pdf_minimo(
            mapspec,
            guard=guard,
            fontes_idx=fontes_idx,
            png_tabela=png_path,
        )
        artefatos.update(pdf_artefatos)
        resultado["pdf"] = pdf_artefatos["pdf"]
        if pdf_artefatos.get("tabela_sobreposta"):
            resultado["tabela_sobreposta"] = True

        if comparar_baseline or mapspec.get("validacao", {}).get("comparar_baseline"):
            template_id = mapspec.get("template")
            if isinstance(template_id, str):
                baseline = resolver_baseline_template(template_id)
                if baseline is not None:
                    comp = comparar_pdf(pdf_path, baseline)
                    artefatos["comparacao_baseline"] = comp
                    resultado["comparacao_baseline"] = comp
                    if not comp["ok"]:
                        avisos.append(
                            f"Diff raster {comp['diferenca_pct']:.2f}% "
                            f"(tolerância {comp['tolerancia_pct']}%)."
                        )
    prog.concluir("exportando_pdf")

    if "xlsx" in saidas:
        quant = artefatos.get("quantitativos") or calcular_quantitativos(
            mapspec, guard=guard, fontes_idx=fontes_idx
        )
        recibo_efetivo = recibo if recibo is not None else _recibo_do_guard(guard)
        pasta_saida = guard.resolver((mapspec.get("saida") or {}).get("pasta", "Mapas"), escrita=True)
        nome_base = (mapspec.get("saida") or {}).get("nome_base", "mapa")
        xlsx_path = pasta_saida / f"{nome_base}_Quantitativos.xlsx"
        exportar_xlsx(quant, xlsx_path, recibo=recibo_efetivo)
        resultado["xlsx"] = str(xlsx_path.relative_to(guard.raiz))
        artefatos["xlsx"] = resultado["xlsx"]
        from mapasfacil_nucleo.quantitativos.conferencia import montar_conferencia

        conf = montar_conferencia(quant, recibo_efetivo)
        artefatos["conferencia"] = conf
        resultado["conferencia"] = conf
        avisos.extend(conf.get("avisos", []))

    relatorio = _montar_validacao_job(mapspec, artefatos, avisos)
    pasta_saida = guard.resolver((mapspec.get("saida") or {}).get("pasta", "Mapas"), escrita=True)
    nome_base = (mapspec.get("saida") or {}).get("nome_base", "mapa")
    json_path = salvar_validacao(pasta_saida / f"{nome_base}_validacao.json", relatorio)
    resultado["validacao"] = str(json_path.relative_to(guard.raiz))
    resultado["validacao_dados"] = relatorio
    prog.concluir("validando_saida")

    return resultado


def _montar_validacao_job(
    mapspec: dict[str, Any],
    artefatos: dict[str, Any],
    avisos: list[str],
) -> dict[str, Any]:
    mxd_info = artefatos.get("mxd") or {}
    pdf_val = artefatos.get("validacao_dados") or {}
    motor = mxd_info.get("motor") or pdf_val.get("motor") or "nativo"
    confianca = mxd_info.get("confianca") or pdf_val.get("confianca") or "estrutural"

    hard = list((pdf_val.get("checks") or {}).get("hard") or [])
    soft = list((pdf_val.get("checks") or {}).get("soft") or [])
    if "mxd" in (mapspec.get("saidas") or []):
        hard.append(
            {
                "id": "H01",
                "ok": bool(mxd_info.get("mxd")),
                "mensagem": f"MXD gerado ({mxd_info.get('motor', '?')})",
            }
        )
    soft.append({"id": "A01", "ok": not avisos, "mensagem": "; ".join(avisos) or "sem avisos"})
    comp = artefatos.get("comparacao_baseline")
    if comp:
        soft.append(
            {
                "id": "B09",
                "ok": comp["ok"],
                "mensagem": (
                    f"Diff raster {comp['diferenca_pct']:.4f}% "
                    f"(tolerância {comp['tolerancia_pct']}%)"
                ),
            }
        )
    if artefatos.get("png_tabela") and mapspec.get("elementos_layout", {}).get("tabela"):
        soft.append(
            {
                "id": "N01",
                "ok": bool(artefatos.get("tabela_sobreposta") or pdf_val.get("tabela_sobreposta")),
                "mensagem": "Overlay da tabela no PDF nativo",
            }
        )

    rel = gerar_validacao(motor=motor, confianca=confianca, checks_hard=hard, checks_soft=soft)
    rel["template"] = mapspec.get("template")
    rel["tier"] = "T2" if motor in ("patch", "copia_template") else motor
    return rel
