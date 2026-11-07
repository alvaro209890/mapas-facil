"""O prompt deve orientar as tools reais sem retornar ao produto MXD."""
from mapasfacil_nucleo.agente.prompt import texto_system_prompt, cabe_no_teto


def test_prompt_v2_pdf_first_orienta_plano_qa_e_geo():
    texto = texto_system_prompt(incluir_web=True)
    for esperado in ('plano_definir', 'pdf_preview', 'visao_analisar', 'layout_validar', 'geo_recortar', 'MF_MXD=1'):
        assert esperado in texto
    assert 'Não edita geometria' not in texto
    assert 'Mapas/' in texto and 'XLSX/' in texto and 'SHP/' in texto
    assert cabe_no_teto(incluir_web=True)
    assert 'skill_carregar' not in texto and 'memoria_escrever' not in texto
    assert 'skill_ler' in texto and 'memoria_gravar' in texto
    assert 'gerar_mapa já processa' in texto
