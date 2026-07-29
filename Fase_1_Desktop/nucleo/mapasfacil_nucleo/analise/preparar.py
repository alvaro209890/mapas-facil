"""Materializa, no workspace, as camadas que a série de mapas usa.

A série inteira desenha a partir de shapefiles locais com **nome canônico**
(`ATP`, `AVN`, `AUAS`, `TIPOLOGIA_FLORESTA`…). Materializar antes, uma vez, tem
três motivos concretos:

1. o motor nativo, os quantitativos e o caminho `.mxd` já sabem ler `local.*` —
   nada precisa aprender a falar WFS;
2. a mesma camada aparece em vários mapas da série (o perímetro aparece nos 20):
   resolver uma vez e reusar evita 20 idas à SEMA;
3. camada temática se pinta **por classe** — Floresta × Cerrado, ano do PRODES.
   Cada classe vira um shapefile próprio, e aí cada uma tem estilo e item de
   legenda como no modelo, sem o motor precisar entender atributo.

Recorte: camada do imóvel é recortada **no polígono do imóvel** (é o que o
modelo mostra); camada de contexto é recortada no extent do mapa, porque some se
for cortada no imóvel — embargo vizinho, TI ao lado, alerta na divisa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import shapefile  # pyshp
from pyproj import CRS
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapasfacil_nucleo.camadas import clip as clip_mod
from mapasfacil_nucleo.camadas.resolver import escrever_shapefile, resolver_camada
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.geo.area import reprojetar
from mapasfacil_nucleo.workspace.shapefile import _abrir_reader, _shapes_para_geometrias

PASTA_PADRAO = "SHP"

RECORTE_IMOVEL = "imovel"
RECORTE_EXTENT = "extent"


@dataclass(frozen=True)
class FonteAnalise:
    """Uma camada da série: de onde vem, como recorta e como se chama aqui."""

    papel: str
    camada: str
    recorte: str = RECORTE_EXTENT
    classe_campo: str | None = None
    classe_valor: str | None = None
    obrigatoria: bool = False
    descricao: str = ""


# As camadas da série, na ordem em que fazem sentido resolver. Os papéis são os
# nomes que as receitas de `serie.py` citam como `local.<papel>`.
FONTES: tuple[FonteAnalise, ...] = (
    # — do imóvel (recortadas no polígono) —
    FonteAnalise("AVN", "car_avn", RECORTE_IMOVEL, obrigatoria=False, descricao="Área de vegetação nativa"),
    FonteAnalise("AC", "area_consolidada_simcar", RECORTE_IMOVEL, descricao="Área consolidada"),
    FonteAnalise("AUAS", "car_auas", RECORTE_IMOVEL, descricao="Área derivada de desmate após 2008"),
    FonteAnalise("APP", "car_app", RECORTE_IMOVEL, descricao="Área de preservação permanente"),
    FonteAnalise("APPD", "car_appd", RECORTE_IMOVEL, descricao="APP degradada"),
    FonteAnalise("ARL", "car_arl", RECORTE_IMOVEL, descricao="Reserva legal"),
    # — contexto (recortadas no extent do mapa) —
    FonteAnalise("MUNICIPIOS", "lim_municipios_mt", descricao="Limite municipal"),
    FonteAnalise("DLA", "dla", descricao="Declaração de limpeza de área"),
    FonteAnalise("PEF", "autorizacao_desmate_sema", descricao="Desmate licenciado"),
    FonteAnalise("EMBARGOS_SEMA", "embargos_sema", descricao="Áreas embargadas SEMA"),
    FonteAnalise("EMBARGOS_SIGA", "embargos_siga", descricao="Área embargada SIGA (polígono)"),
    FonteAnalise("EMBARGOS_IBAMA", "embargos_ibama", descricao="Áreas embargadas pelo Ibama"),
    FonteAnalise("TERRAS_INDIGENAS", "terras_indigenas_funai", descricao="Terras Indígenas"),
    FonteAnalise("UNIDADES_CONSERVACAO", "unidades_conservacao", descricao="Unidades de Conservação"),
    FonteAnalise("ALERTAS_MAPBIOMAS", "alertas_mapbiomas", descricao="Alertas emitidos pelo MapBiomas"),
    FonteAnalise("PRODES", "prodes_yearly", descricao="Alertas emitidos pelo PRODES"),
    FonteAnalise(
        "TIPOLOGIA_FLORESTA",
        "tipologia_sema",
        classe_campo="TIPO",
        classe_valor="FLORESTA",
        descricao="Tipologia: Floresta",
    ),
    FonteAnalise(
        "TIPOLOGIA_CERRADO",
        "tipologia_sema",
        classe_campo="TIPO",
        classe_valor="CERRADO",
        descricao="Tipologia: Cerrado",
    ),
)

BASES_LOCAIS: dict[str, str] = {
    "UF": "lml_uf_a",
}
"""Bases versionadas no repo (IBGE) — não passam por rede."""


@dataclass
class ResultadoPreparacao:
    """O que ficou pronto no workspace, e o que faltou."""

    fontes_idx: dict[str, str] = field(default_factory=dict)
    feicoes: dict[str, int] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    falhas: dict[str, str] = field(default_factory=dict)
    identidade: dict[str, Any] | None = None

    def tem(self, papel: str) -> bool:
        return papel in self.fontes_idx and self.feicoes.get(papel, 0) > 0

    def para_ndjson(self) -> dict[str, Any]:
        return {
            "camadas": [
                {"papel": p, "arquivo": a, "feicoes": self.feicoes.get(p, 0)}
                for p, a in sorted(self.fontes_idx.items())
            ],
            "falhas": dict(self.falhas),
            "avisos": list(self.avisos),
        }


def _geom_do_shapefile(caminho: Path) -> BaseGeometry | None:
    reader, _enc = _abrir_reader(caminho)
    geoms = [g for g in _shapes_para_geometrias(reader) if not g.is_empty]
    if not geoms:
        return None
    uniao = unary_union(geoms)
    return uniao if uniao.is_valid else uniao.buffer(0)


def _valor_classe(props: dict[str, Any], campo: str) -> str:
    return str(props.get(campo) or "").strip().upper()


def _base_local_para(
    stem: str,
    *,
    guard: WorkspaceGuard,
    extent: tuple[float, float, float, float],
    epsg: int,
    destino_papel: str,
    pasta: str,
) -> tuple[str, int]:
    """Copia uma base do repo (WGS84) recortada no extent, já no CRS do mapa."""
    from mapasfacil_nucleo.camadas import ibge as ibge_mod

    origem = ibge_mod.pasta_shapefile_repo() / f"{stem}.shp"
    if not origem.is_file():
        raise ErroNucleo("NU-241", f"Base local ausente: {origem}")

    reader = shapefile.Reader(str(origem))
    geoms: list[BaseGeometry] = []
    for shp in reader.iterShapes():
        try:
            geom = reprojetar(_shape_para_geom(shp), 4674, epsg)
        except Exception:  # noqa: BLE001 — feição quebrada da base não derruba
            continue
        if geom.is_empty:
            continue
        geoms.append(geom)
    recortadas = clip_mod.clip_bbox(geoms, extent)
    destino = guard.resolver(f"{pasta}/{destino_papel}", escrita=True)
    escritas = escrever_shapefile(destino, recortadas, epsg)
    return str(destino.with_suffix(".shp").relative_to(guard.raiz)), escritas


def _shape_para_geom(shp: Any) -> BaseGeometry:
    from shapely.geometry import shape as _shape

    return _shape(shp.__geo_interface__)


def preparar(
    *,
    guard: WorkspaceGuard,
    atp_rel: str,
    extent: tuple[float, float, float, float],
    epsg: int = 31982,
    pasta: str = PASTA_PADRAO,
    fontes: tuple[FonteAnalise, ...] = FONTES,
    ao_progresso: Callable[[str, int, int], None] | None = None,
) -> ResultadoPreparacao:
    """Resolve e materializa as camadas da análise. Falha de uma não para as outras.

    `extent` é o retângulo do **maior** mapa da série: resolver uma vez nele
    serve todos os mapas, porque recorte menor é só filtro local depois.
    """
    resultado = ResultadoPreparacao()

    atp_path = guard.resolver(atp_rel)
    if not atp_path.is_file():
        raise ErroNucleo("NU-240", f"Polígono do imóvel não encontrado: {atp_rel}")
    resultado.fontes_idx["ATP"] = str(atp_path.relative_to(guard.raiz))
    imovel = _geom_do_shapefile(atp_path)
    if imovel is None:
        raise ErroNucleo("NU-240", f"Polígono do imóvel vazio: {atp_rel}")
    resultado.feicoes["ATP"] = 1

    total = len(fontes) + len(BASES_LOCAIS)
    indice = 0

    # Uma resolução por camada do catálogo, reusada pelas classes que dela saem.
    cache_resolucao: dict[str, Any] = {}

    for fonte in fontes:
        indice += 1
        if ao_progresso:
            ao_progresso(fonte.papel, indice, total)
        try:
            if fonte.camada not in cache_resolucao:
                resolucao = resolver_camada(fonte.camada, extent, f"EPSG:{epsg}", guard=guard)
                if resolucao.vazia and resolucao.origem_cache != "miss":
                    # Cache antigo pode guardar um vazio de soluço do serviço.
                    # Antes de aceitar "não tem nada aqui", pergunta ao vivo.
                    resolucao = resolver_camada(
                        fonte.camada, extent, f"EPSG:{epsg}", guard=guard, usar_cache=False
                    )
                cache_resolucao[fonte.camada] = resolucao
            resolucao = cache_resolucao[fonte.camada]
        except Exception as exc:  # noqa: BLE001 — série continua sem esta camada
            codigo = getattr(exc, "codigo", type(exc).__name__)
            resultado.falhas[fonte.papel] = f"{codigo}: {getattr(exc, 'mensagem', exc)}"
            resultado.avisos.append(
                f"Camada '{fonte.camada}' ({fonte.descricao or fonte.papel}) indisponível: {codigo}."
            )
            if fonte.obrigatoria:
                raise
            continue

        pares = list(zip(resolucao.geometrias, resolucao.propriedades or [{}] * len(resolucao.geometrias)))
        if fonte.classe_campo and fonte.classe_valor:
            alvo = fonte.classe_valor.strip().upper()
            pares = [(g, p) for g, p in pares if _valor_classe(p, fonte.classe_campo) == alvo]

        geoms = [g for g, _ in pares]
        if fonte.recorte == RECORTE_IMOVEL:
            geoms = clip_mod.clip_poligono(geoms, imovel)

        destino = guard.resolver(f"{pasta}/{fonte.papel}", escrita=True)
        escritas = escrever_shapefile(destino, geoms, epsg)
        resultado.fontes_idx[fonte.papel] = str(destino.with_suffix(".shp").relative_to(guard.raiz))
        resultado.feicoes[fonte.papel] = escritas
        if escritas == 0:
            resultado.avisos.append(
                f"'{fonte.descricao or fonte.papel}' não tem feição nesta área — "
                "o mapa correspondente sai sem essa camada."
            )

    _derivar(resultado, guard=guard, epsg=epsg, pasta=pasta)

    for papel, stem in BASES_LOCAIS.items():
        indice += 1
        if ao_progresso:
            ao_progresso(papel, indice, total)
        try:
            rel, escritas = _base_local_para(
                stem,
                guard=guard,
                extent=extent,
                epsg=epsg,
                destino_papel=papel,
                pasta=pasta,
            )
            resultado.fontes_idx[papel] = rel
            resultado.feicoes[papel] = escritas
        except Exception as exc:  # noqa: BLE001
            resultado.falhas[papel] = str(exc)

    return resultado


# Camadas que **não** vêm de serviço nenhum: saem de conta sobre as que vieram.
# Cada uma existe porque o modelo do Julio tem o item na legenda e o dado
# correspondente não é publicado por ninguém.
DERIVADAS: tuple[dict[str, Any], ...] = (
    {
        "papel": "AREA_PRECISA_DLA",
        "operacao": "diferenca",
        "de": "AUAS",
        "menos": "DLA",
        "descricao": "Área derivada de desmate após 2008 ainda sem DLA emitida",
    },
    {
        "papel": "TI_AMORTECIMENTO",
        "operacao": "anel",
        "de": "TERRAS_INDIGENAS",
        "metros": 10_000.0,
        "descricao": "Zona de amortecimento da Terra Indígena (aproximação de 10 km)",
    },
    {
        "papel": "UC_AMORTECIMENTO",
        "operacao": "anel",
        "de": "UNIDADES_CONSERVACAO",
        "metros": 3_000.0,
        "descricao": "Zona de amortecimento da UC (3 km, CONAMA 428/2010)",
    },
)


def _ler_geometrias(guard: WorkspaceGuard, rel: str) -> list[BaseGeometry]:
    caminho = guard.resolver(rel)
    if not caminho.is_file():
        return []
    reader, _enc = _abrir_reader(caminho)
    return [g for g in _shapes_para_geometrias(reader) if not g.is_empty]


def _derivar(
    resultado: ResultadoPreparacao,
    *,
    guard: WorkspaceGuard,
    epsg: int,
    pasta: str,
) -> None:
    """Calcula as camadas que nenhum serviço publica (lacunas C3/C4 do GOAL)."""
    for regra in DERIVADAS:
        papel = str(regra["papel"])
        origem_rel = resultado.fontes_idx.get(str(regra["de"]))
        if not origem_rel:
            continue
        origem = _ler_geometrias(guard, origem_rel)
        if not origem:
            continue

        try:
            base = unary_union(origem)
            if not base.is_valid:
                base = base.buffer(0)

            if regra["operacao"] == "diferenca":
                outro_rel = resultado.fontes_idx.get(str(regra["menos"]))
                subtrair = _ler_geometrias(guard, outro_rel) if outro_rel else []
                geom = base
                if subtrair:
                    corte = unary_union(subtrair)
                    geom = base.difference(corte if corte.is_valid else corte.buffer(0))
            else:  # anel de amortecimento
                metros = float(regra["metros"])
                geom = base.buffer(metros).difference(base)

            if geom.is_empty:
                resultado.feicoes[papel] = 0
                continue
            partes = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
            destino = guard.resolver(f"{pasta}/{papel}", escrita=True)
            escritas = escrever_shapefile(destino, partes, epsg)
            resultado.fontes_idx[papel] = str(destino.with_suffix(".shp").relative_to(guard.raiz))
            resultado.feicoes[papel] = escritas
        except Exception as exc:  # noqa: BLE001 — derivada é bônus, não bloqueio
            resultado.falhas[papel] = str(exc)


def escrever_prj(destino_stem: Path, epsg: int) -> None:
    """Reescreve o `.prj` — usado quando um shapefile é copiado à mão."""
    destino_stem.with_suffix(".prj").write_text(CRS.from_epsg(epsg).to_wkt(), encoding="utf-8")
