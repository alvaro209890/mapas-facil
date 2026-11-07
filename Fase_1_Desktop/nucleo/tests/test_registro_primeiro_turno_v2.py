"""Catálogo precisa estar completo mesmo no primeiro turno do processo."""
from mapasfacil_nucleo.agente import registro, tools
from mapasfacil_nucleo.agente.plano import registrar_tools_plano


def test_schemas_carregam_catalogo_com_registro_parcial(monkeypatch):
    novo = registro.RegistroFerramentas()
    registrar_tools_plano(novo)
    monkeypatch.setattr(registro, 'registro_padrao', novo)
    nomes = {s['function']['name'] for s in tools.schemas_openai()}
    assert {'plano_definir', 'workspace_listar', 'layout_renderizar', 'visao_analisar', 'geo_dissolver'} <= nomes


def test_sugerir_enquadramento_preserva_folha_como_objeto(monkeypatch):
    from shapely.geometry import box
    monkeypatch.setattr(tools, '_estado', lambda: object())
    monkeypatch.setattr(tools, '_geometria_imovel', lambda estado: (box(600000,8300000,601000,8301000),31982))
    res=tools.executar('sugerir_enquadramento', {'formatos':['A3']},
        {'mapspec':{'folha':{'formato':'A3','orientacao':'retrato'}}})
    assert res['ok'],res
    assert res['folha_atual']['formato']=='A3'
    assert res['atual']['escala']>0

