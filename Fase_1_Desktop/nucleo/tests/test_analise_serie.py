"""Série "Análise de área" — receitas, perfis medidos e basemap por ano.

Nada aqui vai à rede: o que se testa é a montagem do MapSpec, a resolução do
mosaico e a coerência entre receitas, estilos e anatomia medida.
"""

from __future__ import annotations

import json

import pytest

from mapasfacil_nucleo.analise import serie as serie_mod
from mapasfacil_nucleo.analise.identidade import IdentidadeImovel
from mapasfacil_nucleo.config import raiz_repositorio
from mapasfacil_nucleo.mapspec.validar import validar
from mapasfacil_nucleo.motores import basemap, perfil_pagina
from mapasfacil_nucleo.motores.estilos import ESTILOS
from mapasfacil_nucleo.motores.manifesto import obter_template
from mapasfacil_nucleo.validacao import anatomia


@pytest.fixture
def identidade() -> IdentidadeImovel:
    return IdentidadeImovel(
        nome="Fazenda Aruanã I",
        area_atp_ha=7408.8844,
        municipio={"nome": "Ribeirão Cascalheira", "cod_ibge": "5107180", "sigla_uf": "MT"},
        car_estadual="MT117446/2017",
        confianca=0.9995,
    )


@pytest.fixture
def disponiveis() -> dict[str, int]:
    """Todos os papéis com feição — o caso do imóvel completo."""
    papeis = {c.papel for r in serie_mod.RECEITAS for c in r.camadas}
    return {papel: 5 for papel in papeis}


def test_serie_tem_os_20_mapas_do_acervo() -> None:
    assert len(serie_mod.RECEITAS) == 20
    ordens = [r.ordem for r in serie_mod.ordenadas()]
    assert ordens == list(range(1, 21)), "a ordem da série é a das páginas do PDF compilado"


def test_todo_estilo_citado_existe_na_paleta() -> None:
    """Receita com estilo inventado viraria polígono cinza sem ninguém notar."""
    usados = {c.estilo for r in serie_mod.RECEITAS for c in r.camadas}
    assert usados <= set(ESTILOS), f"estilos fora da paleta: {sorted(usados - set(ESTILOS))}"


def test_todo_mapa_tem_template_registrado_no_manifest() -> None:
    for receita in serie_mod.RECEITAS:
        tpl = obter_template(receita.template)
        assert tpl["formato_pagina"]["papel"] == "A4"


def test_todo_mapa_tem_anatomia_medida_do_modelo() -> None:
    caminho = raiz_repositorio() / "shared" / "padrao-imap" / "anatomia_serie.json"
    mapas = json.loads(caminho.read_text(encoding="utf-8"))["mapas"]
    for receita in serie_mod.RECEITAS:
        assert receita.id in mapas, f"{receita.id} sem anatomia medida"
        assert mapas[receita.id]["modelo_pdf"] == receita.modelo_pdf


def test_perfil_do_template_vem_do_modelo_medido() -> None:
    perfil = perfil_pagina.por_template("serie_terras_indigenas")
    assert perfil is not None
    assert perfil.orientacao == "paisagem"
    # A base do quadro das Terras Indígenas é 17 mm mais alta que a da
    # Tipologia: é justamente o que um perfil médio erraria.
    tipologia = perfil_pagina.por_template("serie_tipologia")
    assert tipologia is not None
    assert tipologia.mapa.y1 - perfil.mapa.y1 > 10.0


def test_perfil_de_template_comum_nao_vira_serie() -> None:
    assert perfil_pagina.por_template("dinamica_retrato") is None


def test_mapspec_da_receita_e_valido(identidade, disponiveis) -> None:
    for receita in serie_mod.RECEITAS:
        spec = serie_mod.montar_mapspec(receita, identidade, fontes_disponiveis=disponiveis)
        resultado = validar(spec, fontes_locais=frozenset(disponiveis))
        assert resultado["valido"], (receita.id, resultado["erros"])


def test_camada_sem_feicao_sai_do_mapa_e_da_legenda(identidade) -> None:
    receita = serie_mod.POR_ID["tipologia"]
    spec = serie_mod.montar_mapspec(
        receita,
        identidade,
        fontes_disponiveis={"ATP": 1, "TIPOLOGIA_FLORESTA": 3, "TIPOLOGIA_CERRADO": 0},
    )
    legendas = [c["legenda"] for c in spec["camadas"]]
    assert "Tipologia: Floresta" in legendas
    assert "Tipologia: Cerrado" not in legendas, "legenda não anuncia camada que não existe"


def test_perimetro_usa_o_id_que_o_motor_enquadra(identidade, disponiveis) -> None:
    spec = serie_mod.montar_mapspec(
        serie_mod.POR_ID["dinamica_2026"], identidade, fontes_disponiveis=disponiveis
    )
    perimetro = next(c for c in spec["camadas"] if c["fonte"] == "local.ATP")
    assert perimetro["id"] == "perimetro"
    assert perimetro["rotulo_texto"] == "Fazenda Aruanã I"


def test_nome_do_imovel_entra_na_legenda(identidade, disponiveis) -> None:
    spec = serie_mod.montar_mapspec(
        serie_mod.POR_ID["dinamica_2000"], identidade, fontes_disponiveis=disponiveis
    )
    assert any(c["legenda"] == "Fazenda Aruanã I" for c in spec["camadas"])


def test_mosaico_por_id_e_por_ano() -> None:
    assert basemap.camada_de_mosaico("landsat5_2000")["layer"] == "Mosaicos:LANDSAT_5_2000"
    # 2013: o Landsat 5 já não operava; a SEMA publica Landsat 8 (§4.1 do GOAL).
    assert basemap.camada_de_mosaico("2013")["layer"] == "Mosaicos:LANDSAT_8_2013"


def test_mosaico_de_ano_inexistente_cai_no_anterior_e_declara() -> None:
    escolhido = basemap.camada_de_mosaico("2026")
    assert escolhido is not None
    assert escolhido["ano"] < 2026
    assert escolhido["ano_exato"] is False, "ano aproximado tem de ser declarado"


def test_mosaico_desconhecido_nao_inventa() -> None:
    assert basemap.camada_de_mosaico("nao_existe_esse_mosaico") is None


def test_anatomia_compara_metadados_pelo_centro() -> None:
    """Bloco centralizado mais largo dos dois lados não é desvio de posição."""
    modelo = {
        "metadados": {"x0": 60.0, "y0": 170.0, "x1": 140.0, "y1": 200.0},
        "quadro_mapa": {"x0": 5.0, "y0": 5.0, "x1": 200.0, "y1": 160.0},
        "legenda": {"x0": 150.0, "y0": 170.0, "x1": 190.0, "y1": 200.0},
        "titulo": {"caixa_mm": {"x0": 70.0, "y0": 3.0, "x1": 130.0, "y1": 20.0}},
        "rotulos_dms": {"por_borda": {"superior": 4, "inferior": 4, "esquerda": 4, "direita": 4}},
        "orientacao": "retrato",
    }
    gerado = json.loads(json.dumps(modelo))
    gerado["metadados"] = {"x0": 50.0, "y0": 170.0, "x1": 150.0, "y1": 200.0}  # +20 mm de largura
    resultado = anatomia.comparar(modelo, gerado)
    a03 = next(i for i in resultado["itens"] if i["id"] == "A03")
    assert a03["ok"], "bloco 20 mm mais largo, mesmo centro, não pode reprovar"

    gerado["metadados"] = {"x0": 70.0, "y0": 170.0, "x1": 150.0, "y1": 200.0}  # deslocado 10 mm
    a03 = next(i for i in anatomia.comparar(modelo, gerado)["itens"] if i["id"] == "A03")
    assert not a03["ok"], "bloco deslocado 10 mm tem de reprovar"
