"""W2 — ponte: protocolo, allowlist, worker e pool (com o núcleo falso)."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import pytest

from mapasfacil_servidor.erros import ErroServidor
from mapasfacil_servidor.ponte import allowlist, pool, protocolo
from mapasfacil_servidor.ponte import worker as worker_mod
from mapasfacil_servidor.ponte.worker import Worker, montar_env, redigir

RAIZ = Path(__file__).resolve().parents[1]
ROTEIROS = Path(__file__).resolve().parent / "roteiros"
REPO = Path(__file__).resolve().parents[3]
NUCLEO_MAIN = REPO / "Fase_1_Desktop" / "nucleo" / "mapasfacil_nucleo" / "__main__.py"


def cmd_fake(roteiro: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "mapasfacil_servidor.ponte.fake_nucleo",
        "--roteiro",
        str(ROTEIROS / roteiro),
    ]


def fazer_worker(tmp_path: Path, roteiro: str, **kw) -> Worker:
    raiz = tmp_path / "projeto"
    raiz.mkdir(parents=True, exist_ok=True)
    env = montar_env(
        projeto_raiz=raiz, usuario_id="usuario_01", extra={"PYTHONPATH": str(RAIZ)}
    )
    return Worker(
        projeto_id="p1",
        raiz=raiz,
        cmd=cmd_fake(roteiro),
        env=env,
        timeout_req_s=kw.pop("timeout_req_s", 10.0),
        log_path=tmp_path / "logs" / "p1.log",
        **kw,
    )


# --- protocolo ------------------------------------------------------------


def test_envelopes_do_contrato():
    req = protocolo.envelope_req("workspace.abrir", {"pasta": "/x"})
    assert req["v"] == protocolo.PROTOCOLO_VERSAO == 1
    assert req["tipo"] == "req" and req["metodo"] == "workspace.abrir"
    assert protocolo.parsear_linha(protocolo.serializar_linha(req)) == req

    evt = protocolo.envelope_evt(req["id"], "job.progresso", {"pct": 50})
    assert evt["tipo"] == "evt" and evt["dados"]["pct"] == 50


def test_evento_fora_do_vocabulario_falha():
    with pytest.raises(protocolo.ProtocoloInvalido):
        protocolo.envelope_evt("x", "job.inventado", {})


def test_linha_invalida_falha():
    for linha in ("", "  ", "nao-json", "[1,2]"):
        with pytest.raises(protocolo.ProtocoloInvalido):
            protocolo.parsear_linha(linha)


def test_redacao_de_cpf_e_chave():
    texto = "cpf 123.456.789-09 chave sk-abcdef123456 authkey=SEGREDO Bearer abc.def.ghi"
    saida = redigir(texto)
    assert "123.456.789-09" not in saida
    assert "abcdef123456" not in saida
    assert "SEGREDO" not in saida
    assert "abc.def.ghi" not in saida
    assert "***.***.***-**" in saida


def test_env_minimo_nao_herda_o_ambiente_do_servidor(monkeypatch, tmp_path):
    monkeypatch.setenv("MAPASFACIL_PROVEDOR_CHAVE", "vazaria")
    env = montar_env(
        projeto_raiz=tmp_path,
        usuario_id="u1",
        segredos={"MAPASFACIL_SEMA_AUTHKEY": "s3m4"},
        vagas_dir=tmp_path / "vagas",
        max_jobs=2,
    )
    assert "MAPASFACIL_PROVEDOR_CHAVE" not in env
    assert env["MAPASFACIL_MODO"] == "servidor"
    assert env["MAPASFACIL_SESSAO_SERVIDOR"] == "u1"
    assert env["MAPASFACIL_MAX_JOBS"] == "2"
    assert env["MAPASFACIL_SEMA_AUTHKEY"] == "s3m4"
    assert env["LANG"] == "C.UTF-8"
    assert env["PYTHONIOENCODING"] == "utf-8"


# --- allowlist ------------------------------------------------------------


def test_permitido_passa():
    for metodo in ("workspace.abrir", "mapa.gerar", "chat.enviar", "ping"):
        allowlist.verificar(metodo)


def test_bloqueado_recusa_antes_do_worker():
    with pytest.raises(ErroServidor) as exc:
        allowlist.verificar("cofre.definir")
    assert exc.value.codigo == "SV-201"
    assert exc.value.status_http == 403
    assert "keyring" in (exc.value.porque or "")


def test_desconhecido_recusa():
    with pytest.raises(ErroServidor) as exc:
        allowlist.verificar("shell.exec")
    assert exc.value.codigo == "SV-201"


def _metodos_do_nucleo() -> set[str]:
    """Lê os métodos registrados no `__main__` do núcleo (fonte, sem importar)."""
    if not NUCLEO_MAIN.exists():  # pragma: no cover - repo incompleto
        pytest.skip("fonte do núcleo não encontrada")
    texto = NUCLEO_MAIN.read_text(encoding="utf-8")
    return set(re.findall(r'roteador\.registrar\(\s*"([^"]+)"', texto))


def test_todo_metodo_do_nucleo_esta_classificado():
    metodos = _metodos_do_nucleo()
    assert metodos, "não li nenhum método do __main__ do núcleo"
    sem_classificacao = sorted(metodos - allowlist.PERMITIDOS - set(allowlist.BLOQUEADOS))
    assert not sem_classificacao, (
        "método novo no núcleo sem decisão na ponte: " + ", ".join(sem_classificacao)
    )


def test_allowlist_nao_aponta_metodo_inexistente():
    metodos = _metodos_do_nucleo()
    fantasmas = sorted((allowlist.PERMITIDOS | set(allowlist.BLOQUEADOS)) - metodos)
    assert not fantasmas, "allowlist cita método que o núcleo não registra: " + ", ".join(fantasmas)


# --- worker com o núcleo falso -------------------------------------------


def test_worker_sobe_e_responde(tmp_path):
    async def cenario():
        w = fazer_worker(tmp_path, "indexar_ok.ndjson")
        await w.iniciar()
        assert w.estado == "pronto"
        resultado = await w.chamar("workspace.abrir", {"pasta": str(tmp_path)})
        assert resultado["workspace"]["shp"] == ["ATP.shp"]
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())


def test_worker_entrega_eventos_ao_dono_da_requisicao(tmp_path):
    async def cenario():
        w = fazer_worker(tmp_path, "dinamica_ok.ndjson")
        await w.iniciar()
        eventos: list[dict] = []

        async def ao_evento(evt: dict) -> None:
            eventos.append(evt)

        resultado = await w.chamar("mapa.gerar", {"mapspec": {}}, ao_evento=ao_evento)
        assert resultado["job_id"] == "01JOB"
        assert [e["evento"] for e in eventos] == ["job.progresso", "job.log", "job.progresso"]
        assert eventos[0]["dados"]["pct"] == 10
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())


def test_erro_do_nucleo_chega_tipado(tmp_path):
    async def cenario():
        w = fazer_worker(tmp_path, "dinamica_falha_hard.ndjson")
        await w.iniciar()
        with pytest.raises(ErroServidor) as exc:
            await w.chamar("mapa.gerar", {})
        assert exc.value.codigo == "NUCLEO:NU-500"
        assert "HARD" in exc.value.mensagem
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())


def test_morte_do_worker_derruba_a_requisicao(tmp_path):
    async def cenario():
        w = fazer_worker(tmp_path, "morrer_no_meio.ndjson")
        await w.iniciar()
        with pytest.raises(ErroServidor) as exc:
            await w.chamar("mapa.gerar", {}, timeout_s=10)
        assert exc.value.codigo == "SV-221"
        assert w.estado == "caido"
        # requisição depois da morte também falha tipada
        with pytest.raises(ErroServidor) as exc2:
            await w.chamar("ping", {})
        assert exc2.value.codigo == "SV-221"
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())


def test_timeout_de_requisicao(tmp_path):
    async def cenario():
        w = fazer_worker(tmp_path, "dinamica_ok.ndjson", timeout_req_s=0.3)
        # o roteiro responde rápido; forçamos timeout com um passo lento
        roteiro = tmp_path / "lento.ndjson"
        roteiro.write_text(
            '{"metodo": "ping", "resultado": {}}\n'
            '{"metodo": "mapa.gerar", "atraso": 3, "resultado": {}}\n',
            encoding="utf-8",
        )
        w.cmd = [sys.executable, "-m", "mapasfacil_servidor.ponte.fake_nucleo",
                 "--roteiro", str(roteiro)]
        await w.iniciar()
        with pytest.raises(ErroServidor) as exc:
            await w.chamar("mapa.gerar", {}, timeout_s=0.3)
        assert exc.value.codigo == "SV-220"
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())


def test_stderr_vai_redigido_para_o_log(tmp_path):
    roteiro = tmp_path / "simples.ndjson"
    roteiro.write_text('{"metodo": "ping", "resultado": {}}\n', encoding="utf-8")

    async def cenario():
        raiz = tmp_path / "projeto"
        raiz.mkdir(parents=True, exist_ok=True)
        env = montar_env(projeto_raiz=raiz, usuario_id="u1", extra={"PYTHONPATH": str(RAIZ)})
        w = Worker(
            projeto_id="p1",
            raiz=raiz,
            cmd=[sys.executable, "-m", "mapasfacil_servidor.ponte.fake_nucleo",
                 "--roteiro", str(roteiro), "--echo-stderr", "cpf 123.456.789-09"],
            env=env,
            log_path=tmp_path / "logs" / "p1.log",
        )
        await w.iniciar()
        for _ in range(50):
            if w.log_path.exists() and w.log_path.read_text(encoding="utf-8"):
                break
            await asyncio.sleep(0.05)
        await w.encerrar(motivo="teste")

    asyncio.run(cenario())
    conteudo = (tmp_path / "logs" / "p1.log").read_text(encoding="utf-8")
    assert "123.456.789-09" not in conteudo
    assert "***.***.***-**" in conteudo


# --- pool -----------------------------------------------------------------


def _pool(tmp_path: Path, *, max_workers: int = 2, roteiro: str = "indexar_ok.ndjson") -> pool.Pool:
    projetos = tmp_path / "projetos"
    projetos.mkdir(parents=True, exist_ok=True)
    return pool.Pool(
        raiz_projetos=projetos,
        cmd_base=cmd_fake(roteiro),
        max_workers=max_workers,
        timeout_req_s=10.0,
        env_por_projeto=lambda pid, raiz: montar_env(
            projeto_raiz=raiz, usuario_id="u1", extra={"PYTHONPATH": str(RAIZ)}
        ),
    )


def test_pool_reusa_o_worker_do_projeto(tmp_path):
    async def cenario():
        p = _pool(tmp_path)
        await p.chamar("p1", "workspace.abrir", {})
        primeiro = p.obter_existente("p1")
        await p.chamar("p1", "workspace.inspecionar", {})
        assert p.obter_existente("p1") is primeiro
        await p.encerrar_todos()

    asyncio.run(cenario())


def test_pool_respeita_o_teto_encerrando_o_ocioso(tmp_path):
    async def cenario():
        p = _pool(tmp_path, max_workers=2)
        await p.chamar("p1", "workspace.abrir", {})
        await p.chamar("p2", "workspace.abrir", {})
        assert len(p._workers) == 2
        await p.chamar("p3", "workspace.abrir", {})
        assert len(p._workers) == 2
        assert "p3" in p._workers
        assert "p1" not in p._workers  # o mais ocioso saiu
        await p.encerrar_todos()

    asyncio.run(cenario())


def test_pool_recusa_segundo_turno_de_chat(tmp_path):
    async def cenario():
        p = _pool(tmp_path)
        await p.chamar("p1", "workspace.abrir", {})
        p._chat_em_curso.add("p1")
        with pytest.raises(ErroServidor) as exc:
            await p.chamar("p1", "chat.enviar", {})
        assert exc.value.codigo == "SV-210"
        await p.encerrar_todos()

    asyncio.run(cenario())


def test_pool_sobe_worker_novo_depois_da_morte(tmp_path):
    """Critério de aceite W2: matar o worker não derruba o projeto."""

    async def cenario():
        p = _pool(tmp_path, roteiro="morrer_no_meio.ndjson")
        with pytest.raises(ErroServidor) as exc:
            await p.chamar("p1", "mapa.gerar", {})
        assert exc.value.codigo == "SV-221"
        assert p.obter_existente("p1") is None
        # a próxima mensagem sobe um worker novo e funciona
        resultado = await p.chamar("p1", "ping", {})
        assert resultado == {"pong": True}
        assert p.obter_existente("p1") is not None
        await p.encerrar_todos()

    asyncio.run(cenario())


def test_pool_recusa_metodo_fora_da_allowlist_sem_subir_worker(tmp_path):
    async def cenario():
        p = _pool(tmp_path)
        with pytest.raises(ErroServidor) as exc:
            await p.chamar("p1", "cofre.definir", {})
        assert exc.value.codigo == "SV-201"
        assert p._workers == {}
        await p.encerrar_todos()

    asyncio.run(cenario())
