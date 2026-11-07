"""Rotas de projetos (W-03 §Projetos)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse

from .. import projetos_repo, versoes_sync
from ..auth import contas, sessoes
from ..erros import ErroServidor
from ..pacote import OpcoesPacote, montar_pacote_do_projeto
from . import deps, modelos

router = APIRouter(prefix="/projetos", tags=["projetos"])


def _admin(usuario: contas.Usuario) -> bool:
    return usuario.papel == "admin"


@router.get("")
def listar(
    busca: str | None = Query(default=None, max_length=120),
    estado: str | None = Query(default=None, max_length=30),
    antes: str | None = Query(default=None, max_length=64),
    limite: int = Query(default=50, ge=1, le=200),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    return projetos_repo.listar(
        con,
        usuario_id=usuario.id,
        admin=_admin(usuario),
        busca=busca,
        estado=estado,
        antes=antes,
        limite=limite,
    )


@router.post("", status_code=201)
def criar(
    corpo: modelos.ProjetoNovo,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    projeto = projetos_repo.criar(
        con,
        usuario_id=usuario.id,
        nome=corpo.nome,
        folha=corpo.folha.model_dump(),
    )
    contas.auditar(con, acao="criou_projeto", usuario_id=usuario.id, alvo=projeto.id)
    return {"projeto": projeto.completo()}


@router.get("/{projeto_id}")
def detalhar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    # Versão gerada pelo chat e ainda não registrada (ex.: turno que caiu no meio) entra aqui.
    if versoes_sync.sincronizar_seguro(
        con, projeto.id, versoes_sync.raiz_do_projeto(estado, projeto.id)
    ):
        projeto = projetos_repo.exigir(
            con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
        )
    return {
        "projeto": projeto.completo(),
        "imoveis": projetos_repo.listar_imoveis(con, projeto.id),
        "versoes": projetos_repo.versoes(con, projeto.id),
    }


@router.get("/{projeto_id}/imoveis")
def listar_imoveis(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
) -> dict:
    """Lista os imóveis do projeto (aditivo multi-imóvel)."""
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    return {"imoveis": projetos_repo.listar_imoveis(con, projeto.id)}


@router.get("/{projeto_id}/agente")
def obter_estado_agente(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    """Lê o estado do agente (read-only) e publica token de aprovação pendente para o owner."""
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    raiz = versoes_sync.raiz_do_projeto(estado, projeto.id)
    caminho_estado = raiz / ".agente" / "estado.json"

    dados_estado: dict = {}
    if caminho_estado.is_file():
        try:
            import json as _json

            conteudo = _json.loads(caminho_estado.read_text(encoding="utf-8"))
            if isinstance(conteudo, dict):
                dados_estado = conteudo
        except Exception:
            dados_estado = {}

    # Leitura do pedido de aprovação formal (.servidor/aprovacoes/pedido.json)
    # ou da decisão já registrada (.servidor/aprovacoes/decisao.json)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    caminho_pedido = pasta_aprov / "pedido.json"
    caminho_decisao = pasta_aprov / "decisao.json"
    aprovacao_payload = dados_estado.get("aprovacao")

    if caminho_decisao.is_file():
        try:
            import json as _json

            decisao = _json.loads(caminho_decisao.read_text(encoding="utf-8"))
            if isinstance(decisao, dict):
                aprovacao_payload = decisao
        except Exception:
            pass
    elif caminho_pedido.is_file():
        try:
            import json as _json
            import time as _time

            pedido = _json.loads(caminho_pedido.read_text(encoding="utf-8"))
            if isinstance(pedido, dict):
                ts = float(pedido.get("ts") or pedido.get("timestamp") or 0.0)
                ttl = float(pedido.get("ttl") or 300.0)
                agora = _time.time()
                status_pedido = str(pedido.get("status") or "pendente")
                if status_pedido != "pendente":
                    aprovacao_payload = {
                        "status": status_pedido,
                        "action": pedido.get("action") or pedido.get("acao"),
                        "path": pedido.get("path") or pedido.get("caminho"),
                        "version": pedido.get("version") or pedido.get("versao"),
                        "hash": pedido.get("hash_alvo") or pedido.get("hash"),
                        "motivo": pedido.get("motivo"),
                    }
                elif ts > 0 and (agora - ts) > ttl:
                    aprovacao_payload = {
                        "status": "expirado",
                        "expirado": True,
                        "motivo": "TTL expirado",
                    }
                else:
                    # Publica token com segurança exclusivamente via GET agente/owner autenticado
                    token_pub = str(pedido.get("token") or "")
                    aprovacao_payload = {
                        "status": "pendente",
                        "token": token_pub,
                        "action": pedido.get("action") or pedido.get("acao"),
                        "path": pedido.get("path") or pedido.get("caminho"),
                        "version": pedido.get("version") or pedido.get("versao"),
                        "hash": pedido.get("hash_alvo") or pedido.get("hash"),
                        "ttl": ttl,
                        "motivo": pedido.get("motivo"),
                        "criado_em": ts,
                        "expira_em": ts + ttl if ts > 0 else None,
                    }
        except Exception:
            pass

    if isinstance(aprovacao_payload, dict):
        # Mesmo vocabulário canônico do NDJSON/store, preservando aliases legados.
        aprovacao_payload = {**aprovacao_payload,
            'acao': aprovacao_payload.get('acao') or aprovacao_payload.get('action'),
            'caminho': aprovacao_payload.get('caminho') or aprovacao_payload.get('path')}

    status_final = dados_estado.get("status")
    if not status_final and aprovacao_payload and aprovacao_payload.get("status"):
        status_final = aprovacao_payload.get("status")

    return {
        "passos": dados_estado.get("passos", []),
        "arquivos": dados_estado.get("arquivos", []),
        "previews": dados_estado.get("previews", []),
        "aprovacao": aprovacao_payload,
        "status": status_final or "pendente",
        "resumo": dados_estado.get("resumo"),
        "versao": dados_estado.get("versao"),
    }


@router.post("/{projeto_id}/agente/aprovacao")
def registrar_aprovacao_agente(
    projeto_id: str,
    corpo: modelos.AprovacaoAgenteCorpo,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    """Registra decisão de aprovação conferindo token constante, TTL, action, path, version e hash.

    Escreve atomicamente em .servidor/aprovacoes/decisao.json sem confiar em estado fabricável.
    """
    import hmac
    import json as _json
    import time as _time

    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    acao = (corpo.acao or "").strip().lower()
    if acao not in {"aprovar", "rejeitar"}:
        raise ErroServidor(
            "SV-095",
            "Ação inválida. Use 'aprovar' ou 'rejeitar'.",
            status_http=400,
        )

    raiz = versoes_sync.raiz_do_projeto(estado, projeto.id)
    pasta_aprov = raiz / ".servidor" / "aprovacoes"
    caminho_pedido = pasta_aprov / "pedido.json"

    if not caminho_pedido.is_file():
        raise ErroServidor(
            "SV-096",
            "Nenhum pedido de aprovação pendente encontrado.",
            status_http=404,
        )

    try:
        pedido = _json.loads(caminho_pedido.read_text(encoding="utf-8"))
        if not isinstance(pedido, dict):
            raise ValueError("Pedido não é um objeto JSON.")
    except Exception as exc:
        raise ErroServidor(
            "SV-096",
            f"Pedido de aprovação inválido: {exc}",
            status_http=400,
        )

    status_pedido = str(pedido.get("status") or "pendente")
    if status_pedido not in {"pendente", ""}:
        raise ErroServidor(
            "SV-096",
            f"Pedido de aprovação não está mais pendente (status atual: {status_pedido}).",
            status_http=409,
        )

    # 1. Conferência de TTL
    ts = float(pedido.get("ts") or pedido.get("timestamp") or 0.0)
    ttl = float(pedido.get("ttl") or 300.0)
    agora = _time.time()
    if ts > 0 and (agora - ts) > ttl:
        raise ErroServidor(
            "SV-097",
            "Pedido de aprovação expirado (TTL esgotado).",
            status_http=400,
        )

    # 2. Conferência de Token em tempo constante (timing attack safe)
    token_esperado = str(pedido.get("token") or "").strip()
    token_recebido = str(corpo.token or "").strip()
    if not token_recebido or not hmac.compare_digest(token_esperado, token_recebido):
        raise ErroServidor(
            "SV-098",
            "Token de aprovação inválido ou ausente.",
            status_http=403,
        )

    # 3. Conferência estrita de action, path, version e hash
    p_action = pedido.get("action") or pedido.get("acao")
    if corpo.action and p_action and corpo.action != p_action:
        raise ErroServidor(
            "SV-099",
            f"Action informada ({corpo.action}) diverge do pedido ({p_action}).",
            status_http=400,
        )

    p_path = pedido.get("path") or pedido.get("caminho")
    if corpo.path and p_path and corpo.path != p_path:
        raise ErroServidor(
            "SV-099",
            f"Path informado ({corpo.path}) diverge do pedido ({p_path}).",
            status_http=400,
        )

    p_version = pedido.get("version") or pedido.get("versao")
    if corpo.version is not None and p_version is not None and corpo.version != p_version:
        raise ErroServidor(
            "SV-099",
            f"Versão informada ({corpo.version}) diverge do pedido ({p_version}).",
            status_http=400,
        )

    p_hash = pedido.get("hash_alvo") or pedido.get("hash")
    if corpo.hash and p_hash and corpo.hash != p_hash:
        raise ErroServidor(
            "SV-099",
            "Hash informado diverge do pedido.",
            status_http=400,
        )

    # 4. Gravação atômica em .servidor/aprovacoes/decisao.json seguindo o contrato nativo de aprovação.py:
    # {aprovado: bool, acao: str, caminho: str, hash_alvo: str, timestamp: float, consumido: False, pedido_id: str}
    pasta_aprov.mkdir(parents=True, exist_ok=True)
    aprovado_bool = (acao == "aprovar")
    status_decisao = "aprovado" if aprovado_bool else "rejeitado"

    p_pedido_id = str(pedido.get("pedido_id") or "")
    p_caminho = pedido.get("caminho") or pedido.get("path") or ""
    p_acao_nativo = pedido.get("acao") or pedido.get("action") or acao

    decisao_dados = {
        # Contrato nativo de aprovação.py / verificar_e_consumir_decisao:
        "aprovado": aprovado_bool,
        "acao": p_acao_nativo,
        "caminho": p_caminho,
        "hash_alvo": p_hash,
        "timestamp": agora,
        "consumido": False,
        "pedido_id": p_pedido_id,
        # Aliases para UI, auditoria e retrocompatibilidade:
        "status": status_decisao,
        "decisao": status_decisao,
        "action": p_action or p_acao_nativo,
        "path": p_path or p_caminho,
        "version": p_version,
        "hash": p_hash,
        "token": token_esperado,
        "usuario_id": usuario.id,
        "usuario_nome": usuario.nome,
        "motivo": corpo.motivo,
        "ts": agora,
        "em": sessoes.iso(sessoes.agora()),
    }

    temp_decisao = pasta_aprov / "decisao.json.tmp"
    temp_decisao.write_text(
        _json.dumps(decisao_dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_decisao.replace(pasta_aprov / "decisao.json")

    # Atualiza o pedido sem apagá-lo prematuramente (deixa status='aprovado' ou 'recusado');
    # o consumo único é realizado pelo núcleo ao executar a tool (verificar_e_consumir_decisao).
    pedido["status"] = "aprovado" if aprovado_bool else "recusado"
    temp_pedido = pasta_aprov / "pedido.json.tmp"
    temp_pedido.write_text(
        _json.dumps(pedido, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_pedido.replace(caminho_pedido)

    contas.auditar(
        con,
        acao=f"agente_{acao}",
        usuario_id=usuario.id,
        alvo=projeto.id,
        detalhe=corpo.motivo,
    )

    return {
        "ok": True,
        "status": status_decisao,
        "decisao": decisao_dados,
        "aprovacao": decisao_dados,
    }


@router.patch("/{projeto_id}")
async def renomear(
    projeto_id: str,
    corpo: modelos.ProjetoPatch,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if corpo.nome is not None:
        projeto = projetos_repo.renomear(con, projeto, corpo.nome)
        # W5-11: o título da conversa acompanha o nome do projeto.
        conversa_id = con.execute(
            "SELECT conversa_id FROM projetos WHERE id = ?", (projeto.id,)
        ).fetchone()["conversa_id"]
        pool = getattr(estado, "pool", None)
        if conversa_id and pool is not None:
            from ..erros import ErroServidor

            try:
                await pool.chamar(
                    projeto.id,
                    "chat.renomear",
                    {"conversation_id": conversa_id, "title": projeto.nome},
                )
            except ErroServidor:
                # Renomear o projeto não pode falhar porque a conversa não renomeou.
                pass
    return {"projeto": projeto.completo()}


@router.delete("/{projeto_id}", status_code=204)
def apagar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> Response:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado == "gerando":
        raise ErroServidor(
            "SV-094",
            "Não apague um projeto enquanto ele gera.",
            status_http=409,
            o_que_fazer="Espere a geração terminar ou cancele.",
        )
    projetos_repo.transicionar(con, projeto, "lixeira")
    contas.auditar(con, acao="apagou_projeto", usuario_id=usuario.id, alvo=projeto.id)
    return Response(status_code=204)


@router.post("/{projeto_id}/restaurar")
def restaurar(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    _sessao: sessoes.Sessao = Depends(deps.exigir_csrf),
) -> dict:
    projeto = projetos_repo.exigir(con, projeto_id, usuario_id=usuario.id)
    if projeto.estado != "lixeira":
        raise ErroServidor(
            "SV-090",
            "Este projeto não está na lixeira.",
            status_http=409,
        )
    destino = "pronto" if projeto.versao_atual > 0 else "aguardando_zip"
    projeto = projetos_repo.transicionar(con, projeto, destino)
    return {"projeto": projeto.completo()}


@router.get("/{projeto_id}/versoes")
def versoes(
    projeto_id: str,
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> dict:
    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    versoes_sync.sincronizar_seguro(
        con, projeto.id, versoes_sync.raiz_do_projeto(estado, projeto.id)
    )
    return {"itens": projetos_repo.versoes(con, projeto.id)}


def _sanitizar_nome_download(nome: str, versao: int) -> str:
    import re

    # Remove qualquer tentativa de path traversal ou separador de diretório
    nome_limpo = re.sub(r"[\/\\]+", "_", str(nome or ""))
    nome_limpo = re.sub(r"\.\.+", "_", nome_limpo)
    # Remove dois-pontos e outros caracteres não seguros para nomes de arquivo
    nome_limpo = re.sub(r"[^a-zA-Z0-9_\-]", "_", nome_limpo)
    nome_limpo = re.sub(r"_+", "_", nome_limpo).strip("._")
    base = nome_limpo or "projeto"
    return f"{base}_v{versao:03d}.zip"


@router.get("/{projeto_id}/versoes/{versao}/pacote.zip")
def baixar_pacote_zip(
    projeto_id: str,
    versao: int,
    mxd: bool = Query(False),
    con: sqlite3.Connection = Depends(deps.pegar_con),
    usuario: contas.Usuario = Depends(deps.pegar_usuario),
    estado: deps.AppState = Depends(deps.pegar_estado),
) -> FileResponse:
    """Download do pacote de entrega completo (MXD/SHP/Mapas) de uma versão (W10-10)."""
    import hashlib
    import json as _json
    import os

    projeto = projetos_repo.exigir(
        con, projeto_id, usuario_id=usuario.id, admin=_admin(usuario)
    )
    linha_versao = con.execute(
        "SELECT * FROM versoes WHERE projeto_id = ? AND numero = ?",
        (projeto.id, versao),
    ).fetchone()
    if not linha_versao:
        raise ErroServidor("SV-240", "Versão não encontrada.", status_http=404)

    raiz = versoes_sync.raiz_do_projeto(estado, projeto.id)
    nome_download = _sanitizar_nome_download(projeto.nome, versao)

    artefatos_dict = _json.loads(linha_versao["artefatos"] or "{}")
    tem_mxd = bool(artefatos_dict.get("mxd"))
    mxd_conforme = bool(linha_versao["conforme"])

    # Gates para inclusão de MXD: opt-in explícito na query E MF_MXD=1 no ambiente
    env_gate = os.environ.get("MF_MXD") == "1"
    incluir_mxd_efetivo = bool(mxd) and env_gate and tem_mxd and mxd_conforme
    policy_str = "mxd" if incluir_mxd_efetivo else "nomxd"

    # Fingerprint controlado para cache separado e invalidação se artefatos/política mudarem
    conteudo_fp = (
        f"{linha_versao['artefatos']}|{linha_versao['conforme']}|"
        f"{incluir_mxd_efetivo}|{linha_versao['pasta']}"
    )
    fingerprint = hashlib.sha256(conteudo_fp.encode("utf-8")).hexdigest()[:12]

    # Nome físico: ID controlado + versão + policy + fingerprint
    nome_fisico = f"{projeto.id}_v{versao:03d}_{policy_str}_{fingerprint}.zip"
    pasta_pacotes = raiz / ".servidor" / "pacotes"
    pasta_pacotes.mkdir(parents=True, exist_ok=True)
    caminho_zip = pasta_pacotes / nome_fisico

    if not caminho_zip.exists():
        opcoes = OpcoesPacote(
            nome_imovel=projeto.nome,
            nome_template="Mapa",
            versao=versao,
            mxd_conforme=mxd_conforme,
            incluir_mxd=incluir_mxd_efetivo,
        )

        montar_pacote_do_projeto(
            raiz,
            str(linha_versao["pasta"]),
            artefatos_dict,
            caminho_zip,
            opcoes,
        )

    return FileResponse(
        path=caminho_zip,
        media_type="application/zip",
        filename=nome_download,
    )
