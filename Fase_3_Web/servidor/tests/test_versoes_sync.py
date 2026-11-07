"""Mapa gerado pelo chat aparece na tela e no download (caso real do teste_22, 04/11/2026).

O núcleo gravava `Mapas/v001/` com PDF, PNG e planilha (e o `.mxd` em `MXD/`), o chat dizia
"o mapa está pronto" — e a tela seguia em "sem versões": ninguém registrava a versão no banco
do servidor nem emitia `versao.criada`.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from mapasfacil_servidor import projetos_repo, versoes_sync
from mapasfacil_servidor.db import Banco
from mapasfacil_servidor.eventos.log import LogEventos
from mapasfacil_servidor.pacote import OpcoesPacote, montar_pacote_do_projeto
from mapasfacil_servidor.ponte import versao as versao_mod
from mapasfacil_servidor.ponte.pool import Pool

VALIDACAO_NUCLEO = {
    "versao": 1,
    "motor": "binario",
    "resumo": {"hard_total": 2, "hard_ok": 2, "aprovado": True},
    "checks": {
        "hard": [{"id": "H01", "ok": True}, {"id": "H02", "ok": True}],
        "soft": [{"id": "S03", "ok": False}],
    },
}


def _versao_como_o_nucleo_grava(raiz: Path, numero: int = 1, nome: str = "Dinamica_2008") -> None:
    pasta = raiz / "Mapas" / f"v{numero:03d}"
    (pasta / "recursos").mkdir(parents=True)
    (pasta / f"{nome}.pdf").write_bytes(b"%PDF-1.4")
    Image.new("RGB", (2480, 3508), "white").save(pasta / f"{nome}_pagina.png")
    (pasta / f"{nome}_Quantitativos.xlsx").write_bytes(b"PK")
    (pasta / f"{nome}_validacao.json").write_text(json.dumps(VALIDACAO_NUCLEO), encoding="utf-8")
    (pasta / "mapspec.json").write_text("{}", encoding="utf-8")
    # insumos internos não são entrega
    Image.new("RGB", (10, 10)).save(pasta / "recursos" / "tabela_quantitativos.png")
    (raiz / "MXD").mkdir(exist_ok=True)
    (raiz / "MXD" / f"{nome}.mxd").write_bytes(b"MXD")
    (raiz / "SHP").mkdir(exist_ok=True)
    (raiz / "SHP" / "ATP.shp").write_bytes(b"SHP")


@pytest.fixture
def ambiente(tmp_path: Path):
    banco = Banco(tmp_path / "dados" / "mapasfacil.sqlite")
    banco.migrar()
    con = banco.conectar()
    con.execute(
        "INSERT INTO usuarios (id, nome, email, senha_hash, papel, criado_em)"
        " VALUES ('u1', 'U', 'u@x.com', 'x', 'usuario', 'agora')"
    )
    projeto = projetos_repo.criar(
        con, usuario_id="u1", nome="teste_22", folha={"formato": "A4", "orientacao": "retrato"}
    )
    raiz = tmp_path / "dados" / "projetos" / projeto.id
    raiz.mkdir(parents=True)
    yield banco, con, projeto, raiz
    con.close()


def test_montar_le_o_layout_real_do_nucleo(tmp_path):
    raiz = tmp_path
    _versao_como_o_nucleo_grava(raiz)
    registro = versao_mod.montar(raiz, 1)
    assert registro.artefatos == {
        "pdf": "Mapas/v001/Dinamica_2008.pdf",
        "png": "Mapas/v001/Dinamica_2008_pagina.png",
        "xlsx": "Mapas/v001/Dinamica_2008_Quantitativos.xlsx",
        "mxd": "MXD/Dinamica_2008.mxd",
    }
    assert registro.conforme is True, "resumo.aprovado do núcleo vale; SOFT não reprova"
    assert registro.validacao["motor"] == "binario"


def test_hard_reprovado_no_formato_novo(tmp_path):
    raiz = tmp_path
    _versao_como_o_nucleo_grava(raiz)
    validacao = {"checks": {"hard": [{"id": "H01", "ok": False}], "soft": []}}
    (raiz / "Mapas" / "v001" / "Dinamica_2008_validacao.json").write_text(
        json.dumps(validacao), encoding="utf-8"
    )
    assert versao_mod.montar(raiz, 1).conforme is False


def test_sincronizar_registra_gera_miniatura_e_e_idempotente(ambiente):
    _banco, con, projeto, raiz = ambiente
    _versao_como_o_nucleo_grava(raiz)

    novas = versoes_sync.sincronizar(con, projeto.id, raiz)
    assert [v["numero"] for v in novas] == [1]
    assert novas[0]["miniatura"] == "Mapas/v001/miniatura.jpg"
    with Image.open(raiz / "Mapas" / "v001" / "miniatura.jpg") as mini:
        assert mini.width <= 900, "miniatura leve, não o PNG de 3 MB"
    assert "miniatura.jpg" not in json.dumps(novas[0]["artefatos"])
    atualizado = projetos_repo.obter(con, projeto.id, usuario_id="u1")
    assert atualizado is not None and atualizado.versao_atual == 1

    assert versoes_sync.sincronizar(con, projeto.id, raiz) == [], "nada novo, nada emitido"


def test_versao_sem_pdf_ainda_nao_entra(ambiente):
    _banco, con, projeto, raiz = ambiente
    (raiz / "Mapas" / "v001").mkdir(parents=True)
    (raiz / "Mapas" / "v001" / "mapspec.json").write_text("{}", encoding="utf-8")
    assert versoes_sync.sincronizar(con, projeto.id, raiz) == []
    assert projetos_repo.versoes(con, projeto.id) == []


def test_planilha_que_chega_depois_atualiza_a_versao_mais_recente(ambiente):
    _banco, con, projeto, raiz = ambiente
    _versao_como_o_nucleo_grava(raiz)
    xlsx = raiz / "Mapas" / "v001" / "Dinamica_2008_Quantitativos.xlsx"
    xlsx.unlink()
    primeira = versoes_sync.sincronizar(con, projeto.id, raiz)
    assert "xlsx" not in primeira[0]["artefatos"]
    xlsx.write_bytes(b"PK")
    segunda = versoes_sync.sincronizar(con, projeto.id, raiz)
    assert "xlsx" in segunda[0]["artefatos"]


def test_publicar_novas_emite_versao_criada(ambiente):
    banco, _con, projeto, raiz = ambiente
    _versao_como_o_nucleo_grava(raiz)
    emitidos: list[tuple[str, dict]] = []

    novas = asyncio.run(
        versoes_sync.publicar_novas(
            banco=banco,
            projeto_id=projeto.id,
            raiz=raiz,
            emitir=lambda nome, dados: emitidos.append((nome, dados)),
        )
    )
    assert len(novas) == 1
    assert emitidos and emitidos[0][0] == "versao.criada"
    assert emitidos[0][1]["versao"]["numero"] == 1
    assert emitidos[0][1]["projeto_id"] == projeto.id


def test_pacote_do_projeto_junta_mxd_shp_e_mapas(tmp_path, monkeypatch):
    monkeypatch.setenv("MF_MXD", "1")
    raiz = tmp_path
    _versao_como_o_nucleo_grava(raiz)
    registro = versao_mod.montar(raiz, 1)
    destino = raiz / ".servidor" / "pacotes" / "teste_v001.zip"
    montar_pacote_do_projeto(raiz, registro.pasta, registro.artefatos, destino, OpcoesPacote(incluir_mxd=True))
    with zipfile.ZipFile(io.BytesIO(destino.read_bytes())) as zf:
        nomes = set(zf.namelist())
    assert {"LEIA-ME.txt", "MXD/Dinamica_2008.mxd", "SHP/ATP.shp", "Mapas/Dinamica_2008.pdf"} <= nomes
    assert not any("recursos" in n or "miniatura" in n for n in nomes)


# --- replay: job do chat termina com o turno ------------------------------------------


def test_job_do_gerar_mapa_termina_com_o_turno(tmp_path):
    log = LogEventos(tmp_path)
    for pct in (5, 50, 100):
        log.registrar(
            origem="nucleo", evento="job.progresso", dados={"pct": pct}, job_id="j1", req_id="r1"
        )
    log.registrar(
        origem="nucleo", evento="layout.elemento", dados={"elemento": "titulo"}, job_id="j1", req_id="r1"
    )
    log.registrar(
        origem="servidor", evento="versao.criada", dados={"versao": {"numero": 1}}, req_id="r1"
    )
    log.registrar(origem="servidor", evento="nucleo.res", dados={"ok": True}, req_id="r1")

    compactado = log.compactar(log.ler_desde(0))
    progresso = [e for e in compactado if e["evento"] == "job.progresso"]
    assert [e["dados"]["pct"] for e in progresso] == [100], "só o fim do job volta"
    assert any(e["evento"] == "versao.criada" for e in compactado)


# --- pool: o chat não trava as outras chamadas do projeto ---------------------------


def test_historico_responde_durante_um_turno_de_chat(tmp_path):
    """Recarregar a página no meio da geração: `GET /mensagens` não espera o turno acabar."""
    roteiro = tmp_path / "roteiro.ndjson"
    roteiro.write_text(
        '{"metodo": "ping", "resultado": {}}\n'
        '{"metodo": "chat.enviar", "resultado": {"ok": true}, "atraso": 1.5}\n'
        '{"metodo": "chat.carregar_anteriores", "resultado": {"mensagens": []}}\n',
        encoding="utf-8",
    )
    cmd = [sys.executable, "-m", "mapasfacil_servidor.ponte.fake_nucleo", "--roteiro", str(roteiro)]
    raiz_servidor = str(Path(__file__).resolve().parents[1])
    pool = Pool(
        raiz_projetos=tmp_path / "projetos",
        cmd_base=cmd,
        env_por_projeto=lambda _pid, _raiz: {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(filter(None, [raiz_servidor, os.environ.get("PYTHONPATH")])),
        },
    )

    async def rodar() -> float:
        loop = asyncio.get_running_loop()
        try:
            turno = asyncio.create_task(pool.chamar("p1", "chat.enviar", {}))
            await asyncio.sleep(0.3)
            assert pool.chat_em_curso("p1")
            inicio = loop.time()
            await pool.chamar("p1", "chat.carregar_anteriores", {})
            demora = loop.time() - inicio
            await turno
            assert not pool.chat_em_curso("p1")
            return demora
        finally:
            await pool.encerrar_todos()

    assert asyncio.run(rodar()) < 1.0


# --- histórico: o contrato que a web lê -------------------------------------------------


def test_mensagem_do_nucleo_vira_contrato_da_web():
    """O núcleo manda `conteudo`/`criado_em`; a web lia `texto` e abria o chat vazio."""
    from mapasfacil_servidor.api.mensagens import _mensagem_para_web

    linha = {
        "message_id": "m1",
        "conversation_id": "c1",
        "seq": 4,
        "papel": "assistente",
        "conteudo": "",
        "criado_em": "2026-11-04T13:17:09Z",
        "cancelada": False,
        "tool_traces": [
            {"trace_id": "t1", "tool": "perguntar", "args_resumo": '{"pergunta": "Qual?"}', "ok": True, "ms": 3},
        ],
    }
    web = _mensagem_para_web(linha)
    assert web["texto"] == ""
    assert web["criada_em"] == "2026-11-04T13:17:09Z"
    assert web["tool_traces"][0]["tool"] == "perguntar"
    assert "conversation_id" not in web
