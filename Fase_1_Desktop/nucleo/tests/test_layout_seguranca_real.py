"""Validação física do LayoutSpec e rejeição de layout explicitamente inválido."""
import copy
import pytest
from mapasfacil_nucleo.layout import carregar, de_perfil, validar
from mapasfacil_nucleo.motores.perfil_pagina import RETRATO
from mapasfacil_nucleo.motores.nativo import _perfil_do_mapspec
from mapasfacil_nucleo.erros import ErroNucleo


@pytest.mark.parametrize('alteracao', ['fora', 'invertida', 'nan', 'titulo_fora_quadro'])
def test_layout_invalido_geometricamente_e_reprovado(alteracao):
    spec = de_perfil(RETRATO).para_dict()
    if alteracao == 'fora':
        spec['elementos']['logo']['x1'] = 999
    elif alteracao == 'invertida':
        spec['elementos']['titulo']['x1'] = 1
    elif alteracao == 'nan':
        spec['elementos']['mapa']['x0'] = float('nan')
    else:
        spec['elementos']['titulo'].update(y0=0, y1=3)
    assert not validar(spec)['valido']


def test_loader_nao_descarta_campo_desconhecido_para_fingir_valido():
    spec = de_perfil(RETRATO).para_dict()
    spec['campo_inventado'] = True
    with pytest.raises(ValueError):
        carregar(spec)


def test_render_nao_ignora_layout_explicito_invalido():
    with pytest.raises((ValueError, ErroNucleo)):
        _perfil_do_mapspec({'template': 'dinamica_retrato', 'layout_spec': {'invalido': True}})
