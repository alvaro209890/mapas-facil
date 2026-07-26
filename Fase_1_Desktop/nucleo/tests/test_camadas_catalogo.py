# A13 — catálogo de camadas (`camadas/catalogo.py`, `catalogo.listar`).

from __future__ import annotations

import json

import pytest

from mapasfacil_nucleo.__main__ import criar_roteador, processar_linha
from mapasfacil_nucleo.camadas import catalogo
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import envelope_req
from tests.helpers_fixtures import eventos_e_resposta


def test_camadas_carrega_as_41_do_catalogo_real() -> None:
    assert len(catalogo.camadas()) == 41
    assert "embargos_siga" in catalogo.ids()
    assert "car_atp" in catalogo.ids()


def test_buscar_aceita_prefixo_catalogo_ponto() -> None:
    direto = catalogo.buscar("embargos_siga")
    prefixado = catalogo.buscar("catalogo.embargos_siga")
    assert direto == prefixado
    assert direto["layer"] == "Geoportal:AREA_EMBARGADA_SIGA_POLIGONO"


def test_buscar_camada_inexistente_e_nu_130() -> None:
    with pytest.raises(ErroNucleo) as exc:
        catalogo.buscar("camada_que_nao_existe")
    assert exc.value.codigo == "NU-130"


def test_listar_filtra_por_tema() -> None:
    resultado = catalogo.listar("embargos")
    assert resultado["total"] == len(resultado["camadas"])
    assert all(c["tema"] == "embargos" for c in resultado["camadas"])
    assert resultado["total"] >= 4
    assert "car" in resultado["temas"]


def test_listar_sem_tema_devolve_tudo() -> None:
    resultado = catalogo.listar(None)
    assert resultado["total"] == 41


def test_listar_marca_todos_os_tipos_como_suportados() -> None:
    """Os 4 tipos do catálogo têm cliente — nenhum 'ainda não implementei' silencioso."""
    resultado = catalogo.listar(None)
    por_id = {c["id"]: c for c in resultado["camadas"]}
    assert por_id["embargos_siga"]["suportada"] is True  # wms_wfs
    assert por_id["embargos_ibama"]["suportada"] is True  # arcgis_rest
    assert por_id["sigef_particular_mt"]["suportada"] is True  # wfs_gml
    assert por_id["mosaico_spot_2008"]["suportada"] is True  # wms_raster
    assert all(c["suportada"] for c in resultado["camadas"])


def test_listar_distingue_saida_vetor_de_raster() -> None:
    """Raster serve de fundo: não produz feição para contar nem área para somar."""
    por_id = {c["id"]: c for c in catalogo.listar(None)["camadas"]}
    assert por_id["embargos_siga"]["saida"] == "vetor"
    assert por_id["sigef_particular_mt"]["saida"] == "vetor"
    assert por_id["mosaico_spot_2008"]["saida"] == "raster"
    assert por_id["prodes_inpe"]["saida"] == "raster"


def test_nenhuma_camada_com_auth_expoe_nome_de_variavel_estranho() -> None:
    """`auth` é só o nome da chave no cofre — nunca um valor (AP-03)."""
    for c in catalogo.camadas():
        auth = c.get("auth")
        assert auth is None or auth in {"sema_authkey", "planet_api_key", "deepseek_api_key"}


def test_ndjson_catalogo_listar() -> None:
    linha = json.dumps(envelope_req("catalogo.listar", {"tema": "car"}), ensure_ascii=False)
    saida = processar_linha(linha, criar_roteador())
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is True
    assert res["resultado"]["tema_filtrado"] == "car"
    assert res["resultado"]["total"] > 0


def test_ndjson_catalogo_listar_tema_invalido_tipo() -> None:
    linha = json.dumps(envelope_req("catalogo.listar", {"tema": 123}), ensure_ascii=False)
    saida = processar_linha(linha, criar_roteador())
    _evts, res = eventos_e_resposta(saida)
    assert res["ok"] is False
    assert res["erro"]["codigo"] == "NU-001"
