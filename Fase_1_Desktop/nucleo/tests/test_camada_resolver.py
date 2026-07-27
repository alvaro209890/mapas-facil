# A13 — `camada.resolver`: catálogo → cache → WFS → clip → shapefile local.
#
# Critérios de aceite (AGENT_BRIEF / F1-13 A13): fixture HTTP gravada (proibido
# rede real no CI), `.shp` válido sob fsguard, bbox/crs respeitados, códigos
# `NU-1xx` corretos para timeout/XML-erro/vazio, e authkey nunca aparece na
# resposta NDJSON nem em log.

from __future__ import annotations

import json
from pathlib import Path

import pytest
import shapefile as pyshp

from mapasfacil_nucleo import cofre
from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.camadas import http
from mapasfacil_nucleo.camadas.resolver import resolver_camada
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.protocolo import envelope_req
from tests.helpers_fixtures import eventos_e_resposta

FIXTURES = Path(__file__).parent / "fixtures" / "wfs"
BBOX = (-58.02, -11.02, -57.98, -10.98)
CHAVE_TESTE = "sk-authkey-nao-pode-vazar-9f8e7d"


@pytest.fixture(autouse=True)
def _cofre_memoria():
    mem = cofre.BackendMemoria()
    cofre.configurar_backend(mem)
    yield mem
    cofre.configurar_backend(None)


@pytest.fixture(autouse=True)
def _sem_transporte_real():
    yield
    http.configurar_transporte(None)


@pytest.fixture
def guard(tmp_path: Path) -> WorkspaceGuard:
    (tmp_path / "SHP").mkdir()
    return WorkspaceGuard(tmp_path)


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "_cache_teste"


def _transporte_fixture(nome: str, *, status: int = 200, content_type: str = "application/json"):
    corpo = (FIXTURES / nome).read_bytes()

    def _fn(url: str, timeout: int) -> http.RespostaHttp:
        # A URL de saída PRECISA ter a chave real (é assim que a SEMA autentica);
        # o que não pode vazar é o valor em log/erro/NDJSON — `redigir_url` cobre isso.
        assert CHAVE_TESTE in url
        return http.RespostaHttp(status=status, corpo=corpo, content_type=content_type)

    return _fn


def test_resolver_camada_gera_shp_valido_sob_fsguard(guard: WorkspaceGuard, cache_dir: Path) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)
    http.configurar_transporte(_transporte_fixture("embargos_siga_getfeature.json"))

    resultado = resolver_camada(
        "embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir
    )

    assert resultado.feicoes == 1
    assert resultado.vazia is False
    assert resultado.epsg == 4674
    caminho_shp = guard.raiz / resultado.arquivo_rel
    assert caminho_shp.exists()
    assert caminho_shp.is_relative_to(guard.raiz)  # dentro do workspace — fsguard

    leitor = pyshp.Reader(str(caminho_shp.with_suffix("")))
    assert leitor.numRecords == 1
    assert leitor.shapeTypeName == "POLYGON"
    prj = caminho_shp.with_suffix(".prj").read_text(encoding="utf-8")
    assert "4674" in prj or "SIRGAS" in prj.upper()


def test_resolver_camada_respeita_bbox_expandido(guard: WorkspaceGuard, cache_dir: Path) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)
    urls: list[str] = []

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        urls.append(url)
        corpo = (FIXTURES / "embargos_siga_getfeature.json").read_bytes()
        return http.RespostaHttp(status=200, corpo=corpo, content_type="application/json")

    http.configurar_transporte(fake)
    resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)

    assert urls, "o transporte não foi chamado"
    # bbox expandido ~25%: a caixa original tem 0,04° de lado; expandida passa de 0,04
    assert "bbox=-58.03" in urls[0] or "-58.03" in urls[0]


def test_resolver_camada_vazia_gera_shp_valido_com_aviso_nu120(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)
    http.configurar_transporte(_transporte_fixture("vazio_getfeature.json"))

    resultado = resolver_camada(
        "embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir
    )

    assert resultado.vazia is True
    assert resultado.feicoes == 0
    assert any(a["codigo"] == "NU-120" for a in resultado.avisos)
    caminho_shp = guard.raiz / resultado.arquivo_rel
    assert caminho_shp.exists()  # vazio ainda é um shapefile válido


def test_resolver_camada_timeout_e_nu101(guard: WorkspaceGuard, cache_dir: Path) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)

    def fake_timeout(url: str, timeout: int) -> http.RespostaHttp:
        raise ErroNucleo("NU-101", "timeout simulado")

    http.configurar_transporte(fake_timeout)
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-101"


def test_resolver_camada_xml_de_erro_e_nu110(guard: WorkspaceGuard, cache_dir: Path) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)
    http.configurar_transporte(
        _transporte_fixture("erro_geoserver.xml", content_type="text/xml")
    )
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-110"
    # a URL vai nos detalhes do erro (log), mas com a chave mascarada — nunca crua.
    assert CHAVE_TESTE not in json.dumps(exc.value.para_dict())
    url_no_erro = (exc.value.detalhes or {}).get("url", "")
    assert "authkey=***" in url_no_erro or "authkey=%2A%2A%2A" in url_no_erro


def test_resolver_camada_sem_chave_configurada_e_nu102(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    # cofre vazio — nenhuma chave definida.
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-102"


def test_resolver_camada_fonte_fora_do_catalogo_e_nu130(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("camada_inventada", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-130"


def test_todo_tipo_do_catalogo_tem_cliente() -> None:
    """NU-140 virou salvaguarda de tipo desconhecido, não 'ainda não implementei'."""
    from mapasfacil_nucleo.camadas import catalogo as catalogo_mod

    tipos_no_catalogo = {c["tipo"] for c in catalogo_mod.camadas()}
    assert tipos_no_catalogo <= catalogo_mod.TIPOS_SUPORTADOS, (
        f"tipo sem cliente no catálogo: {tipos_no_catalogo - catalogo_mod.TIPOS_SUPORTADOS}"
    )


def test_resolver_camada_bbox_invalido_e_nu001(guard: WorkspaceGuard, cache_dir: Path) -> None:
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("embargos_siga", (1, 2, 1, 2), "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-001"


def test_resolver_camada_crs_invalido_e_nu001(guard: WorkspaceGuard, cache_dir: Path) -> None:
    with pytest.raises(ErroNucleo) as exc:
        resolver_camada("embargos_siga", BBOX, "não-epsg", guard=guard, cache_base=cache_dir)
    assert exc.value.codigo == "NU-001"


def test_resolver_camada_usa_cache_na_segunda_chamada(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    cofre.definir("sema_authkey", CHAVE_TESTE)
    chamadas = {"n": 0}

    def fake(url: str, timeout: int) -> http.RespostaHttp:
        chamadas["n"] += 1
        corpo = (FIXTURES / "embargos_siga_getfeature.json").read_bytes()
        return http.RespostaHttp(status=200, corpo=corpo, content_type="application/json")

    http.configurar_transporte(fake)
    r1 = resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    r2 = resolver_camada("embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)

    assert r1.origem_cache == "miss"
    assert r2.origem_cache == "hit"
    assert chamadas["n"] == 1  # segunda chamada não bateu na rede


def test_resolver_camada_offline_usa_cache_expirado_com_aviso(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    from mapasfacil_nucleo.camadas import cache as cache_mod

    cofre.definir("sema_authkey", CHAVE_TESTE)
    # Popula o cache já "expirado" manualmente (salvo_em no passado).
    dados = json.loads((FIXTURES / "embargos_siga_getfeature.json").read_text())
    cache_mod.salvar("embargos_siga", (-58.03, -11.03, -57.97, -10.97), "EPSG:4674", dados, base=cache_dir)
    caminho_cache = next(cache_dir.glob("embargos_siga_*.json"))
    bruto = json.loads(caminho_cache.read_text())
    bruto["salvo_em"] = 0  # 1970 — garantidamente expirado
    caminho_cache.write_text(json.dumps(bruto), encoding="utf-8")

    def fake_offline(url: str, timeout: int) -> http.RespostaHttp:
        raise ErroNucleo("NU-101", "sem rede")

    http.configurar_transporte(fake_offline)
    resultado = resolver_camada(
        "embargos_siga", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir
    )
    assert resultado.origem_cache == "expirado"
    assert resultado.feicoes == 1
    assert any(a["codigo"] == "NU-103" for a in resultado.avisos)


def test_ndjson_camada_resolver_nunca_devolve_authkey(tmp_path: Path) -> None:
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    (tmp_path / "SHP").mkdir()
    workspace_servico.abrir(str(tmp_path))
    try:
        cofre.definir("sema_authkey", CHAVE_TESTE)
        http.configurar_transporte(_transporte_fixture("embargos_siga_getfeature.json"))

        linha = json.dumps(
            envelope_req("camada.resolver", {"fonte": "embargos_siga", "bbox": list(BBOX), "crs": "EPSG:4674"}),
            ensure_ascii=False,
        )
        saida = processar_linha(linha, criar_roteador())
        assert CHAVE_TESTE not in saida
        _evts, res = eventos_e_resposta(saida)
        assert res["ok"] is True
        assert res["resultado"]["feicoes"] == 1
        assert "geometrias" not in res["resultado"]
        assert res["resultado"]["arquivo"].replace("\\", "/").startswith("SHP/")
    finally:
        workspace_servico.fechar()


def test_ndjson_camada_resolver_sem_workspace_e_nu040() -> None:
    from mapasfacil_nucleo.workspace import servico as workspace_servico

    workspace_servico.fechar()
    linha = json.dumps(
        envelope_req("camada.resolver", {"fonte": "embargos_siga", "bbox": list(BBOX), "crs": "EPSG:4674"}),
        ensure_ascii=False,
    )
    saida = processar_linha(linha, criar_roteador())
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is False
    assert res["erro"]["codigo"] == "NU-040"


# ------------------------------------------------ tipos além de wms_wfs (épico pós-A13)


def test_resolver_arcgis_rest_gera_shapefile(guard: WorkspaceGuard, cache_dir: Path) -> None:
    """`embargos_ibama` é `arcgis_rest` e não exige chave (auth: null)."""
    corpo = json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-58.01, -11.01],
                                [-57.99, -11.01],
                                [-57.99, -10.99],
                                [-58.01, -10.99],
                                [-58.01, -11.01],
                            ]
                        ],
                    },
                    "properties": {},
                }
            ],
        }
    ).encode()
    http.configurar_transporte(
        lambda url, timeout: http.RespostaHttp(
            status=200, corpo=corpo, content_type="application/json"
        )
    )
    r = resolver_camada("embargos_ibama", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert r.tipo_saida == "vetor"
    assert r.feicoes == 1
    assert (guard.raiz / r.arquivo_rel).exists()


def test_resolver_wfs_gml_reprojeta_do_epsg_nativo(guard: WorkspaceGuard, cache_dir: Path) -> None:
    """INCRA declara `epsg: 4326`; pedindo 31982 o resolver tem de reprojetar."""
    gml = (
        '<?xml version="1.0"?><wfs:FeatureCollection '
        'xmlns:wfs="http://www.opengis.net/wfs" xmlns:gml="http://www.opengis.net/gml">'
        "<gml:featureMember><f><gml:Polygon><gml:outerBoundaryIs><gml:LinearRing>"
        "<gml:coordinates>-58.01,-11.01 -57.99,-11.01 -57.99,-10.99 -58.01,-10.99"
        "</gml:coordinates></gml:LinearRing></gml:outerBoundaryIs></gml:Polygon></f>"
        "</gml:featureMember></wfs:FeatureCollection>"
    ).encode()
    http.configurar_transporte(
        lambda url, timeout: http.RespostaHttp(status=200, corpo=gml, content_type="text/xml")
    )
    # bbox em UTM 22S cobrindo onde (-58,-11) cai depois de reprojetado
    # (≈ x -267.5k, y 8.774M). Se o resolver NÃO reprojetasse, a geometria ficaria
    # em graus (~-58) e o clip a descartaria — a contagem prova a conversão.
    bbox_utm = (-270_000.0, 8_770_000.0, -263_000.0, 8_779_000.0)
    r = resolver_camada(
        "sigef_particular_mt", bbox_utm, "EPSG:31982", guard=guard, cache_base=cache_dir
    )
    assert r.tipo_saida == "vetor"
    assert r.epsg == 31982
    assert r.feicoes == 1, "geometria sobreviveu ao clip ⇒ foi reprojetada de 4326 para 31982"
    assert r.vazia is False


def test_resolver_wms_raster_salva_imagem_e_marca_tipo_saida(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    (guard.raiz / "Mapas").mkdir(exist_ok=True)
    cofre.definir("sema_authkey", CHAVE_TESTE)
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    )
    http.configurar_transporte(
        lambda url, timeout: http.RespostaHttp(status=200, corpo=png, content_type="image/png")
    )
    r = resolver_camada("mosaico_spot_2008", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert r.tipo_saida == "raster"
    assert r.arquivo_rel.endswith(".png")
    assert r.feicoes == 0  # WMS não devolve feição — nunca fingir contagem
    assert (guard.raiz / r.arquivo_rel).read_bytes() == png
    assert any(a["codigo"] == "NU-112" for a in r.avisos)


def test_resolver_wms_raster_nao_devolve_authkey_no_ndjson(
    guard: WorkspaceGuard, cache_dir: Path
) -> None:
    (guard.raiz / "Mapas").mkdir(exist_ok=True)
    cofre.definir("sema_authkey", CHAVE_TESTE)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    http.configurar_transporte(
        lambda url, timeout: http.RespostaHttp(status=200, corpo=png, content_type="image/png")
    )
    r = resolver_camada("mosaico_spot_2008", BBOX, "EPSG:4674", guard=guard, cache_base=cache_dir)
    assert CHAVE_TESTE not in json.dumps(r.para_ndjson(), ensure_ascii=False)
