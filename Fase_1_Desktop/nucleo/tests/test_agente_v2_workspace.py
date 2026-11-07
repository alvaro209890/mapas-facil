import json
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from mapasfacil_nucleo.agente.aprovacao import GerenciadorAprovacao
from mapasfacil_nucleo.agente.registro import RegistroFerramentas
from mapasfacil_nucleo.agente.tools_workspace import registrar_tools_workspace
from mapasfacil_nucleo.protocolo import Emissor


@pytest.fixture
def ws_temp():
    temp_dir = tempfile.mkdtemp(prefix="mf_test_ws_")
    ws_path = Path(temp_dir)
    # Criar subpastas padrão do Mapas Fácil
    (ws_path / "Mapas").mkdir(parents=True)
    (ws_path / "SHP").mkdir(parents=True)
    (ws_path / "teste.txt").write_text("conteudo original", encoding="utf-8")
    yield ws_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_workspace_listar(ws_temp):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)

    ctx = {"workspace": ws_temp}
    res = registro.executar("workspace_listar", {"subpasta": ""}, ctx)

    assert res["ok"] is True
    itens = res["itens"]
    caminhos = [item["caminho"] for item in itens]
    assert "teste.txt" in caminhos
    assert "Mapas" in caminhos
    assert "SHP" in caminhos


def test_workspace_guard_bloqueia_path_traversal(ws_temp):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)

    ctx = {"workspace": ws_temp}
    res_fora = registro.executar("workspace_ler", {"caminho": "../fora.txt"}, ctx)
    assert res_fora["ok"] is False
    assert (
        "bloqueado" in res_fora["mensagem"].lower()
        or "não autorizado" in res_fora["mensagem"].lower()
        or "fora" in res_fora["mensagem"].lower()
        or "traversal" in res_fora["mensagem"].lower()
    )


def test_workspace_escrever_com_backup(ws_temp):
    registro = RegistroFerramentas()
    eventos = []
    emissor = Emissor("req-1", sink=lambda evt: eventos.append(evt))
    gerenciador_aprov = GerenciadorAprovacao(ws_padrao=ws_temp)
    registrar_tools_workspace(registro, gerenciador_aprovacao=gerenciador_aprov)

    ctx = {"workspace": ws_temp, "emissor": emissor}

    # 1. Criar novo arquivo (não existe previamente) -> grava sem exigir aprovação
    res_novo = registro.executar("workspace_escrever", {"caminho": "novo_arquivo.txt", "conteudo": "inédito"}, ctx)
    assert res_novo["ok"] is True
    assert (ws_temp / "novo_arquivo.txt").read_text(encoding="utf-8") == "inédito"

    # 2. Sobrescrever teste.txt (já existe) -> EXIGE aprovação prévia
    res_sobrescrita = registro.executar("workspace_escrever", {"caminho": "teste.txt", "conteudo": "novo conteudo"}, ctx)
    assert res_sobrescrita["ok"] is False
    assert res_sobrescrita.get("aguardando_aprovacao") is True
    assert "sobrescrever" in res_sobrescrita["acao"]

    # LLM não pode se auto-aprovar passando token em argumento
    res_fake = registro.executar(
        "workspace_escrever",
        {"caminho": "teste.txt", "conteudo": "novo conteudo", "token_aprovacao": "chute"},
        ctx,
    )
    assert res_fake["ok"] is False

    # Proprietário autoriza pelo canal seguro fora do modelo
    token = gerenciador_aprov.obter_token_pendente("sobrescrever", "teste.txt", ws_root=ws_temp)
    assert token is not None
    assert gerenciador_aprov.registrar_decisao(token, aprovado=True, ws_root=ws_temp) is True

    # Agora a sobrescrita executa e consome a decisão
    res_ok = registro.executar("workspace_escrever", {"caminho": "teste.txt", "conteudo": "novo conteudo"}, ctx)
    assert res_ok["ok"] is True
    assert (ws_temp / "teste.txt").read_text(encoding="utf-8") == "novo conteudo"

    # Verificar que backup sem colisão existe em .agente/backups
    backup_dir = ws_temp / ".agente" / "backups"
    assert backup_dir.exists()
    backups = list(backup_dir.glob("*teste.txt"))
    assert len(backups) >= 1
    assert backups[0].read_text(encoding="utf-8") == "conteudo original"

    # Tentar sobrescrever novamente sem nova aprovação -> EXIGE nova aprovação (single-use)
    res_rep = registro.executar("workspace_escrever", {"caminho": "teste.txt", "conteudo": "terceiro conteudo"}, ctx)
    assert res_rep["ok"] is False
    assert res_rep.get("aguardando_aprovacao") is True


def test_workspace_apagar_exige_aprovacao_llm_nao_pode_auto_conceder(ws_temp):
    registro = RegistroFerramentas()
    eventos = []
    emissor = Emissor("req-1", sink=lambda evt: eventos.append(evt))
    gerenciador_aprov = GerenciadorAprovacao(ws_padrao=ws_temp)
    registrar_tools_workspace(registro, gerenciador_aprovacao=gerenciador_aprov)

    ctx = {"workspace": ws_temp, "emissor": emissor}

    # Tentativa de apagar sem decisão aprovada
    res = registro.executar("workspace_apagar", {"caminho": "teste.txt"}, ctx)

    assert res["ok"] is False
    assert res.get("aguardando_aprovacao") is True
    assert "aprovação" in res["mensagem"].lower()
    # Token NUNCA pode ser devolvido na resposta da tool
    assert "token" not in res

    # O arquivo NÃO deve ter sido apagado
    assert (ws_temp / "teste.txt").exists()

    # Evento agente.aprovacao emitido SEM token
    evts_aprov = [e for e in eventos if e["evento"] == "agente.aprovacao"]
    assert len(evts_aprov) == 1
    assert evts_aprov[0]["dados"]["acao"] == "apagar"
    assert evts_aprov[0]["dados"]["caminho"] == "teste.txt"
    assert "token" not in evts_aprov[0]["dados"]

    # LLM tenta passar token falso/chutado no payload -> DEVE RECUSAR
    res_fake = registro.executar(
        "workspace_apagar",
        {"caminho": "teste.txt", "token_aprovacao": "token_inventado"},
        ctx,
    )
    assert res_fake["ok"] is False
    assert (ws_temp / "teste.txt").exists()

    # Servidor/Usuário concede aprovação via endpoint/canal confiável
    token_real = gerenciador_aprov.obter_token_pendente("apagar", "teste.txt", ws_root=ws_temp)
    assert token_real is not None
    assert gerenciador_aprov.registrar_decisao(token_real, aprovado=True, ws_root=ws_temp) is True

    # Agora a ferramenta consome a decisão aprovada e apaga com backup
    res_ok = registro.executar("workspace_apagar", {"caminho": "teste.txt"}, ctx)
    assert res_ok["ok"] is True
    assert not (ws_temp / "teste.txt").exists()

    # Backup sem colisão existe
    backup_dir = ws_temp / ".agente" / "backups"
    assert any("teste.txt" in f.name for f in backup_dir.iterdir())

    # Decisão já foi consumida uma vez: tentativa de reuso falha (single-use)
    (ws_temp / "teste.txt").write_text("outro arquivo", encoding="utf-8")
    res_reuso = registro.executar("workspace_apagar", {"caminho": "teste.txt"}, ctx)
    assert res_reuso["ok"] is False
    assert res_reuso.get("aguardando_aprovacao") is True


def test_workspace_guard_bloqueia_escapes_e_pastas_protegidas(ws_temp):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)
    ctx = {"workspace": ws_temp}

    # 1. Caminhos absolutos em qualquer plataforma
    assert registro.executar("workspace_ler", {"caminho": "/etc/passwd"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "C:/Windows/System32/cmd.exe"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "c:\\windows\\system.ini"}, ctx)["ok"] is False

    # 2. Path traversal com backslash e slash
    assert registro.executar("workspace_ler", {"caminho": "..\\..\\fora.txt"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "Mapas/../../fora.txt"}, ctx)["ok"] is False

    # 3. Pastas de controle interno e segurança
    assert registro.executar("workspace_ler", {"caminho": ".agente/memoria.md"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": ".servidor/aprovacoes/pedido.json"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": ".estado/checkpoint.json"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "chats.sqlite"}, ctx)["ok"] is False

    # 4. Versões Mapas/vNNN imutáveis
    (ws_temp / "Mapas" / "v001").mkdir(parents=True)
    (ws_temp / "Mapas" / "v001" / "mapa.pdf").write_text("v001 pdf", encoding="utf-8")
    # Versão é imutável, não ilegível: preview/QA leem, escrita continua negada.
    assert registro.executar("workspace_ler", {"caminho": "Mapas/v001/mapa.pdf"}, ctx)["ok"] is True
    assert (
        registro.executar(
            "workspace_escrever",
            {"caminho": "Mapas/v001/mapa.pdf", "conteudo": "adulterado"},
            ctx,
        )["ok"]
        is False
    )

    # 5. Arquivos de segredos
    assert registro.executar("workspace_ler", {"caminho": ".env"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "servidor.env"}, ctx)["ok"] is False
    assert registro.executar("workspace_ler", {"caminho": "segredos/chave.key"}, ctx)["ok"] is False

    # 6. Exclusão e movimentação de pastas estruturais e raiz
    assert registro.executar("workspace_apagar", {"caminho": ""}, ctx)["ok"] is False
    assert registro.executar("workspace_apagar", {"caminho": "."}, ctx)["ok"] is False
    assert registro.executar("workspace_apagar", {"caminho": "Mapas"}, ctx)["ok"] is False
    assert registro.executar("workspace_mover", {"origem": "Mapas", "destino": "Mapas_backup"}, ctx)["ok"] is False

    # 7. Leitura bounded no disco
    grande = ws_temp / "arquivo_grande.txt"
    grande.write_text("A" * 150_000, encoding="utf-8")
    # Teste no handler direto para verificar o teto de 100_000 lidos do disco
    handler_ler = registro.obter("workspace_ler").handler
    res_direto = handler_ler({"caminho": "arquivo_grande.txt"}, ctx)
    assert res_direto["ok"] is True
    assert res_direto["truncado"] is True
    assert len(res_direto["conteudo"]) == 100_000
    assert res_direto["tamanho_bytes"] == 150_000

    # Execução pelo registro com truncamento de resposta para a LLM
    res_ler = registro.executar("workspace_ler", {"caminho": "arquivo_grande.txt"}, ctx)
    assert res_ler["ok"] is True
    assert res_ler["truncado"] is True


def test_workspace_estat_e_mover(ws_temp):
    registro = RegistroFerramentas()
    registrar_tools_workspace(registro)

    ctx = {"workspace": ws_temp}
    res_estat = registro.executar("workspace_estat", {"caminho": "teste.txt"}, ctx)
    assert res_estat["ok"] is True
    assert res_estat["existe"] is True
    assert res_estat["eh_arquivo"] is True
    assert res_estat["tamanho_bytes"] > 0

    res_mover = registro.executar("workspace_mover", {"origem": "teste.txt", "destino": "Mapas/teste_movido.txt"}, ctx)
    assert res_mover["ok"] is True
    assert not (ws_temp / "teste.txt").exists()
    assert (ws_temp / "Mapas" / "teste_movido.txt").exists()
