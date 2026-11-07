import json
import shutil
import tempfile
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao
from mapasfacil_nucleo.agente.estado import carregar_estado
from mapasfacil_nucleo.agente.orquestrador_v2 import OrquestradorV2, pedir_cancelamento
from mapasfacil_nucleo.agente.provedor import DeltaStream, ProvedorIA
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace
from mapasfacil_nucleo.protocolo import Emissor


class MockProvedorInfinito(ProvedorIA):
    """Gera stream contínuo para testar cancelamento cooperativo."""

    def __init__(self):
        self.cancelado = False

    def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
        for i in range(100):
            if self.cancelado:
                break
            yield DeltaStream(texto=f"Gerando parte {i}...")

    def cancelar(self):
        self.cancelado = True


class MockProvedorApagar(ProvedorIA):
    """Pede para apagar um arquivo."""

    def __init__(self, caminho: str):
        self.caminho = caminho
        self.chamado = 0

    def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
        self.chamado += 1
        if self.chamado == 1:
            yield DeltaStream(
                tool_calls=[
                    {
                        "id": "c_del",
                        "function": {
                            "name": "workspace_apagar",
                            "arguments": json.dumps({"caminho": self.caminho}),
                        },
                    }
                ]
            )
        else:
            yield DeltaStream(texto="Nunca deve chegar aqui sem aprovação prévia.")


@pytest.fixture
def ws_canc():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_canc_")
    ws_path = Path(temp_dir)
    (ws_path / "arquivo_sensivel.shp").write_text("shp dados", encoding="utf-8")
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_cancelamento_no_orquestrador(ws_canc):
    registro = RegistroFerramentas()
    provedor = MockProvedorInfinito()
    eventos = []
    emissor = Emissor("req-canc", sink=lambda evt: eventos.append(evt))

    conv_id = "conv-cancelar"
    pedir_cancelamento(conv_id)

    orq = OrquestradorV2(registro=registro, provedor=provedor)
    res = orq.executar(conversation_id=conv_id, mensagem="Começar", workspace=ws_canc, emissor=emissor)

    assert res["status"] == "cancelado"
    evts_fim = [e for e in eventos if e["evento"] == "agente.fim"]
    assert len(evts_fim) == 1
    assert evts_fim[0]["dados"]["status"] == "cancelado"

    estado_disco = carregar_estado(ws_canc)
    assert estado_disco is not None
    assert estado_disco.status == "cancelado"


def test_aprovacao_interrompe_turno_sem_continuar_llm(ws_canc):
    registro = RegistroFerramentas()
    gerenciador_aprov = GerenciadorAprovacao()
    registrar_tools_workspace(registro, gerenciador_aprovacao=gerenciador_aprov)

    provedor = MockProvedorApagar("arquivo_sensivel.shp")
    eventos = []
    emissor = Emissor("req-aprov", sink=lambda evt: eventos.append(evt))

    orq = OrquestradorV2(registro=registro, provedor=provedor)
    res = orq.executar(
        conversation_id="conv-aprov",
        mensagem="Apague o arquivo sensível",
        workspace=ws_canc,
        emissor=emissor,
    )

    # Turno encerra imediatamente
    assert res["status"] == "aguardando_aprovacao"
    assert provedor.chamado == 1  # NÃO chamou a LLM uma segunda vez!

    # Evento agente.aprovacao emitido
    evts_aprov = [e for e in eventos if e["evento"] == "agente.aprovacao"]
    assert len(evts_aprov) == 1
    assert evts_aprov[0]["dados"]["acao"] == "apagar"
    assert evts_aprov[0]["dados"]["caminho"] == "arquivo_sensivel.shp"

    # Estado gravado como aguardando_aprovacao
    estado_disco = carregar_estado(ws_canc)
    assert estado_disco is not None
    assert estado_disco.status == "aguardando_aprovacao"
    assert estado_disco.aprovacao is not None
    assert estado_disco.aprovacao["caminho"] == "arquivo_sensivel.shp"

    # Arquivo intacto
    assert (ws_canc / "arquivo_sensivel.shp").exists()
