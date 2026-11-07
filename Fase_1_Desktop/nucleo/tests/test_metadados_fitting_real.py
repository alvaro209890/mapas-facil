"""Rodapé real: nenhum texto pode invadir o minimapa nem sair da caixa."""
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from mapasfacil_nucleo.motores.nativo import _perfil_do_mapspec
from mapasfacil_nucleo.motores.blocos import bloco_metadados


@pytest.mark.parametrize('formato', ['A4', 'A3', 'A0'])
@pytest.mark.parametrize('orientacao', ['retrato', 'paisagem'])
def test_metadados_longos_cabem_sem_cortar_texto(formato, orientacao):
    perfil = _perfil_do_mapspec({'template': f'dinamica_{orientacao}',
        'folha': {'formato': formato, 'orientacao': orientacao}})
    fig = Figure(figsize=(perfil.largura_mm / 25.4, perfil.altura_mm / 25.4), dpi=80)
    canvas = FigureCanvasAgg(fig)
    valor = 'Fixture de dois CARs fictícios sem imagem de satélite para validação geométrica'
    pares = [{'rotulo': 'Satélite/Sensor', 'valor': valor},
             {'rotulo': 'Fonte', 'valor': 'Sem imagem - teste sintético'},
             {'rotulo': 'Datum', 'valor': 'SIRGAS 2000 UTM 22 S'},
             {'rotulo': 'Identificador', 'valor': 'X' * 70}]
    assert bloco_metadados(fig, perfil, pares) == len(pares)
    canvas.draw()
    renderer = canvas.get_renderer()
    ax = fig.axes[-1]
    limite = ax.get_window_extent(renderer)
    for texto in ax.texts:
        bbox = texto.get_window_extent(renderer)
        assert bbox.x0 >= limite.x0 - 0.5, (texto.get_text(), bbox, limite)
        assert bbox.x1 <= limite.x1 + 0.5, (texto.get_text(), bbox, limite)
        assert bbox.y0 >= limite.y0 - 0.5, (texto.get_text(), bbox, limite)
        assert bbox.y1 <= limite.y1 + 0.5, (texto.get_text(), bbox, limite)
    preservado = ''.join(t.get_text() for t in ax.texts).replace(' ', '').replace('\n', '')
    assert valor.replace(' ', '') in preservado
    assert 'X' * 70 in preservado
