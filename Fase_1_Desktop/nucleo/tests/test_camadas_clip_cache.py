# A13 — bbox/clip (`camadas/clip.py`) e cache TTL por tema (`camadas/cache.py`).

from __future__ import annotations

import time
from pathlib import Path

from shapely.geometry import Point, box

from mapasfacil_nucleo.camadas import cache as cache_mod
from mapasfacil_nucleo.camadas import clip


def test_expandir_bbox_aplica_25_por_cento() -> None:
    bbox = (0.0, 0.0, 1.0, 2.0)
    expandido = clip.expandir_bbox(bbox)
    assert expandido == (-0.25, -0.5, 1.25, 2.5)


def test_expandir_bbox_respeita_minimo_para_bbox_minusculo() -> None:
    bbox = (0.0, 0.0, 0.0001, 0.0001)
    expandido = clip.expandir_bbox(bbox)
    xmin, ymin, xmax, ymax = expandido
    assert xmax - 0.0001 >= clip.MINIMO_GRAUS - 1e-9
    assert xmin <= -clip.MINIMO_GRAUS + 1e-9


def test_clip_bbox_descarta_o_que_fica_fora() -> None:
    retangulo = (0.0, 0.0, 10.0, 10.0)
    dentro = box(1, 1, 2, 2)
    fora = box(20, 20, 21, 21)
    parcial = box(9, 9, 15, 15)
    recortadas = clip.clip_bbox([dentro, fora, parcial], retangulo)
    assert len(recortadas) == 2  # `fora` some, `parcial` vira o pedaço dentro
    for geom in recortadas:
        assert geom.within(box(*retangulo).buffer(1e-9))


def test_clip_poligono_pelo_perimetro_exato_do_imovel() -> None:
    imovel = box(0, 0, 10, 10)
    dentro = box(1, 1, 2, 2)
    cruzando = box(9, 9, 15, 15)
    fora = box(20, 20, 21, 21)
    recortadas = clip.clip_poligono([dentro, cruzando, fora], imovel)
    assert len(recortadas) == 2
    areas = sorted(round(g.area, 4) for g in recortadas)
    assert areas[0] == 1.0  # `dentro` inteiro (1x1)
    assert areas[1] == 1.0  # `cruzando` vira o quadrado 1x1 dentro do imóvel


def test_ttl_por_tema_conhecido_e_padrao() -> None:
    assert cache_mod.ttl_do_tema("car") == 7 * 24 * 3600
    assert cache_mod.ttl_do_tema("embargos") == 24 * 3600
    assert cache_mod.ttl_do_tema("tema_sem_regra") == cache_mod.TTL_PADRAO
    assert cache_mod.ttl_do_tema(None) == cache_mod.TTL_PADRAO


def test_cache_salvar_e_obter_fresco(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    dados = {"features": [1, 2, 3]}
    cache_mod.salvar("embargos_siga", (0, 0, 1, 1), "EPSG:4674", dados, base=base)
    entrada = cache_mod.obter("embargos_siga", (0, 0, 1, 1), "EPSG:4674", tema="embargos", base=base)
    assert entrada is not None
    assert entrada.dados == dados
    assert entrada.expirada is False


def test_cache_obter_ausente_devolve_none(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    assert cache_mod.obter("nunca_salvo", (0, 0, 1, 1), "EPSG:4674", tema="car", base=base) is None


def test_cache_bbox_arredondado_a_mesma_celula(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    cache_mod.salvar("car_atp", (0.00001, 0.00002, 1.00001, 1.00002), "EPSG:4674", {"x": 1}, base=base)
    entrada = cache_mod.obter("car_atp", (0.00002, 0.00001, 1.00002, 1.00001), "EPSG:4674", tema="car", base=base)
    assert entrada is not None  # bbox "vizinho" (diferença < 0,001°) cai na mesma célula


def test_cache_expirado_quando_passa_do_ttl(tmp_path: Path) -> None:
    base = tmp_path / "cache"
    cache_mod.salvar("embargos_siga", (0, 0, 1, 1), "EPSG:4674", {"x": 1}, base=base)
    caminho = next(base.glob("embargos_siga_*.json"))
    import json

    bruto = json.loads(caminho.read_text())
    bruto["salvo_em"] = time.time() - cache_mod.ttl_do_tema("embargos") - 10
    caminho.write_text(json.dumps(bruto), encoding="utf-8")

    entrada = cache_mod.obter("embargos_siga", (0, 0, 1, 1), "EPSG:4674", tema="embargos", base=base)
    assert entrada is not None
    assert entrada.expirada is True


def test_diretorio_cache_usa_override(tmp_path: Path) -> None:
    assert cache_mod.diretorio_cache(tmp_path / "x") == (tmp_path / "x").resolve()
