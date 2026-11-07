"""Arquivos históricos precisam ser legíveis para QA, mas nunca editáveis."""
import pymupdf
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_pdf import registrar_tools_pdf
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace


def test_pdf_versionado_tem_preview_sem_permitir_sobrescrita(tmp_path):
    pasta = tmp_path / 'Mapas/v001'
    pasta.mkdir(parents=True)
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40, 40), 'QA SINTETICO')
        doc.save(pasta / 'mapa.pdf')
    reg = RegistroFerramentas()
    registrar_tools_pdf(reg)
    registrar_tools_workspace(reg)
    ctx = {'workspace': tmp_path}
    res = reg.executar('pdf_preview', {'caminho_pdf': 'Mapas/v001/mapa.pdf'}, ctx)
    assert res['ok'], res
    assert (tmp_path / res['preview_caminho']).is_file()
    alteracao = reg.executar('workspace_escrever', {'caminho': 'Mapas/v001/mapa.pdf', 'conteudo': 'corrompido'}, ctx)
    assert not alteracao['ok']
    with pymupdf.open(pasta / 'mapa.pdf') as doc:
        assert 'SINTETICO' in doc[0].get_text()


def test_geo_nao_sobrescreve_fonte_existente(tmp_path):
    from tests.test_multi_imovel import _criar_shapefile_pyshp
    from mapasfacil_nucleo.agente.tools_geo import registrar_tools_geo
    _criar_shapefile_pyshp(tmp_path / 'SHP', 'ATP', [(600000,8300000),(600000,8301000),(601000,8301000),(601000,8300000)])
    original = (tmp_path / 'SHP/ATP.shp').read_bytes()
    reg = RegistroFerramentas()
    registrar_tools_geo(reg)
    res = reg.executar('geo_dissolver', {'camada_entrada': 'SHP/ATP.shp', 'camada_saida': 'SHP/ATP.shp'}, {'workspace': tmp_path})
    assert not res['ok'], res
    assert (tmp_path / 'SHP/ATP.shp').read_bytes() == original


def test_qa_pos_render_usa_geometria_real_e_nao_corrige_so_na_memoria(tmp_path, mapspec_canonico, monkeypatch):
    import copy
    from mapasfacil_nucleo.agente import tools
    from mapasfacil_nucleo.motores import gerar, nativo
    from mapasfacil_nucleo.validacao import revisao_visual
    from mapasfacil_nucleo.workspace import servico
    from tests.helpers_fixtures import montar_workspace_minimo
    montar_workspace_minimo(tmp_path)
    servico.abrir(str(tmp_path))
    capturado = {}
    def revisar(**kwargs):
        capturado.update(kwargs)
        return {'problemas_restantes': []}
    monkeypatch.setattr(revisao_visual, 'executar_revisao_completa', revisar)
    # Stub apenas da geração: o contrato sob teste é o encaminhamento do QA.
    monkeypatch.setattr(gerar, 'gerar_mapa', lambda *a, **kw: {})
    ms = copy.deepcopy(mapspec_canonico)
    ms['folha'] = {'formato':'A3', 'orientacao':'paisagem'}
    ms['template'] = 'tipologia_paisagem'
    try:
        tools.tool_gerar_mapa({'saidas':['pdf']}, {'mapspec':ms})
        perfil = nativo._perfil_do_mapspec(ms)
        assert capturado['folha_largura_mm'] == perfil.largura_mm
        assert capturado['folha_altura_mm'] == perfil.altura_mm
        assert capturado['max_rodadas'] == 0
        por_id = {e['id']:e for e in capturado['layout_elementos']}
        c = perfil.metadados
        assert por_id['metadados']['bbox_mm'] == [c.x0,c.y0,c.x1,c.y1]
        assert por_id['metadados']['bbox_mm'] != [10,10,50,30]
    finally:
        servico.fechar()

