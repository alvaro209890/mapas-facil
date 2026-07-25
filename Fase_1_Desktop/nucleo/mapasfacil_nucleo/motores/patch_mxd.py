from __future__ import annotations

import shutil
import struct
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores.manifesto import obter_template, resolver_caminho_preparado, sha256_arquivo


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
            val = item.get("valor", "")
            if rot and val:
                linhas.append(f"<bol>{rot}</bol> {val}")
        if linhas:
            textos["METADADOS"] = "\r\n".join(linhas)
    return textos


def gerar_mxd_t2(
    mapspec: dict[str, Any],
    *,
    guard: WorkspaceGuard,
    bbox: tuple[float, float, float, float] | None = None,
    escala: float | None = None,
) -> dict[str, Any]:
    template_id = mapspec.get("template")
    if not isinstance(template_id, str):
        raise ErroNucleo("NU-205", "MapSpec sem template.")

    saida = mapspec.get("saida") or {}
    nome_base = saida.get("nome_base", "mapa")
    pasta_mxd = guard.resolver("MXD", escrita=True)
    destino_mxd = pasta_mxd / f"{nome_base}.mxd"

    copia = copiar_template(template_id, destino_mxd)
    tpl = obter_template(template_id)
    textos = _textos_do_mapspec(mapspec)
    patch = aplicar_patch_manifesto(
        destino_mxd,
        tpl,
        bbox=bbox,
        escala=escala,
        textos=textos,
    )

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
