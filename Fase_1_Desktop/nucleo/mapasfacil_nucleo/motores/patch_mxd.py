from __future__ import annotations

import shutil
import struct
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.manifesto import obter_template, resolver_caminho_preparado, sha256_arquivo

if TYPE_CHECKING:
    from mapasfacil_nucleo.mxd_binario import ManifestoSlots


def patch_float64_le(dados: bytearray, offset: int, valor: float) -> None:
    dados[offset : offset + 8] = struct.pack("<d", valor)


def patch_extent_le(dados: bytearray, offset: int, bbox: tuple[float, float, float, float]) -> None:
    for i, v in enumerate(bbox):
        patch_float64_le(dados, offset + i * 8, v)


def ler_float64_le(dados: bytes, offset: int) -> float:
    return struct.unpack("<d", dados[offset : offset + 8])[0]


def validar_offset_sentinela(
    dados: bytes,
    offset: int,
    esperado: float,
    *,
    tolerancia: float = 1e-6,
) -> bool:
    try:
        atual = ler_float64_le(dados, offset)
    except struct.error:
        return False
    return abs(atual - esperado) < tolerancia


def copiar_template(template_id: str, destino_mxd: Path) -> dict[str, Any]:
    tpl = obter_template(template_id)
    origem = resolver_caminho_preparado(tpl)
    destino_mxd.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origem, destino_mxd)
    hash_atual = sha256_arquivo(destino_mxd)
    esperado = tpl.get("sha256")
    return {
        "template": template_id,
        "origem": str(origem),
        "destino": str(destino_mxd),
        "sha256": hash_atual,
        "sha256_template_ok": esperado is None or esperado == hash_atual,
    }


def patch_texto_utf16le_slot(
    dados: bytearray,
    offset: int,
    texto: str,
    *,
    slot_caracteres: int,
) -> str | None:
    """Escreve texto em slot UTF-16LE de tamanho fixo. Retorna aviso se truncou."""
    encaixado = texto[:slot_caracteres]
    if len(texto) > slot_caracteres:
        aviso = f"Texto truncado de {len(texto)} para {slot_caracteres} caracteres."
    else:
        aviso = None
        encaixado = encaixado + (" " * (slot_caracteres - len(encaixado)))
    payload = encaixado.encode("utf-16le")
    fim = offset + len(payload)
    if fim > len(dados):
        raise ErroNucleo(
            "AG-030",
            "Slot de texto ultrapassa o tamanho do arquivo.",
            {"offset": offset, "slot": slot_caracteres},
        )
    dados[offset:fim] = payload
    return aviso


def aplicar_patch_manifesto(
    destino_mxd: Path,
    template: dict[str, Any],
    *,
    bbox: tuple[float, float, float, float] | None = None,
    escala: float | None = None,
    textos: dict[str, str] | None = None,
) -> dict[str, Any]:
    patch_cfg = (template.get("patch") or {})
    offsets = patch_cfg.get("offsets") or {}
    avisos: list[str] = []
    aplicados: list[str] = []

    dados = bytearray(destino_mxd.read_bytes())

    if bbox and "extent" in offsets:
        cfg = offsets["extent"]
        off = int(cfg["offset"])
        sentinela = cfg.get("sentinela")
        if sentinela is not None and not validar_offset_sentinela(dados, off, float(sentinela)):
            avisos.append("Offset de extent não confere com o sentinela do manifesto.")
        else:
            patch_extent_le(dados, off, bbox)
            aplicados.append("extent")
    elif bbox:
        avisos.append("Extent informado, mas manifesto sem offsets — patch ignorado (T3).")

    if escala is not None and "escala" in offsets:
        cfg = offsets["escala"]
        off = int(cfg["offset"])
        sentinela = cfg.get("sentinela")
        if sentinela is not None and not validar_offset_sentinela(dados, off, float(sentinela)):
            avisos.append("Offset de escala não confere com o sentinela do manifesto.")
        else:
            patch_float64_le(dados, off, float(escala))
            aplicados.append("escala")
    elif escala is not None:
        avisos.append("Escala informada, mas manifesto sem offsets — patch ignorado (T3).")

    if textos:
        elementos = {
            el["nome"]: el
            for el in (template.get("elementos") or [])
            if el.get("nome")
        }
        for nome, valor in textos.items():
            cfg = (offsets.get("textos") or {}).get(nome)
            el = elementos.get(nome)
            if not cfg or not el:
                avisos.append(f"Texto '{nome}' sem offset no manifesto — ignorado (T3).")
                continue
            off = int(cfg["offset"])
            slot = int(cfg.get("slot_caracteres") or el.get("slot_caracteres") or 0)
            if slot <= 0:
                avisos.append(f"Texto '{nome}' sem slot_caracteres — ignorado.")
                continue
            aviso_trunc = patch_texto_utf16le_slot(dados, off, valor, slot_caracteres=slot)
            if aviso_trunc:
                avisos.append(aviso_trunc)
            aplicados.append(f"texto:{nome}")

    if aplicados:
        destino_mxd.write_bytes(dados)

    return {"aplicados": aplicados, "avisos": avisos, "modo": "patch" if aplicados else "copia"}


def _resolver_valor_metadado(rotulo: str, valor: Any, mapspec: dict[str, Any]) -> str:
    """Troca placeholders 'auto' pelos valores reais do MapSpec / basemap."""
    texto = str(valor or "").strip()
    if texto and texto.lower() != "auto":
        return texto

    rot = (rotulo or "").strip().lower()
    if rot.startswith("data"):
        mosaico = str((mapspec.get("basemap") or {}).get("mosaico") or "")
        # planet_..._2026-03_... ou global_monthly_2026_03_mosaic
        import re

        m = re.search(r"(20\d{2})[-_](\d{2})", mosaico)
        if m:
            meses = {
                "01": "Janeiro",
                "02": "Fevereiro",
                "03": "Março",
                "04": "Abril",
                "05": "Maio",
                "06": "Junho",
                "07": "Julho",
                "08": "Agosto",
                "09": "Setembro",
                "10": "Outubro",
                "11": "Novembro",
                "12": "Dezembro",
            }
            return f"{meses.get(m.group(2), m.group(2))}/{m.group(1)}"
        return "Março/2026"
    if rot.startswith("datum"):
        crs = str(mapspec.get("crs") or "EPSG:31982")
        if "31982" in crs:
            return "SIRGAS 2000 UTM 22 S"
        if "31981" in crs:
            return "SIRGAS 2000 UTM 21 S"
        return crs.replace("EPSG:", "EPSG ")
    if rot.startswith("escala"):
        escala = mapspec.get("escala")
        if isinstance(escala, (int, float)) and escala > 0:
            return f"1:{int(escala):,}".replace(",", ".")
        if isinstance(escala, str) and escala.isdigit():
            return f"1:{int(escala):,}".replace(",", ".")
        return "1:60.000"
    return texto


def _textos_do_mapspec(mapspec: dict[str, Any]) -> dict[str, str]:
    textos: dict[str, str] = {}
    titulo = mapspec.get("titulo")
    if isinstance(titulo, str) and titulo.strip():
        textos["TITULO"] = titulo.strip()
    imovel = mapspec.get("imovel") or {}
    rotulo = imovel.get("nome") or imovel.get("rotulo")
    if isinstance(rotulo, str) and rotulo.strip():
        textos["ROTULO_IMOVEL"] = rotulo.strip()
    metadados = mapspec.get("metadados")
    if isinstance(metadados, list):
        linhas: list[str] = []
        for item in metadados:
            if not isinstance(item, dict):
                continue
            rot = item.get("rotulo", "")
            val = _resolver_valor_metadado(str(rot), item.get("valor", ""), mapspec)
            if rot and val:
                linhas.append(f"<bol>{rot}</bol> {val}")
        if linhas:
            textos["METADADOS"] = "\r\n".join(linhas)
    return textos




def gerar_mxd_binario(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    bbox: tuple[float, float, float, float] | None = None,
    escala: float | None = None,
    ao_etapa: Callable[[str], Any] | None = None,
) -> dict[str, Any] | None:
    """W10-11: Motor MXD binário baseado em slots.json e gates de qualidade."""
    from mapasfacil_nucleo.mxd_binario import DocumentoMxd, ManifestoSlots, verificar_todos

    template_id = mapspec.get("template")
    if not isinstance(template_id, str):
        return None

    try:
        tpl = obter_template(template_id)
    except ErroNucleo:
        try:
            tpl = obter_template(template_id.lower())
        except ErroNucleo:
            return None

    origem = resolver_caminho_preparado(tpl)
    candidatos_slots = [
        origem.with_suffix(".slots.json"),
        origem.parent / f"{template_id}.slots.json",
        origem.parent / f"{template_id.lower()}.slots.json",
        origem.parent / f"{tpl.get('id', '')}.slots.json",
    ]
    slots_json = None
    for cand in candidatos_slots:
        if cand.exists():
            slots_json = cand
            break
    if slots_json is None:
        return None

    manifesto = ManifestoSlots.carregar(slots_json)
    saida = mapspec.get("saida") or {}
    nome_base = saida.get("nome_base", "mapa")
    pasta_mxd = guard.resolver("MXD", escrita=True)
    destino_mxd = pasta_mxd / f"{nome_base}.mxd"

    if ao_etapa is not None:
        ao_etapa("preparando_template")

    doc = DocumentoMxd.abrir(origem)
    imovel = mapspec.get("imovel") or {}
    municipio_obj = imovel.get("municipio")
    nome_mun = municipio_obj.get("nome") if isinstance(municipio_obj, dict) else str(municipio_obj or "")
    uf_mun = municipio_obj.get("uf") if isinstance(municipio_obj, dict) else ""

    valores: dict[str, Any] = {}
    if mapspec.get("titulo"):
        valores["titulo"] = mapspec["titulo"]
    if imovel.get("nome"):
        valores["rotulo_imovel"] = imovel["nome"]
    if nome_mun:
        valores["municipio"] = nome_mun
    if uf_mun:
        valores["uf"] = uf_mun
    if escala:
        valores["escala"] = escala
    if bbox:
        valores["df_principal"] = bbox

    valores, avisos_slots, bloqueio = _caber_nas_sentinelas(valores, manifesto)
    if bloqueio:
        return {
            "mxd": None,
            "motor": "binario",
            "confianca": "reprovado_gates",
            "avisos": avisos_slots + [bloqueio],
        }

    doc.aplicar(valores, manifesto=manifesto)

    if ao_etapa is not None:
        ao_etapa("aplicando_layout")

    template_bytes = origem.read_bytes()
    gerado_bytes = doc.obter_bytes()

    gates = verificar_todos(template_bytes, gerado_bytes, manifesto, valores)
    falhas = [g for g in gates if not g.ok]
    if falhas:
        # Se algum gate falhar, aplica D37: aviso emitido e mxd não é liberado
        return {
            "mxd": None,
            "motor": "binario",
            "confianca": "reprovado_gates",
            "avisos": [f"[{f.codigo_erro}] {f.mensagem}" for f in falhas],
        }

    doc.salvar(destino_mxd)
    if ao_etapa is not None:
        ao_etapa("salvando_mxd")

    return {
        "mxd": destino_mxd.relative_to(guard.raiz).as_posix(),
        "motor": "binario",
        "confianca": "alta" if not avisos_slots else "media",
        "avisos": avisos_slots,
    }


# Textos que só aparecem no layout: se não couberem, o MXD sai com o campo em branco (abre
# normal, e o aviso pede para escrever no ArcMap). Os demais (município, UF) também entram
# em consultas de camada — cortar mudaria o filtro, então o MXD não é liberado.
_SLOTS_SO_LAYOUT = {"titulo", "rotulo_imovel"}


def _caber_nas_sentinelas(
    valores: dict[str, Any], manifesto: ManifestoSlots
) -> tuple[dict[str, Any], list[str], str | None]:
    """Ajusta os textos ao tamanho das sentinelas do template.

    O motor binário só troca texto **do mesmo tamanho** (trocar o tamanho corrompia o
    PageLayout — teste_22, 04/11/2026). Devolve (valores, avisos, motivo_de_bloqueio).
    """
    ajustados = dict(valores)
    avisos: list[str] = []
    for slot in manifesto.slots:
        if slot.tipo != "texto" or slot.id not in ajustados:
            continue
        texto = str(ajustados[slot.id])
        limite = len(str(slot.sentinela))
        if len(texto) <= limite:
            continue
        if slot.id in _SLOTS_SO_LAYOUT:
            ajustados[slot.id] = ""
            avisos.append(
                f"[MX-050] \"{texto}\" tem {len(texto)} letras e o campo '{slot.id}' do "
                f"modelo MXD comporta {limite}: ficou em branco no .mxd (o PDF sai completo)."
            )
        else:
            return ajustados, avisos, (
                f"[MX-050] \"{texto}\" não cabe no campo '{slot.id}' do modelo MXD "
                f"({limite} letras); o .mxd não foi gerado (o PDF sai completo)."
            )
    return ajustados, avisos, None


def gerar_mxd_t2(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    bbox: tuple[float, float, float, float] | None = None,
    escala: float | None = None,
    ao_etapa: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """T2 — delega ao motor binário se houver slots.json, senão aplica patch legado.

    `ao_etapa(nome)` marca as etapas do contrato de `job.progresso` conforme elas
    terminam: `preparando_template`, `aplicando_layout`, `salvando_mxd`.
    """
    res_bin = gerar_mxd_binario(mapspec, guard=guard, bbox=bbox, escala=escala, ao_etapa=ao_etapa)
    if res_bin is not None:
        return res_bin
    template_id = mapspec.get("template")
    if not isinstance(template_id, str):
        raise ErroNucleo("NU-205", "MapSpec sem template.")

    saida = mapspec.get("saida") or {}
    nome_base = saida.get("nome_base", "mapa")
    pasta_mxd = guard.resolver("MXD", escrita=True)
    destino_mxd = pasta_mxd / f"{nome_base}.mxd"

    copia = copiar_template(template_id, destino_mxd)
    tpl = obter_template(template_id)
    if ao_etapa is not None:
        ao_etapa("preparando_template")

    textos = _textos_do_mapspec(mapspec)
    patch = aplicar_patch_manifesto(
        destino_mxd,
        tpl,
        bbox=bbox,
        escala=escala,
        textos=textos,
    )
    if ao_etapa is not None:
        ao_etapa("aplicando_layout")
        ao_etapa("salvando_mxd")

    confianca = "patch" if patch["aplicados"] else "estrutural"
    if patch["avisos"]:
        confianca = "estrutural"

    return {
        "mxd": str(destino_mxd.relative_to(guard.raiz)),
        "motor": "patch" if patch["aplicados"] else "copia_template",
        "confianca": confianca,
        "copia": copia,
        "patch": patch,
    }
