"""Testes de aceitação do W5-22 / D41 — Abertura do projeto com a leitura do ZIP.

Critérios de aceite:
- teste com imovel_ficticio.zip (abertura completa);
- zip sem hidrografia (opção marcada como "falta");
- zip em SAD69 (aviso de conversão);
- 9Router fora (abertura determinística);
- reload sem abertura duplicada.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from mapasfacil_servidor.chat.abertura import (
    extrair_dados_abertura,
    montar_pergunta_galeria,
    montar_texto_abertura,
    disparar_abertura_projeto,
)
from mapasfacil_servidor.db import Banco
from mapasfacil_servidor.eventos.sse import Hub


class FakeWorker:
    def __init__(self):
        self.chamadas = []
        self.falhar_chat = False

    async def chamar(self, metodo: str, params: dict[str, Any], ao_evento=None) -> dict[str, Any]:
        self.chamadas.append((metodo, params))
        if metodo == "galeria.listar":
            return {
                "modelos": [
                    {"id": "dinamica_2026_retrato", "titulo": "Dinâmica 2026", "status": "pronto"},
                    {"id": "analise_hidro", "titulo": "Mapa de Hidrografia", "status": "indisponivel", "motivo": "hidrografia"},
                ]
            }
        if metodo == "chat.criar_conversa":
            return {"conversation_id": "conv_fake_1"}
        if metodo == "chat.enviar":
            if self.falhar_chat:
                raise RuntimeError("9Router connection timeout / 502 Bad Gateway")
            if ao_evento is not None and getattr(self, "falar", False):
                await ao_evento({"evento": "chat.delta", "dados": {"texto": "Olá! Li o pacote."}})
            return {"message_id": "msg_llm_1", "seq": 1, "texto": ""}
        if metodo == "chat.gravar_mensagem":
            return {"message_id": "msg_gravada_1", "seq": 1}
        if metodo == "perguntar":
            return {"ok": True, "pergunta_id": "p_fake"}
        return {}


class FakePool:
    def __init__(self, worker: FakeWorker):
        self.worker = worker

    async def obter(self, projeto_id: str):
        return self.worker


@pytest.fixture
def banco_teste(tmp_path: Path):
    db_path = tmp_path / "teste.sqlite"
    banco = Banco(db_path)
    banco.migrar()
    con = banco.conectar()
    # Cria usuário e projeto fictícios
    con.execute(
        "INSERT INTO usuarios (id, email, senha_hash, nome, papel, criado_em) "
        "VALUES ('u1', 'u@test.com', 'hash', 'Usuario', 'usuario', datetime('now'))"
    )
    con.execute(
        "INSERT INTO projetos (id, usuario_id, nome, estado, folha_formato, folha_orientacao, criado_em, atualizado_em) "
        "VALUES ('p1', 'u1', 'Projeto Teste', 'pronto', 'A4', 'retrato', datetime('now'), datetime('now'))"
    )
    con.execute(
        "INSERT INTO importacoes (id, projeto_id, upload_id, estado, criada_em) "
        "VALUES ('imp1', 'p1', 'up1', 'pronto', datetime('now'))"
    )
    con.close()
    return banco


def test_extrair_dados_abertura_padrao():
    resumo = {
        "imovel": {"nome": "Fazenda Harmonia", "area_ha": 1234.5678, "municipio": "Querência", "uf": "MT"},
        "shapefiles": [
            {"papel": "ATP", "area_ha": 1234.5678, "datum": "SIRGAS 2000"},
            {"papel": "AVN", "area_ha": 450.0},
        ],
        "bbox": [600000, 8300000, 605000, 8305000],
    }
    dados = extrair_dados_abertura(resumo)
    assert dados["nome_imovel"] == "Fazenda Harmonia"
    assert dados["area_ha"] == 1234.5678
    assert dados["municipio_uf"] == "Querência - MT"
    assert dados["veio_sad69"] is False
    assert "Perímetro do imóvel" in dados["camadas_encontradas"]
    assert "Vegetação nativa" in dados["camadas_encontradas"]
    assert dados["sugestao_folha"] == "A4 retrato"


def test_zip_em_sad69_gera_aviso_conversao():
    resumo = {
        "imovel": {"nome": "Lote SAD69", "area_ha": 500.0, "municipio": "Querência", "uf": "MT"},
        "shapefiles": [
            {"papel": "ATP", "area_ha": 500.0, "datum": "SAD69", "epsg": 29182},
        ],
    }
    dados = extrair_dados_abertura(resumo)
    assert dados["veio_sad69"] is True
    texto = montar_texto_abertura(dados)
    assert "convertido de SAD69 para SIRGAS 2000" in texto


def test_zip_sem_hidrografia_marca_falta_na_galeria():
    modelos = [
        {"id": "dinamica", "titulo": "Dinâmica do Uso", "status": "pronto"},
        {"id": "hidro", "titulo": "Mapa Hidrográfico", "status": "indisponivel", "motivo": "hidrografia"},
    ]
    pergunta = montar_pergunta_galeria(modelos)
    assert pergunta["multipla"] is True
    assert len(pergunta["opcoes"]) == 2

    # Opção pronta
    op_din = next(op for op in pergunta["opcoes"] if op["id"] == "dinamica")
    assert "(pronto)" in op_din["rotulo"]

    # Opção com falta de hidrografia
    op_hidro = next(op for op in pergunta["opcoes"] if op["id"] == "hidro")
    assert "falta: hidrografia" in op_hidro["rotulo"]


@pytest.mark.anyio
async def test_abertura_deterministica_quando_9router_fora(banco_teste):
    """Critério: se o 9Router estiver fora/falhar, gera abertura determinística sem LLM."""
    worker = FakeWorker()
    worker.falhar_chat = True  # Simula 9Router offline
    pool = FakePool(worker)
    hub = Hub()
    eventos_capturados = []
    fila = hub.assinar("p1")

    resumo = {
        "imovel": {"nome": "Fazenda Fictícia", "area_ha": 100.0, "municipio": "Querência", "uf": "MT"},
        "shapefiles": [
            {"papel": "ATP", "area_ha": 100.0, "datum": "SIRGAS 2000", "id_local": "ATP"},
        ],
        "bbox": [600000, 8300000, 601000, 8301000],
    }

    await disparar_abertura_projeto(
        banco=banco_teste,
        pool=pool,
        hub=hub,
        projeto_id="p1",
        importacao_id="imp1",
        resumo=resumo,
    )

    # Plano B não chama método bloqueado na allowlist (`chat.gravar_mensagem`).
    chamadas_metodos = [m[0] for m in worker.chamadas]
    assert "chat.gravar_mensagem" not in chamadas_metodos

    # Verificou emissão dos eventos no SSE
    eventos_capturados = []
    while not fila.empty():
        eventos_capturados.append(fila.get_nowait())
    nomes_eventos = [e["evento"] for e in eventos_capturados]
    assert "viewport.foco" in nomes_eventos
    assert "camada.renderizada" in nomes_eventos
    # Vocabulário que a tela entende: `chat.delta` (não `chat.chunk`/`chat.fim`).
    assert "chat.delta" in nomes_eventos
    assert "chat.pergunta" in nomes_eventos


@pytest.mark.anyio
async def test_abertura_com_raiz_grava_no_log_com_seq_e_repassa_eventos_do_turno(banco_teste, tmp_path):
    """Com `raiz`, os eventos ganham `seq` (senão o SSE ao vivo os descarta) e o turno da IA
    chega na tela pelo `ao_evento`; o prompt vai marcado como origem sistema."""
    from mapasfacil_servidor.chat.abertura import PREFIXO_SISTEMA
    from mapasfacil_servidor.eventos.log import LogEventos

    worker = FakeWorker()
    worker.falar = True
    hub = Hub()
    resumo = {"shapefiles": [{"papel": "ATP", "area_ha": 100.0, "id_local": "ATP"}]}
    await disparar_abertura_projeto(
        banco=banco_teste,
        pool=FakePool(worker),
        hub=hub,
        projeto_id="p1",
        importacao_id="imp1",
        resumo=resumo,
        raiz=tmp_path,
    )
    gravados = LogEventos(tmp_path).ler_desde(0)
    nomes = [e["evento"] for e in gravados]
    assert all(int(e["seq"]) > 0 for e in gravados)
    assert "chat.delta" in nomes and "nucleo.res" in nomes
    delta = next(e for e in gravados if e["evento"] == "chat.delta")
    assert delta["dados"]["texto"] == "Olá! Li o pacote."
    enviado = next(p for m, p in worker.chamadas if m == "chat.enviar")
    assert enviado["mensagem"].startswith(PREFIXO_SISTEMA)


@pytest.mark.anyio
async def test_reload_sem_abertura_duplicada(banco_teste):
    """Critério: recarregar a página ou reexecutar não duplica a abertura."""
    worker = FakeWorker()
    worker.falhar_chat = True
    pool = FakePool(worker)
    hub = Hub()
    eventos_capturados = []
    fila = hub.assinar("p1")

    resumo = {
        "imovel": {"nome": "Fazenda Fictícia", "area_ha": 100.0},
        "shapefiles": [{"papel": "ATP", "area_ha": 100.0, "id_local": "ATP"}],
    }

    # 1ª execução
    await disparar_abertura_projeto(
        banco=banco_teste,
        pool=pool,
        hub=hub,
        projeto_id="p1",
        importacao_id="imp1",
        resumo=resumo,
    )
    eventos_capturados = []
    while not fila.empty():
        eventos_capturados.append(fila.get_nowait())
    qtd_eventos_rodada_1 = len(eventos_capturados)
    assert qtd_eventos_rodada_1 > 0

    # 2ª execução (simula reload/reexecução com a mesma importação)
    await disparar_abertura_projeto(
        banco=banco_teste,
        pool=pool,
        hub=hub,
        projeto_id="p1",
        importacao_id="imp1",
        resumo=resumo,
    )
    # Nenhum evento novo deve ser emitido
    novos_eventos = []
    while not fila.empty():
        novos_eventos.append(fila.get_nowait())
    assert len(novos_eventos) == 0


def test_opcao_usa_o_nome_e_o_subtitulo_da_galeria():
    """`galeria.listar` devolve `nome`; o botão mostrava o id técnico do modelo."""
    modelos = [
        {
            "id": "dinamica_2008_spot_quadro",
            "nome": "Dinâmica 2008 (SPOT)",
            "subtitulo": "Imagem SPOT 2008 e quadro de áreas",
            "status": "pronto",
        },
        {"id": "uc_paisagem", "nome": "Unidades de Conservação", "status": "pronto"},
    ]
    pergunta = montar_pergunta_galeria(modelos)
    op = next(o for o in pergunta["opcoes"] if o["id"] == "dinamica_2008_spot_quadro")
    assert op["rotulo"] == "Dinâmica 2008 (SPOT) (pronto)"
    assert op["descricao"] == "Imagem SPOT 2008 e quadro de áreas"
