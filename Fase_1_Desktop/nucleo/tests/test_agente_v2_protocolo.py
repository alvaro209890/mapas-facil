from mapasfacil_nucleo.protocolo import EVENTOS, envelope_evt, evento_valido


def test_eventos_agente_v2_registrados():
    novos_eventos = {
        "agente.plano",
        "agente.passo",
        "agente.arquivo",
        "agente.preview",
        "agente.aprovacao",
        "agente.fim",
    }
    for evento in novos_eventos:
        assert evento in EVENTOS, f"Evento {evento} deve estar em EVENTOS"
        assert evento_valido(evento), f"evento_valido({evento}) deve retornar True"


def test_envelope_evt_com_novos_eventos():
    env_plano = envelope_evt("req-1", "agente.plano", {"passos": [{"id": "p1", "titulo": "Ler", "status": "pendente"}]})
    assert env_plano["evento"] == "agente.plano"
    assert env_plano["dados"]["passos"][0]["id"] == "p1"

    env_aprov = envelope_evt("req-2", "agente.aprovacao", {"acao": "apagar", "caminho": "SHP/teste.shp", "motivo": "exclusao"})
    assert env_aprov["evento"] == "agente.aprovacao"
