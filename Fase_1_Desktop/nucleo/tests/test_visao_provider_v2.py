"""Rota de visão deve seguir o provider configurado do servidor, não DeepSeek legado."""
from mapasfacil_nucleo.agente.visao import servico


def test_visao_servidor_usa_mesmo_endpoint_e_modelo_configurados(monkeypatch):
    monkeypatch.setattr(servico, '_provedor_override', None)
    monkeypatch.setattr(servico, 'ler_chave_deepseek', lambda: None)
    monkeypatch.setenv('MAPASFACIL_PROVEDOR', 'openai_compat')
    monkeypatch.setenv('MAPASFACIL_PROVEDOR_URL', 'http://127.0.0.1:20128/v1')
    monkeypatch.setenv('MAPASFACIL_PROVEDOR_CHAVE', 'credencial-sintetica-nao-real')
    monkeypatch.setenv('MAPASFACIL_MODELO_VISAO', 'ag/modelo-sintetico-teste')
    provedor = servico._obter_provedor()
    assert provedor is not None
    assert provedor.endpoint == 'http://127.0.0.1:20128/v1/chat/completions'
    assert provedor.modelo == 'ag/modelo-sintetico-teste'
