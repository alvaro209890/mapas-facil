"""Perfis de página do padrão Harmonia, em milímetros.

Os retângulos vêm **medidos** dos PDFs-modelo de `Referencias_IMAP/Mapas/01`
(rasterização a 100 dpi + bbox de texto) e estão tabelados em
[`planos/01-padrao-imap-harmonia.md`](../../../../planos/01-padrao-imap-harmonia.md)
§Retângulos medidos. Este módulo é a tradução literal daquela tabela: nenhum
número aqui foi estimado, e mudar um deles é mudar o padrão cartográfico.

Convenção: `y` cresce **para baixo**, a partir do topo da página — igual à
tabela do plano e ao layout do ArcMap. A conversão para coordenada de figura do
matplotlib (origem embaixo) é feita por `Caixa.fracao`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Caixa:
    """Retângulo em mm, com origem no topo-esquerda da página."""

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

    @property
    def centro(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def fracao(self, largura_pagina: float, altura_pagina: float) -> tuple[float, float, float, float]:
        """`[left, bottom, width, height]` em fração de figura (origem embaixo)."""
        return (
            self.x0 / largura_pagina,
            (altura_pagina - self.y1) / altura_pagina,
            self.largura / largura_pagina,
            self.altura / altura_pagina,
        )


@dataclass(frozen=True)
class PerfilPagina:
    """Um dos dois formatos do perfil Harmonia."""

    id: str
    orientacao: str
    largura_mm: float
    altura_mm: float
    mapa: Caixa
    titulo: Caixa
    rosa: Caixa
    minimapa: Caixa
    metadados: Caixa
    legenda: Caixa
    logo: Caixa
    tabela: Caixa
    crs_padrao: str
    titulo_legenda: str
    pt_titulo: float
    pt_metadados: float
    pt_legenda: float
    pt_grade: float
    # Título do bloco de legenda: nos modelos ele é bem maior que os itens
    # (9,1 pt contra 6,2 no retrato). 0 = derivar do tamanho dos itens.
    pt_legenda_titulo: float = 0.0
    # Título do bloco de metadados: quase todo modelo escreve "METADADOS
    # IMAGEM", mas o de Terras Indígenas escreve só "METADADOS" — e a diferença
    # de largura desloca a âncora do bloco inteiro.
    titulo_metadados: str = "METADADOS IMAGEM"

    @property
    def figsize_pol(self) -> tuple[float, float]:
        return (self.largura_mm / 25.4, self.altura_mm / 25.4)

    def fracao(self, caixa: Caixa) -> tuple[float, float, float, float]:
        return caixa.fracao(self.largura_mm, self.altura_mm)


# Série Dinâmica — A4 retrato 210 × 297 mm.
RETRATO = PerfilPagina(
    id="retrato",
    orientacao="retrato",
    largura_mm=210.0,
    altura_mm=297.0,
    mapa=Caixa(7.0, 5.0, 203.5, 257.0),
    titulo=Caixa(63.7, 3.6, 132.7, 21.8),
    rosa=Caixa(186.3, 4.0, 202.0, 27.0),
    minimapa=Caixa(0.0, 262.0, 62.0, 297.0),
    metadados=Caixa(64.9, 265.2, 120.0, 291.2),
    legenda=Caixa(131.8, 266.0, 172.0, 295.0),
    logo=Caixa(175.0, 265.0, 208.0, 292.0),
    # 67,1 → 203,0 mm em x; 40,7 → 60,7 mm medidos **da base** da página.
    tabela=Caixa(67.1, 297.0 - 60.7, 203.0, 297.0 - 40.7),
    crs_padrao="EPSG:31982",
    titulo_legenda="Legenda",
    pt_titulo=24.0,
    pt_metadados=9.0,
    pt_legenda=8.0,
    pt_grade=6.0,
)

# Temáticos — A4 paisagem 297 × 210 mm.
PAISAGEM = PerfilPagina(
    id="paisagem",
    orientacao="paisagem",
    largura_mm=297.0,
    altura_mm=210.0,
    mapa=Caixa(5.6, 4.8, 291.1, 168.5),
    titulo=Caixa(107.2, 3.0, 185.0, 20.5),
    rosa=Caixa(276.7, 4.3, 288.5, 21.7),
    minimapa=Caixa(2.0, 172.0, 62.0, 208.0),
    metadados=Caixa(76.4, 173.8, 156.2, 205.3),
    legenda=Caixa(177.1, 172.0, 227.0, 208.2),
    logo=Caixa(245.0, 175.0, 292.0, 205.0),
    # Os temáticos do acervo não trazem tabela; a caixa existe para quando o
    # MapSpec pedir `tabela: true` num paisagem.
    tabela=Caixa(80.0, 140.0, 285.0, 160.0),
    crs_padrao="EPSG:3857",
    titulo_legenda="LEGENDA",
    pt_titulo=26.0,
    pt_metadados=11.0,
    pt_legenda=10.0,
    pt_grade=6.0,
)

PERFIS: dict[str, PerfilPagina] = {"retrato": RETRATO, "paisagem": PAISAGEM}

PREFIXO_SERIE = "serie_"
"""Template da série `Análise de área`: o layout vem do modelo medido, não do MXD."""


@lru_cache(maxsize=1)
def _anatomia_serie() -> dict[str, dict]:
    """Anatomia medida dos PDFs-modelo (`shared/padrao-imap/anatomia_serie.json`).

    Ausente = sem série instalada; o chamador cai no perfil por orientação.
    """
    from mapasfacil_nucleo.config import raiz_repositorio

    caminho = raiz_repositorio() / "shared" / "padrao-imap" / "anatomia_serie.json"
    if not caminho.is_file():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    mapas = dados.get("mapas")
    return mapas if isinstance(mapas, dict) else {}


def _caixa_de_lista(valor: object, padrao: Caixa) -> Caixa:
    if isinstance(valor, (list, tuple)) and len(valor) == 4 and all(v is not None for v in valor):
        return Caixa(float(valor[0]), float(valor[1]), float(valor[2]), float(valor[3]))
    return padrao


def por_anatomia(mapa_id: str | None) -> PerfilPagina | None:
    """Perfil de um mapa da série, com os retângulos **medidos do modelo dele**.

    Não existe "o" layout paisagem: entre os modelos do acervo a base do quadro
    varia de 151 mm (Terras Indígenas, que abre espaço para uma legenda alta) a
    169 mm (Tipologia). Média erra os dois; o modelo de cada mapa acerta o seu.
    """
    if not mapa_id:
        return None
    registro = _anatomia_serie().get(str(mapa_id))
    if not isinstance(registro, dict):
        return None

    base = PERFIS.get(str(registro.get("orientacao") or "retrato"), RETRATO)
    pagina = registro.get("pagina_mm") or [base.largura_mm, base.altura_mm]
    meta = registro.get("metadados") or {}
    legenda = registro.get("legenda") or {}

    return PerfilPagina(
        id=f"{base.id}:{mapa_id}",
        orientacao=base.orientacao,
        largura_mm=float(pagina[0]),
        altura_mm=float(pagina[1]),
        mapa=_caixa_de_lista(registro.get("mapa"), base.mapa),
        titulo=_caixa_de_lista(registro.get("titulo"), base.titulo),
        rosa=base.rosa,
        minimapa=base.minimapa,
        metadados=_caixa_de_lista(meta.get("caixa"), base.metadados),
        legenda=_caixa_de_lista(legenda.get("caixa"), base.legenda),
        logo=base.logo,
        tabela=base.tabela,
        crs_padrao=base.crs_padrao,
        titulo_legenda=str(legenda.get("titulo") or base.titulo_legenda),
        pt_titulo=base.pt_titulo,
        pt_metadados=float(meta.get("pt") or base.pt_metadados),
        pt_legenda=float(legenda.get("pt") or base.pt_legenda),
        pt_grade=base.pt_grade,
        pt_legenda_titulo=float(legenda.get("pt_titulo") or 0.0),
        titulo_metadados=str(meta.get("titulo") or "METADADOS IMAGEM"),
    )


def por_template(template_id: str | None) -> PerfilPagina | None:
    """`serie_tipologia` → perfil medido do `Tipologia.pdf`."""
    if not template_id:
        return None
    texto = str(template_id)
    if not texto.startswith(PREFIXO_SERIE):
        return None
    return por_anatomia(texto[len(PREFIXO_SERIE) :])


def obter(orientacao: str | None) -> PerfilPagina:
    """`"retrato"`/`"paisagem"` → perfil. Default retrato (série Dinâmica)."""
    if not orientacao:
        return RETRATO
    return PERFIS.get(str(orientacao).strip().lower(), RETRATO)


def por_formato(formato_pagina: dict | None) -> PerfilPagina:
    """Escolhe o perfil pelo `formato_pagina` do MANIFEST do template."""
    if not isinstance(formato_pagina, dict):
        return RETRATO
    orientacao = formato_pagina.get("orientacao")
    if orientacao:
        return obter(str(orientacao))
    mm = formato_pagina.get("mm")
    if isinstance(mm, (list, tuple)) and len(mm) == 2 and float(mm[0]) > float(mm[1]):
        return PAISAGEM
    return RETRATO
