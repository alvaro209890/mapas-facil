"""Worker que sobe de novo abre a pasta do projeto (caso real do teste_22, 04/11/2026).

O núcleo guarda o workspace só em memória. Depois de um restart do app (ou da varredura de
ociosos), o worker novo respondia "Nenhuma pasta conectada" a toda tool do chat e o agente
voltava sempre para a mesma pergunta.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mapasfacil_servidor.ponte import worker as worker_mod
from mapasfacil_servidor.ponte.pool import Pool


def _pool(tmp_path: Path) -> Pool:
    roteiro = tmp_path / "roteiro.ndjson"
    roteiro.write_text(
        '{"metodo": "ping", "resultado": {}}\n'
        '{"metodo": "workspace.abrir", "resultado": {"workspace": {}}}\n'
        '{"metodo": "chat.listar_conversas", "resultado": {"itens": []}}\n',
        encoding="utf-8",
    )
    cmd = [sys.executable, "-m", "mapasfacil_servidor.ponte.fake_nucleo", "--roteiro", str(roteiro)]
    return Pool(raiz_projetos=tmp_path / "projetos", cmd_base=cmd)


def _espiar(monkeypatch) -> list[str]:
    chamados: list[str] = []
    original = worker_mod.Worker.chamar

    async def chamar(self, metodo, params=None, **kw):
        chamados.append(metodo)
        return await original(self, metodo, params, **kw)

    monkeypatch.setattr(worker_mod.Worker, "chamar", chamar)
    return chamados


def test_worker_novo_de_projeto_importado_abre_a_pasta(tmp_path, monkeypatch):
    chamados = _espiar(monkeypatch)
    pool = _pool(tmp_path)
    (tmp_path / "projetos" / "p1" / "entrada").mkdir(parents=True)

    async def rodar():
        try:
            await pool.chamar("p1", "chat.listar_conversas", {})
        finally:
            await pool.encerrar_todos()

    asyncio.run(rodar())
    assert chamados[:3] == ["ping", "workspace.abrir", "chat.listar_conversas"]


def test_projeto_sem_importacao_e_a_propria_importacao_nao_abrem_duas_vezes(tmp_path, monkeypatch):
    chamados = _espiar(monkeypatch)
    pool = _pool(tmp_path)

    async def sem_entrada():
        try:
            await pool.chamar("p2", "chat.listar_conversas", {})
        finally:
            await pool.encerrar_todos()

    asyncio.run(sem_entrada())
    assert "workspace.abrir" not in chamados

    chamados.clear()
    (tmp_path / "projetos" / "p3" / "entrada").mkdir(parents=True)

    async def importacao():
        try:
            await pool.chamar("p3", "workspace.abrir", {"caminho": "x"})
        finally:
            await pool.encerrar_todos()

    asyncio.run(importacao())
    assert chamados.count("workspace.abrir") == 1
