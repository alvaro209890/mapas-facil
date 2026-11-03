"""W7-01 — contrato dos três eventos de palco (`motion.py`).

Cada teste aqui corresponde a uma linha do critério de aceite de W-03: nível voltando dentro do job
levanta, bbox invertido levanta, caminho absoluto levanta, elemento fora da lista levanta.
"""

from __future__ import annotations

import pytest

from mapasfacil_nucleo import motion
from mapasfacil_nucleo.motores import perfil_pagina
from mapasfacil_nucleo.progresso import RastreadorProgresso


# ------------------------------------------------------------- viewport.foco
def test_viewport_estado_valido() -> None:
    dados = motion.montar_dados_viewport(
        "estado",
        [-61.63, -18.04, -50.22, -7.35],
        "Mato Grosso",
        "ibge",
        job_id="01JBZ",
        etapa="validando_spec",
    )
    assert dados["nivel"] == "estado"
    assert dados["bbox_4326"] == [-61.63, -18.04, -50.22, -7.35]
    assert dados["escala"] is None and dados["crs_mapa"] is None and dados["quadro_mm"] is None


def test_viewport_fora_de_job_so_aceita_tres_niveis() -> None:
    for nivel in ("estado", "municipio", "imovel"):
        dados = motion.montar_dados_viewport(
            nivel, [-52.5, -12.7, -52.4, -12.6], "Querência/MT", "ibge", etapa=None
        )
        assert dados["job_id"] is None and dados["etapa"] is None
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "folha", [-52.5, -12.7, -52.4, -12.6], "folha", "perfil_pagina", etapa=None
        )


def test_viewport_nivel_voltando_levanta() -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "imovel",
            [-52.5, -12.7, -52.4, -12.6],
            "Fazenda",
            "geometria_local",
            job_id="01JBZ",
            etapa="resolvendo_camadas_locais",
            nivel_anterior="enquadramento",
        )


def test_viewport_nivel_repetido_passa() -> None:
    dados = motion.montar_dados_viewport(
        "imovel",
        [-52.5, -12.7, -52.4, -12.6],
        "Fazenda",
        "geometria_local",
        job_id="01JBZ",
        etapa="resolvendo_camadas_locais",
        nivel_anterior="imovel",
    )
    assert dados["nivel"] == "imovel"


@pytest.mark.parametrize(
    "bbox",
    [
        [-52.4, -12.7, -52.5, -12.6],  # oeste > leste
        [-52.5, -12.6, -52.4, -12.7],  # sul > norte
        [-52.5, -12.7, -52.4],
        [0, 0, 0, 0],
        [-190, -12.7, -52.4, -12.6],
        [-52.5, -95, -52.4, -12.6],
        [-52.5, -12.7, float("nan"), -12.6],
    ],
)
def test_viewport_bbox_invalido_levanta(bbox: list[float]) -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "imovel", bbox, "Fazenda", "geometria_local", job_id="01JBZ", etapa="resolvendo_camadas_locais"
        )


def test_viewport_escala_so_no_enquadramento() -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "imovel",
            [-52.5, -12.7, -52.4, -12.6],
            "Fazenda",
            "geometria_local",
            job_id="01JBZ",
            etapa="resolvendo_camadas_locais",
            escala=50_000,
        )
    dados = motion.montar_dados_viewport(
        "enquadramento",
        [-52.5, -12.7, -52.4, -12.6],
        "1:50.000",
        "calculo_escala",
        job_id="01JBZ",
        etapa="aplicando_layout",
        escala=50_000,
        crs_mapa="epsg:31982",
        quadro_mm={"largura": 285.5, "altura": 146.8},
    )
    assert dados["escala"] == 50_000
    assert dados["crs_mapa"] == "EPSG:31982"
    assert dados["quadro_mm"] == {"largura": 285.5, "altura": 146.8}


def test_viewport_etapa_obrigatoria_dentro_do_job() -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "estado", [-61.6, -18.0, -50.2, -7.3], "MT", "ibge", job_id="01JBZ", etapa=None
        )
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_viewport(
            "estado", [-61.6, -18.0, -50.2, -7.3], "MT", "ibge", job_id="01JBZ", etapa="etapa_falsa"
        )


# --------------------------------------------------------- camada.renderizada
def _camada(**kwargs):
    base = {
        "camada_id": "avn",
        "papel": "avn",
        "nome": "Área de vegetação nativa",
        "geometria": "poligono",
        "sequencia": 2,
        "total": 6,
        "caminho": "Mapas/.preview/01JBZ/camadas/avn.geojson",
        "job_id": "01JBZ",
        "etapa": "resolvendo_camadas_locais",
        "bbox": [-52.41, -12.71, -52.33, -12.64],
        "estilo": {"cor_linha": "#4CE500", "hachura": "xx", "largura": 1.0},
        "n_feicoes": 12,
        "area_ha": 812.4410,
    }
    base.update(kwargs)
    return motion.montar_dados_camada(**base)


def test_camada_valida_traduz_estilo_do_motor() -> None:
    dados = _camada()
    assert dados["estilo"] == {
        "preenchimento": None,
        "contorno": "#4CE500",
        "espessura_pt": 1.0,
        "padrao": "hachura",
    }
    assert dados["area_ha"] == 812.441
    assert dados["ordem_desenho"] < motion.ordem_desenho("basemap")


def test_camada_caminho_absoluto_levanta() -> None:
    for caminho in (
        "C:/Users/Usuario/mapa.geojson",
        "/home/server/mapafacil/x.geojson",
        "Mapas/../etc/passwd",
        "Mapas/.preview/OUTRO_JOB/camadas/avn.geojson",
    ):
        with pytest.raises(motion.MotionInvalido):
            _camada(caminho=caminho)


def test_camada_raster_exige_bbox() -> None:
    with pytest.raises(motion.MotionInvalido):
        _camada(geometria="raster", bbox=None, papel="basemap", camada_id="basemap")
    dados = _camada(
        geometria="raster", papel="basemap", camada_id="basemap", area_ha=None, n_feicoes=0
    )
    assert dados["bbox_4326"] is not None


def test_camada_area_so_em_poligono() -> None:
    with pytest.raises(motion.MotionInvalido):
        _camada(geometria="linha", area_ha=12.0)


def test_camada_sequencia_maior_que_total_levanta() -> None:
    with pytest.raises(motion.MotionInvalido):
        _camada(sequencia=7, total=6)


def test_prioridade_de_papel_segue_a_ordem_de_pintura() -> None:
    ordem = motion.ordenar_por_papel(["basemap", "auas", "perimetro", "avn", "ac", "externa", "zzz"])
    assert ordem == ["perimetro", "avn", "ac", "auas", "externa", "zzz", "basemap"]
    assert motion.prioridade_do_papel("perimetro") < motion.prioridade_do_papel("basemap")


# ------------------------------------------------------------ layout.elemento
def _folha_a4_retrato():
    return {"formato": "A4", "orientacao": "retrato", "largura_mm": 210, "altura_mm": 297}


def test_layout_valido() -> None:
    dados = motion.montar_dados_layout(
        "minimapa",
        sequencia=1,
        total=11,
        folha=_folha_a4_retrato(),
        caixa_mm={"x0": 136.2, "y0": 18.9, "x1": 199.0, "y1": 80.4},
        job_id="01JBZ",
        caminho="Mapas/.preview/01JBZ/layout/minimapa.png",
    )
    assert dados["elemento"] == "minimapa"
    assert dados["caixa_mm"]["x1"] == 199.0
    assert dados["caminho"].endswith("minimapa.png")


def test_layout_elemento_fora_da_lista_levanta() -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_layout(
            "globo3d",
            sequencia=1,
            total=1,
            folha=_folha_a4_retrato(),
            caixa_mm={"x0": 0, "y0": 0, "x1": 10, "y1": 10},
            job_id="01JBZ",
        )


def test_layout_caixa_invertida_ou_fora_da_folha_levanta() -> None:
    for caixa in (
        {"x0": 10, "y0": 10, "x1": 5, "y1": 20},
        {"x0": 0, "y0": 0, "x1": 250, "y1": 10},
    ):
        with pytest.raises(motion.MotionInvalido):
            motion.montar_dados_layout(
                "legenda",
                sequencia=1,
                total=1,
                folha=_folha_a4_retrato(),
                caixa_mm=caixa,
                job_id="01JBZ",
            )


def test_layout_conteudo_gigante_levanta() -> None:
    with pytest.raises(motion.MotionInvalido):
        motion.montar_dados_layout(
            "legenda",
            sequencia=1,
            total=1,
            folha=_folha_a4_retrato(),
            caixa_mm={"x0": 0, "y0": 0, "x1": 10, "y1": 10},
            job_id="01JBZ",
            conteudo={"itens": ["x" * 100] * 100},
        )


def test_caixa_do_elemento_vem_do_perfil() -> None:
    perfil = perfil_pagina.obter("retrato")
    caixa = motion.caixa_do_elemento(perfil, "minimapa")
    assert caixa["x1"] > caixa["x0"] and caixa["y1"] > caixa["y0"]
    with pytest.raises(motion.MotionInvalido):
        motion.caixa_do_elemento(perfil, "nao_existe")


def test_elementos_na_ordem_de_montagem() -> None:
    assert motion.elementos_na_ordem(["logo", "titulo_caixa", "legenda", "inventado"]) == [
        "titulo_caixa",
        "legenda",
        "logo",
    ]
    # A ordem é a de desenho da folha: moldura primeiro, tabela por último.
    assert motion.elementos_na_ordem(motion.ELEMENTOS)[0] == "grade"
    assert motion.elementos_na_ordem(motion.ELEMENTOS)[-1] == "tabela"


# ------------------------------------------------------- rastreador (W7-03)
def test_rastreador_emite_os_tres_eventos_na_ordem() -> None:
    emitidos: list[tuple[str, dict]] = []
    prog = RastreadorProgresso(lambda e, d: emitidos.append((e, d)), job_id="01JBZ")
    prog.concluir("validando_spec")
    prog.foco("estado", [-61.63, -18.04, -50.22, -7.35], "Mato Grosso", "ibge")
    prog.foco("municipio", [-52.6, -12.8, -52.3, -12.5], "Querência/MT", "ibge")
    prog.foco("imovel", [-52.5, -12.7, -52.4, -12.6], "Fazenda Boa Vista", "geometria_local")
    prog.camada(
        camada_id="perimetro",
        papel="perimetro",
        nome="Perímetro do imóvel",
        geometria="poligono",
        total=2,
        caminho="Mapas/.preview/01JBZ/camadas/perimetro.geojson",
        n_feicoes=1,
    )
    prog.camada(
        camada_id="avn",
        papel="avn",
        nome="Vegetação nativa",
        geometria="poligono",
        total=2,
        caminho="Mapas/.preview/01JBZ/camadas/avn.geojson",
        n_feicoes=4,
        area_ha=812.4410,
    )
    prog.foco(
        "enquadramento",
        [-52.5, -12.7, -52.4, -12.6],
        "1:50.000",
        "calculo_escala",
        escala=50_000,
        crs_mapa="EPSG:31982",
        quadro_mm=(285.5, 146.8),
    )
    prog.foco("folha", [-52.5, -12.7, -52.4, -12.6], "A4 retrato", "perfil_pagina", quadro_mm=(285.5, 146.8))
    prog.elemento(
        elemento="titulo_caixa",
        sequencia=1,
        total=2,
        folha=_folha_a4_retrato(),
        caixa_mm={"x0": 10, "y0": 10, "x1": 200, "y1": 18},
        conteudo="Dinâmica de uso do solo",
    )

    nomes = [e for e, _ in emitidos]
    assert nomes[1:] == [
        "viewport.foco",
        "viewport.foco",
        "viewport.foco",
        "camada.renderizada",
        "camada.renderizada",
        "viewport.foco",
        "viewport.foco",
        "layout.elemento",
    ]
    niveis = [d["nivel"] for e, d in emitidos if e == "viewport.foco"]
    assert niveis == ["estado", "municipio", "imovel", "enquadramento", "folha"]
    camadas = [d for e, d in emitidos if e == "camada.renderizada"]
    assert [c["sequencia"] for c in camadas] == [1, 2]
    assert all(c["total"] == 2 for c in camadas)


def test_rastreador_conta_camadas_e_total_que_cresce() -> None:
    emitidos: list[dict] = []
    prog = RastreadorProgresso(lambda e, d: emitidos.append(d), job_id="01JBX")
    prog.camada(
        camada_id="a", papel="avn", nome="A", geometria="poligono", total=2,
        caminho="Mapas/.preview/01JBX/camadas/a.geojson",
    )
    prog.camada(
        camada_id="b", papel="ac", nome="B", geometria="poligono", total=3,
        caminho="Mapas/.preview/01JBX/camadas/b.geojson",
    )
    prog.camada(
        camada_id="c", papel="externa", nome="C", geometria="poligono", total=1,
        caminho="Mapas/.preview/01JBX/camadas/c.geojson",
    )
    assert [d["sequencia"] for d in emitidos] == [1, 2, 3]
    # `total` nunca encolhe: a terceira camada veio com total=1 e continua mostrando 3.
    assert [d["total"] for d in emitidos] == [2, 3, 3]


def test_rastreador_sem_canal_nao_explode() -> None:
    prog = RastreadorProgresso(None)
    prog.foco("estado", [-61.6, -18.0, -50.2, -7.3], "MT", "ibge")
    prog.camada(
        camada_id="a", papel="avn", nome="A", geometria="poligono", total=1,
        caminho="Mapas/.preview/J/camadas/a.geojson",
    )
    assert prog.nivel_viewport == "estado"
