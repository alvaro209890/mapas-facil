"""Quem é o imóvel — descoberto, não perguntado.

Entrada: o polígono ATP que o usuário largou na pasta. Saída: município, número
do CAR estadual e federal, área registrada e situação. Nada disso é perguntado
ao usuário enquanto der para deduzir:

- **município** sai da base IBGE versionada no repo, por ponto-em-polígono —
  sem rede, sem chave, sem chute;
- **CAR** sai da camada `car_atp` do catálogo (CAR digital da SEMA-MT),
  escolhendo o registro cuja geometria mais se sobrepõe ao polígono entregue.

Privacidade é regra, não zelo: a camada do CAR traz `NOMESPROPRIETARIOS` e a de
embargos traz `CPF_CNPJ`. **Nenhum dos dois sai daqui** — a lista branca de
campos em `CAMPOS_CAR` é a única coisa que atravessa (AP-09/LGPD).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyproj import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapasfacil_nucleo.camadas import ibge as ibge_mod
from mapasfacil_nucleo.camadas.resolver import resolver_camada
from mapasfacil_nucleo.fsguard import WorkspaceGuard

CAMADA_CAR = "car_atp"
"""CAR digital validado da SEMA-MT. `car_sema` (requerimentos) é o plano B."""

CAMADA_CAR_ALTERNATIVA = "car_sema"

CAMPOS_CAR = (
    "NUMEROESTADUAL",
    "CAR_FEDERAL",
    "CODIGO_CAR_FEDERAL",
    "NOMEPROPRIEDADE",
    "SITUACAO_CAR",
    "SITUACAO",
    "PROTOCOLO",
    "CODIGO",
    "MODULOS_FISCAIS",
    "MUNICIPIO_CODIGO",
    "AREA_HA",
)
"""Lista branca. O que não está aqui **não** é lido — inclusive nome e CPF."""

IOU_MINIMO = 0.60
"""Abaixo disso não é o mesmo imóvel: é vizinho encostado ou sobreposição."""


@dataclass(frozen=True)
class IdentidadeImovel:
    """O que o sistema sabe do imóvel sem ter perguntado nada."""

    nome: str
    area_atp_ha: float
    municipio: dict[str, str]
    car_estadual: str | None = None
    car_federal: str | None = None
    protocolo: str | None = None
    codigo_car: str | None = None
    situacao_car: str | None = None
    area_car_ha: float | None = None
    modulos_fiscais: float | None = None
    confianca: float = 0.0
    fonte_car: str | None = None
    avisos: list[str] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        """O texto que vai para o rótulo do mapa e para a legenda."""
        return self.nome

    def para_mapspec(self) -> dict[str, Any]:
        """Bloco `imovel` do MapSpec — sem nenhum dado pessoal."""
        return {
            "nome": self.nome,
            # O contrato MapSpec exige string; CAR não encontrado é representado
            # por vazio e permanece declarado nos avisos da identificação.
            "car": self.car_estadual or "",
            "matricula": None,
            "area_total_ha": round(self.area_atp_ha, 4),
            "municipio": {
                "nome": self.municipio.get("nome", ""),
                "ibge": self.municipio.get("cod_ibge", ""),
                "uf": self.municipio.get("sigla_uf", "MT"),
            },
            "geometria": "local.ATP",
        }

    def para_ndjson(self) -> dict[str, Any]:
        return {
            "nome": self.nome,
            "car_estadual": self.car_estadual,
            "car_federal": self.car_federal,
            "situacao": self.situacao_car,
            "area_atp_ha": round(self.area_atp_ha, 4),
            "area_car_ha": self.area_car_ha,
            "modulos_fiscais": self.modulos_fiscais,
            "municipio": self.municipio,
            "confianca": round(self.confianca, 4),
            "fonte_car": self.fonte_car,
            "avisos": list(self.avisos),
        }


def _apenas_permitidos(props: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in props.items() if k in CAMPOS_CAR}


def _numero(valor: Any) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _centroide_lonlat(geom: BaseGeometry, epsg: int) -> tuple[float, float]:
    ponto = geom.representative_point()
    para_geo = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4674", always_xy=True)
    lon, lat = para_geo.transform(ponto.x, ponto.y)
    return float(lon), float(lat)


def _melhor_sobreposicao(
    alvo: BaseGeometry,
    geometrias: list[BaseGeometry],
    propriedades: list[dict[str, Any]],
) -> tuple[float, dict[str, Any]] | None:
    """Registro do CAR com maior IoU contra o polígono entregue.

    IoU (e não "só interseção") porque o imóvel entregue pode estar dentro de um
    CAR muito maior — cobertura alta e identidade errada. Área semelhante **e**
    posição semelhante é o que caracteriza o mesmo imóvel.
    """
    melhor: tuple[float, dict[str, Any]] | None = None
    for geom, props in zip(geometrias, propriedades):
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        try:
            intersecao = geom.intersection(alvo).area
            uniao = geom.union(alvo).area
        except Exception:  # noqa: BLE001 — geometria patológica não derruba a análise
            continue
        if uniao <= 0 or intersecao <= 0:
            continue
        iou = intersecao / uniao
        if melhor is None or iou > melhor[0]:
            melhor = (iou, _apenas_permitidos(props))
    return melhor


def identificar(
    atp: list[BaseGeometry] | BaseGeometry,
    *,
    guard: WorkspaceGuard,
    epsg: int = 31982,
    nome_fallback: str = "Imóvel sem nome",
    consultar_car: bool = True,
) -> IdentidadeImovel:
    """Resolve município + CAR a partir do polígono. Nunca levanta por rede."""
    geom = atp if isinstance(atp, BaseGeometry) else unary_union(list(atp))
    if not geom.is_valid:
        geom = geom.buffer(0)
    area_ha = geom.area / 10_000.0
    avisos: list[str] = []

    lon, lat = _centroide_lonlat(geom, epsg)
    municipio = ibge_mod.municipio_do_ponto(lon, lat) or {}
    if not municipio:
        avisos.append(
            "Município não resolvido pela base IBGE local — o centroide do imóvel "
            "caiu fora de todos os polígonos municipais."
        )

    if not consultar_car:
        return IdentidadeImovel(
            nome=nome_fallback,
            area_atp_ha=area_ha,
            municipio=municipio,
            avisos=avisos,
        )

    bbox = tuple(geom.bounds)  # type: ignore[assignment]
    melhor: tuple[float, dict[str, Any]] | None = None
    fonte: str | None = None
    for camada_id in (CAMADA_CAR, CAMADA_CAR_ALTERNATIVA):
        try:
            resultado = resolver_camada(camada_id, bbox, f"EPSG:{epsg}", guard=guard)
        except Exception as exc:  # noqa: BLE001 — sem CAR o mapa ainda sai
            avisos.append(f"Camada '{camada_id}' indisponível: {exc}")
            continue
        candidato = _melhor_sobreposicao(geom, resultado.geometrias, resultado.propriedades)
        if candidato and (melhor is None or candidato[0] > melhor[0]):
            melhor, fonte = candidato, camada_id
        if melhor and melhor[0] >= 0.99:
            break

    if melhor is None or melhor[0] < IOU_MINIMO:
        if melhor is not None:
            avisos.append(
                f"Nenhum registro do CAR bateu com o polígono (melhor sobreposição "
                f"{melhor[0]:.2f}, mínimo {IOU_MINIMO:.2f})."
            )
        else:
            avisos.append("Nenhum registro do CAR encontrado no bbox do imóvel.")
        return IdentidadeImovel(
            nome=nome_fallback,
            area_atp_ha=area_ha,
            municipio=municipio,
            avisos=avisos,
        )

    iou, props = melhor
    nome_bruto = str(props.get("NOMEPROPRIEDADE") or "").strip()
    codigo = props.get("CODIGO")

    return IdentidadeImovel(
        nome=_formatar_nome(nome_bruto) or nome_fallback,
        area_atp_ha=area_ha,
        municipio=municipio,
        car_estadual=str(props.get("NUMEROESTADUAL") or "") or None,
        car_federal=str(props.get("CAR_FEDERAL") or props.get("CODIGO_CAR_FEDERAL") or "") or None,
        protocolo=str(props.get("PROTOCOLO") or "") or None,
        codigo_car=str(codigo) if codigo not in (None, "") else None,
        situacao_car=_formatar_situacao(props.get("SITUACAO_CAR") or props.get("SITUACAO")),
        area_car_ha=_numero(props.get("AREA_HA")),
        modulos_fiscais=_numero(props.get("MODULOS_FISCAIS")),
        confianca=iou,
        fonte_car=fonte,
        avisos=avisos,
    )


def _formatar_nome(bruto: str) -> str:
    """`FAZENDA ARUANÃ I` → `Fazenda Aruanã I`.

    O CAR grava tudo em caixa alta; o rótulo do mapa-modelo é capitalizado.
    Algarismo romano e conectivo minúsculo são as duas exceções que aparecem em
    nome de fazenda.
    """
    if not bruto:
        return ""
    romanos = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"}
    conectivos = {"de", "da", "do", "das", "dos", "e"}
    palavras: list[str] = []
    for i, palavra in enumerate(bruto.split()):
        limpa = palavra.strip()
        if not limpa:
            continue
        if limpa.upper() in romanos:
            palavras.append(limpa.upper())
        elif i > 0 and limpa.lower() in conectivos:
            palavras.append(limpa.lower())
        else:
            palavras.append(limpa.capitalize())
    return " ".join(palavras)


def _formatar_situacao(bruto: Any) -> str | None:
    """`[AGUARDANDO_ENVIO_PRA]` → `Aguardando envio PRA`."""
    if not bruto:
        return None
    texto = str(bruto).strip().strip("[]").replace("_", " ").strip()
    if not texto:
        return None
    partes = texto.split()
    saida = [partes[0].capitalize()]
    for parte in partes[1:]:
        saida.append(parte if parte.isupper() and len(parte) <= 4 else parte.lower())
    return " ".join(saida)
