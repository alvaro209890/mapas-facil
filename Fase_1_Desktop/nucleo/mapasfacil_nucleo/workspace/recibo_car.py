from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from mapasfacil_nucleo.erros import ErroNucleo


@dataclass(slots=True)
class DocumentoArea:
    documento: str
    tipo: str
    area_ha: float | None


@dataclass(slots=True)
class ReciboCAR:
    nome_imovel: str | None
    municipio: str | None
    uf: str | None
    car_estadual: str | None
    recibo_federal: str | None
    area_total_ha: float | None
    situacao: str | None
    areas: dict[str, float | None] = field(default_factory=dict)
    tipologia: dict[str, float | None] = field(default_factory=dict)
    documentos: list[DocumentoArea] = field(default_factory=list)

    def para_dict(self) -> dict[str, Any]:
        dados = asdict(self)
        # Garantia explícita: CPF nunca é campo
        dados.pop("cpf", None)
        return dados


def _linhas_pdf(caminho: Path) -> list[str]:
    doc = fitz.open(caminho)
    linhas: list[str] = []
    try:
        for pagina in doc:
            texto = pagina.get_text()
            linhas.extend(linha.strip() for linha in texto.splitlines())
    finally:
        doc.close()
    return [l for l in linhas if l]


def _secao(lines: list[str], titulo: str, fins: list[str]) -> list[str]:
    if titulo not in lines:
        return []
    inicio = lines.index(titulo)
    fim = len(lines)
    for marcador in fins:
        if marcador in lines[inicio + 1 :]:
            fim = min(fim, lines.index(marcador, inicio + 1))
    return [l.strip() for l in lines[inicio + 1 : fim] if l.strip()]


def _parse_float_brasileiro(valor: str) -> float | None:
    texto = valor.strip().replace("ha", "").replace("Ha", "").strip()
    if not texto:
        return None
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _extrair_rotulo_valor(lines: list[str], rotulos: list[str]) -> str | None:
    for i, linha in enumerate(lines):
        for rotulo in rotulos:
            if linha.lower().startswith(rotulo.lower()):
                partes = linha.split(":", 1)
                if len(partes) == 2 and partes[1].strip():
                    return partes[1].strip()
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
    return None


def _extrair_areas_tabela(lines: list[str]) -> dict[str, float | None]:
    mapa_rotulos = {
        "area_total": ["Área do Imóvel", "Área total", "Área Total da Propriedade"],
        "arl": ["Reserva Legal", "Área de Reserva Legal"],
        "app": ["Área de Preservação Permanente", "APP"],
        "consolidada": ["Área Consolidada", "Área consolidada"],
        "vegetacao_nativa": ["Área de Vegetação Nativa", "Vegetação Nativa"],
    }
    resultado: dict[str, float | None] = {}
    for chave, rotulos in mapa_rotulos.items():
        valor = _extrair_rotulo_valor(lines, rotulos)
        resultado[chave] = _parse_float_brasileiro(valor) if valor else None
    return resultado


def _extrair_tipologia(lines: list[str]) -> dict[str, float | None]:
    secao = _secao(lines, "Tipologia da Vegetação", ["Dados das Áreas", "Dados de Reserva"])
    tipologia: dict[str, float | None] = {}
    for linha in secao:
        if "Floresta" in linha:
            nums = re.findall(r"[\d.,]+", linha)
            if nums:
                tipologia["floresta_ha"] = _parse_float_brasileiro(nums[-1])
        if "Cerrado" in linha:
            nums = re.findall(r"[\d.,]+", linha)
            if nums:
                tipologia["cerrado_ha"] = _parse_float_brasileiro(nums[-1])
    return tipologia


def _extrair_documentos(lines: list[str]) -> list[DocumentoArea]:
    raw = _secao(
        lines,
        "Dados das Áreas dos Imóveis Rurais",
        ["Dados de Reserva Legal", "Dados de Reserva", "Tipologia"],
    )
    raw = [l for l in raw if l not in ("Documento", "Tipo", "Área (ha)", "Área(ha)")]

    documentos: list[DocumentoArea] = []
    rotulo: list[str] = []
    i = 0
    while i < len(raw):
        linha = raw[i]
        if linha in ("Matrícula", "Posse"):
            area_txt = raw[i + 1] if i + 1 < len(raw) else ""
            documentos.append(
                DocumentoArea(
                    documento=" ".join(rotulo).strip(),
                    tipo=linha,
                    area_ha=_parse_float_brasileiro(area_txt),
                )
            )
            rotulo = []
            i += 2
        else:
            rotulo.append(linha)
            i += 1
    return documentos


def eh_recibo_car(caminho: Path, linhas: list[str] | None = None) -> bool:
    texto = "\n".join(linhas or _linhas_pdf(caminho)).lower()
    marcadores = (
        "cadastro ambiental rural",
        "recibo de inscrição",
        "nº do registro no car",
        "dados das áreas dos imóveis rurais",
    )
    return any(m in texto for m in marcadores)


def parsear(caminho: str | Path) -> ReciboCAR:
    caminho_pdf = Path(caminho)
    if not caminho_pdf.exists():
        raise ErroNucleo("NU-001", "Arquivo PDF não encontrado.", {"caminho": str(caminho_pdf)})

    try:
        linhas = _linhas_pdf(caminho_pdf)
    except Exception as exc:
        raise ErroNucleo("NU-030", "Não foi possível ler o PDF do recibo.") from exc

    if not eh_recibo_car(caminho_pdf, linhas):
        raise ErroNucleo("NU-031", "PDF não parece ser um recibo do CAR.")

    texto_completo = "\n".join(linhas)
    # Descarta CPF: remove linhas com padrão de CPF antes de qualquer extração adicional
    linhas = [l for l in linhas if not re.search(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", l)]

    car_match = re.search(r"\b(MT\d{6,}/\d{4})\b", texto_completo)
    federal_match = re.search(r"\b([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})\b", texto_completo, re.I)

    areas = _extrair_areas_tabela(linhas)

    return ReciboCAR(
        nome_imovel=_extrair_rotulo_valor(linhas, ["Nome do Imóvel", "Imóvel"]),
        municipio=_extrair_rotulo_valor(linhas, ["Município"]),
        uf=_extrair_rotulo_valor(linhas, ["UF"]),
        car_estadual=car_match.group(1) if car_match else None,
        recibo_federal=federal_match.group(1) if federal_match else None,
        area_total_ha=areas.get("area_total"),
        situacao=_extrair_rotulo_valor(linhas, ["Situação", "Situacao"]),
        areas={
            "arl_ha": areas.get("arl"),
            "app_ha": areas.get("app"),
            "consolidada_ha": areas.get("consolidada"),
            "vegetacao_nativa_ha": areas.get("vegetacao_nativa"),
        },
        tipologia=_extrair_tipologia(linhas),
        documentos=_extrair_documentos(linhas),
    )
