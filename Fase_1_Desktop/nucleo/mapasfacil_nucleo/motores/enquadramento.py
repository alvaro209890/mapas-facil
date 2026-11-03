"""Enquadramento cartográfico — o **zoom na camada** do ArcMap (W-10, algoritmo de 10 passos).

O que este módulo resolve: dado o que precisa aparecer no mapa (o imóvel, o imóvel + a feição
alvo, ou só a área temática) e o perfil da folha, devolver **escala redonda, extent e CRS** —
sem ninguém ajeitar à mão depois.

As regras vêm medidas nos 18 mapas da Análise PH e nos modelos do escritório:

1. **CRS** — zona UTM SIRGAS 2000 do centroide: `31980` (20 S), `31981` (21 S), `31982` (22 S).
2. **Caixa de conteúdo** — `imovel` (padrão), `imovel_mais_alvo` (TI/UC/TE: une imóvel, feição
   alvo e linha de distância) ou `area_tematica` (DLA/AUAS: só a feição do tema).
3. **Faixa útil** — o quadro do mapa **menos as zonas proibidas** (título, rosa, minimapa,
   legenda, tabela, logo que caem sobre o quadro). É o maior retângulo alinhado aos eixos que
   não toca nenhuma delas; no perfil do escritório, a faixa **abaixo do título**.
4. **Margem de 15 %** sobre a caixa — é o que reproduz a PH: 12,1 km × 1,15 = 13,9 km em
   285,5 mm → 1:48.740 → **1:50.000**.
5. **Escala** arredondada **para cima** pelo degrau (nunca mais zoom que o necessário):

   | Escala calculada | múltiplo |
   |---|---|
   | até 1:10.000 | 500 |
   | 1:10.000 a 1:200.000 | 5.000 |
   | 1:200.000 a 1:1.000.000 | 50.000 |
   | acima de 1:1.000.000 | 100.000 |

6. **Série com escala única** — todos os mapas do mesmo imóvel usam a **maior** escala da série
   (menos zoom), como a PH faz; `imovel_mais_alvo` fica fora da regra.
7. **Centro** na faixa útil (não no centro do quadro) — daí o `deslocamento_mm`.
8. **Minimapa** é do W11 (`motores/minimapa.py`); aqui só se conhece a folga disponível.
9. **Alternativas** — a mesma conta para folha × orientação, em tabela.
10. O resultado é o que o `MapSpec` grava em `enquadramento` (reexecução dá o mesmo mapa).

Escala pedida pelo usuário entra como `escala_fixa`: se a caixa não couber, **não corta** —
levanta `NU-310` dizendo quanto cortaria e qual é a menor escala que cabe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Iterable, Sequence

from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.motores import perfil_pagina
from mapasfacil_nucleo.motores.folhas import ORDEM, folha_mm
from mapasfacil_nucleo.motores.perfil_pagina import Caixa, PerfilPagina

# Margem total sobre a caixa de conteúdo (7,5 % por lado). Calibrada na Análise PH.
MARGEM = 0.15

# Degraus de arredondamento: (até este denominador, múltiplo).
DEGRAUS: tuple[tuple[float, int], ...] = (
    (10_000.0, 500),
    (200_000.0, 5_000),
    (1_000_000.0, 50_000),
    (math.inf, 100_000),
)

ORIENTACOES = ("retrato", "paisagem")

# Tipos de caixa de conteúdo (passo 2).
TIPOS_CAIXA = ("imovel", "imovel_mais_alvo", "area_tematica")

# Área mínima (mm²) para uma caixa contar como zona proibida sobre o quadro.
_AREA_MIN_PROIBIDA = 1.0

CRS_UTM = {20: "31980", 21: "31981", 22: "31982"}
"""SIRGAS 2000 / UTM. `EPSG:31980` entrou no W11 (MT a oeste de 60° W)."""


# --------------------------------------------------------------------- escala
def degrau(escala_calculada: float) -> int:
    """Múltiplo a usar para arredondar esta escala calculada."""
    for limite, passo in DEGRAUS:
        if escala_calculada <= limite:
            return passo
    return DEGRAUS[-1][1]


def escala_redonda(escala_calculada: float) -> int:
    """Arredonda **para cima** no degrau — `1:48.740 → 1:50.000`, `1:8.335.900 → 1:8.400.000`."""
    if escala_calculada <= 0:
        return degrau(0)
    passo = degrau(escala_calculada)
    return int(math.ceil(escala_calculada / passo) * passo)


def eh_degrau(valor: int) -> bool:
    """A escala é múltiplo exato do degrau dela?

    É o teste que separa o que o arredondamento do W-10 produz (1:50.000, 1:65.000, 1:850.000)
    do que ele nunca produziria (1:48.737). Serve para o validador do `MapSpec` aceitar a escala
    calculada sem afrouxar a lista de escalas que o **usuário** pode pedir.
    """
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        return False
    return valor % degrau(valor) == 0


def texto_escala(escala: int) -> str:
    return f"1:{int(escala):,}".replace(",", ".")


# ------------------------------------------------------------------------- CRS
def zona_utm(lon: float) -> int:
    """Zona UTM (20, 21 ou 22) da longitude, pela divisão que o escritório usa em MT."""
    if lon < -60.0:
        return 20
    if lon < -54.0:
        return 21
    return 22


def crs_utm(lon: float) -> str:
    """EPSG do SIRGAS 2000 / UTM da zona da longitude."""
    return CRS_UTM[zona_utm(float(lon))]


# ------------------------------------------------------------------ perfil
def perfil_para(formato: str, orientacao: str = "paisagem") -> PerfilPagina:
    """Perfil da folha pedida, escalado a partir do modelo A4 do escritório.

    Os retângulos do perfil foram medidos em mm no A4; nas outras folhas o layout cresce na
    mesma proporção (o que importa aqui é o quadro e onde os blocos caem sobre ele).
    """
    formato = str(formato or "A4").upper()
    orientacao = str(orientacao or "paisagem").lower()
    if orientacao not in ORIENTACOES:
        orientacao = "paisagem"
    base = perfil_pagina.obter(orientacao)
    largura, altura = folha_mm(formato, orientacao)
    if abs(largura - base.largura_mm) < 0.5 and abs(altura - base.altura_mm) < 0.5:
        return base
    k = largura / base.largura_mm

    def escalar(caixa: Caixa) -> Caixa:
        return Caixa(caixa.x0 * k, caixa.y0 * k, caixa.x1 * k, caixa.y1 * k)

    return replace(
        base,
        id=f"{base.id}-{formato.lower()}",
        largura_mm=largura,
        altura_mm=altura,
        mapa=escalar(base.mapa),
        titulo=escalar(base.titulo),
        rosa=escalar(base.rosa),
        minimapa=escalar(base.minimapa),
        metadados=escalar(base.metadados),
        legenda=escalar(base.legenda),
        logo=escalar(base.logo),
        tabela=escalar(base.tabela),
    )


# ------------------------------------------------------------------ faixa útil
def _area(caixa: Caixa) -> float:
    return max(0.0, caixa.largura) * max(0.0, caixa.altura)


def _intersecao(a: Caixa, b: Caixa) -> Caixa | None:
    x0, y0 = max(a.x0, b.x0), max(a.y0, b.y0)
    x1, y1 = min(a.x1, b.x1), min(a.y1, b.y1)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return None
    return Caixa(x0, y0, x1, y1)


def zonas_do_perfil(perfil: PerfilPagina, extra: Sequence[Caixa] = ()) -> list[Caixa]:
    """Blocos opacos que caem **sobre** o quadro do mapa (mais de 1 mm² de interseção).

    A `tabela` fica de fora por padrão: no perfil do escritório ela é uma caixa que só existe
    quando o `MapSpec` pede tabela — contá-la sempre engoliria 2 cm de altura do quadro em todo
    mapa. Quem usa tabela passa a caixa em `zonas_proibidas`.
    """
    candidatas = [
        perfil.titulo,
        perfil.rosa,
        perfil.minimapa,
        perfil.metadados,
        perfil.legenda,
        perfil.logo,
        *extra,
    ]
    proibidas: list[Caixa] = []
    for caixa in candidatas:
        pedaco = _intersecao(caixa, perfil.mapa)
        if pedaco is not None and _area(pedaco) > _AREA_MIN_PROIBIDA:
            proibidas.append(pedaco)
    return proibidas


def _maior_livre(base: Caixa, obstaculos: Sequence[Caixa], profundidade: int = 0) -> Caixa:
    """Maior retângulo dentro de `base` que não toca nenhum obstáculo.

    Recorta em volta do primeiro obstáculo que atrapalha e recomeça nos quatro pedaços; com
    poucos blocos (o caso do layout do escritório) converge rápido e dá o resultado exato para
    retângulos alinhados aos eixos.
    """
    for obstaculo in obstaculos:
        if _intersecao(base, obstaculo) is None:
            continue
        if profundidade > 8:  # pragma: no cover - salvaguarda, não acontece no layout real
            return base
        pedacos = [
            Caixa(base.x0, base.y0, obstaculo.x0, base.y1),  # à esquerda
            Caixa(obstaculo.x1, base.y0, base.x1, base.y1),  # à direita
            Caixa(base.x0, base.y0, base.x1, obstaculo.y0),  # acima
            Caixa(base.x0, obstaculo.y1, base.x1, base.y1),  # abaixo
        ]
        melhor = Caixa(base.x0, base.y0, base.x0, base.y0)
        for pedaco in pedacos:
            if _area(pedaco) <= _area(melhor):
                continue
            livre = _maior_livre(pedaco, obstaculos, profundidade + 1)
            if _area(livre) > _area(melhor):
                melhor = livre
        return melhor
    return base


def faixa_util(perfil: PerfilPagina, zonas_proibidas: Sequence[Caixa] = ()) -> Caixa:
    """Maior retângulo do quadro sem tocar zona proibida — onde o mapa pode aparecer."""
    proibidas = zonas_do_perfil(perfil, zonas_proibidas)
    livre = _maior_livre(perfil.mapa, proibidas)
    if _area(livre) < 100.0:  # menos de 1 cm²: layout inviável, devolve o quadro inteiro
        return perfil.mapa
    return livre


def quadro_util_mm(formato: str, orientacao: str = "paisagem") -> tuple[float, float]:
    """Largura e altura da faixa útil, em mm."""
    faixa = faixa_util(perfil_para(formato, orientacao))
    return faixa.largura, faixa.altura


# ------------------------------------------------------------- caixa de conteúdo
def bbox_do_dict(bbox: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(bbox["xmin"]),
        float(bbox["ymin"]),
        float(bbox["xmax"]),
        float(bbox["ymax"]),
    )


def _unir(caixas: Iterable[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    lista = list(caixas)
    if not lista:
        raise ErroNucleo("NU-311", "Nada para enquadrar: a caixa de conteúdo está vazia.")
    return (
        min(c[0] for c in lista),
        min(c[1] for c in lista),
        max(c[2] for c in lista),
        max(c[3] for c in lista),
    )


def caixa_de_conteudo(
    geometrias: Sequence[dict[str, Any]] | dict[str, Any],
    tipo: str = "imovel",
) -> tuple[float, float, float, float]:
    """Caixa (passo 2) do que manda no zoom.

    `geometrias` aceita um `bbox` solto (compatível com o código antigo) ou uma lista de
    `{"bbox": {...}, "papel": "imovel" | "alvo" | "tema"}`.
    """
    if tipo not in TIPOS_CAIXA:
        raise ErroNucleo(
            "NU-311",
            f"Tipo de caixa desconhecido: {tipo!r}.",
            {"tipos": list(TIPOS_CAIXA)},
        )
    if isinstance(geometrias, dict):
        return bbox_do_dict(geometrias)
    lista = list(geometrias)
    if not lista:
        raise ErroNucleo("NU-311", "Nada para enquadrar: nenhuma geometria visível.")

    if tipo == "imovel":
        papeis = {"imovel"}
    elif tipo == "imovel_mais_alvo":
        papeis = {"imovel", "alvo"}
    else:  # area_tematica
        papeis = {"tema"}

    escolhidas = [
        bbox_do_dict(item["bbox"]) for item in lista if item.get("papel", "imovel") in papeis
    ]
    if not escolhidas:
        # Sem a feição do tema, cai no imóvel: não devolve caixa vazia por falta de cadastro.
        escolhidas = [
            bbox_do_dict(item["bbox"]) for item in lista if item.get("papel", "imovel") == "imovel"
        ]
    return _unir(escolhidas)


# ----------------------------------------------------------------- resultado
@dataclass(frozen=True)
class Enquadramento:
    """Resultado do enquadramento — é isto que vai para o `MapSpec`."""

    crs: str
    escala: int
    extent: tuple[float, float, float, float]
    quadro_mm: tuple[float, float]
    aproveitamento: float
    deslocamento_mm: tuple[float, float]
    caixa: str = "imovel"
    folha: str = "A4"
    orientacao: str = "paisagem"
    alternativas: tuple[dict[str, Any], ...] = ()

    def para_dict(self) -> dict[str, Any]:
        return {
            "crs": self.crs,
            "escala": self.escala,
            "escala_texto": texto_escala(self.escala),
            "extent": list(self.extent),
            "quadro_mm": list(self.quadro_mm),
            "aproveitamento": self.aproveitamento,
            "deslocamento_mm": list(self.deslocamento_mm),
            "caixa": self.caixa,
            "folha": self.folha,
            "orientacao": self.orientacao,
            "alternativas": [dict(a) for a in self.alternativas],
        }


def _escala_para(largura_m: float, altura_m: float, faixa: Caixa, margem: float) -> float:
    """Denominador contínuo da escala em que a caixa (com margem) cabe na faixa."""
    if faixa.largura <= 0 or faixa.altura <= 0:
        raise ErroNucleo("NU-312", "Faixa útil do quadro sem dimensão — perfil de página inválido.")
    com_margem_l = largura_m * (1 + margem)
    com_margem_a = altura_m * (1 + margem)
    return max(com_margem_l / (faixa.largura / 1000.0), com_margem_a / (faixa.altura / 1000.0))


def enquadrar(
    geometrias: Sequence[dict[str, Any]] | dict[str, Any],
    perfil: PerfilPagina,
    *,
    tipo: str = "imovel",
    margem: float = MARGEM,
    zonas_proibidas: Sequence[Caixa] = (),
    escala_fixa: int | None = None,
    crs: str | None = None,
    alternativas: bool = True,
) -> Enquadramento:
    """Resolve escala, extent e CRS para a caixa de conteúdo na folha do `perfil`."""
    xmin, ymin, xmax, ymax = caixa_de_conteudo(geometrias, tipo)
    largura_m = abs(xmax - xmin)
    altura_m = abs(ymax - ymin)
    if largura_m <= 0 or altura_m <= 0:
        raise ErroNucleo("NU-311", "A caixa de conteúdo tem área zero — geometria degenerada.")

    faixa = faixa_util(perfil, zonas_proibidas)
    continua = _escala_para(largura_m, altura_m, faixa, margem)
    cabe_em = escala_redonda(continua)

    if escala_fixa is not None:
        escala = int(escala_fixa)
        if escala < cabe_em:
            # Não corta: diz quanto cortaria e qual a menor escala que cabe (regra do W-10).
            corte_l = 1 - (faixa.largura / 1000.0 * escala) / (largura_m * (1 + margem))
            corte_a = 1 - (faixa.altura / 1000.0 * escala) / (altura_m * (1 + margem))
            corte = max(corte_l, corte_a)
            raise ErroNucleo(
                "NU-310",
                (
                    f"Em {perfil.id} a {texto_escala(escala)} corta {corte * 100:.0f}% do imóvel; "
                    f"a menor escala que cabe é {texto_escala(cabe_em)}."
                ),
                {
                    "escala_pedida": escala,
                    "escala_minima": cabe_em,
                    "corte_pct": round(corte * 100, 1),
                    "folha": perfil.id,
                },
            )
    else:
        escala = cabe_em

    largura_extent = faixa.largura / 1000.0 * escala
    altura_extent = faixa.altura / 1000.0 * escala
    centro_conteudo = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)
    extent = (
        centro_conteudo[0] - largura_extent / 2.0,
        centro_conteudo[1] - altura_extent / 2.0,
        centro_conteudo[0] + largura_extent / 2.0,
        centro_conteudo[1] + altura_extent / 2.0,
    )

    centro_faixa = faixa.centro
    centro_quadro = perfil.mapa.centro
    deslocamento = (
        round(centro_faixa[0] - centro_quadro[0], 2),
        round(centro_faixa[1] - centro_quadro[1], 2),
    )

    area_caixa_m2 = (largura_m * (1 + margem)) * (altura_m * (1 + margem))
    area_util_m2 = (faixa.largura / 1000.0 * escala) * (faixa.altura / 1000.0 * escala)
    aproveitamento = round(min(1.0, area_caixa_m2 / area_util_m2), 3) if area_util_m2 > 0 else 0.0

    crs_final = crs or crs_utm(centro_conteudo[0])

    tabela: tuple[dict[str, Any], ...] = ()
    if alternativas:
        tabela = tuple(
            _linha_alternativa(geometrias, tipo, formato, orientacao, margem, zonas_proibidas)
            for formato in ORDEM
            for orientacao in ORIENTACOES
        )

    return Enquadramento(
        crs=crs_final,
        escala=escala,
        extent=extent,
        quadro_mm=(round(faixa.largura, 1), round(faixa.altura, 1)),
        aproveitamento=aproveitamento,
        deslocamento_mm=deslocamento,
        caixa=tipo,
        folha=perfil.id,
        orientacao=perfil.orientacao,
        alternativas=tabela,
    )


def _linha_alternativa(
    geometrias: Sequence[dict[str, Any]] | dict[str, Any],
    tipo: str,
    formato: str,
    orientacao: str,
    margem: float,
    zonas_proibidas: Sequence[Caixa],
) -> dict[str, Any]:
    perfil = perfil_para(formato, orientacao)
    faixa = faixa_util(perfil, zonas_proibidas)
    xmin, ymin, xmax, ymax = caixa_de_conteudo(geometrias, tipo)
    largura_m = abs(xmax - xmin)
    altura_m = abs(ymax - ymin)
    escala = escala_redonda(_escala_para(largura_m, altura_m, faixa, margem))
    area_caixa_m2 = (largura_m * (1 + margem)) * (altura_m * (1 + margem))
    area_util_m2 = (faixa.largura / 1000.0 * escala) * (faixa.altura / 1000.0 * escala)
    return {
        "folha": formato,
        "orientacao": orientacao,
        "escala": escala,
        "escala_texto": texto_escala(escala),
        "aproveitamento": (
            round(min(1.0, area_caixa_m2 / area_util_m2), 3) if area_util_m2 > 0 else 0.0
        ),
        "quadro_mm": [round(faixa.largura, 1), round(faixa.altura, 1)],
    }


def escala_da_serie(enquadramentos: Iterable[Enquadramento]) -> int:
    """Escala única da série: a **maior** (menos zoom) entre os mapas com a mesma caixa.

    A PH faz exatamente isso: todos os mapas do bloco de 12 matrículas saem a 1:50.000.
    Enquadramentos `imovel_mais_alvo` ficam fora da regra (mapa de contexto tem caixa própria).
    """
    lista = list(enquadramentos)
    escalas = [e.escala for e in lista if e.caixa != "imovel_mais_alvo"]
    if not escalas:
        escalas = [e.escala for e in lista]
    if not escalas:
        raise ErroNucleo("NU-311", "Série sem enquadramento para unificar a escala.")
    return max(escalas)


def com_escala(anterior: Enquadramento, escala: int) -> Enquadramento:
    """Reaplica a escala única da série mantendo o centro do extent."""
    xmin, ymin, xmax, ymax = anterior.extent
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    largura = anterior.quadro_mm[0] / 1000.0 * escala
    altura = anterior.quadro_mm[1] / 1000.0 * escala
    return replace(
        anterior,
        escala=int(escala),
        extent=(cx - largura / 2.0, cy - altura / 2.0, cx + largura / 2.0, cy + altura / 2.0),
    )


# ------------------------------------------------- tabela folha × orientação
def escala_minima(bbox: dict[str, Any], formato: str, orientacao: str = "paisagem") -> float:
    """Denominador contínuo em que a caixa cabe na faixa útil (antes do arredondamento)."""
    xmin, ymin, xmax, ymax = bbox_do_dict(bbox)
    faixa = faixa_util(perfil_para(formato, orientacao))
    return _escala_para(abs(xmax - xmin), abs(ymax - ymin), faixa, MARGEM)


def escala_do_enquadramento(
    bbox: dict[str, Any],
    formato: str,
    orientacao: str = "paisagem",
    *,
    folga: float = 1.0,
    margem: float = MARGEM,
) -> int:
    """Escala redonda para esta caixa (com folga) nesta folha — a conta que a série usa.

    `folga` é o quanto se acrescenta à caixa antes de enquadrar (o `folga_extent` da receita).
    A escala sai pelos degraus do W-10, então é reproduzível e comparável entre mapas.
    """
    xmin, ymin, xmax, ymax = bbox_do_dict(bbox)
    faixa = faixa_util(perfil_para(formato, orientacao))
    largura = abs(xmax - xmin) * max(1.0, folga)
    altura = abs(ymax - ymin) * max(1.0, folga)
    return escala_redonda(_escala_para(largura, altura, faixa, margem))


def aproveitamento(bbox: dict[str, Any], formato: str, orientacao: str, escala: int) -> float:
    """Quanto da faixa útil a caixa (com margem) ocupa, em % (0–100)."""
    xmin, ymin, xmax, ymax = bbox_do_dict(bbox)
    faixa = faixa_util(perfil_para(formato, orientacao))
    largura_m = abs(xmax - xmin) * (1 + MARGEM)
    altura_m = abs(ymax - ymin) * (1 + MARGEM)
    area_util = (faixa.largura / 1000.0 * escala) * (faixa.altura / 1000.0 * escala)
    if area_util <= 0:
        return 0.0
    return round(100.0 * (largura_m * altura_m) / area_util, 1)


def para_dict(bbox: dict[str, Any], formato: str, orientacao: str = "paisagem") -> dict[str, Any]:
    """Uma linha da tabela de sugestão: folha, orientação, escala redonda e aproveitamento."""
    escala = escala_redonda(escala_minima(bbox, formato, orientacao))
    faixa = faixa_util(perfil_para(formato, orientacao))
    return {
        "folha": formato,
        "orientacao": orientacao,
        "escala": escala,
        "escala_texto": texto_escala(escala),
        "aproveitamento_pct": aproveitamento(bbox, formato, orientacao, escala),
        "faixa_util_mm": [round(faixa.largura, 1), round(faixa.altura, 1)],
    }


def sugerir(
    bbox: dict[str, Any],
    *,
    formatos: Iterable[str] = ORDEM,
) -> list[dict[str, Any]]:
    """Tabela folha × orientação, da folha com **mais** aproveitamento para a com menos.

    Aproveitamento alto = mapa mais detalhado na mesma informação. Empate desfeito pela folha
    menor (gasta menos papel e cabe na impressora do escritório).
    """
    linhas = [
        para_dict(bbox, formato, orientacao) for formato in formatos for orientacao in ORIENTACOES
    ]
    linhas.sort(key=lambda l: (-l["aproveitamento_pct"], ORDEM.index(l["folha"]), l["orientacao"]))
    return linhas


def melhor(bbox: dict[str, Any], *, formatos: Iterable[str] = ORDEM) -> dict[str, Any] | None:
    linhas = sugerir(bbox, formatos=formatos)
    return linhas[0] if linhas else None
