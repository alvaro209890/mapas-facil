"""Regressões de integridade do MVP multi-imóvel, sem dados reais."""
from pathlib import Path
from openpyxl import load_workbook
from mapasfacil_nucleo.multi_imovel import gerar_xlsx_combinado


def test_xlsx_aceita_nomes_com_barra_e_resolve_colisao_de_abas(tmp_path: Path):
    destino = tmp_path / 'combinado.xlsx'
    imoveis = [
        {'id': 'alfa', 'nome': 'Gleba 1/2', 'area': 1.0},
        {'id': 'beta', 'nome': 'Gleba 1:2', 'area': 2.0},
    ]
    gerar_xlsx_combinado(imoveis, {}, destino)
    wb = load_workbook(destino)
    assert len(wb.sheetnames) == 4
    assert len({n.lower() for n in wb.sheetnames}) == 4
    assert all(len(n) <= 31 and not any(c in n for c in '\\/?*:[]') for n in wb.sheetnames)
    assert wb['Resumo Imóveis']['B3'].value == 'Gleba 1/2'
    wb.close()


def test_recibo_ambiguo_nao_e_atribuido_ao_primeiro_atp(tmp_path: Path):
    from tests.test_multi_imovel import _criar_recibo_pdf, _criar_shapefile_pyshp
    from mapasfacil_nucleo.multi_imovel import identificar_imoveis, _casar_atp_com_evidencia
    candidatos = [{'caminho': 'SHP/ATP1.shp'}, {'caminho': 'SHP/ATP2.shp'}]
    recibo = {'caminho': 'SHP/recibo.pdf', 'dados': {'nome_imovel': 'Fazenda Desconhecida'}}
    assert _casar_atp_com_evidencia(recibo, candidatos) is None
    for nome, deslocamento in [('ATP1', 0), ('ATP2', 2000)]:
        x = 600000 + deslocamento
        _criar_shapefile_pyshp(tmp_path / 'SHP', nome,
                              [(x, 8300000), (x, 8301000), (x+1000, 8301000), (x+1000, 8300000)])
    _criar_recibo_pdf(tmp_path / 'documentos/recibo.pdf', 'Fazenda Desconhecida', 'MT9999999/2026', 999)
    imoveis = identificar_imoveis(tmp_path)
    assert len(imoveis) == 2
    assert all(im.get('car') is None for im in imoveis)
    assert all(im.get('nome') != 'Fazenda Desconhecida' for im in imoveis)


def test_geracao_nao_copia_car_e_area_do_principal_para_secundario(tmp_path, monkeypatch):
    from mapasfacil_nucleo.multi_imovel import gerar_mapas_por_imovel
    from mapasfacil_nucleo.motores import gerar as motor
    recebidos = []
    monkeypatch.setattr(motor, 'gerar_mapa', lambda ms, *a, **kw: recebidos.append(ms) or {})
    ms = {
        'imovel': {'nome': 'Principal', 'car': 'MT1000001/2026', 'area_total_ha': 999},
        'imoveis': [
            {'id':'alfa', 'nome':'Alfa', 'car':'MT1000001/2026', 'area':100, 'atp':'SHP/Alfa.shp'},
            {'id':'beta', 'nome':'Beta', 'car':None, 'area':None, 'atp':'SHP/Beta.shp'},
        ],
    }
    gerar_mapas_por_imovel(ms, tmp_path, fontes_idx={})
    assert recebidos[1]['imovel']['car'] in (None, '')
    assert recebidos[1]['imovel']['area_total_ha'] is None


def test_reindexar_nao_inventa_imoveis_de_artefatos_gerados(tmp_path):
    import shutil
    import zipfile
    import sys
    from mapasfacil_nucleo.multi_imovel import identificar_imoveis
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'Fase_3_Web/fixtures'))
    from gerar_zip_dois_imoveis import gerar_zip_dois_imoveis
    zip_path = tmp_path / 'fixture.zip'
    gerar_zip_dois_imoveis(zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_path)
    antes = identificar_imoveis(tmp_path)
    assert len(antes) == 2
    for pasta in ('SHP', 'Mapas/v001/SHP', 'Mapas/v001'):
        destino = tmp_path / pasta
        destino.mkdir(parents=True, exist_ok=True)
        for origem in (tmp_path / 'CAR_Alfa').glob('*'):
            if origem.suffix.lower() in ('.pdf', '.shp', '.shx', '.dbf', '.prj'):
                shutil.copy2(origem, destino / origem.name)
    depois = identificar_imoveis(tmp_path)
    assert [(i['nome'], i['car'], i['atp']) for i in depois] == [(i['nome'], i['car'], i['atp']) for i in antes]


def test_validacao_consolidada_inclui_reprovacao_do_segundo_imovel(tmp_path, monkeypatch):
    import json
    import pymupdf
    from mapasfacil_nucleo import multi_imovel as multi
    (tmp_path / 'Mapas/v001').mkdir(parents=True)
    for nome in ('alfa', 'beta'):
        with pymupdf.open() as doc:
            doc.new_page().insert_text((40,40), nome)
            doc.save(tmp_path / f'Mapas/v001/{nome}.pdf')
    resultados = {n:{'pdf':f'Mapas/v001/{n}.pdf','validacao_dados':{'checks':{
        'hard':[{'id':'H01','ok':n=='alfa','mensagem':n}], 'soft':[]}}} for n in ('alfa','beta')}
    monkeypatch.setattr(multi,'gerar_mapas_por_imovel',lambda *a,**kw:resultados)
    ms={'titulo':'Sintético','imoveis':[{'id':n,'nome':n} for n in resultados],
        'saida':{'pasta':'Mapas/v001','nome_base':'atlas'}}
    res=multi.gerar_multi_imovel(ms,tmp_path)
    validacao=res['validacao_dados']
    assert validacao['conforme'] is False
    assert {c['imovel_id'] for c in validacao['checks']['hard']} == {'alfa','beta'}
    assert json.loads((tmp_path/'Mapas/v001/validacao.json').read_text(encoding='utf-8'))['conforme'] is False


