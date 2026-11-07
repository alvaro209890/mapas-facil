import json
import shutil
import tempfile
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.estado import EstadoAgente, carregar_estado, salvar_estado
from mapasfacil_nucleo.agente.orquestrador_v2 import OrquestradorV2, pedir_cancelamento
from mapasfacil_nucleo.agente.plano import PlanoAgente
from mapasfacil_nucleo.agente.provedor import DeltaStream, MensagemLLM, ProvedorIA
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace
from mapasfacil_nucleo.protocolo import Emissor


class MockProvedorRepetido(ProvedorIA):
    """Simula LLM chamando repetidamente uma tool que falha."""

    def __init__(self, tool_name: str, max_chamadas: int = 10):
        self.tool_name = tool_name
        self.chamadas = 0
        self.max_chamadas = max_chamadas

    def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
        self.chamadas += 1
        yield DeltaStream(
            tool_calls=[
                {
                    "id": f"call_{self.chamadas}",
                    "function": {"name": self.tool_name, "arguments": "{}"},
                }
            ]
        )


class MockProvedorPlano(ProvedorIA):
    """Simula LLM definindo plano, executando passo e concluindo."""

    def __init__(self):
        self.rodada = 0

    def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
        self.rodada += 1
        if self.rodada == 1:
            yield DeltaStream(
                tool_calls=[
                    {
                        "id": "c1",
                        "function": {
                            "name": "plano_definir",
                            "arguments": json.dumps(
                                {
                                    "passos": [
                                        {"id": "p1", "titulo": "Ler dados", "status": "pendente"},
                                        {"id": "p2", "titulo": "Gerar prancha", "status": "pendente"},
                                    ]
                                }
                            ),
                        },
                    }
                ]
            )
        elif self.rodada == 2:
            yield DeltaStream(
                tool_calls=[
                    {
                        "id": "c2",
                        "function": {
                            "name": "plano_atualizar",
                            "arguments": json.dumps(
                                {"passo_id": "p1", "status": "concluido", "resumo": "Dados lidos"}
                            ),
                        },
                    }
                ]
            )
        else:
            yield DeltaStream(texto="Processo concluído com sucesso!")


@pytest.fixture
def ws_orq():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_orq_")
    ws_path = Path(temp_dir)
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_persistencia_estado_agente(ws_orq):
    estado = EstadoAgente(
        conversation_id="conv-001",
        status="executando",
        passos=[{"id": "1", "titulo": "Iniciar", "status": "concluido"}],
        arquivos=[{"caminho": "Mapas/teste.pdf", "acao": "criacao"}],
        previews=[{"caminho": "Mapas/previews/p1.png", "pagina": 1}],
    )
    salvar_estado(ws_orq, estado)

    carregado = carregar_estado(ws_orq)
    assert carregado is not None
    assert carregado.conversation_id == "conv-001"
    assert carregado.status == "executando"
    assert len(carregado.passos) == 1
    assert len(carregado.arquivos) == 1
    assert len(carregado.previews) == 1


def test_plano_agente_eventos():
    eventos = []
    emissor = Emissor("req-plano", sink=lambda evt: eventos.append(evt))
    plano = PlanoAgente(emissor=emissor)

    plano.definir(
        [
            {"id": "step1", "titulo": "Passo 1", "status": "pendente"},
            {"id": "step2", "titulo": "Passo 2", "status": "pendente"},
        ]
    )

    evts_plano = [e for e in eventos if e["evento"] == "agente.plano"]
    assert len(evts_plano) == 1
    assert len(evts_plano[0]["dados"]["passos"]) == 2

    plano.atualizar("step1", "concluido", resumo="Concluído com êxito")
    evts_passo = [e for e in eventos if e["evento"] == "agente.passo"]
    assert len(evts_passo) == 1
    assert evts_passo[0]["dados"]["id"] == "step1"
    assert evts_passo[0]["dados"]["status"] == "concluido"
    assert evts_passo[0]["dados"]["resumo"] == "Concluído com êxito"


def test_loop_encerra_em_falha_repetida(ws_orq):
    registro = RegistroFerramentas()
    # Tool que sempre falha
    @registro.ferramenta(nome="tool_falha", descricao="Falha", categoria="teste")
    def handler_falha(args, ctx):
        return {"ok": False, "codigo": "ERR-1", "mensagem": "Erro simulado"}

    provedor = MockProvedorRepetido("tool_falha")
    eventos = []
    emissor = Emissor("req-falha", sink=lambda evt: eventos.append(evt))

    orquestrador = OrquestradorV2(registro=registro, provedor=provedor, max_rodadas=100)
    res = orquestrador.executar(
        conversation_id="conv-falha",
        mensagem="Execute algo",
        workspace=ws_orq,
        emissor=emissor,
    )

    # Deve ter encerrado por falha repetida
    assert res["status"] == "erro"
    assert "repetida" in res["resumo"].lower() or "consecutiv" in res["resumo"].lower()

    # Evento agente.fim emitido com status erro
    evts_fim = [e for e in eventos if e["evento"] == "agente.fim"]
    assert len(evts_fim) == 1
    assert evts_fim[0]["dados"]["status"] == "erro"

    # Estado persistido em .agente/estado.json
    estado_disco = carregar_estado(ws_orq)
    assert estado_disco is not None
    assert estado_disco.status == "erro"


def test_orquestrador_com_plano_e_fim_concluido(ws_orq):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)
    provedor = MockProvedorPlano()
    eventos = []
    emissor = Emissor("req-ok", sink=lambda evt: eventos.append(evt))

    orquestrador = OrquestradorV2(registro=registro, provedor=provedor, max_rodadas=100)
    res = orquestrador.executar(
        conversation_id="conv-sucesso",
        mensagem="Planeje e execute",
        workspace=ws_orq,
        emissor=emissor,
    )

    assert res["status"] == "concluido"

    # Evento agente.fim com concluído
    evts_fim = [e for e in eventos if e["evento"] == "agente.fim"]
    assert len(evts_fim) == 1
    assert evts_fim[0]["dados"]["status"] == "concluido"

    # Estado em disco
    estado_disco = carregar_estado(ws_orq)
    assert estado_disco is not None
    assert estado_disco.status == "concluido"
    assert len(estado_disco.passos) == 2
