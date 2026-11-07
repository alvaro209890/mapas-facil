"""Contrato PDF-first do ZIP público, com fontes sintéticas."""
from pathlib import Path
from zipfile import ZipFile

from mapasfacil_servidor.pacote import OpcoesPacote, montar_pacote_do_projeto


def test_pacote_padrao_nao_inclui_mxd_nem_instrui_arcmap(tmp_path: Path):
    raiz = tmp_path / 'projeto'
    versao = raiz / 'Mapas/v001'
    versao.mkdir(parents=True)
    (versao / 'mapa.pdf').write_bytes(b'%PDF-fixture-de-teste')
    (raiz / 'MXD').mkdir()
    (raiz / 'MXD/mapa.mxd').write_bytes(b'fixture-opcional')
    destino = tmp_path / 'pacote.zip'
    montar_pacote_do_projeto(raiz, 'Mapas/v001', {'mxd': 'MXD/mapa.mxd'}, destino, OpcoesPacote())
    with ZipFile(destino) as z:
        assert not any(n.startswith('MXD/') for n in z.namelist())
        texto = z.read('LEIA-ME.txt').decode()
        assert 'PDF' in texto
        assert 'Abra o arquivo' not in texto
        assert 'ArcMap' not in texto


def test_planilhas_em_pasta_propria_e_mxd_solto_nunca_vaza(tmp_path: Path):
    raiz = tmp_path / 'projeto'
    versao = raiz / 'Mapas/v001'
    versao.mkdir(parents=True)
    (versao / 'mapa.pdf').write_bytes(b'%PDF-fixture')
    (versao / 'mapa.png').write_bytes(b'png-fixture')
    (versao / 'tabela.xlsx').write_bytes(b'xlsx-fixture')
    (versao / 'mapa.mxd').write_bytes(b'nao-deve-sair-em-Mapas')
    destino = tmp_path / 'pacote.zip'
    montar_pacote_do_projeto(raiz, 'Mapas/v001', {}, destino, OpcoesPacote())
    with ZipFile(destino) as z:
        assert 'XLSX/tabela.xlsx' in z.namelist()
        assert 'Mapas/mapa.pdf' in z.namelist()
        assert 'Mapas/mapa.png' in z.namelist()
        assert not any(n.lower().endswith('.mxd') for n in z.namelist())
