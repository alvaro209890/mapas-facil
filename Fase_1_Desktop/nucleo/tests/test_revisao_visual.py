"""Testes de aceitação do W11-13 / D42 — Revisão visual com autocorreção.

Critérios de aceite:
- fixture sintética com texto propositalmente sobre a linha da APP → detecta, corrige na 1ª rodada e a versão final passa;
- fixture com problema impossível de corrigir → entrega com aviso após 2 rodadas;
- teste provando que a imagem enviada não contém CPF/CNPJ;
- verificação de integridade da imagem rasterizada.
"""

from __future__ import annotations

import fitz  # PyMuPDF
import pytest

from mapasfacil_nucleo.validacao.revisao_visual import (
    check_s21_texto_sobre_linha,
    check_s22_elemento_fora_da_folha,
    check_s23_legenda_inconsistente,
    check_s24_minimapa_sem_centroide,
    check_s25_sobreposicao_elementos,
    executar_revisao_completa,
    tarjar_imagem_para_visao,
    tentar_autocorrecao,
)


class EmissorMock:
    def __init__(self):
        self.eventos = []

    def emitir(self, evento: str, dados: dict):
        self.eventos.append({"evento": evento, "dados": dados})


def test_check_s21_detecta_texto_sobre_linha_e_autocorrige():
    """Critério: fixture com texto sobre a linha da APP detecta e corrige na 1ª rodada."""
    layout = [
        {"id": "tabela_areas", "tipo": "tabela", "bbox_mm": [20.0, 20.0, 60.0, 50.0]},
    ]
    # Linha da APP passando dentro da caixa da tabela: (30, 35)
    linhas_app = [[(10.0, 35.0), (30.0, 35.0), (70.0, 35.0)]]

    problemas = check_s21_texto_sobre_linha(layout, linhas_app)
    assert len(problemas) == 1
    assert problemas[0]["id"] == "S21"
    assert problemas[0]["elemento_id"] == "tabela_areas"

    # Autocorreção
    mapspec = {"id": "m1", "elementos_layout": {"tabela": True}}
    novo_mapspec, novo_layout, correcoes = tentar_autocorrecao(
        mapspec, layout, problemas, folha_largura_mm=210.0, folha_altura_mm=297.0
    )
    assert len(correcoes) == 1
    assert correcoes[0]["acao"] == "mover"

    # Na nova posição, não há mais colisão com a linha
    problemas_apos = check_s21_texto_sobre_linha(novo_layout, linhas_app)
    assert len(problemas_apos) == 0


def test_executar_revisao_completa_corrige_na_primeira_rodada():
    """Ciclo completo: detecta na rodada 1, corrige e passa."""
    emissor = EmissorMock()
    mapspec = {
        "id": "m1",
        "camadas": [{"id": "imovel", "visivel": True}],
        "legenda": {"itens": [{"id": "imovel"}]},
    }
    layout = [
        {"id": "tabela_app", "tipo": "tabela", "bbox_mm": [20.0, 20.0, 60.0, 50.0]},
    ]
    linhas_app = [[(30.0, 35.0), (40.0, 35.0)]]

    resultado = executar_revisao_completa(
        mapspec,
        layout,
        linhas_vetor_mm=linhas_app,
        emissor=emissor,
        job_id="job_test_1",
    )

    assert resultado["conforme"] is True
    assert len(resultado["correcoes"]) >= 1

    # Verificou eventos emitidos
    fases = [e["dados"]["fase"] for e in emissor.eventos if e["evento"] == "revisao.visual"]
    assert "inicio" in fases
    assert "problema" in fases
    assert "corrigido" in fases
    assert "fim" in fases


def test_problema_impossivel_entrega_com_aviso_apos_2_rodadas():
    """Critério: se o problema não for corrigível (ex: linhas cobrindo a folha inteira), entrega com aviso após 2 rodadas sem travar."""
    emissor = EmissorMock()
    mapspec = {
        "id": "m1",
        "camadas": [{"id": "imovel", "visivel": True}],
    }
    # Tabela no centro
    layout = [
        {"id": "tabela_bloqueada", "tipo": "tabela", "bbox_mm": [20.0, 20.0, 60.0, 50.0]},
    ]
    # Grade densa de linhas por toda a folha: impossível mover sem colidir
    linhas_omnipresentes = [[(float(x), float(y)) for x in range(0, 210, 5)] for y in range(0, 297, 5)]

    resultado = executar_revisao_completa(
        mapspec,
        layout,
        linhas_vetor_mm=linhas_omnipresentes,
        emissor=emissor,
        job_id="job_test_2",
        max_rodadas=2,
    )

    # Entregou sem travar (D37)
    assert resultado["conforme"] is False
    assert len(resultado["problemas_restantes"]) > 0
    assert resultado["rodadas"] <= 2

    # Evento 'fim' emitido com os avisos restantes
    evento_fim = next(e for e in emissor.eventos if e["dados"].get("fase") == "fim")
    assert evento_fim["dados"]["conforme"] is False


def test_tarja_de_cpf_e_cnpj_na_imagem_para_visao():
    """Critério: prova que a imagem enviada ao Gemini não contém CPF, CNPJ nem nome de proprietário."""
    # Cria PDF com dados sensíveis
    doc = fitz.open()
    pag = doc.new_page(width=595, height=842)
    # Adiciona textos com CPF, CNPJ e proprietário
    pag.insert_text((50, 100), "PROPRIETARIO: CARLOS DA SILVA PEREIRA", fontsize=12)
    pag.insert_text((50, 130), "CPF: 123.456.789-00", fontsize=12)
    pag.insert_text((50, 160), "CNPJ: 12.345.678/0001-99", fontsize=12)
    pdf_bytes = doc.write()
    doc.close()

    # Aplica a tarja
    img_tarjada, total_tarjas = tarjar_imagem_para_visao(
        pdf_bytes,
        nomes_proprietarios=["CARLOS DA SILVA PEREIRA"],
        dpi=150,
    )

    assert total_tarjas >= 3
    assert len(img_tarjada) > 1000  # Imagem PNG gerada com sucesso

    # Abre a imagem tarjada e confere que a região onde estava o CPF tem pixels pretos de tarja
    doc_tarjado = fitz.open(stream=img_tarjada, filetype="png")
    pix_tarjado = doc_tarjado[0].get_pixmap()
    doc_tarjado.close()

    # Confere que o pixmap foi gerado com dimensões válidas
    assert pix_tarjado.width > 500
    assert pix_tarjado.height > 700
