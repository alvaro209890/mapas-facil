"""Grade, legenda e município conforme os PDFs-modelo da IMAP (Dinâmica 2008 da Aline, 04/11/2026)."""

from __future__ import annotations

from mapasfacil_nucleo.motores import blocos, grade_dms, nativo, perfil_pagina

# Quadro do 15844 (Querência-MT) em UTM 22S, ~1:38.000 num A4 retrato.
EXTENT_15844 = (365_900.0, 8_633_400.0, 373_400.0, 8_643_000.0)


def _passo(itens: list[dict], chave: str = "valor") -> float:
    valores = sorted(i[chave] for i in itens)
    return round((valores[1] - valores[0]) * 3600.0)


def test_grade_usa_o_mesmo_passo_nos_dois_eixos() -> None:
    grade = grade_dms.calcular(EXTENT_15844, epsg_projetado=31982)
    assert grade["passo_segundos"]["x"] == grade["passo_segundos"]["y"]
    assert _passo(grade["x"]) == _passo(grade["y"])


def test_densidade_do_modelo_da_aline_da_30_segundos() -> None:
    grade = grade_dms.calcular(EXTENT_15844, epsg_projetado=31982, rotulos_alvo=8)
    assert grade["passo_segundos"] == {"x": 30, "y": 30}


def test_grade_legivel_recua_quando_os_rotulos_se_encostam() -> None:
    # Paisagem com o lado menor em latitude: 8 rótulos nele dariam um X apinhado.
    paisagem = perfil_pagina.PAISAGEM
    extent = (366_000.0, 8_634_500.0, 371_000.0, 8_637_400.0)
    grade = nativo._grade_legivel(extent, 31982, paisagem, 30.0)
    x0, _, x1, _ = extent
    assert nativo._rotulos_cabem(grade["x"], "inferior", paisagem.mapa.largura, x1 - x0, paisagem.pt_grade)


def test_retrato_tem_grade_serifada_e_paisagem_nao() -> None:
    assert perfil_pagina.RETRATO.fonte_grade[0] == "Cambria"
    assert perfil_pagina.PAISAGEM.fonte_grade == ()
    a3 = perfil_pagina.perfil_para({"formato": "A3", "orientacao": "retrato"})
    assert a3.fonte_grade == perfil_pagina.RETRATO.fonte_grade


def test_familia_ignora_fonte_que_nao_existe() -> None:
    assert blocos.familia_disponivel(("Fonte Que Nao Existe",)) == "DejaVu Sans"


def test_ajustes_do_modelo_mudam_o_corpo_da_legenda_e_da_grade() -> None:
    mapspec = {"ajustes_layout": {"legenda": {"pt": 7.0, "pt_titulo": 9.8}, "grade": {"pt": 7.9}}}
    perfil = nativo._perfil_com_ajustes(perfil_pagina.RETRATO, mapspec)
    assert (perfil.pt_legenda, perfil.pt_legenda_titulo, perfil.pt_grade) == (7.0, 9.8, 7.9)
    # Sem ajuste, o mesmo objeto (o golden do A4 não muda).
    assert nativo._perfil_com_ajustes(perfil_pagina.RETRATO, {}) is perfil_pagina.RETRATO


def test_municipio_sai_do_poligono_quando_nao_ha_recibo(tmp_path) -> None:
    """15844 da Aline: só os shapes, sem recibo — o minimapa dizia "Desconhecido"."""
    import shapefile as pyshp

    from mapasfacil_nucleo.camadas import ibge
    from mapasfacil_nucleo.galeria.montar import municipio_do_perimetro
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    if not ibge.shapefile_municipios().is_file():
        import pytest

        pytest.skip("base IBGE local ausente")
    (tmp_path / "SHP").mkdir()
    with pyshp.Writer(str(tmp_path / "SHP" / "ATP"), shapeType=pyshp.POLYGON) as w:
        w.field("ID", "N")
        w.poly([[(-52.2459, -12.3390), (-52.1922, -12.3390), (-52.1922, -12.3560), (-52.2459, -12.3560), (-52.2459, -12.3390)]])
        w.record(1)
    (tmp_path / "SHP" / "ATP.prj").write_text(
        'GEOGCS["GCS_SIRGAS_2000",DATUM["D_SIRGAS_2000",SPHEROID["GRS_1980",6378137.0,298.257222101]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
        encoding="utf-8",
    )
    aberto = workspace_servico.abrir(str(tmp_path))
    municipio = municipio_do_perimetro(aberto["workspace"])
    assert municipio and municipio["nome"] == "Querência"
