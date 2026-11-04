"""As 20 receitas da série "Análise de área", uma por PDF-modelo do acervo.

Cada receita é a tradução literal de um modelo do Julio: o mesmo título, as
mesmas linhas de metadado, os mesmos itens de legenda **na mesma ordem**, o
mesmo formato de página. O que muda de um imóvel para outro é só o dado — nome,
CAR, município, geometria e as camadas que existem naquela região.

De onde vieram os números e textos: `ferramentas/medir_modelos_serie.py`
(anatomia em mm) e `ferramentas/amostrar_cores_modelo.py` (cores). Nada aqui foi
estimado a olho.

Camada que não existe no imóvel simplesmente não entra — e o item some da
legenda junto, como aconteceria no ArcMap. É por isso que a legenda é montada a
partir das camadas efetivamente desenhadas, e não de uma lista fixa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mapasfacil_nucleo.analise.identidade import IdentidadeImovel

PERFIL = "harmonia"
from mapasfacil_nucleo.mapspec.migrar import CONTRACT_ATUAL as CONTRACT_VERSION  # noqa: E402
from mapasfacil_nucleo.motores.folhas import folha_do_template, folha_padrao


@dataclass(frozen=True)
class CamadaReceita:
    """Uma camada do mapa: papel local, estilo oficial e rótulo da legenda."""

    papel: str
    estilo: str
    legenda: str | None
    ordem: int
    rotulo_imovel: bool = False


@dataclass(frozen=True)
class ReceitaMapa:
    """O contrato de um mapa da série."""

    id: str
    ordem: int
    nome: str
    modelo_pdf: str
    titulo: str
    camadas: tuple[CamadaReceita, ...]
    metadados: tuple[tuple[str, str], ...]
    basemap: str
    folga_extent: float = 1.12
    tabela: bool = False
    escala: Any = "auto"
    notas: tuple[str, ...] = field(default_factory=tuple)

    @property
    def template(self) -> str:
        return f"serie_{self.id}"


# Camadas que aparecem em quase todo mapa retrato da série, sempre nesta ordem
# de legenda: imóvel, limite municipal, limite estadual.
_BASE_RETRATO = (
    CamadaReceita("ATP", "perimetro_imovel", "{imovel}", 10, rotulo_imovel=True),
    CamadaReceita("MUNICIPIOS", "limite_municipal", "Limite municipal", 90),
    CamadaReceita("UF", "limite_estadual", "Limite estadual", 95),
)

# Os paisagem temáticos do acervo não trazem limite municipal/estadual na
# legenda — só o imóvel e o tema.
_BASE_PAISAGEM = (CamadaReceita("ATP", "perimetro_imovel", "{imovel}", 10, rotulo_imovel=True),)

_META_DINAMICA_COM_FONTE = (
    ("Satélite/Sensor", "auto"),
    ("Data da imagem", "auto"),
    ("Fonte", "WMS-SEMA"),
    ("Datum", "auto"),
    ("Escala", "auto"),
)

_META_DINAMICA_SEM_FONTE = (
    ("Satélite/Sensor", "auto"),
    ("Data da imagem", "auto"),
    ("Datum", "auto"),
    ("Escala", "auto"),
)

_META_TEMATICO_PLANET = (
    ("Satélite", "auto"),
    ("Data da imagem", "auto"),
    ("Datum", "auto"),
)


def _dinamica(id_: str, ordem: int, ano: int, basemap: str, *, com_fonte: bool) -> ReceitaMapa:
    """Mapa de dinâmica: imagem do ano + perímetro. É o miolo da série."""
    return ReceitaMapa(
        id=id_,
        ordem=ordem,
        nome=f"Dinâmica {ano}",
        modelo_pdf=f"Dinamica_{ano}.pdf",
        titulo=f"Ano: {ano}",
        camadas=_BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE if com_fonte else _META_DINAMICA_SEM_FONTE,
        basemap=basemap,
    )


RECEITAS: tuple[ReceitaMapa, ...] = (
    ReceitaMapa(
        id="alertas_mapbiomas",
        ordem=1,
        nome="Alertas MapBiomas",
        modelo_pdf="Alertas_MAPBIOMAS_2.pdf",
        titulo="Alertas MAPBIOMAS",
        camadas=(
            CamadaReceita("ALERTAS_MAPBIOMAS", "alerta_mapbiomas", "Alertas emitidos pelo MapBiomas", 20),
        )
        + _BASE_PAISAGEM,
        metadados=_META_TEMATICO_PLANET,
        basemap="2026",
    ),
    ReceitaMapa(
        id="alertas_prodes",
        ordem=2,
        nome="Alertas PRODES",
        modelo_pdf="Alertas_PRODES_VF.pdf",
        titulo="Alertas PRODES",
        camadas=(CamadaReceita("PRODES", "alerta_prodes", "Alertas emitidos pelo PRODES", 20),)
        + _BASE_PAISAGEM,
        metadados=_META_TEMATICO_PLANET,
        basemap="2026",
    ),
    ReceitaMapa(
        id="dla",
        ordem=3,
        nome="Declarações de limpeza de área",
        modelo_pdf="DLA.pdf",
        titulo="Declarações de limpeza de área",
        camadas=(CamadaReceita("DLA", "dla", "Declaração de Limpeza de Área - DLA", 20),)
        + _BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="2026",
    ),
    ReceitaMapa(
        id="unidades_conservacao",
        ordem=4,
        nome="Unidades de Conservação",
        modelo_pdf="Unidade_de_Conservação.pdf",
        titulo="Unidades de Conservação",
        camadas=(
            CamadaReceita("UC_AMORTECIMENTO", "uc_amortecimento", "Unidades de Conservação - Amortecimento", 30),
            CamadaReceita("UNIDADES_CONSERVACAO", "unidade_conservacao", "Unidades de Conservação", 20),
        )
        + _BASE_PAISAGEM,
        metadados=_META_TEMATICO_PLANET,
        basemap="2026",
        # O modelo enquadra a região inteira: a UC mais próxima da Harmonia está
        # a ~22 km. Enquadrar no imóvel deixaria o mapa vazio.
        folga_extent=6.0,
        notas=("Zona de amortecimento derivada por buffer de 3 km da UC (CONAMA 428/2010).",),
    ),
    ReceitaMapa(
        id="tipologia",
        ordem=5,
        nome="Tipologia vegetal",
        modelo_pdf="Tipologia.pdf",
        titulo="Tipologia Vegetal",
        camadas=(
            CamadaReceita("TIPOLOGIA_FLORESTA", "tipologia_floresta", "Tipologia: Floresta", 30),
            CamadaReceita("TIPOLOGIA_CERRADO", "tipologia_cerrado", "Tipologia: Cerrado", 31),
        )
        + _BASE_PAISAGEM,
        metadados=(
            ("Base", "Radam Brasil"),
            ("Fonte", "WMS SEMA"),
            ("Datum", "auto"),
        ),
        basemap="2026",
    ),
    ReceitaMapa(
        id="terras_indigenas",
        ordem=6,
        nome="Terras Indígenas",
        modelo_pdf="Terras_Indigenas.pdf",
        titulo="Terras Indígenas",
        camadas=(
            CamadaReceita("TI_AMORTECIMENTO", "zona_amortecimento", "Zona de amortecimento", 30),
            CamadaReceita("TERRAS_INDIGENAS", "terra_indigena", "Terras Indígenas", 20),
        )
        + _BASE_PAISAGEM,
        metadados=(("Fonte", "WMS FUNAI"), ("Datum", "auto")),
        basemap="2026",
        folga_extent=3.0,
        notas=("Zona de amortecimento da TI derivada por buffer de 10 km — aproximação declarada.",),
    ),
    ReceitaMapa(
        id="tcr",
        ordem=7,
        nome="Termo de Recuperação de Área",
        modelo_pdf="TCR.pdf",
        titulo="Termo de Recuperação de Área",
        camadas=(
            CamadaReceita("APPD", "appd", "Área de Preservação permanente Degradada", 20),
        )
        + _BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="2026",
        notas=(
            "Pontos de TAC/TCR não existem em WFS público — o modelo usa dado do "
            "escritório. O mapa sai sem esse item até o usuário fornecer (lacuna C4).",
        ),
    ),
    ReceitaMapa(
        id="pef",
        ordem=8,
        nome="Área desmatada com licenciamento",
        modelo_pdf="PEF.pdf",
        titulo="Área Desmatada Com Licenciamento",
        camadas=(CamadaReceita("PEF", "desmate_licenciado", "Desmate Licenciado", 20),)
        + _BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="2026",
    ),
    ReceitaMapa(
        id="embargos_sema_siga",
        ordem=9,
        nome="Embargos SEMA/SIGA",
        modelo_pdf="Embargos_SEMA_SIGA_Poligono.pdf",
        titulo="Embargos SEMA/SIGA",
        camadas=(
            CamadaReceita("EMBARGOS_SEMA", "embargo_sema", "Áreas Embargadas - SEMA", 20),
            CamadaReceita("EMBARGOS_SIGA", "embargo_siga", "Área Embargada - SIGA - Polígono", 21),
        )
        + _BASE_PAISAGEM,
        metadados=_META_TEMATICO_PLANET,
        basemap="2026",
    ),
    ReceitaMapa(
        id="embargos_ibama",
        ordem=10,
        nome="Embargos IBAMA",
        modelo_pdf="Embargos_IBAMA.pdf",
        titulo="Embargos IBAMA",
        camadas=(CamadaReceita("EMBARGOS_IBAMA", "embargo_ibama", "Áreas embargadas pelo Ibama", 20),)
        + _BASE_PAISAGEM,
        metadados=_META_TEMATICO_PLANET,
        basemap="2026",
    ),
    ReceitaMapa(
        id="areas_cultivaveis",
        ordem=11,
        nome="Áreas cultiváveis",
        modelo_pdf="Areas_Cultivaveis_VF.pdf",
        titulo="Áreas Cultiváveis",
        camadas=(
            CamadaReceita("AREA_PRECISA_DLA", "area_precisa_dla", "Área que Precisara de DLA", 20),
            CamadaReceita("AUAS", "auas", "Área Cultivável Derivada de Desmate Após 2008", 21),
            CamadaReceita("AC", "ac", "Área Cultivável Consolidada", 22),
            CamadaReceita("AVN", "avn", "Área de Vegetação Nativa", 30),
        )
        + _BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="2026",
        notas=("'Área que precisará de DLA' = AUAS menos as DLAs já emitidas (derivação C3).",),
    ),
    ReceitaMapa(
        id="dinamica_quantitativos",
        ordem=12,
        nome="Dinâmica com quantitativos",
        modelo_pdf="Dinamica_2026_quantitativos.pdf",
        titulo="Dinâmica {ano}",
        camadas=(
            CamadaReceita("AUAS", "auas", "Área Derivada de Desmate Após 2008", 20),
            CamadaReceita("AC", "ac", "Área consolidada", 21),
            CamadaReceita("AVN", "avn", "Área de vegetação nativa", 30),
        )
        + _BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="2026",
        tabela=True,
    ),
    _dinamica("dinamica_2026", 13, 2026, "2026", com_fonte=False),
    _dinamica("dinamica_2023", 14, 2023, "2023", com_fonte=False),
    _dinamica("dinamica_2019", 15, 2019, "2019", com_fonte=False),
    _dinamica("dinamica_2017", 16, 2017, "2017", com_fonte=False),
    _dinamica("dinamica_2013", 17, 2013, "2013", com_fonte=True),
    ReceitaMapa(
        id="dinamica_2008_spot",
        ordem=18,
        nome="Dinâmica 2008 (SPOT)",
        modelo_pdf="Dinamica_2008_SPOT.pdf",
        titulo="Ano: 2008",
        camadas=_BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="spot_2008",
        notas=("Marco do Código Florestal: o SPOT 2,5 m prevalece sobre o Landsat 30 m.",),
    ),
    ReceitaMapa(
        id="dinamica_2008_landsat",
        ordem=19,
        nome="Dinâmica 2008 (Landsat)",
        modelo_pdf="Dinamica_2008_LANDSAT.pdf",
        titulo="Ano: 2008",
        camadas=_BASE_RETRATO,
        metadados=_META_DINAMICA_COM_FONTE,
        basemap="landsat5_2008",
    ),
    _dinamica("dinamica_2000", 20, 2000, "landsat5_2000", com_fonte=True),
)

POR_ID: dict[str, ReceitaMapa] = {r.id: r for r in RECEITAS}


def ordenadas() -> list[ReceitaMapa]:
    """Receitas na ordem de entrega (a mesma das páginas do PDF compilado)."""
    return sorted(RECEITAS, key=lambda r: r.ordem)


def montar_mapspec(
    receita: ReceitaMapa,
    identidade: IdentidadeImovel,
    *,
    fontes_disponiveis: dict[str, int],
    pasta_saida: str = "Mapas",
    crs: str = "EPSG:31982",
    mapspec_id: str | None = None,
    saidas: tuple[str, ...] = ("pdf",),
    escala: int | None = None,
) -> dict[str, Any]:
    """Receita + imóvel → MapSpec válido no contrato v2.

    `fontes_disponiveis` é `{papel: nº de feições}`: camada sem feição não entra
    no MapSpec, e portanto não aparece na legenda. É o comportamento do modelo —
    uma legenda com item que não existe no mapa é bug, não zelo.
    """
    nome_imovel = identidade.rotulo
    camadas: list[dict[str, Any]] = []
    for camada in receita.camadas:
        if fontes_disponiveis.get(camada.papel, 0) <= 0:
            continue
        legenda = (camada.legenda or "").replace("{imovel}", nome_imovel) or None
        # O motor enquadra o mapa pelo id `perimetro` (F1-05): com outro id ele
        # usaria o bbox de **todas** as camadas — o limite estadual recortado no
        # extent — e a escala saltava de 1:60.000 para 1:300.000.
        camada_id = "perimetro" if camada.rotulo_imovel else camada.papel.lower()
        entrada: dict[str, Any] = {
            "id": camada_id,
            "nome_no_mxd": legenda or camada.papel,
            "fonte": f"local.{camada.papel}",
            "estilo": camada.estilo,
            "legenda": legenda,
            "ordem": camada.ordem,
        }
        if camada.rotulo_imovel:
            entrada["rotulo_texto"] = nome_imovel
        camadas.append(entrada)

    if not camadas:
        # O schema exige ao menos uma camada, e um mapa sem o imóvel não é mapa.
        raise ValueError(f"Receita '{receita.id}' ficou sem nenhuma camada disponível.")

    titulo = receita.titulo.replace("{ano}", str(_ano_do_basemap(receita.basemap) or ""))
    titulo = titulo.replace("{imovel}", nome_imovel).strip()

    return {
        "contract_version": CONTRACT_VERSION,
        "perfil": PERFIL,
        "id": mapspec_id or f"spec_{receita.id}",
        "versao": 1,
        "titulo": titulo,
        "template": receita.template,
        "folha": folha_do_template(receita.template) or folha_padrao(),
        "saidas": list(saidas),
        "imovel": identidade.para_mapspec(),
        "crs": crs,
        # Escala única da série (W-10 passo 6) entra por aqui; sem ela, a receita decide
        # (`"auto"` = o motor calcula pela folga do imóvel).
        "escala": escala if escala is not None else receita.escala,
        "extent": None,
        "camadas": camadas,
        # Cadeia de recuo por ano: mosaico furado ou ano inexistente cai para o
        # anterior, e só no fim para o SPOT 2008, que cobre MT inteiro.
        "basemap": {
            "tipo": receita.basemap,
            "fallback": ["2023", "2022", "2021", "2020", "landsat8_2017", "spot_2008"],
        },
        "elementos_layout": {
            "titulo_caixa": True,
            "norte": True,
            "grade": True,
            "grade_linhas": False,
            "escala_grafica": False,
            "minimapa": True,
            "metadados": True,
            "legenda": True,
            "logo": True,
            "tabela": receita.tabela,
            "rotulo_imovel": True,
        },
        "metadados": [{"rotulo": r, "valor": v} for r, v in receita.metadados],
        "saida": {
            "pasta": pasta_saida,
            "nome_base": receita.id,
            "caminhos_relativos": True,
        },
    }


def _ano_do_basemap(basemap: str) -> int | None:
    texto = str(basemap)
    if texto.isdigit() and len(texto) == 4:
        return int(texto)
    digitos = "".join(c for c in texto if c.isdigit())
    if len(digitos) >= 4:
        return int(digitos[-4:])
    return None


MARCOS_QUANTITATIVOS = (2000, 2008, 2026)
"""Apenas três marcos da série levam quantitativo (W11-11). As demais são limpas."""


def calcular_quantitativos_dinamica(
    geom_imovel: BaseGeometry,
    geom_ac: BaseGeometry | None = None,
    geom_agua: BaseGeometry | None = None,
    geom_auas: BaseGeometry | None = None,
    geoms_aef: list[BaseGeometry] | None = None,
    limiar_lasca_m2: float = 100.0,
) -> dict[str, Any]:
    """Calcula os quantitativos oficiais da série Dinâmica (W11-11).

    Regras:
    1. AVN = AIR - AC - massa_dagua
    2. Lascas com área < 100 m² (0.01 ha) na divisa são descartadas.
    3. No marco atual: desmate pós-2008 = AC + AUAS, separado em autorizado
       (interseção com AEF da SEMA) e não autorizado.
    """
    from shapely.geometry import MultiPolygon, Polygon
    from shapely.ops import unary_union

    imovel = geom_imovel if geom_imovel.is_valid else geom_imovel.buffer(0)
    area_imovel_m2 = float(imovel.area)

    # 1. AC
    ac = geom_ac.intersection(imovel) if geom_ac and not geom_ac.is_empty else Polygon()
    if not ac.is_valid:
        ac = ac.buffer(0)

    # 2. Água (massa d'água)
    agua = geom_agua.intersection(imovel) if geom_agua and not geom_agua.is_empty else Polygon()
    if not agua.is_valid:
        agua = agua.buffer(0)

    # 3. AVN = AIR - AC - massa_dagua
    ocupado = unary_union([ac, agua])
    avn_raw = imovel.difference(ocupado) if not ocupado.is_empty else imovel
    if not avn_raw.is_valid:
        avn_raw = avn_raw.buffer(0)

    # Descarte de lascas < 100 m²
    poligonos_avn = []
    if isinstance(avn_raw, Polygon):
        if avn_raw.area >= limiar_lasca_m2:
            poligonos_avn.append(avn_raw)
    elif isinstance(avn_raw, MultiPolygon):
        for p in avn_raw.geoms:
            if p.area >= limiar_lasca_m2:
                poligonos_avn.append(p)

    avn = MultiPolygon(poligonos_avn) if poligonos_avn else Polygon()

    # 4. Desmate pós-2008 (AC + AUAS)
    auas = geom_auas.intersection(imovel) if geom_auas and not geom_auas.is_empty else Polygon()
    desmate_pos_2008 = unary_union([ac, auas])

    desmate_autorizado = Polygon()
    if geoms_aef and not desmate_pos_2008.is_empty:
        aef_uniao = unary_union([g if g.is_valid else g.buffer(0) for g in geoms_aef if not g.is_empty])
        desmate_autorizado = desmate_pos_2008.intersection(aef_uniao)
        if not desmate_autorizado.is_valid:
            desmate_autorizado = desmate_autorizado.buffer(0)

    desmate_nao_autorizado = (
        desmate_pos_2008.difference(desmate_autorizado)
        if not desmate_autorizado.is_empty
        else desmate_pos_2008
    )

    ha = 10_000.0
    return {
        "marcos_com_quantitativo": list(MARCOS_QUANTITATIVOS),
        "area_imovel_ha": round(area_imovel_m2 / ha, 4),
        "ac_ha": round(float(ac.area) / ha, 4),
        "agua_ha": round(float(agua.area) / ha, 4),
        "avn_ha": round(float(avn.area) / ha, 4),
        "auas_ha": round(float(auas.area) / ha, 4),
        "desmate_pos_2008_ha": round(float(desmate_pos_2008.area) / ha, 4),
        "desmate_autorizado_ha": round(float(desmate_autorizado.area) / ha, 4),
        "desmate_nao_autorizado_ha": round(float(desmate_nao_autorizado.area) / ha, 4),
    }
