"""Modelos de dados para o LayoutSpec declarativo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CaixaMm:
    """Caixa delimitadora em milímetros, com origem no topo-esquerdo."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def largura(self) -> float:
        return self.x1 - self.x0

    @property
    def altura(self) -> float:
        return self.y1 - self.y0

    def para_dict(self) -> dict[str, float]:
        return {
            "x0": round(float(self.x0), 3),
            "y0": round(float(self.y0), 3),
            "x1": round(float(self.x1), 3),
            "y1": round(float(self.y1), 3),
        }

    @classmethod
    def de_valor(cls, valor: Any) -> CaixaMm:
        if isinstance(valor, CaixaMm):
            return valor
        if isinstance(valor, dict):
            return cls(
                x0=float(valor["x0"]),
                y0=float(valor["y0"]),
                x1=float(valor["x1"]),
                y1=float(valor["y1"]),
            )
        if isinstance(valor, (list, tuple)) and len(valor) == 4:
            return cls(
                x0=float(valor[0]),
                y0=float(valor[1]),
                x1=float(valor[2]),
                y1=float(valor[3]),
            )
        raise ValueError(f"Formato inválido de caixa: {valor}")


@dataclass(frozen=True)
class DimensoesMm:
    largura: float
    altura: float

    def para_dict(self) -> dict[str, float]:
        return {
            "largura": round(float(self.largura), 3),
            "altura": round(float(self.altura), 3),
        }

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> DimensoesMm:
        return cls(
            largura=float(dados.get("largura", 210.0)),
            altura=float(dados.get("altura", 297.0)),
        )


@dataclass(frozen=True)
class FolhaPadrao:
    formato: str = "A4"
    orientacao: str = "retrato"

    def para_dict(self) -> dict[str, str]:
        return {"formato": self.formato, "orientacao": self.orientacao}

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> FolhaPadrao:
        return cls(
            formato=str(dados.get("formato", "A4")),
            orientacao=str(dados.get("orientacao", "retrato")),
        )


@dataclass(frozen=True)
class Tipografia:
    pt_titulo: float = 24.0
    pt_metadados: float = 9.0
    pt_legenda: float = 8.0
    pt_grade: float = 7.7
    pt_legenda_titulo: float = 0.0
    titulo_legenda: str = "Legenda"
    titulo_metadados: str = "METADADOS IMAGEM"
    fonte_grade: tuple[str, ...] = ("Cambria", "Liberation Serif", "Times New Roman", "DejaVu Serif")

    def para_dict(self) -> dict[str, Any]:
        return {
            "pt_titulo": float(self.pt_titulo),
            "pt_metadados": float(self.pt_metadados),
            "pt_legenda": float(self.pt_legenda),
            "pt_grade": float(self.pt_grade),
            "pt_legenda_titulo": float(self.pt_legenda_titulo),
            "titulo_legenda": str(self.titulo_legenda),
            "titulo_metadados": str(self.titulo_metadados),
            "fonte_grade": list(self.fonte_grade),
        }

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> Tipografia:
        return cls(
            pt_titulo=float(dados.get("pt_titulo", 24.0)),
            pt_metadados=float(dados.get("pt_metadados", 9.0)),
            pt_legenda=float(dados.get("pt_legenda", 8.0)),
            pt_grade=float(dados.get("pt_grade", 7.7)),
            pt_legenda_titulo=float(dados.get("pt_legenda_titulo", 0.0)),
            titulo_legenda=str(dados.get("titulo_legenda", "Legenda")),
            titulo_metadados=str(dados.get("titulo_metadados", "METADADOS IMAGEM")),
            fonte_grade=tuple(dados.get("fonte_grade", ())),
        )


@dataclass
class LayoutSpec:
    """Especificação declarativa e versionada de layout de página."""

    id: str
    nome: str
    orientacao: str
    dimensoes_mm: DimensoesMm
    elementos: dict[str, CaixaMm]
    contract_version: int = 1
    versao: int = 1
    descricao: str = ""
    perfil: str = "harmonia"
    folha_padrao: FolhaPadrao | None = None
    tipografia: Tipografia = field(default_factory=Tipografia)
    crs_padrao: str = "EPSG:31982"
    metadados_medidos: dict[str, Any] = field(default_factory=dict)

    def para_dict(self) -> dict[str, Any]:
        resultado: dict[str, Any] = {
            "contract_version": self.contract_version,
            "versao": self.versao,
            "id": self.id,
            "nome": self.nome,
            "perfil": self.perfil,
            "orientacao": self.orientacao,
            "dimensoes_mm": self.dimensoes_mm.para_dict(),
            "elementos": {k: v.para_dict() for k, v in self.elementos.items()},
            "tipografia": self.tipografia.para_dict(),
            "crs_padrao": self.crs_padrao,
        }
        if self.descricao:
            resultado["descricao"] = self.descricao
        if self.folha_padrao:
            resultado["folha_padrao"] = self.folha_padrao.para_dict()
        if self.metadados_medidos:
            resultado["metadados_medidos"] = dict(self.metadados_medidos)
        return resultado

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> LayoutSpec:
        dim = DimensoesMm.de_dict(dados.get("dimensoes_mm", {}))
        folha = (
            FolhaPadrao.de_dict(dados["folha_padrao"])
            if dados.get("folha_padrao")
            else FolhaPadrao(orientacao=dados.get("orientacao", "retrato"))
        )
        tipo = (
            Tipografia.de_dict(dados["tipografia"])
            if dados.get("tipografia")
            else Tipografia()
        )
        elementos_raw = dados.get("elementos", {})
        elementos = {k: CaixaMm.de_valor(v) for k, v in elementos_raw.items()}

        return cls(
            contract_version=int(dados.get("contract_version", 1)),
            versao=int(dados.get("versao", 1)),
            id=str(dados.get("id", "layout_desconhecido")),
            nome=str(dados.get("nome", "Layout")),
            descricao=str(dados.get("descricao", "")),
            perfil=str(dados.get("perfil", "harmonia")),
            orientacao=str(dados.get("orientacao", folha.orientacao)),
            folha_padrao=folha,
            dimensoes_mm=dim,
            elementos=elementos,
            tipografia=tipo,
            crs_padrao=str(dados.get("crs_padrao", "EPSG:31982")),
            metadados_medidos=dict(dados.get("metadados_medidos", {})),
        )
