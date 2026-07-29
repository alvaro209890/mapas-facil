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

from dataclasses import dataclass


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
