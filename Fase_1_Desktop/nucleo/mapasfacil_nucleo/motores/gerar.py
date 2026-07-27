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
from mapasfacil_nucleo import jobs
from mapasfacil_nucleo.workspace import watcher as workspace_watcher
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


def _escala_numerica(escala: Any) -> float | None:
    """`MapSpec.escala` aceita número **ou** `"auto"` (plano 02) — só o número
    vira patch de escala no `.mxd`.

    `"auto"` significa "deixe o data frame como o template define"; tratar como
    número derrubava `mapa.gerar` com `ValueError` sem código — e `"auto"` é
    justamente o default dos modelos da galeria.
    """
    if escala is None or isinstance(escala, bool):
        return None
    if isinstance(escala, (int, float)):
        return float(escala)
    texto = str(escala).strip()
    if not texto or texto.lower() == "auto":
        return None
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return None


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

    Durante o job o watcher (A12) ignora pastas de saída para não emitir
    `workspace.mudou` a cada PNG/PDF intermediário.
    """
    prog = progresso or RastreadorProgresso()

    resultado_val = validar(mapspec, fontes_locais=frozenset(fontes_idx))
    if not resultado_val["valido"]:
        primeiro = resultado_val["erros"][0]
        raise ErroNucleo(primeiro["codigo"], primeiro["mensagem"], {"erros": resultado_val["erros"]})
    jobs.verificar_nao_cancelado(prog.job_id)
    prog.concluir("validando_spec")

    workspace_watcher.pausar_pastas_saida(True)
    try:
        resultado = _gerar_mapa_corpo(
            mapspec,
            guard,
            fontes_idx,
            comparar_baseline=comparar_baseline,
            recibo=recibo,
            prog=prog,
        )
        if prog.job_id:
            resultado["job_id"] = prog.job_id
        return resultado
    finally:
        workspace_watcher.pausar_pastas_saida(False)


def _gerar_mapa_corpo(
    mapspec: dict[str, Any],
    guard: WorkspaceGuard,
    fontes_idx: dict[str, str],
    *,
    comparar_baseline: bool,
    recibo: dict[str, Any] | None,
    prog: RastreadorProgresso,
) -> dict[str, Any]:
    saidas = mapspec.get("saidas") or ["pdf"]
    saida_cfg = mapspec.get("saida") or {}
    pasta_shp = saida_cfg.get("materializar_camadas_em", "SHP")

    artefatos: dict[str, Any] = {}
    avisos: list[str] = []
    resultado: dict[str, Any] = {"artefatos": artefatos, "avisos": avisos}

    def _avisar(codigo: str, mensagens: Any) -> None:
        """Aviso não-fatal: entra no `validacao.json` **e** sai como evento `aviso`.

        Um lugar só para os dois destinos — antes o aviso ficava só no relatório
        e a UI nunca ficava sabendo enquanto o job rodava.
        """
        lista = [mensagens] if isinstance(mensagens, str) else list(mensagens or [])
        for mensagem in lista:
            texto = str(mensagem).strip()
            if not texto:
                continue
            avisos.append(texto)
            prog.aviso(codigo, texto)

    prog.log(
        f"job iniciado · template={mapspec.get('template') or '(nenhum)'} "
        f"· saidas={','.join(saidas)}"
    )

    ordem_por_camada = {
        c.get("id"): c.get("ordem") for c in mapspec.get("camadas") or [] if c.get("id")
    }

    def _camada_pronta(camada_id: str, i: int, total: int, destino_rel: str) -> None:
        """Uma camada materializada: `job.progresso` (item) + artefato `camada`."""
        prog.item("resolvendo_camadas_locais", camada_id, indice=i, total=total)
        prog.artefato(
            "camada",
            caminho=destino_rel,
            etapa="resolvendo_camadas_locais",
            raiz=guard.raiz,
            camada_id=camada_id,
            ordem=ordem_por_camada.get(camada_id),
        )

    precisa_shp = bool(saida_cfg.get("materializar_camadas_em")) or "mxd" in saidas
    if precisa_shp:
        jobs.verificar_nao_cancelado(prog.job_id)
        materializacao = materializar_camadas_locais(
            mapspec,
            guard=guard,
            fontes_idx=fontes_idx,
            pasta_shp=pasta_shp,
            ao_materializar=_camada_pronta,
        )
        artefatos["materializacao"] = materializacao
        prog.log(
            f"camadas locais materializadas em {pasta_shp}/: "
            f"{len(materializacao.get('materializados') or [])}"
        )
        _avisar("NU-121", materializacao.get("avisos", []))
    prog.concluir_se_pendente("resolvendo_camadas_locais")

    # Camadas externas (WFS/WMS) ainda não são resolvidas em runtime — `camada.resolver`
    # é R21/A13. A etapa existe no contrato e fecha sem `item` enquanto não há download.
    jobs.verificar_nao_cancelado(prog.job_id)
    prog.concluir_se_pendente("baixando_externas")

    # Quantitativos cedo: alimentam .xlsx, PNG e overlay no PDF nativo (F1-08).
    precisa_quant = (
        "xlsx" in saidas
        or "png" in saidas
        or bool(mapspec.get("tabela"))
        or bool((mapspec.get("elementos_layout") or {}).get("tabela"))
    )
    if precisa_quant:
        jobs.verificar_nao_cancelado(prog.job_id)
        quant = calcular_quantitativos(mapspec, guard=guard, fontes_idx=fontes_idx)
        artefatos["quantitativos"] = quant
        resultado["quantitativos"] = quant
        prog.log(f"quantitativos calculados · total {quant.get('total_geral')} ha")
        _avisar("NU-122", quant.get("avisos", []))
    prog.concluir("calculando_quantitativos")

    # PNG antes do PDF para permitir overlay (F1-05 / F1-08).
    precisa_png = "png" in saidas or bool((mapspec.get("elementos_layout") or {}).get("tabela"))
    png_path: Path | None = None
    if precisa_png:
        jobs.verificar_nao_cancelado(prog.job_id)
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
        prog.artefato("tabela_png", caminho=rel_png, etapa="gerando_tabela", raiz=guard.raiz)
        prog.log(f"tabela PNG gerada · {meta_png.get('dpi_efetivo')} dpi · {rel_png}")
        if not meta_png.get("ok_dpi"):
            _avisar(
                "NU-123",
                f"PNG da tabela com dpi efetivo {meta_png.get('dpi_efetivo')} (alvo ≥ 600).",
            )
    prog.concluir("gerando_tabela")

    # O `.mxd` vem depois da tabela para a execução seguir a ordem das etapas do
    # contrato (preparando_template → aplicando_layout → salvando_mxd).
    if "mxd" in saidas:
        jobs.verificar_nao_cancelado(prog.job_id)
        if not mapspec.get("template"):
            raise ErroNucleo("NU-205", "MapSpec pede .mxd mas não informa template.")
        bbox = _resolver_bbox_utm(mapspec, guard=guard, fontes_idx=fontes_idx)
        escala = _escala_numerica(mapspec.get("escala"))

        # T1 (ArcMap): minimapa IBGE + queries + retângulo/L. Fallback T2 (patch).
        mxd_info = None
        try:
            from mapasfacil_nucleo.motores.minimapa_job import tentar_gerar_mxd_arcpy

            mxd_info = tentar_gerar_mxd_arcpy(
                mapspec,
                guard=guard,
                fontes_idx=fontes_idx,
                bbox=bbox,
                escala=escala,
                pasta_shp=pasta_shp,
            )
        except ErroNucleo as exc:
            _avisar("NU-127", f"ArcPy/minimapa indisponível ({exc.codigo}): {exc.mensagem}")
            mxd_info = None
        except Exception as exc:  # noqa: BLE001 — fallback T2
            _avisar("NU-127", f"ArcPy/minimapa falhou: {exc}")
            mxd_info = None

        if mxd_info is None:
            mxd_info = gerar_mxd_t2(
                mapspec,
                guard=guard,
                bbox=bbox,
                escala=escala,
                ao_etapa=prog.concluir,
            )
            if (mapspec.get("elementos_layout") or {}).get("minimapa"):
                _avisar(
                    "NU-128",
                    "Minimapa IBGE (query/retângulo/linha L) exige ArcMap — "
                    "MXD gerado por patch T2 sem reposicionar o inset.",
                )
        artefatos["mxd"] = mxd_info
        resultado["mxd"] = mxd_info["mxd"]
        prog.log(
            f".mxd gerado por '{mxd_info.get('motor')}' "
            f"(confiança {mxd_info.get('confianca')}) · {mxd_info['mxd']}"
        )
        _avisar("NU-124", mxd_info.get("patch", {}).get("avisos", []))
        if mxd_info.get("minimapa"):
            prog.log(
                f"minimapa · município={mxd_info['minimapa'].get('municipio')} "
                f"· graficos={mxd_info['minimapa'].get('graficos')}"
            )
    prog.concluir_se_pendente("preparando_template")
    prog.concluir_se_pendente("aplicando_layout")
    prog.concluir_se_pendente("salvando_mxd")

    if "pdf" in saidas:
        jobs.verificar_nao_cancelado(prog.job_id)
        pdf_path, pdf_artefatos = gerar_pdf_minimo(
            mapspec,
            guard=guard,
            fontes_idx=fontes_idx,
            png_tabela=png_path,
            # Sem canal de eventos ninguém vê preview: não rasteriza (custo à toa).
            ao_preview=(
                (
                    lambda caminho, etapa: prog.artefato(
                        "preview_png",
                        caminho=caminho,
                        etapa=etapa,
                        raiz=guard.raiz,
                        com_pct=True,
                    )
                )
                if prog.emite_eventos
                else None
            ),
        )
        artefatos.update(pdf_artefatos)
        resultado["pdf"] = pdf_artefatos["pdf"]
        prog.log(f"PDF exportado · {pdf_artefatos['pdf']}")
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
                        _avisar(
                            "NU-125",
                            f"Diff raster {comp['diferenca_pct']:.2f}% "
                            f"(tolerância {comp['tolerancia_pct']}%).",
                        )
    prog.concluir("exportando_pdf")
    if resultado.get("pdf"):
        # Depois de fechar a etapa: o `pct` do artefato é o do job já com o PDF
        # pronto (90), não o de antes de exportar.
        prog.artefato(
            "pdf",
            caminho=resultado["pdf"],
            etapa="exportando_pdf",
            raiz=guard.raiz,
            com_pct=True,
        )

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
        prog.log(f"planilha exportada · {resultado['xlsx']}")
        _avisar("NU-126", conf.get("avisos", []))

    relatorio = _montar_validacao_job(mapspec, artefatos, avisos)
    pasta_saida = guard.resolver((mapspec.get("saida") or {}).get("pasta", "Mapas"), escrita=True)
    nome_base = (mapspec.get("saida") or {}).get("nome_base", "mapa")
    json_path = salvar_validacao(pasta_saida / f"{nome_base}_validacao.json", relatorio)
    resultado["validacao"] = str(json_path.relative_to(guard.raiz))
    resultado["validacao_dados"] = relatorio
    prog.log(f"job concluído · {len(avisos)} aviso(s) · {resultado['validacao']}")
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
