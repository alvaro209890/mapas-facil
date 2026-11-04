"""Histórico para a web e versões do servidor (caso real do teste_22, 04/11/2026).

- `chat.carregar_anteriores` agora devolve as tools de cada mensagem: um turno que só chamou
  `perguntar` tem texto vazio, e sem as tools a pergunta sumia ao recarregar a página;
- cada `gerar_mapa` no servidor abre a próxima `Mapas/vNNN` (antes caía sempre em `v001` e o
  mapa novo apagava o anterior);
- o nome do arquivo segue o ano do título (um mapa de 2008 saía como `…_2026.pdf`).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mapasfacil_nucleo.agente import tools
from mapasfacil_nucleo.conversas import servico as conversas_servico
from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pasta = tmp_path / "chats"
    pasta.mkdir()
    monkeypatch.setenv("MAPASFACIL_CHATS_DIR", str(pasta))
    conversas_servico.configurar_diretorio(pasta)
    yield RepositorioConversas(pasta)
    conversas_servico.configurar_diretorio(None)


def test_carregar_anteriores_traz_as_tools_de_cada_mensagem(repo):
    cid = repo.criar_conversa()["conversation_id"]
    repo.adicionar_mensagem(cid, papel="usuario", conteudo="oi")
    resposta = repo.adicionar_mensagem(cid, papel="assistente", conteudo="")
    repo.adicionar_tool_trace(
        cid,
        message_id=resposta["message_id"],
        tool="perguntar",
        args_resumo='{"pergunta": "Qual modelo?", "opcoes": [{"id": "a", "rotulo": "Dinâmica"}]}',
        ok=True,
    )

    pagina = repo.carregar_anteriores(cid, antes_de_seq=10**9, limite=50)
    mensagens = pagina["mensagens"]
    assert [m["papel"] for m in mensagens] == ["usuario", "assistente"]
    assert mensagens[0]["tool_traces"] == []
    assert [t["tool"] for t in mensagens[1]["tool_traces"]] == ["perguntar"]
    assert "Qual modelo?" in mensagens[1]["tool_traces"][0]["args_resumo"]


def _estado(raiz: Path) -> SimpleNamespace:
    return SimpleNamespace(guard=SimpleNamespace(raiz=raiz))


def test_proxima_pasta_de_versao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MAPASFACIL_VERSAO_SAIDA", raising=False)
    assert tools._versao_da_geracao(_estado(tmp_path)) == 1
    (tmp_path / "Mapas" / "v001").mkdir(parents=True)
    (tmp_path / "Mapas" / "v003").mkdir()
    (tmp_path / "Mapas" / ".preview").mkdir()
    (tmp_path / "Mapas" / "vXX").mkdir()
    assert tools._versao_da_geracao(_estado(tmp_path)) == 4


def test_variavel_do_servidor_ainda_manda(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    (tmp_path / "Mapas" / "v001").mkdir(parents=True)
    monkeypatch.setenv("MAPASFACIL_VERSAO_SAIDA", "7")
    assert tools._versao_da_geracao(_estado(tmp_path)) == 7


@pytest.mark.parametrize(
    ("nome", "titulo", "esperado"),
    [
        ("Dinamica_de_uso_do_solo_2026", "DINÂMICA DE USO DO SOLO - 2008", "Dinamica_de_uso_do_solo_2008"),
        ("Dinamica_de_uso_do_solo_2026", "Dinâmica de uso do solo", "Dinamica_de_uso_do_solo_2026"),
        ("Mapa", "Mapa de 2008", "Mapa"),
        ("APP_2024", "Comparativo 2008 × 2024", "APP_2024"),
    ],
)
def test_nome_do_arquivo_segue_o_ano_do_titulo(nome, titulo, esperado):
    spec = {"titulo": titulo, "saida": {"pasta": "Mapas/v001", "nome_base": nome}}
    tools._alinhar_ano_do_nome(spec)
    assert spec["saida"]["nome_base"] == esperado
