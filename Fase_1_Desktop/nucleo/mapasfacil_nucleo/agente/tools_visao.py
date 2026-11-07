from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.agente.tools_workspace import _obter_workspace, _resolver_caminho_seguro
from mapasfacil_nucleo.agente.visao import imagem as imagem_mod
from mapasfacil_nucleo.agente.visao import pdf as pdf_mod
from mapasfacil_nucleo.agente.visao import servico as visao_servico
from mapasfacil_nucleo.validacao.revisao_visual import tarjar_imagem_para_visao

_REGEX_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b")
_REGEX_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b")


def _extrair_nomes_proprietarios(ctx: dict[str, Any], args: dict[str, Any]) -> list[str]:
    nomes: list[str] = []
    args_nomes = args.get("nomes_proprietarios")
    if isinstance(args_nomes, list):
        nomes.extend(str(n).strip() for n in args_nomes if str(n).strip())
    elif isinstance(args_nomes, str) and args_nomes.strip():
        nomes.append(args_nomes.strip())

    ms = ctx.get("mapspec")
    if isinstance(ms, dict):
        imovel = ms.get("imovel") or {}
        p = imovel.get("proprietario") or imovel.get("proprietarios")
        if isinstance(p, str) and p.strip():
            nomes.append(p.strip())
        elif isinstance(p, list):
            nomes.extend(str(item).strip() for item in p if str(item).strip())
    return list(dict.fromkeys(nomes))


def _tarjar_imagem_bytes(
    img_bytes: bytes,
    nomes: list[str],
    ext: str,
) -> tuple[bytes, int]:
    import pymupdf

    try:
        tipo = ext.lstrip(".").lower()
        if tipo == "jpg":
            tipo = "jpeg"
        doc = pymupdf.open(stream=img_bytes, filetype=tipo)
    except Exception:
        return img_bytes, 0

    if len(doc) == 0:
        doc.close()
        return img_bytes, 0

    pag = doc[0]
    texto_pagina = pag.get_text("text")
    rects_tarja = []

    for m in _REGEX_CPF.finditer(texto_pagina):
        for r in pag.search_for(m.group(0)):
            rects_tarja.append(r)

    for m in _REGEX_CNPJ.finditer(texto_pagina):
        for r in pag.search_for(m.group(0)):
            rects_tarja.append(r)

    for nome in nomes:
        if len(nome.strip()) >= 4:
            for r in pag.search_for(nome.strip()):
                rects_tarja.append(r)

    for r in rects_tarja:
        pag.draw_rect(r, color=(0, 0, 0), fill=(0, 0, 0))

    pix = pag.get_pixmap(dpi=150)
    saida = pix.tobytes("png")
    doc.close()
    return saida, len(rects_tarja)


def registrar_tools_visao(registro: RegistroFerramentas) -> None:
    @registro.ferramenta(
        nome="visao_analisar",
        descricao="Analisa visualmente um mapa, imagem (PNG/JPG) ou documento PDF usando o modelo multimodal.",
        categoria="visao",
        parametros={
            "type": "object",
            "properties": {
                "caminho_arquivo": {
                    "type": "string",
                    "description": "Caminho relativo da imagem ou PDF a analisar.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Instrução ou pergunta específica para a análise visual.",
                },
                "nomes_proprietarios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Nomes a serem obrigatoriamente tarjados por privacidade.",
                },
            },
            "required": ["caminho_arquivo"],
            "additionalProperties": False,
        },
    )
    def tool_visao_analisar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args["caminho_arquivo"]
            alvo = _resolver_caminho_seguro(caminho_str, ws_root)
            if not alvo.exists():
                return _erro("VIS-001", f"Arquivo '{caminho_str}' não existe.")

            ext = alvo.suffix.lower()
            nomes_proprietarios = _extrair_nomes_proprietarios(ctx, args)
            total_tarjas = 0

            if ext == ".pdf":
                info_pdf = pdf_mod.analisar_pdf(alvo)
                texto_pdf = info_pdf.get("texto", "")[:2000]
                # Tarjamento prévio opaco LGPD antes de converter e enviar
                png_bytes, total_tarjas = tarjar_imagem_para_visao(
                    alvo.read_bytes(),
                    nomes_proprietarios=nomes_proprietarios,
                    dpi=150,
                )
            elif ext in {".png", ".jpg", ".jpeg"}:
                texto_pdf = ""
                # Tarjamento prévio opaco LGPD em imagem
                png_bytes, total_tarjas = _tarjar_imagem_bytes(
                    alvo.read_bytes(),
                    nomes_proprietarios,
                    ext,
                )
            else:
                return _erro("VIS-002", f"Extensão '{ext}' não suportada para visão (apenas PDF, PNG, JPG).")

            medidas = imagem_mod.medir_imagem(png_bytes)

            # Chama provedor existente de visão
            provedor = visao_servico._obter_provedor()
            if provedor is None:
                # Ausência de provedor retorna indisponível com código padrão, NUNCA sucesso inventado
                return _erro(
                    limites.CODIGO_VISAO_INDISPONIVEL,
                    "Provedor de visão indisponível ou chave de API não configurada.",
                    arquivo=alvo.relative_to(ws_root).as_posix(),
                    medidas_deterministicas=medidas,
                    tarjas_aplicadas=total_tarjas,
                )

            prompt_custom = args.get("prompt") or "Analise a composição cartográfica deste mapa."
            b64_str = base64.b64encode(png_bytes).decode("ascii")

            try:
                resposta_visao = provedor.analisar(
                    imagem_base64=b64_str,
                    mime="image/png",
                    prompt=prompt_custom,
                )
            except Exception as exc:
                # Erro do provedor retorna indisponível, NUNCA sucesso/aprovado falso
                return _erro(
                    limites.CODIGO_VISAO_INDISPONIVEL,
                    f"Modelo de visão falhou ou está indisponível: {exc}",
                    arquivo=alvo.relative_to(ws_root).as_posix(),
                )

            return _ok(
                {
                    "arquivo": alvo.relative_to(ws_root).as_posix(),
                    "medidas": medidas,
                    "texto_extraido": texto_pdf,
                    "analise": resposta_visao,
                    "tarjas_aplicadas": total_tarjas,
                }
            )
        except Exception as exc:
            return _erro("VIS-003", f"Falha na análise visual: {exc}")
