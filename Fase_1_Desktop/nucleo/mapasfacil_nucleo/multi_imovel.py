"""Módulo multi-imóvel aditivo do Mapas Fácil.

Suporta a identificação, gestão e processamento de múltiplos imóveis
(múltiplos CARs, matrículas ou perímetros) dentro de um mesmo workspace ou MapSpec.

Mantém compatibilidade singular total com o modelo de imóvel único anterior.
"""

from __future__ import annotations

import copy
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pymupdf as fitz

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.quantitativos.xlsx import (
    COR_CABECALHO,
    COR_TITULO,
    COR_TOTAL,
    _BORDA_FINA,
    _larguras_colunas,
    _preencher_celula,
)
from mapasfacil_nucleo.workspace.recibo_car import eh_recibo_car, parsear


@dataclass
class Imovel:
    id: str
    nome: str
    car: str | None = None
    matricula: str | None = None
    area: float | None = None
    atp: str | None = None
    principal: bool = False
    municipio: dict[str, Any] | None = None
    geometria: str | None = None

    def para_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        dados.pop("cpf", None)
        return dados


def _limpar_id(texto: str) -> str:
    """Gera um identificador ASCII limpo."""
    s = re.sub(r"[^a-zA-Z0-9_-]+", "_", texto.strip().lower()).strip("_")
    return s or "imovel"


def _casar_atp_com_evidencia(
    r_item: dict[str, Any], candidatos_atp: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Busca correspondência entre recibo e ATP com evidência real (pasta em comum ou termos no nome/CAR).

    Nunca resolve por ordem arbitrária (evita falso emparelhamento).
    """
    if not r_item or not candidatos_atp:
        return None

    caminho_recibo = r_item.get("caminho", "")
    pasta_recibo = Path(caminho_recibo).parent.as_posix()
    dados_recibo = r_item.get("dados", {})
    nome_imovel = (dados_recibo.get("nome_imovel") or "").lower().strip()
    car_num = (dados_recibo.get("car_estadual") or dados_recibo.get("recibo_federal") or "").lower().strip()

    # Identidade explícita tem precedência. Pasta compartilhada com vários ATPs
    # não prova qual perímetro pertence ao recibo.
    tokens_ignorar = {"fazenda", "sitio", "lote", "chacara", "imovel", "car", "atp", "shp"}
    tokens_nome = [t for t in re.split(r"[^a-zA-Z0-9]+", nome_imovel)
                   if len(t) >= 4 and t not in tokens_ignorar]
    tokens_car = [t for t in re.split(r"[^a-zA-Z0-9]+", car_num)
                  if len(t) >= 4 and not re.fullmatch(r"(?:19|20)\d{2}", t)]
    for tokens in (tokens_car, tokens_nome):
        casados = [c for c in candidatos_atp
                   if tokens and any(t in c.get("caminho", "").lower() for t in tokens)]
        if len(casados) == 1:
            return casados[0]
        if len(casados) > 1:
            return None
    mesma_pasta = [c for c in candidatos_atp
                   if pasta_recibo != "." and Path(c.get("caminho", "")).parent.as_posix() == pasta_recibo]
    return mesma_pasta[0] if len(mesma_pasta) == 1 else None


def identificar_imoveis(
    raiz: Path | str,
    indice: dict[str, Any] | None = None,
    *,
    guard: WorkspaceGuard | None = None,
) -> list[dict[str, Any]]:
    """Identifica todos os imóveis presentes no workspace com base em evidências reais.

    Regra de integridade:
    - Nunca atribui CAR ou área de um imóvel a outro sem evidência;
    - Ambiguidades de recibo/ATP não são resolvidas por ordem arbitrária.
    """
    raiz_path = Path(raiz)
    guard = guard or WorkspaceGuard(raiz_path)

    if indice is None:
        from mapasfacil_nucleo.workspace.indice import varrer

        indice = varrer(raiz_path, guard)

    def somente_fontes(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Reabrir um projeto não promove PDFs/espelhos de entrega a novos CARs.
        import hashlib
        tem_entrada = (raiz_path / 'entrada').is_dir()
        candidatos = []
        for item in itens:
            partes = Path(str(item.get('caminho') or '')).parts
            if not partes or partes[0].lower() in {'mapas', '.servidor', '.agente', '.estado', 'entrada.anterior'}:
                continue
            if tem_entrada and partes[0].lower() != 'entrada':
                continue
            candidatos.append(item)

        def assinatura(item: dict[str, Any]) -> tuple[str, str] | None:
            try:
                alvo = guard.resolver(item['caminho'])
                with alvo.open('rb') as f:
                    return alvo.suffix.lower(), hashlib.file_digest(f, 'sha256').hexdigest()
            except (OSError, KeyError):
                return None

        # SHP/ é também a cópia portátil do motor. Só a deduplica contra uma
        # fonte idêntica fora dela; dois perímetros originais iguais continuam distintos.
        originais = {sig for item in candidatos
                     if Path(item['caminho']).parts[0].lower() != 'shp'
                     if (sig := assinatura(item)) is not None}
        return [item for item in candidatos
                if Path(item['caminho']).parts[0].lower() != 'shp'
                or assinatura(item) not in originais]

    # 1. Coleta recibos CAR
    recibos_info: list[dict[str, Any]] = []
    pdfs = somente_fontes(indice.get("pdfs", []))
    for p in pdfs:
        caminho_rel = p.get("caminho")
        if not caminho_rel:
            continue
        try:
            caminho_abs = guard.resolver(caminho_rel)
            if eh_recibo_car(caminho_abs):
                recibo_obj = parsear(caminho_abs)
                recibos_info.append(
                    {
                        "caminho": caminho_rel,
                        "dados": recibo_obj.para_dict(),
                    }
                )
        except Exception:
            continue

    # 2. Coleta shapefiles candidatos a ATP / perímetro
    shapefiles = somente_fontes(indice.get("shapefiles", []))
    atps: list[dict[str, Any]] = []
    outros_shps: list[dict[str, Any]] = []
    for shp in shapefiles:
        papel = str(shp.get("papel") or "").upper()
        id_local = str(shp.get("id_local") or "").upper()
        caminho = str(shp.get("caminho") or "")

        # Identifica se é ATP ou perímetro do imóvel
        if papel in {"ATP", "AIR"} or "ATP" in id_local or "LOTE" in id_local or "IMOVEL" in id_local:
            atps.append(shp)
        else:
            outros_shps.append(shp)

    imoveis: list[Imovel] = []

    # Caso A: múltiplos recibos encontrados
    if len(recibos_info) > 1:
        atps_disponiveis = list(atps)
        for idx, r_item in enumerate(recibos_info, start=1):
            dados = r_item["dados"]
            car = dados.get("car_estadual") or dados.get("recibo_federal")
            nome = dados.get("nome_imovel") or f"Imóvel {idx}"
            im_id = _limpar_id(f"imovel_{idx}_{nome}")

            # Busca ATP correspondente estritamente com evidência
            cand_atp = _casar_atp_com_evidencia(r_item, atps_disponiveis)
            atp_correspondente = None
            area_final = dados.get("area_total_ha")

            if cand_atp:
                atp_correspondente = cand_atp["caminho"]
                atps_disponiveis.remove(cand_atp)
                if area_final is None and cand_atp.get("area_ha"):
                    area_final = cand_atp["area_ha"]

            municipio_dict = None
            if dados.get("municipio") or dados.get("uf"):
                municipio_dict = {
                    "nome": dados.get("municipio") or "",
                    "uf": dados.get("uf") or "",
                }

            imoveis.append(
                Imovel(
                    id=im_id,
                    nome=nome,
                    car=car,
                    matricula=None,
                    area=area_final,
                    atp=atp_correspondente,
                    principal=(idx == 1),
                    municipio=municipio_dict,
                    geometria=f"local.{Path(atp_correspondente).stem}" if atp_correspondente else None,
                )
            )

        # ATPs restantes só viram imóveis próprios se houver mais shapefiles que recibos
        if len(atps) > len(recibos_info):
            for idx, cand in enumerate(atps_disponiveis, start=len(recibos_info) + 1):
                stem = Path(cand["caminho"]).stem
                imoveis.append(
                    Imovel(
                        id=_limpar_id(f"imovel_{idx}_{stem}"),
                        nome=stem.replace("_", " ").title(),
                        car=None,
                        matricula=None,
                        area=cand.get("area_ha"),
                        atp=cand["caminho"],
                        principal=False,
                        municipio=None,
                        geometria=f"local.{stem}",
                    )
                )

    # Caso B: 1 recibo (ou nenhum), mas múltiplos shapefiles de ATP / lote
    elif len(atps) > 1:
        atps_disponiveis = list(atps)
        recibo_item = recibos_info[0] if recibos_info else None
        cand_casado = _casar_atp_com_evidencia(recibo_item, atps_disponiveis) if recibo_item else None

        for idx, atp_shp in enumerate(atps, start=1):
            stem = Path(atp_shp["caminho"]).stem
            nome = stem.replace("_", " ").title()
            im_id = _limpar_id(f"imovel_{idx}_{stem}")

            car = None
            area = atp_shp.get("area_ha")
            mun_dict = None
            eh_principal = (idx == 1)

            if recibo_item:
                dados_r = recibo_item["dados"]
                tem_evidencia = (cand_casado and cand_casado["caminho"] == atp_shp["caminho"])

                if tem_evidencia:
                    car = dados_r.get("car_estadual") or dados_r.get("recibo_federal")
                    area = dados_r.get("area_total_ha") or area
                    if dados_r.get("municipio") or dados_r.get("uf"):
                        mun_dict = {
                            "nome": dados_r.get("municipio") or "",
                            "uf": dados_r.get("uf") or "",
                        }
                    if dados_r.get("nome_imovel"):
                        nome = dados_r["nome_imovel"]
                    eh_principal = True

            imoveis.append(
                Imovel(
                    id=im_id,
                    nome=nome,
                    car=car,
                    matricula=None,
                    area=area,
                    atp=atp_shp["caminho"],
                    principal=eh_principal,
                    municipio=mun_dict,
                    geometria=f"local.{stem}",
                )
            )

    # Caso C: 1 imóvel único (ou zero ATP detectado)
    else:
        recibo_dados = recibos_info[0]["dados"] if recibos_info else None
        atp_caminho = atps[0]["caminho"] if atps else None
        if not atp_caminho and shapefiles:
            # Pega o primeiro shapefile como fallback se não houver ATP formal
            atp_caminho = shapefiles[0]["caminho"]

        nome = "Imóvel"
        car = None
        area = None
        mun_dict = None
        if recibo_dados:
            nome = recibo_dados.get("nome_imovel") or nome
            car = recibo_dados.get("car_estadual") or recibo_dados.get("recibo_federal")
            area = recibo_dados.get("area_total_ha")
            if recibo_dados.get("municipio") or recibo_dados.get("uf"):
                mun_dict = {
                    "nome": recibo_dados.get("municipio") or "",
                    "uf": recibo_dados.get("uf") or "",
                }
        elif atp_caminho:
            nome = Path(atp_caminho).stem.replace("_", " ").title()

        stem = Path(atp_caminho).stem if atp_caminho else "ATP"
        imoveis.append(
            Imovel(
                id="imovel_principal",
                nome=nome,
                car=car,
                matricula=None,
                area=area,
                atp=atp_caminho,
                principal=True,
                municipio=mun_dict,
                geometria=f"local.{stem}" if atp_caminho else None,
            )
        )

    # Garante unicidade de IDs e garantia de exatamente um principal
    ids_vistos: set[str] = set()
    tem_principal = False
    resultado: list[dict[str, Any]] = []
    for idx, im in enumerate(imoveis):
        d = im.para_dict()
        if d["id"] in ids_vistos:
            d["id"] = f"{d['id']}_{idx}"
        ids_vistos.add(d["id"])
        if d.get("principal"):
            if not tem_principal:
                tem_principal = True
            else:
                d["principal"] = False
        resultado.append(d)

    if not tem_principal and resultado:
        resultado[0]["principal"] = True

    return resultado


def gerar_mapas_por_imovel(
    mapspec: dict[str, Any],
    workspace_raiz: WorkspaceGuard | Path | str,
    fontes_idx: dict[str, str] | None = None,
    *,
    comparar_baseline: bool = False,
    recibo: dict[str, Any] | None = None,
    progresso: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Helper que gera mapas individualizados para cada imóvel.

    Chama `gerar_mapa` existente de `mapasfacil_nucleo.motores.gerar` com a assinatura REAL.
    """
    from mapasfacil_nucleo.motores.gerar import gerar_mapa

    if isinstance(workspace_raiz, WorkspaceGuard):
        guard = workspace_raiz
    else:
        guard = WorkspaceGuard(Path(workspace_raiz))

    if fontes_idx is None:
        from mapasfacil_nucleo.workspace import indice as indice_mod

        idx = indice_mod.varrer(guard.raiz, guard)
        fontes_idx = {}
        for f in idx.get("fontes_locais", []):
            fontes_idx[f] = f
            if f.startswith("local."):
                fontes_idx[f.split(".", 1)[1]] = f
        for shp in idx.get("shapefiles", []):
            fontes_idx[shp["id_local"]] = shp["caminho"]
            if shp.get("id_local", "").startswith("local."):
                fontes_idx[shp["id_local"].split(".", 1)[1]] = shp["caminho"]
            if shp.get("papel"):
                fontes_idx[shp["papel"]] = shp["caminho"]

    imoveis = mapspec.get("imoveis")
    if not imoveis or not isinstance(imoveis, list):
        # Fallback para singular compatível
        imoveis = [mapspec.get("imovel") or {"id": "imovel_principal", "nome": "Imóvel"}]

    resultados: dict[str, Any] = {}
    camadas_todas = mapspec.get("camadas", [])

    for idx, imovel in enumerate(imoveis, start=1):
        imovel_id = imovel.get("id") or f"imovel_{idx}"
        spec_imovel = copy.deepcopy(mapspec)

        # Identidades individuais não herdam o recibo do principal. O legado
        # singular continua podendo usar o seu próprio bloco imovel.
        singular = len(imoveis) == 1
        base_individual = (mapspec.get("imovel") or {}) if singular else {}
        spec_imovel["imovel"] = {
            "nome": imovel.get("nome") or base_individual.get("nome", "Imóvel"),
            "car": str(imovel.get("car") or base_individual.get("car") or ""),
            "matricula": imovel.get("matricula") or base_individual.get("matricula"),
            "area_total_ha": imovel.get("area", imovel.get("area_total_ha", base_individual.get("area_total_ha"))),
            "municipio": imovel.get("municipio") or base_individual.get("municipio") or {"nome": "", "uf": ""},
            "geometria": imovel.get("geometria") or (f"local.{Path(imovel['atp']).stem}" if imovel.get("atp") else "") or base_individual.get("geometria", ""),
        }

        # Filtra camadas por imovel_id (inclui camadas sem imovel_id OU com o imovel_id do imóvel)
        camadas_filtradas = []
        for cam in camadas_todas:
            cam_im_id = cam.get("imovel_id")
            if cam_im_id is None or cam_im_id == imovel_id:
                camadas_filtradas.append(cam)
        spec_imovel["camadas"] = camadas_filtradas

        # Ajusta nome_base da saída de forma segura e compatível
        saida_cfg = spec_imovel.setdefault("saida", {})
        saida_pasta = saida_cfg.get("pasta") or "Mapas"
        saida_cfg["pasta"] = saida_pasta
        saida_base = saida_cfg.get("nome_base") or "mapa"
        saida_cfg["nome_base"] = f"{saida_base}_{imovel_id}"
        if not singular:
            saida_cfg['materializar_camadas_em'] = f'{saida_pasta}/SHP/{imovel_id}'
        spec_imovel.setdefault("saidas", ["pdf"])

        # Copia fontes_idx e ancora o ATP específico deste imóvel
        fontes_idx_imovel = dict(fontes_idx)
        if imovel.get("atp"):
            fontes_idx_imovel["ATP"] = imovel["atp"]
            fontes_idx_imovel["local.ATP"] = imovel["atp"]
            atp_stem = Path(imovel["atp"]).stem
            fontes_idx_imovel[atp_stem] = imovel["atp"]
            fontes_idx_imovel[f"local.{atp_stem}"] = imovel["atp"]

        # Cada motor tem etapas próprias, mas a barra do lote não regride.
        progresso_imovel = progresso
        if progresso is not None and len(imoveis) > 1:
            progresso_imovel = progresso.fatiar(
                (idx - 1) * 95 / len(imoveis), idx * 95 / len(imoveis), imovel_id=imovel_id
            )
        resultado_geracao = gerar_mapa(
            spec_imovel,
            guard,
            fontes_idx_imovel,
            comparar_baseline=comparar_baseline,
            recibo=recibo if singular else None,
            progresso=progresso_imovel,
        )
        resultados[imovel_id] = resultado_geracao

    return resultados


def gerar_xlsx_combinado(
    imoveis: list[dict[str, Any]],
    resultados_mapas: dict[str, Any],
    destino_xlsx: Path | str,
    *,
    titulo_projeto: str = "Multi-Imóvel",
) -> Path:
    """Gera um arquivo XLSX consolidado combinando todos os imóveis e quantitativos."""
    destino = Path(destino_xlsx)
    destino.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # 1. Aba Resumo de Imóveis
    ws_resumo = wb.active
    ws_resumo.title = "Resumo Imóveis"

    ws_resumo.merge_cells(start_row=1, start_column=1, end_row=1, end_column=7)
    titulo_cel = ws_resumo.cell(row=1, column=1, value=f"Resumo Multi-Imóvel — {titulo_projeto}")
    _preencher_celula(titulo_cel, valor=f"Resumo Multi-Imóvel — {titulo_projeto}", fundo=COR_TITULO, negrito=True, branco=True)
    titulo_cel.alignment = Alignment(horizontal="center", vertical="center")
    ws_resumo.row_dimensions[1].height = 24

    cabecalho = ["ID", "Nome do Imóvel", "CAR", "Matrícula", "Área (ha)", "ATP", "Principal"]
    for col_idx, col_nome in enumerate(cabecalho, start=1):
        cel = ws_resumo.cell(row=2, column=col_idx, value=col_nome)
        _preencher_celula(cel, valor=col_nome, fundo=COR_CABECALHO, negrito=True, branco=True, alinhamento="center")

    soma_area = 0.0
    for row_idx, im in enumerate(imoveis, start=3):
        area_val = im.get("area")
        if isinstance(area_val, (int, float)):
            soma_area += float(area_val)

        valores = [
            im.get("id"),
            im.get("nome"),
            im.get("car") or "—",
            im.get("matricula") or "—",
            area_val,
            im.get("atp") or "—",
            "Sim" if im.get("principal") else "Não",
        ]
        for col_idx, val in enumerate(valores, start=1):
            cel = ws_resumo.cell(row=row_idx, column=col_idx)
            is_num = col_idx == 5 and isinstance(val, (int, float))
            _preencher_celula(cel, valor=val, numero=is_num)
            if is_num:
                cel.number_format = "#,##0.0000"

    # Linha de total se houver imóveis
    if imoveis:
        row_tot = 3 + len(imoveis)
        cel_tot = ws_resumo.cell(row=row_tot, column=1, value="TOTAL")
        _preencher_celula(cel_tot, valor="TOTAL", fundo=COR_TOTAL, negrito=True, branco=True)
        for c in range(2, 8):
            val = soma_area if c == 5 else None
            cel_c = ws_resumo.cell(row=row_tot, column=c, value=val)
            _preencher_celula(cel_c, valor=val, fundo=COR_TOTAL, negrito=True, branco=True, numero=(c == 5))
            if c == 5:
                cel_c.number_format = "#,##0.0000"

    _larguras_colunas(ws_resumo, [1.5, 2.5, 2.2, 1.2, 1.5, 2.0, 1.0])
    ws_resumo.freeze_panes = "A3"

    # 2. Aba Quantitativos Combinados (consolidação de tabelas de quantitativos)
    ws_comb = wb.create_sheet("Quantitativos Combinados")
    ws_comb.merge_cells(start_row=1, start_column=1, end_row=1, end_column=4)
    tit_comb = ws_comb.cell(row=1, column=1, value="Quantitativos Consolidados")
    _preencher_celula(tit_comb, valor="Quantitativos Consolidados", fundo=COR_TITULO, negrito=True, branco=True)
    tit_comb.alignment = Alignment(horizontal="center", vertical="center")

    cab_comb = ["Imóvel", "Classe", "Área (ha)", "Observação"]
    for col_idx, col_nome in enumerate(cab_comb, start=1):
        cel = ws_comb.cell(row=2, column=col_idx, value=col_nome)
        _preencher_celula(cel, valor=col_nome, fundo=COR_CABECALHO, negrito=True, branco=True, alinhamento="center")

    curr_row = 3
    for im in imoveis:
        im_id = im.get("id")
        im_nome = im.get("nome")
        res_mapa = resultados_mapas.get(im_id, {})
        quant = res_mapa.get("quantitativos", {})
        detalhe = quant.get("detalhe", [])
        if detalhe:
            for item in detalhe:
                fonte = item.get("fonte") or item.get("estilo") or "Classe"
                area_ha = item.get("area_ha", 0.0)
                valores_det = [im_nome, fonte, area_ha, "Calculado"]
                for col_idx, val in enumerate(valores_det, start=1):
                    cel = ws_comb.cell(row=curr_row, column=col_idx, value=val)
                    _preencher_celula(cel, valor=val, numero=(col_idx == 3))
                    if col_idx == 3:
                        cel.number_format = "#,##0.0000"
                curr_row += 1
        else:
            # Se não houver detalhe de quantitativos calculado pelo motor
            area_ha = im.get("area") or 0.0
            valores_det = [im_nome, "Área Total Declarada", area_ha, "Declarado"]
            for col_idx, val in enumerate(valores_det, start=1):
                cel = ws_comb.cell(row=curr_row, column=col_idx, value=val)
                _preencher_celula(cel, valor=val, numero=(col_idx == 3))
                if col_idx == 3:
                    cel.number_format = "#,##0.0000"
            curr_row += 1

    _larguras_colunas(ws_comb, [2.5, 2.0, 1.5, 1.5])
    ws_comb.freeze_panes = "A3"

    # 3. Abas individuais por imóvel
    for im in imoveis:
        im_id = im.get("id")
        im_nome = str(im.get("nome") or im_id or "Imóvel")
        # Rótulos de imóveis são dados: barras são comuns e não são títulos Excel.
        base_aba = re.sub(r'[\\/?*:\[\]]', '_', f"Q - {im_nome}").strip("'")[:31] or "Imóvel"
        sheet_title = base_aba
        numero_aba = 2
        while sheet_title.casefold() in {n.casefold() for n in wb.sheetnames}:
            sufixo = f" ({numero_aba})"
            sheet_title = base_aba[:31 - len(sufixo)] + sufixo
            numero_aba += 1
        ws_im = wb.create_sheet(sheet_title)

        ws_im.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)
        tit_im = ws_im.cell(row=1, column=1, value=f"Quantitativos: {im.get('nome')}")
        _preencher_celula(tit_im, valor=f"Quantitativos: {im.get('nome')}", fundo=COR_TITULO, negrito=True, branco=True)

        cab_im = ["Item / Classe", "Área (ha)", "Fonte"]
        for col_idx, col_nome in enumerate(cab_im, start=1):
            cel = ws_im.cell(row=2, column=col_idx, value=col_nome)
            _preencher_celula(cel, valor=col_nome, fundo=COR_CABECALHO, negrito=True, branco=True, alinhamento="center")

        res_mapa = resultados_mapas.get(im_id, {})
        detalhe = res_mapa.get("quantitativos", {}).get("detalhe", [])
        row_im = 3
        if detalhe:
            for item in detalhe:
                val_linha = [item.get("fonte") or item.get("estilo"), item.get("area_ha"), item.get("arquivo", "—")]
                for col_idx, val in enumerate(val_linha, start=1):
                    cel = ws_im.cell(row=row_im, column=col_idx, value=val)
                    _preencher_celula(cel, valor=val, numero=(col_idx == 2))
                    if col_idx == 2 and isinstance(val, (int, float)):
                        cel.number_format = "#,##0.0000"
                row_im += 1
        else:
            val_linha = ["Área Imóvel", im.get("area"), im.get("atp") or "—"]
            for col_idx, val in enumerate(val_linha, start=1):
                cel = ws_im.cell(row=row_im, column=col_idx, value=val)
                _preencher_celula(cel, valor=val, numero=(col_idx == 2))
                if col_idx == 2 and isinstance(val, (int, float)):
                    cel.number_format = "#,##0.0000"
            row_im += 1

        _larguras_colunas(ws_im, [2.5, 1.5, 2.0])
        ws_im.freeze_panes = "A3"

    wb.save(destino)
    return destino


def gerar_multi_imovel(
    mapspec: dict[str, Any],
    workspace_raiz: WorkspaceGuard | Path | str,
    fontes_idx: dict[str, str] | None = None,
    *,
    comparar_baseline: bool = False,
    recibo: dict[str, Any] | None = None,
    progresso: Any | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Orquestrador completo de geração multi-imóvel: gera PDFs por imóvel, versão consolidada e XLSX combinado.

    Retorna dicionário plano compatível com o contrato de versão e pacote.
    """
    if isinstance(workspace_raiz, WorkspaceGuard):
        guard = workspace_raiz
    else:
        guard = WorkspaceGuard(Path(workspace_raiz))

    imoveis = mapspec.get("imoveis") or [mapspec.get("imovel") or {"id": "imovel_principal", "nome": "Imóvel"}]

    resultados_mapas = gerar_mapas_por_imovel(
        mapspec,
        guard,
        fontes_idx,
        comparar_baseline=comparar_baseline,
        recibo=recibo,
        progresso=progresso,
        **kwargs,
    )

    saida_pasta = (mapspec.get("saida") or {}).get("pasta", "Mapas")
    nome_base = (mapspec.get("saida") or {}).get("nome_base", "mapa")

    # 1. Gera versão consolidada imutável dos PDFs
    pdf_consolidado_rel = None
    lista_pdfs_rel: list[str] = []
    for im_id, res in resultados_mapas.items():
        p = res.get("pdf") or (res.get("artefatos") or {}).get("pdf")
        if p:
            lista_pdfs_rel.append(p)

    if lista_pdfs_rel:
        doc_consolidado = fitz.open()
        for p_rel in lista_pdfs_rel:
            p_abs = guard.resolver(p_rel)
            if p_abs.is_file():
                with fitz.open(str(p_abs)) as doc_part:
                    doc_consolidado.insert_pdf(doc_part)

        nome_cons = f"{nome_base}_consolidado.pdf"
        dest_cons = guard.resolver(f"{saida_pasta}/{nome_cons}", escrita=True)
        dest_cons.parent.mkdir(parents=True, exist_ok=True)
        doc_consolidado.save(str(dest_cons), deflate=True)
        doc_consolidado.close()
        pdf_consolidado_rel = f"{saida_pasta}/{nome_cons}"

    # 2. Gera XLSX combinado real
    nome_xlsx = f"{nome_base}_combinado.xlsx"
    destino_xlsx = guard.resolver(f"{saida_pasta}/{nome_xlsx}", escrita=True)
    gerar_xlsx_combinado(
        imoveis=imoveis,
        resultados_mapas=resultados_mapas,
        destino_xlsx=destino_xlsx,
        titulo_projeto=mapspec.get("titulo", "Multi-Imóvel"),
    )
    xlsx_combinado_rel = f"{saida_pasta}/{nome_xlsx}"

    # 3. Monta retorno plano compatível com versoes_sync e API pacote
    artefatos_combinados: dict[str, Any] = {
        "xlsx": xlsx_combinado_rel,
    }
    if pdf_consolidado_rel:
        artefatos_combinados["pdf"] = pdf_consolidado_rel
        artefatos_combinados["pdf_consolidado"] = pdf_consolidado_rel
    elif lista_pdfs_rel:
        artefatos_combinados["pdf"] = lista_pdfs_rel[0]

    for im_id, res in resultados_mapas.items():
        p = res.get("pdf") or (res.get("artefatos") or {}).get("pdf")
        if p:
            artefatos_combinados[f"pdf_{im_id}"] = p

    avisos_todos = []
    for res in resultados_mapas.values():
        avisos_todos.extend(res.get("avisos") or [])

    # A conformidade do atlas é a de TODOS os imóveis, nunca só o primeiro
    # *_validacao.json que a ponte encontrar em ordem alfabética.
    import json
    checks_consolidados: dict[str, list[dict[str, Any]]] = {'hard': [], 'soft': []}
    for im_id, res in resultados_mapas.items():
        dados = res.get('validacao_dados') or {}
        checks = dados.get('checks') or {}
        if not isinstance(checks, dict) or not checks.get('hard'):
            checks_consolidados['hard'].append({'id':'H00', 'ok':False, 'imovel_id':im_id,
                'mensagem':'Validação técnica do imóvel indisponível; conformidade não comprovada.'})
            continue
        for tipo in ('hard', 'soft'):
            checks_consolidados[tipo].extend({**c, 'imovel_id':im_id} for c in checks.get(tipo, []) if isinstance(c, dict))
    conforme = bool(checks_consolidados['hard']) and all(c.get('ok') is True for c in checks_consolidados['hard'])
    validacao_consolidada = {'conforme':conforme, 'checks':checks_consolidados,
        'motor':'nativo', 'imoveis':list(resultados_mapas)}
    rel_validacao = f'{saida_pasta}/validacao.json'
    alvo_validacao = guard.resolver(rel_validacao, escrita=True)
    alvo_validacao.parent.mkdir(parents=True, exist_ok=True)
    alvo_validacao.write_text(json.dumps(validacao_consolidada, ensure_ascii=False, indent=2), encoding='utf-8')
    if progresso is not None and len(imoveis) > 1:
        progresso.concluir('validando_saida')

    return {
        "pdf": pdf_consolidado_rel or (lista_pdfs_rel[0] if lista_pdfs_rel else None),
        "validacao": rel_validacao,
        "validacao_dados": validacao_consolidada,
        "xlsx": xlsx_combinado_rel,
        "artefatos": artefatos_combinados,
        "imoveis": resultados_mapas,
        "xlsx_combinado": xlsx_combinado_rel,
        "avisos": avisos_todos,
        "status": "concluido",
    }
