"""Testes da integração real do Agente V2 ao chat público (NDJSON servico.enviar).

Testa através de servico.enviar com provedor Fake, tools V2 reais (workspace_listar, plano),
persistência de histórico no banco de conversas, eventos agente.* e estado em .agente/estado.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest

from mapasfacil_nucleo import sessao
from mapasfacil_nucleo.agente import limites
from mapasfacil_nucleo.agente import servico as agente_servico
from mapasfacil_nucleo.agente.estado import carregar_estado
from mapasfacil_nucleo.agente.fake import FakeProvedor, PassoFake, tool_call
from mapasfacil_nucleo.agente.orquestrador import configurar_provedor
from mapasfacil_nucleo.agente.provedor import DeltaStream
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import Emissor
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm


@pytest.fixture
def ambiente_chat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path]]:
    """Configura ambiente isolado com pasta de conversas e pasta de workspace."""
    pasta_chats = tmp_path / "chats"
    pasta_chats.mkdir(parents=True, exist_ok=True)
    pasta_ws = tmp_path / "workspace"
    pasta_ws.mkdir(parents=True, exist_ok=True)

    # Cria shapefile no workspace para tool listar
    shp_dir = pasta_ws / "SHP"
    escrever_shapefile_quadrado_utm(shp_dir / "ATP.shp", nome="Fazenda Real", lado_m=3000)

    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta_chats))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    conversas_servico.configurar_diretorio(pasta_chats)
    workspace_servico.abrir(str(pasta_ws))

    # Simula sessão conectada
    sessao.definir(estado="conectado", conta_id="conta-teste-v2")
    configurar_provedor(None)

    yield pasta_chats, pasta_ws

    configurar_provedor(None)
    conversas_servico.configurar_diretorio(None)
    workspace_servico.fechar()
    sessao.resetar()


def _criar_conversa(pasta_chats: Path, ws_path: Path) -> str:
    repo = RepositorioConversas(pasta_chats)
    try:
        c = repo.criar_conversa(workspace=str(ws_path))
        return c["conversation_id"]
    finally:
        repo.fechar()


def test_servico_enviar_executa_tool_v2_workspace_listar_e_persiste_estado(ambiente_chat):
    """Tracer bullet: servico.enviar chama tool V2 real workspace_listar, persiste histórico e estado.json."""
    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    # FakeProvedor chama a tool V2 'workspace_listar' na 1ª rodada e conclui na 2ª
    passos = [
        PassoFake(
            texto="Vou listar os arquivos do projeto.",
            tool_calls=[tool_call("workspace_listar", {"pasta": "SHP"}, "call_ws_1")],
        ),
        PassoFake(texto="Encontrei os shapefiles no diretório SHP."),
    ]
    configurar_provedor(FakeProvedor(passos))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("req-teste-v2-1", sink=lambda evt: eventos.append(evt))

    res = agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Quais arquivos existem na pasta SHP?",
            "workspace": str(pasta_ws),
        },
        emissor=emissor,
    )

    # 1. Verifica retorno de servico.enviar
    assert "Encontrei os shapefiles" in res["texto"]
    assert "workspace_listar" in res["tools_usadas"]

    # 2. Verifica histórico gravado no banco de conversas SQLite
    repo = RepositorioConversas(pasta_chats)
    try:
        dados_conv = repo.abrir_conversa(cid, limite=20)
        mensagens = dados_conv["mensagens"]
        assert len(mensagens) == 2  # 1 usuario + 1 assistente
        msg_user = mensagens[0]
        assert msg_user["papel"] == "usuario"
        assert msg_user["conteudo"] == "Quais arquivos existem na pasta SHP?"

        msg_asst = mensagens[1]
        assert msg_asst["papel"] == "assistente"
        assert "Encontrei os shapefiles" in msg_asst["conteudo"]
        # Traces devem registrar a tool real workspace_listar
        traces = msg_asst["tool_traces"]
        assert len(traces) == 1
        assert traces[0]["tool"] == "workspace_listar"
        assert traces[0]["ok"] is True
    finally:
        repo.fechar()

    # 3. Verifica eventos emitidos
    evts_fim = [e for e in eventos if e.get("evento") == "agente.fim"]
    assert len(evts_fim) == 1, f"Deve emitir exatamente um evento agente.fim: {eventos}"
    assert evts_fim[0]["dados"]["status"] == "concluido"

    # 4. Verifica persistência do estado em .agente/estado.json
    estado_disco = carregar_estado(pasta_ws)
    assert estado_disco is not None, "Arquivo .agente/estado.json deve existir"
    assert estado_disco.conversation_id == cid
    assert estado_disco.status == "concluido"
    assert "Encontrei os shapefiles" in estado_disco.resumo


def test_servico_enviar_plano_e_etapas_com_bloqueio_de_edicao_aprovacao(ambiente_chat):
    """Testa plano_definir e plano_atualizar via servico.enviar; garante que plano não edita aprovação."""
    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    passos = [
        PassoFake(
            texto="Definindo o plano.",
            tool_calls=[
                tool_call(
                    "plano_definir",
                    {
                        "passos": [
                            {"id": "s1", "titulo": "Inspecionar pasta", "status": "pendente"},
                            {"id": "s2", "titulo": "Gerar mapa temático", "status": "pendente"},
                        ]
                    },
                    "c_p1",
                )
            ],
        ),
        PassoFake(
            texto="Atualizando primeiro passo.",
            tool_calls=[
                tool_call(
                    "plano_atualizar",
                    {"passo_id": "s1", "status": "concluido", "resumo": "Arquivos inspecionados"},
                    "c_p2",
                )
            ],
        ),
        PassoFake(texto="Plano atualizado com sucesso."),
    ]
    configurar_provedor(FakeProvedor(passos))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("req-plano-v2", sink=lambda evt: eventos.append(evt))

    res = agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Crie um plano e execute a primeira etapa.",
            "workspace": str(pasta_ws),
        },
        emissor=emissor,
    )

    assert "Plano atualizado com sucesso" in res["texto"]

    # Verifica eventos do plano emitidos
    evts_plano = [e for e in eventos if e.get("evento") == "agente.plano"]
    assert len(evts_plano) >= 1
    assert len(evts_plano[0]["dados"]["passos"]) == 2

    evts_passo = [e for e in eventos if e.get("evento") == "agente.passo"]
    assert len(evts_passo) >= 1
    assert evts_passo[0]["dados"]["id"] == "s1"
    assert evts_passo[0]["dados"]["status"] == "concluido"

    # Verifica persistência no estado.json
    estado_disco = carregar_estado(pasta_ws)
    assert estado_disco is not None
    assert len(estado_disco.passos) == 2
    assert estado_disco.passos[0]["id"] == "s1"
    assert estado_disco.passos[0]["status"] == "concluido"
    assert estado_disco.passos[0].get("resumo") == "Arquivos inspecionados"
    assert estado_disco.passos[1]["id"] == "s2"
    assert estado_disco.passos[1]["status"] == "pendente"

    # Plano do modelo NÃO pode editar estado de aprovação
    assert estado_disco.aprovacao is None


def test_servico_enviar_parada_em_falha_repetida(ambiente_chat):
    """Garante que servico.enviar interrompe loop após falhas consecutivas da mesma tool."""
    from mapasfacil_nucleo.agente.registro import registro_padrao

    # Registra ferramenta que sempre falha
    @registro_padrao.ferramenta(
        nome="tool_quebrei",
        descricao="Simula falha repetida para verificação de contenção",
        categoria="teste",
    )
    def _tool_quebrei(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "codigo": "ERR-99", "mensagem": "Erro proposital de teste"}

    try:
        pasta_chats, pasta_ws = ambiente_chat
        cid = _criar_conversa(pasta_chats, pasta_ws)

        # FakeProvedor tenta chamar 10 vezes a tool que falha
        passos = [
            PassoFake(tool_calls=[tool_call("tool_quebrei", {}, f"call_err_{i}")])
            for i in range(10)
        ]
        configurar_provedor(FakeProvedor(passos))

        eventos: list[dict[str, Any]] = []
        emissor = Emissor("req-repetida", sink=lambda evt: eventos.append(evt))

        with pytest.raises(ErroNucleo) as exc_info:
            agente_servico.enviar(
                {
                    "conversation_id": cid,
                    "mensagem": "Execute a tool problemática.",
                    "workspace": str(pasta_ws),
                    "limite_falhas_consecutivas": 3,
                },
                emissor=emissor,
            )

        assert exc_info.value.codigo == "IA-035"
        assert "falhas consecutivas" in exc_info.value.mensagem

        # Evento agente.fim deve ter sido emitido com erro
        evts_fim = [e for e in eventos if e.get("evento") == "agente.fim"]
        assert len(evts_fim) == 1
        assert evts_fim[0]["dados"]["status"] == "erro"
        assert "tool_quebrei" in evts_fim[0]["dados"]["resumo"]

        # Estado em disco persistido com erro
        estado_disco = carregar_estado(pasta_ws)
        assert estado_disco is not None
        assert estado_disco.status == "erro"
        assert "tool_quebrei" in estado_disco.resumo
    finally:
        registro_padrao._tools.pop("tool_quebrei", None)


def test_servico_enviar_solicitacao_aprovacao_sem_vazar_token(ambiente_chat):
    """Garante que ferramentas que exigem aprovação encerram o turno e não vazam tokens criptográficos."""
    from mapasfacil_nucleo.agente.aprovacao import gerenciador_aprovacao_padrao
    from mapasfacil_nucleo.agente.registro import registro_padrao

    # Registra tool que pede aprovação para excluir arquivo
    @registro_padrao.ferramenta(
        nome="tool_deletar_critico",
        descricao="Solicita autorização prévia para remover arquivo crítico",
        categoria="workspace",
        requer_aprovacao=True,
    )
    def _tool_deletar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        return gerenciador_aprovacao_padrao.solicitar(
            acao="excluir_arquivo",
            caminho="SHP/ATP.shp",
            motivo="Remover perímetro para reiniciar",
            ws_root=ctx.get("workspace"),
            emissor=ctx.get("emissor"),
        )

    try:
        pasta_chats, pasta_ws = ambiente_chat
        cid = _criar_conversa(pasta_chats, pasta_ws)

        passos = [
            PassoFake(
                texto="Preciso deletar o arquivo para reiniciar.",
                tool_calls=[tool_call("tool_deletar_critico", {}, "c_del_1")],
            )
        ]
        configurar_provedor(FakeProvedor(passos))

        eventos: list[dict[str, Any]] = []
        emissor = Emissor("req-aprov", sink=lambda evt: eventos.append(evt))

        res = agente_servico.enviar(
            {
                "conversation_id": cid,
                "mensagem": "Delete o arquivo crítico.",
                "workspace": str(pasta_ws),
            },
            emissor=emissor,
        )

        # 1. Retorno deve indicar aguardando_aprovacao
        assert res.get("status") == "aguardando_aprovacao"
        assert "aprovacao" in res
        assert res["aprovacao"]["acao"] == "excluir_arquivo"
        assert "token" not in res["aprovacao"], "Token seguro não pode vazar no retorno"

        # 2. Eventos emitidos
        evts_aprov = [e for e in eventos if e.get("evento") == "agente.aprovacao"]
        assert len(evts_aprov) == 1
        assert evts_aprov[0]["dados"]["acao"] == "excluir_arquivo"
        assert "token" not in evts_aprov[0]["dados"], "Token não pode ir no evento"

        evts_fim = [e for e in eventos if e.get("evento") == "agente.fim"]
        assert len(evts_fim) == 1
        assert evts_fim[0]["dados"]["status"] == "aguardando_aprovacao"

        # 3. Estado persistido em .agente/estado.json não deve conter segredo/token
        estado_disco = carregar_estado(pasta_ws)
        assert estado_disco is not None
        assert estado_disco.status == "aguardando_aprovacao"
        assert estado_disco.aprovacao is not None
        assert estado_disco.aprovacao["acao"] == "excluir_arquivo"
        assert "token" not in estado_disco.aprovacao

        arquivo_json = (pasta_ws / ".agente" / "estado.json").read_text(encoding="utf-8")
        assert "token" not in arquivo_json.lower()
    finally:
        registro_padrao._tools.pop("tool_deletar_critico", None)


def test_servico_cancelar_emite_agente_fim_e_salva_estado_cancelado(ambiente_chat):
    """Garante que cancelamento via servico.cancelar emite agente.fim e salva estado cancelado."""
    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    # Simula provedor que cancela ao receber a primeira requisição
    class ProvedorComCancelamento(FakeProvedor):
        def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
            # Solicita cancelamento durante o streaming
            agente_servico.cancelar({"conversation_id": cid})
            yield DeltaStream(texto="Iniciando...")

    configurar_provedor(ProvedorComCancelamento([PassoFake(texto="teste")]))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("req-cancel", sink=lambda evt: eventos.append(evt))

    res = agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Faça algo cancelável.",
            "workspace": str(pasta_ws),
        },
        emissor=emissor,
    )

    assert res.get("cancelada") is True

    # Evento agente.fim emitido com status cancelado
    evts_fim = [e for e in eventos if e.get("evento") == "agente.fim"]
    assert len(evts_fim) == 1
    assert evts_fim[0]["dados"]["status"] == "cancelado"

    # Estado em disco salvo como cancelado
    estado_disco = carregar_estado(pasta_ws)
    assert estado_disco is not None
    assert estado_disco.status == "cancelado"


def test_tool_perguntar_emite_agente_fim_e_atualiza_estado(ambiente_chat):
    """Garante que a ferramenta perguntar (D40) encerra turno com agente.fim e status coerente."""
    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    passos = [
        PassoFake(
            texto="Preciso saber qual o ano da Dinâmica.",
            tool_calls=[
                tool_call(
                    "perguntar",
                    {
                        "pergunta": "Qual o ano de referência da análise de dinâmica?",
                        "opcoes": [
                            {"id": "2020", "rotulo": "2020"},
                            {"id": "2024", "rotulo": "2024"},
                        ],
                    },
                    "c_perg_1",
                )
            ],
        )
    ]
    configurar_provedor(FakeProvedor(passos))

    eventos: list[dict[str, Any]] = []
    emissor = Emissor("req-perg", sink=lambda evt: eventos.append(evt))

    res = agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Faça a análise da Dinâmica.",
            "workspace": str(pasta_ws),
        },
        emissor=emissor,
    )

    assert "pergunta" in res
    assert res["pergunta"]["pergunta"] == "Qual o ano de referência da análise de dinâmica?"

    evts_fim = [e for e in eventos if e.get("evento") == "agente.fim"]
    assert len(evts_fim) == 1
    assert evts_fim[0]["dados"]["status"] == "aguardando_pergunta"

    estado_disco = carregar_estado(pasta_ws)
    assert estado_disco is not None
    assert estado_disco.status == "aguardando_pergunta"


def test_wire_role_nunca_e_usuario_deve_ser_user(ambiente_chat):
    """Garante que no wire para a LLM, mensagens de usuário sempre têm role 'user', nunca 'usuario'."""
    from mapasfacil_nucleo.agente.orquestrador_v2 import OrquestradorV2
    from mapasfacil_nucleo.agente.registro import registro_padrao

    mensagens_recebidas: list[list[Any]] = []

    class ProvedorEspiao(FakeProvedor):
        def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
            mensagens_recebidas.append(list(mensagens))
            yield DeltaStream(texto="Resposta do modelo.")

    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    provedor = ProvedorEspiao([])
    configurar_provedor(provedor)

    # 1. Teste via servico.enviar
    agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Olá, verifique os papéis das mensagens.",
            "workspace": str(pasta_ws),
        },
        emissor=None,
    )

    assert len(mensagens_recebidas) >= 1
    for msg in mensagens_recebidas[0]:
        assert msg.papel != "usuario", f"Mensagem com papel 'usuario' proibida no wire: {msg}"
        assert msg.papel in {"system", "user", "assistant", "tool"}, f"Papel inesperado: {msg.papel}"

    # 2. Teste via OrquestradorV2 diretamente
    mensagens_v2: list[list[Any]] = []

    class ProvedorEspiaoV2(FakeProvedor):
        def enviar_stream(self, mensagens, tools=None, max_tokens=8000, modelo=None):
            mensagens_v2.append(list(mensagens))
            yield DeltaStream(texto="Resposta V2.")

    orq_v2 = OrquestradorV2(registro=registro_padrao, provedor=ProvedorEspiaoV2([]))
    orq_v2.executar(
        conversation_id="conv-wire-v2",
        mensagem="Mensagem V2 teste.",
        workspace=pasta_ws,
    )

    assert len(mensagens_v2) >= 1
    for msg in mensagens_v2[0]:
        assert msg.papel != "usuario", f"OrquestradorV2 enviou 'usuario' no wire: {msg}"
        assert msg.papel in {"system", "user", "assistant", "tool"}, f"Papel inesperado: {msg.papel}"


def test_servico_enviar_suporta_rodadas_configuraveis_alem_de_24(ambiente_chat):
    """Garante que chat.enviar permite 100 rodadas configuráveis sem travar em 24."""
    pasta_chats, pasta_ws = ambiente_chat
    cid = _criar_conversa(pasta_chats, pasta_ws)

    # 26 chamadas a estado_do_projeto (ultrapassa as 24 antigas)
    passos = [
        PassoFake(tool_calls=[tool_call("estado_do_projeto", {}, f"c{i}")])
        for i in range(26)
    ] + [PassoFake(texto="Concluí 26 rodadas com sucesso.")]

    configurar_provedor(FakeProvedor(passos))

    res = agente_servico.enviar(
        {
            "conversation_id": cid,
            "mensagem": "Execute 26 rodadas.",
            "workspace": str(pasta_ws),
            "max_rodadas": 50,
        },
        emissor=None,
    )

    assert res["rodadas_tool"] == 26
    assert "Concluí 26 rodadas" in res["texto"]


def test_confirmar_schemas_legado_e_v2_sem_duplicacao_e_reload_estado(ambiente_chat):
    """Garante catálogo unificado de schemas legados e V2 e reload íntegro do estado."""
    from mapasfacil_nucleo.agente.tools import nomes_tools, schemas_openai

    todos_nomes = nomes_tools()
    schemas = schemas_openai()

    nomes_schemas = [s["function"]["name"] for s in schemas]

    # Verifica ausência de duplicatas
    assert len(nomes_schemas) == len(set(nomes_schemas)), "Schemas não podem conter ferramentas duplicadas"

    # Confirma presença de ferramentas legadas essenciais
    assert "criar_mapa" in nomes_schemas
    assert "perguntar" in nomes_schemas
    assert "listar_arquivos" in nomes_schemas

    # Confirma presença de ferramentas V2 essenciais
    assert "workspace_listar" in nomes_schemas
    assert "workspace_ler" in nomes_schemas
    assert "plano_definir" in nomes_schemas
    assert "plano_atualizar" in nomes_schemas

    # Confirma persistência e reload íntegro de estado
    from mapasfacil_nucleo.agente.estado import EstadoAgente, salvar_estado

    _, pasta_ws = ambiente_chat
    estado_inicial = EstadoAgente(
        conversation_id="conv-reload-teste",
        status="em_andamento",
        passos=[{"id": "p1", "titulo": "Passo 1", "status": "pendente"}],
        arquivos=[{"caminho": "SHP/ATP.shp", "acao": "leitura"}],
        previews=[{"caminho": "Mapas/previews/1.png", "pagina": 1}],
        aprovacao={"acao": "exportar", "caminho": "Mapas/final.pdf", "motivo": "Entrega"},
    )
    salvar_estado(pasta_ws, estado_inicial)

    estado = carregar_estado(pasta_ws)
    assert estado is not None
    # Serialização e deserialização funcionam sem perda
    dados = estado.para_dict()
    assert "passos" in dados
    assert len(dados["passos"]) == 1
    assert "arquivos" in dados
    assert "previews" in dados
    assert "aprovacao" in dados
    assert dados["aprovacao"]["acao"] == "exportar"
    assert "status" in dados
    assert dados["status"] == "em_andamento"
    # Sem tokens
    assert "token" not in json.dumps(dados).lower()
