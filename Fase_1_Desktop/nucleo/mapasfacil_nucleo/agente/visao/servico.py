# F1-07 — orquestrador de `analisar_referencia`: escolhe o caminho (imagem/pdf/
# mxd/zip) pela extensão, roda o determinístico sempre, e só chama o modelo de
# visão quando faz sentido (imagem/pdf) e há chave configurada. Falha do modelo
# de visão nunca derruba a tool — vira aviso tipado, e o determinístico continua
# valendo (F1-07 §Limites e honestidade).

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.chave import ler_chave_deepseek
from mapasfacil_nucleo.agente.visao import imagem as imagem_mod
from mapasfacil_nucleo.agente.visao import mapear
from mapasfacil_nucleo.agente.visao import mxd_strings
from mapasfacil_nucleo.agente.visao import pdf as pdf_mod
from mapasfacil_nucleo.agente.visao import zip_inventario
from mapasfacil_nucleo.agente.visao.prompt import montar_prompt
from mapasfacil_nucleo.agente.visao.provedor import DeepSeekVisaoProvedor, ProvedorVisao
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.mapspec.validar import ESTILOS_PERMITIDOS
from mapasfacil_nucleo.workspace import zip_simcar

EXTENSOES_IMAGEM = frozenset({".png", ".jpg", ".jpeg"})

_provedor_override: ProvedorVisao | None = None


def configurar_provedor(provedor: ProvedorVisao | None) -> None:
    """Testes injetam `ProvedorVisaoFixo`/`Falha`; produção usa `None` (DeepSeek + chave)."""
    global _provedor_override
    _provedor_override = provedor


def _obter_provedor() -> ProvedorVisao | None:
    if _provedor_override is not None:
        return _provedor_override
    chave = ler_chave_deepseek()
    if not chave:
        return None
    return DeepSeekVisaoProvedor(chave)


def _chamar_visao(
    png_bytes: bytes, medidas: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[str]]:
    provedor = _obter_provedor()
    if provedor is None:
        return None, [
            "sem chave DeepSeek configurada — só a análise determinística roda "
            "(configure em Preferências para a interpretação de legenda/série)."
        ]

    prompt = montar_prompt(
        medidas=medidas,
        estilos_permitidos=sorted(ESTILOS_PERMITIDOS),
        mapas_serie=sorted(mapear.MAPAS_SERIE_CONHECIDOS),
    )
    imagem_b64 = base64.b64encode(png_bytes).decode("ascii")
    try:
        bruto_texto = provedor.analisar(imagem_base64=imagem_b64, mime="image/png", prompt=prompt)
        bruto = mapear.parsear_resposta(bruto_texto)
    except ErroNucleo as exc:
        return None, [f"modelo de visão indisponível ({exc.codigo}): {exc.mensagem}"]
    return mapear.sanitizar_resposta(bruto)


def _analisar_imagem_bytes(png_bytes: bytes) -> dict[str, Any]:
    medidas = imagem_mod.medir_imagem(png_bytes)
    analise, avisos_visao = _chamar_visao(png_bytes, medidas)
    proposta = mapear.montar_proposta(
        analise=analise,
        avisos_sanitizacao=avisos_visao,
        orientacao=medidas.get("orientacao"),
    )
    return {"fonte": "imagem", "medidas_deterministicas": medidas, **proposta}


def _analisar_pdf(caminho: Path) -> dict[str, Any]:
    info = pdf_mod.analisar_pdf(caminho)
    resultado = _analisar_imagem_bytes(info["png_pagina1"])
    resultado["fonte"] = "pdf"
    resultado["texto_extraido"] = info["texto"][:2000]
    resultado["tem_texto_pdf"] = info["tem_texto"]
    return resultado


def _analisar_mxd(caminho: Path) -> dict[str, Any]:
    resultado = mxd_strings.extrair(caminho)
    resultado["perguntas"] = []
    resultado["mapspec_candidato"] = None
    resultado["proximos_passos"] = [
        "Sem ArcMap não dá para montar um MapSpec automático a partir do .mxd — use "
        "usar_modelo_da_galeria/criar_mapa como base e adicionar_camada/editar_camada "
        "com os candidatos_camada encontrados.",
    ]
    return resultado


def _analisar_zip(caminho: Path, *, guard: WorkspaceGuard) -> dict[str, Any]:
    inventario = zip_inventario.inventariar(caminho)

    if inventario["mxds"]:
        extraido = zip_simcar.extrair(caminho, guard=guard, subpasta=f"analise_{caminho.stem}")
        alvo_rel = next((a for a in extraido["arquivos"] if a.lower().endswith(".mxd")), None)
        if alvo_rel is not None:
            resultado = _analisar_mxd(guard.raiz / alvo_rel)
            resultado["fonte"] = "zip_mxd"
            resultado["inventario"] = inventario
            return resultado

    if len(inventario["pdfs"]) == 1 and not inventario["mxds"]:
        extraido = zip_simcar.extrair(caminho, guard=guard, subpasta=f"analise_{caminho.stem}")
        alvo_rel = next((a for a in extraido["arquivos"] if a.lower().endswith(".pdf")), None)
        if alvo_rel is not None:
            resultado = _analisar_pdf(guard.raiz / alvo_rel)
            resultado["fonte"] = "zip_pdf"
            resultado["inventario"] = inventario
            return resultado

    return {
        "fonte": "zip",
        "inventario": inventario,
        "perguntas": [],
        "avisos": [
            "zip sem .mxd e sem PDF único de referência — só o inventário. Se houver "
            "shapefiles candidatos, use zip.extrair e depois adicionar_camada manualmente.",
        ],
        "mapspec_candidato": None,
        "proximos_passos": [] if not inventario["shapefiles_stems"] else [
            f"shapefiles candidatos no zip: {', '.join(inventario['shapefiles_stems'][:10])} "
            "— extraia com zip.extrair para usá-los.",
        ],
    }


def analisar_referencia(arquivo_rel: str, *, guard: WorkspaceGuard) -> dict[str, Any]:
    """`{arquivo}` relativo ao workspace (AP-11, via `fsguard`) → proposta F1-07."""
    caminho = guard.resolver(arquivo_rel)  # CaminhoNaoAutorizado se fora do workspace
    if not caminho.is_file():
        raise ErroNucleo("NU-001", f"Arquivo de referência não encontrado: {arquivo_rel}")

    sufixo = caminho.suffix.lower()
    if sufixo in EXTENSOES_IMAGEM:
        resultado = _analisar_imagem_bytes(caminho.read_bytes())
    elif sufixo == ".pdf":
        resultado = _analisar_pdf(caminho)
    elif sufixo == ".mxd":
        resultado = _analisar_mxd(caminho)
    elif sufixo == ".zip":
        resultado = _analisar_zip(caminho, guard=guard)
    else:
        raise ErroNucleo(
            "NU-001",
            f"Extensão não suportada para análise de referência: '{sufixo or '(sem extensão)'}'. "
            "Use imagem (.png/.jpg), .pdf, .mxd ou .zip.",
        )
    resultado.setdefault("arquivo", arquivo_rel)
    return resultado
