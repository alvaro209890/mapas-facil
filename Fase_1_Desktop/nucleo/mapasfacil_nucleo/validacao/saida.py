from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import fitz

from mapasfacil_nucleo.validacao.comparar_pdf import rasterizar_pdf

# Typos e títulos de outras séries vistos no acervo Harmonia (F1-09 / S11).
LISTA_NEGRA_S11 = (
    "concolidada",
    "Dadosr",
    "Alertas MAPBIOMAS",
    "PRODES",
    "Trevisol",
)

_LIMIAR_COBERTURA_H09 = 0.05
_TOLERANCIA_MM_H02 = 1.0


def _check(id_check: str, ok: bool, mensagem: str, *, severidade: str = "hard") -> dict[str, Any]:
    return {"id": id_check, "ok": ok, "mensagem": mensagem, "severidade": severidade}


def _fracao_pixels_nao_brancos(arr) -> float:
    if arr.size == 0:
        return 0.0
    branco = (arr[:, :, 0] > 250) & (arr[:, :, 1] > 250) & (arr[:, :, 2] > 250)
    return float((~branco).sum()) / float(branco.size)


def _formato_pagina_mm(pagina: fitz.Page) -> tuple[float, float]:
    larg_mm = pagina.rect.width * 25.4 / 72.0
    alt_mm = pagina.rect.height * 25.4 / 72.0
    return larg_mm, alt_mm


def _escala_esperada(mapspec: dict[str, Any]) -> int | None:
    escala = mapspec.get("escala")
    if escala is None or isinstance(escala, bool):
        return None
    if isinstance(escala, (int, float)):
        return int(escala)
    texto = str(escala).strip().lower()
    if not texto or texto == "auto":
        return None
    try:
        return int(float(texto.replace(".", "").replace(",", ".")))
    except ValueError:
        return None


def verificar_h01_fontes_quebradas(relatorio_arcpy: dict[str, Any] | None) -> dict[str, Any]:
    if relatorio_arcpy is None:
        return _check(
            "H01",
            False,
            "Relatório ArcPy ausente — não foi possível medir fontes quebradas",
        )
    quebradas = relatorio_arcpy.get("quebradas") or []
    ok = len(quebradas) == 0
    msg = "Nenhuma fonte quebrada no .mxd" if ok else f"Fontes quebradas: {', '.join(map(str, quebradas))}"
    return _check("H01", ok, msg)


def verificar_pdf(
    pdf_path: Path,
    mapspec: dict[str, Any],
    *,
    template: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Checks HARD/SOFT mensuráveis no PDF final (F1-09 §3)."""
    hard: list[dict[str, Any]] = []
    soft: list[dict[str, Any]] = []

    if not pdf_path.is_file():
        hard.append(_check("H09", False, f"PDF ausente: {pdf_path}"))
        return hard, soft

    doc = fitz.open(pdf_path)
    try:
        if doc.page_count == 0:
            hard.append(_check("H09", False, "PDF sem páginas"))
            return hard, soft
        pagina = doc[0]
        texto = pagina.get_text() or ""
        larg_mm, alt_mm = _formato_pagina_mm(pagina)

        formato = (template or {}).get("formato_pagina") or {}
        mm = formato.get("mm") or [210, 297]
        esperado_larg, esperado_alt = float(mm[0]), float(mm[1])
        retrato = (larg_mm, alt_mm) == (esperado_larg, esperado_alt)
        paisagem = (larg_mm, alt_mm) == (esperado_alt, esperado_larg)
        h02_ok = retrato or paisagem
        if not h02_ok:
            h02_ok = (
                abs(larg_mm - esperado_larg) <= _TOLERANCIA_MM_H02
                and abs(alt_mm - esperado_alt) <= _TOLERANCIA_MM_H02
            ) or (
                abs(larg_mm - esperado_alt) <= _TOLERANCIA_MM_H02
                and abs(alt_mm - esperado_larg) <= _TOLERANCIA_MM_H02
            )
        orientacao = formato.get("orientacao", "retrato")
        hard.append(
            _check(
                "H02",
                h02_ok,
                f"Formato {larg_mm:.1f}×{alt_mm:.1f} mm (esperado {orientacao} {esperado_larg}×{esperado_alt})",
            )
        )

        titulo = str(mapspec.get("titulo") or "").strip()
        h03_ok = bool(titulo) and titulo in texto
        hard.append(
            _check(
                "H03",
                h03_ok,
                f"Título '{titulo}' no PDF" if h03_ok else f"Título '{titulo}' não encontrado no texto extraído",
            )
        )

        escala = _escala_esperada(mapspec)
        if escala:
            padroes = (
                rf"1\s*:\s*{escala:,}".replace(",", r"[\s.,]?"),
                rf"1\s*:\s*{escala}",
                rf"Escala:\s*1\s*:\s*{escala}",
            )
            h06_ok = any(re.search(p, texto, re.IGNORECASE) for p in padroes)
            hard.append(
                _check(
                    "H06",
                    h06_ok,
                    f"Escala 1:{escala} no PDF"
                    if h06_ok
                    else f"Escala 1:{escala} não encontrada no texto extraído",
                )
            )

        arr = rasterizar_pdf(pdf_path, dpi=150, pagina=0)
        cobertura = _fracao_pixels_nao_brancos(arr)
        hard.append(
            _check(
                "H09",
                cobertura > _LIMIAR_COBERTURA_H09,
                f"Cobertura não-branca {cobertura * 100:.1f}% (mín. {_LIMIAR_COBERTURA_H09 * 100:.0f}%)",
            )
        )

        metadados = mapspec.get("metadados") or []
        faltando: list[str] = []
        for item in metadados:
            if not isinstance(item, dict):
                continue
            rotulo = str(item.get("rotulo") or "").strip()
            valor = str(item.get("valor") or "").strip()
            if not rotulo or rotulo.lower() == "escala" or valor.lower() == "auto":
                continue
            if rotulo not in texto:
                faltando.append(rotulo)
        h10_ok = not faltando
        hard.append(
            _check(
                "H10",
                h10_ok,
                "Metadados presentes no PDF"
                if h10_ok
                else f"Metadados ausentes no texto: {', '.join(faltando)}",
            )
        )

        soft.append(verificar_s11_texto_herdado(texto, mapspec))
    finally:
        doc.close()

    return hard, soft


def verificar_s11_texto_herdado(texto: str, mapspec: dict[str, Any]) -> dict[str, Any]:
    imovel = mapspec.get("imovel") or {}
    municipio = ((imovel.get("municipio") or {}).get("nome") or "").strip()
    fazenda = str(imovel.get("nome") or "").strip()
    matricula = imovel.get("matricula")

    achados: list[str] = []
    texto_lower = texto.lower()

    for termo in LISTA_NEGRA_S11:
        if termo.lower() in texto_lower:
            achados.append(f"lista negra: {termo}")

    # Matrícula no PDF quando o spec não declara uma.
    if matricula in (None, ""):
        if re.search(r"\bmatr[íi]cula\b", texto, re.IGNORECASE):
            achados.append("menção a matrícula sem valor no MapSpec")

    # Outros municípios MT comuns no acervo (heurística conservadora).
    if municipio:
        candidatos = re.findall(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)*\b", texto)
        for nome in candidatos:
            if len(nome) < 5:
                continue
            if nome != municipio and nome.endswith((" Rica", " Norte", " Sul", " Leste", " Oeste")):
                if municipio not in nome and nome not in municipio:
                    achados.append(f"possível município estranho: {nome}")

    ok = not achados
    return _check(
        "S11",
        ok,
        "Sem indícios de texto herdado" if ok else "; ".join(achados),
        severidade="soft",
    )


def executar_checks_saida(
    mapspec: dict[str, Any],
    *,
    pdf_path: Path | None = None,
    template: dict[str, Any] | None = None,
    relatorio_arcpy: dict[str, Any] | None = None,
    motor: str = "nativo",
) -> dict[str, Any]:
    hard: list[dict[str, Any]] = []
    soft: list[dict[str, Any]] = []

    if motor == "arcpy" or relatorio_arcpy is not None:
        hard.append(verificar_h01_fontes_quebradas(relatorio_arcpy))

    if pdf_path is not None:
        h_pdf, s_pdf = verificar_pdf(pdf_path, mapspec, template=template)
        hard.extend(h_pdf)
        soft.extend(s_pdf)

    confianca = "arcpy" if motor == "arcpy" and relatorio_arcpy else "estrutural"
    if motor == "arcpy" and relatorio_arcpy and (relatorio_arcpy.get("quebradas") or []):
        confianca = "estrutural"

    return {
        "motor": motor,
        "confianca": confianca,
        "checks": {"hard": hard, "soft": soft},
    }
