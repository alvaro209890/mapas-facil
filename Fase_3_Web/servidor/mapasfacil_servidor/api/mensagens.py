"""Chat do projeto — um turno por vez, streaming pelo SSE (W-05/W5-10/W5-11)."""

from __future__ import annotations

import asyncio
import sqlite3
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from .. import projetos_repo, versoes_sync
from ..auth import contas, sessoes
from ..erros import ErroServidor
from ..eventos.log import LogEventos
from . import deps, modelos

router = APIRouter(prefix="/projetos", tags=["chat"])

# Referência forte dos turnos em curso (o loop só guarda referência fraca das tarefas).
_TURNOS_VIVOS: set[asyncio.Task] = set()


def _raiz(estado: deps.AppState, projeto_id: str):
    from pathlib import Path

    from ..config import Config

    cfg = estado.config
    if isinstance(cfg, Config):
        return cfg.projetos / projeto_id
    return Path(str(estado.banco.caminho)).parent / "projetos" / projeto_id


def _exigir_pool(estado: deps.AppState):
    pool = getattr(estado, "pool", None)
    if pool is None:
        raise ErroServidor(
            "SV-240",
            "O motor de geração não está configurado neste servidor.",
            status_http=503,
            porque="Sem o pool de workers não há como conversar com o núcleo.",
            o_que_fazer="Confira MF_PYTHON_NUCLEO e reinicie o serviço.",
        )
    return pool


def _conversa_do_projeto(con: sqlite3.Connection, projeto_id: str) -> str | None:
    linha = con.execute(
        "SELECT conversa_id FROM projetos WHERE id = ?", (projeto_id,)
    ).fetchone()
    return linha["conversa_id"] if linha else None


def _guardar_conversa(con: sqlite3.Connection, projeto_id: str, conversa_id: str) -> None:
    con.execute(
        "UPDATE projetos SET conversa_id = ? WHERE id = ?", (conversa_id, projeto_id)
    )


def _emitir(
    *,
    raiz,
    hub,
    projeto_id: str,
    evento: str,
    dados: dict,
    req_id: str | None = None,
    job_id: str | None = None,
    origem: str = "servidor",
) -> dict:
    envelope = LogEventos(raiz).registrar(
        origem=origem, evento=evento, dados=dados, req_id=req_id, job_id=job_id
    )
    hub.publicar(projeto_id, envelope)
    return envelope


@router.get("/{projeto_id}/mensagens")
async def listar_mensagens(
    projeto_id: str,
    antes: int | None = Query(default=None, ge=1),
    limite: int = Query(default=50, ge=1, le=200),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=usuario.papel == "admin"
    )
    conversa_id = _conversa_do_projeto(con, projeto.id)
    if not conversa_id:
        return {"itens": [], "proximo": None}

    pool = _exigir_pool(estado)
    try:
        dados = await pool.chamar(
            projeto.id,
            "chat.carregar_anteriores",
            {
                "conversation_id": conversa_id,
                "antes_de_seq": antes if antes is not None else 10**9,
                "limite": limite,
            },
        )
    except ErroServidor as exc:
        if exc.codigo.endswith("NU-002"):
            return {"itens": [], "proximo": None}
        raise
    itens = [_mensagem_para_web(m) for m in (dados.get("mensagens") or dados.get("itens") or [])]
    return {"itens": itens, "proximo": dados.get("proximo")}


def _mensagem_para_web(m: dict) -> dict:
    """Linha do banco do núcleo → contrato `Mensagem` da web (`texto`, `criada_em`, tools).

    O núcleo chama de `conteudo`/`criado_em`; a web lia `texto` e quebrava ao recarregar a
    página — o chat abria vazio. As tools vão junto (sem os resultados longos) para os
    cartões e a pergunta de um turno passado voltarem também.
    """
    traces = []
    for t in m.get("tool_traces") or []:
        if not isinstance(t, dict):
            continue
        traces.append(
            {
                "trace_id": t.get("trace_id"),
                "tool": t.get("tool"),
                "args_resumo": t.get("args_resumo"),
                "resultado_resumo": t.get("resultado_resumo"),
                "ok": bool(t.get("ok", True)),
                "ms": t.get("ms"),
            }
        )
    return {
        "message_id": m.get("message_id"),
        "seq": m.get("seq"),
        "papel": m.get("papel"),
        "texto": m.get("texto") if m.get("texto") is not None else (m.get("conteudo") or ""),
        "criada_em": m.get("criada_em") or m.get("criado_em"),
        "cancelada": bool(m.get("cancelada", False)),
        "tool_traces": traces,
    }


@router.post("/{projeto_id}/mensagens", status_code=202)
async def enviar_mensagem(
    projeto_id: str,
    corpo: modelos.MensagemNova,
    tarefas: BackgroundTasks,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado in {"importando", "indexando"}:
        raise ErroServidor(
            "SV-241",
            "Espere a importação terminar para conversar sobre o projeto.",
            status_http=409,
        )
    pool = _exigir_pool(estado)
    raiz = _raiz(estado, projeto.id)
    hub = estado.hub
    req_id = uuid.uuid4().hex
    texto = (corpo.texto or "").strip()
    if corpo.resposta:
        selecionados = corpo.resposta.get("selecionados") or []
        opcao_id = corpo.resposta.get("opcao_id")
        if opcao_id and opcao_id not in selecionados:
            selecionados.append(opcao_id)
        texto_livre = (corpo.resposta.get("texto_livre") or corpo.resposta.get("texto") or "").strip()
        if selecionados:
            texto_resp = f"Opção selecionada: {', '.join(str(s) for s in selecionados)}"
            texto = f"{texto} " + texto_resp if texto else texto_resp if texto else texto_resp
        elif texto_livre:
            texto = f"{texto} " + texto_livre if texto else texto_livre if texto else texto_livre

    if corpo.contexto:
        elem_id = corpo.contexto.get("elemento_id")
        tipo = corpo.contexto.get("tipo") or "elemento"
        versao_ctx = corpo.contexto.get("versao")
        coord = corpo.contexto.get("coord_geo")

        # Validação do contexto apontado (Recurso D / W8-11 / D43)
        if versao_ctx is not None:
            linha_v = con.execute(
                "SELECT numero FROM versoes WHERE projeto_id = ? AND numero = ?",
                (projeto.id, int(versao_ctx)),
            ).fetchone()
            if linha_v is None:
                raise ErroServidor(
                    "SV-242",
                    f"Versão {versao_ctx} não encontrada para este projeto.",
                    status_http=400,
                )
            ELEMENTOS_VALIDOS = {
                "titulo", "titulo_caixa", "legenda", "minimapa", "tabela",
                "norte", "rosa", "escala_grafica", "metadados", "creditos",
                "logo", "grade", "grade_linhas", "quadro_mapa", "mapa",
            }
            if elem_id and str(elem_id).lower() not in ELEMENTOS_VALIDOS:
                raise ErroServidor(
                    "SV-242",
                    f"Elemento '{elem_id}' não existe no layout da versão {versao_ctx}.",
                    status_http=400,
                )

        extra_ctx = f"[O usuário apontou para: {tipo} (id: {elem_id})"
        if versao_ctx is not None:
            extra_ctx += f" da versão {versao_ctx}"
        if coord:
            extra_ctx += f" nas coordenadas {coord}"
        extra_ctx += "]"
        texto = extra_ctx + " " + texto if texto else extra_ctx if texto else extra_ctx

    conversa_id = _conversa_do_projeto(con, projeto.id)
    banco = estado.banco

    async def _rodar() -> None:
        if True:  # mantém o bloco do turno indentado como estava
            pass
        async def _turno() -> None:
            nao_local = None
            try:
                worker = await pool.obter(projeto.id)
                conversa = conversa_id
                if not conversa:
                    criada = await worker.chamar(
                        "chat.criar_conversa",
                        {"workspace": str(raiz), "title": projeto.nome},
                    )
                    conversa = criada.get("conversation_id") or criada.get("id")
                    if conversa:
                        con_local = banco.conectar()
                        try:
                            _guardar_conversa(con_local, projeto.id, conversa)
                        finally:
                            con_local.close()

                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="mensagem.criada",
                    dados={"mensagem": {"papel": "usuario", "texto": texto}},
                    req_id=req_id,
                )
                # Avisa a tela (inclusive outra aba) que o turno começou antes do primeiro
                # token: sem isso o chat parecia vazio enquanto o modelo pensava.
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="chat.turno",
                    dados={"fase": "inicio", "origem": "usuario"},
                    req_id=req_id,
                )

                async def ao_evento(mensagem: dict) -> None:
                    dados_evt = mensagem.get("dados") or {}
                    _emitir(
                        raiz=raiz,
                        hub=hub,
                        projeto_id=projeto.id,
                        evento=mensagem.get("evento", "aviso"),
                        dados=dados_evt,
                        req_id=req_id,
                        job_id=dados_evt.get("job_id"),
                        origem="nucleo",
                    )
                    # O mapa aparece na tela assim que o PDF existe — não espera a IA
                    # terminar de escrever a resposta.
                    if (
                        mensagem.get("evento") == "chat.tool"
                        and dados_evt.get("tool") == "gerar_mapa"
                        and dados_evt.get("fase") == "fim"
                        and dados_evt.get("ok") is not False
                    ):
                        await _publicar_versoes()

                async def _publicar_versoes() -> None:
                    await versoes_sync.publicar_novas(
                        banco=banco,
                        projeto_id=projeto.id,
                        raiz=raiz,
                        emitir=lambda nome, dados_v: _emitir(
                            raiz=raiz,
                            hub=hub,
                            projeto_id=projeto.id,
                            evento=nome,
                            dados=dados_v,
                            req_id=req_id,
                        ),
                    )

                try:
                    await pool.chamar(
                        projeto.id,
                        "chat.enviar",
                        {"conversation_id": conversa, "mensagem": texto},
                        ao_evento=ao_evento,
                    )
                finally:
                    # Turno que gerou e caiu depois (timeout, erro do modelo) também publica.
                    await _publicar_versoes()
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={"req_id": req_id, "ok": True},
                    req_id=req_id,
                )
            except ErroServidor as exc:
                nao_local = exc
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={
                        "req_id": req_id,
                        "ok": False,
                        "erro": {"codigo": exc.codigo, "mensagem": exc.mensagem},
                    },
                    req_id=req_id,
                )
            except Exception as exc:  # pragma: no cover - defensivo
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="nucleo.res",
                    dados={
                        "req_id": req_id,
                        "ok": False,
                        "erro": {"codigo": "SV-099", "mensagem": type(exc).__name__},
                    },
                    req_id=req_id,
                )
            finally:
                _emitir(
                    raiz=raiz,
                    hub=hub,
                    projeto_id=projeto.id,
                    evento="chat.turno",
                    dados={"fase": "fim", "origem": "usuario"},
                    req_id=req_id,
                )

        # O turno vive numa tarefa própria do servidor, não na requisição: quem fecha o site
        # (ou cai a conexão) não para a IA — ela termina, grava a conversa e publica a versão;
        # na volta, `GET /mensagens` e o replay do SSE mostram tudo. O `shield` mantém a
        # tarefa viva mesmo se a requisição for cancelada.
        tarefa = asyncio.create_task(_turno(), name=f"turno-{projeto.id}")
        _TURNOS_VIVOS.add(tarefa)
        tarefa.add_done_callback(_TURNOS_VIVOS.discard)
        await asyncio.shield(tarefa)

    tarefas.add_task(_rodar)
    return {"req_id": req_id}


@router.post("/{projeto_id}/cancelar", status_code=202)
async def cancelar(
    projeto_id: str,
    corpo: modelos.Cancelamento,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    pool = _exigir_pool(estado)

    # O `req_id` da web é o do servidor, não o id interno da ponte: quem para o turno é o
    # `chat.cancelar` da conversa (o núcleo encerra na próxima rodada e grava o que tinha).
    conversa_id = _conversa_do_projeto(con, projeto.id)
    if conversa_id:
        try:
            await pool.chamar(projeto.id, "chat.cancelar", {"conversation_id": conversa_id})
        except ErroServidor:
            pass  # turno já terminou
    worker = pool.obter_existente(projeto.id)
    if worker is not None:
        await worker.cancelar(corpo.req_id)
    return {"cancelado": corpo.req_id}
