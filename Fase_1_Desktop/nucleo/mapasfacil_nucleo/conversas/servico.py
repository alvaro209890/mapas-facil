# Handlers NDJSON `chat.*` de histórico (F1-17 / M6). Sem gate de sessão.

from __future__ import annotations

from pathlib import Path
from typing import Any

from mapasfacil_nucleo.conversas.repositorio import RepositorioConversas
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace import servico as workspace_servico

_repo: RepositorioConversas | None = None
_repo_dir: Path | None = None


def configurar_diretorio(diretorio: str | Path | None) -> None:
    """Usado por testes e pelo Electron via env; reinicia o singleton."""
    global _repo, _repo_dir
    if _repo is not None:
        _repo.fechar()
    _repo = None
    _repo_dir = Path(diretorio).expanduser() if diretorio else None


def repositorio() -> RepositorioConversas:
    global _repo
    if _repo is None:
        _repo = RepositorioConversas(_repo_dir)
    return _repo


def _workspace_param(params: dict[str, Any]) -> str | None:
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    if workspace:
        return workspace
    estado = workspace_servico.estado_atual()
    if estado is not None:
        caminho = estado.indice.get("raiz")
        if isinstance(caminho, str):
            return caminho
    return None


def _id_obrigatorio(params: dict[str, Any]) -> str:
    cid = params.get("conversation_id")
    if not isinstance(cid, str) or not cid:
        raise ErroNucleo("NU-001", "Parâmetro 'conversation_id' é obrigatório.")
    return cid


def criar_conversa(params: dict[str, Any]) -> dict[str, Any]:
    title = params.get("title")
    if title is not None and not isinstance(title, str):
        raise ErroNucleo("NU-001", "Parâmetro 'title' inválido.")
    workspace = _workspace_param(params)
    return repositorio().criar_conversa(workspace=workspace, title=title)


def listar_conversas(params: dict[str, Any]) -> dict[str, Any]:
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    # filtro explícito: se veio workspace use; se chave ausente e há pasta aberta,
    # a UI decide — aqui `None` lista todas (comportamento "todos os chats")
    incluir = bool(params.get("incluir_arquivadas", False))
    limite = params.get("limite", 50)
    antes_de = params.get("antes_de")
    if antes_de is not None and not isinstance(antes_de, str):
        raise ErroNucleo("NU-001", "Parâmetro 'antes_de' inválido.")
    if not isinstance(limite, int):
        raise ErroNucleo("NU-001", "Parâmetro 'limite' inválido.")
    return repositorio().listar_conversas(
        workspace=workspace,
        incluir_arquivadas=incluir,
        limite=limite,
        antes_de=antes_de,
    )


def abrir_conversa(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    limite = params.get("limite", 30)
    if not isinstance(limite, int):
        raise ErroNucleo("NU-001", "Parâmetro 'limite' inválido.")
    return repositorio().abrir_conversa(cid, limite=limite)


def carregar_anteriores(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    antes = params.get("antes_de_seq")
    if not isinstance(antes, int):
        raise ErroNucleo("NU-001", "Parâmetro 'antes_de_seq' é obrigatório (inteiro).")
    limite = params.get("limite", 50)
    if not isinstance(limite, int):
        raise ErroNucleo("NU-001", "Parâmetro 'limite' inválido.")
    return repositorio().carregar_anteriores(cid, antes_de_seq=antes, limite=limite)


def renomear(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    title = params.get("title")
    if not isinstance(title, str):
        raise ErroNucleo("NU-001", "Parâmetro 'title' é obrigatório.")
    return repositorio().renomear(cid, title)


def arquivar(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    if "arquivada" not in params or not isinstance(params["arquivada"], bool):
        raise ErroNucleo("NU-001", "Parâmetro 'arquivada' (bool) é obrigatório.")
    return repositorio().arquivar(cid, params["arquivada"])


def apagar(params: dict[str, Any]) -> dict[str, Any]:
    return repositorio().apagar(_id_obrigatorio(params))


def ramificar(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    seq = params.get("a_partir_do_seq")
    if not isinstance(seq, int):
        raise ErroNucleo("NU-001", "Parâmetro 'a_partir_do_seq' é obrigatório (inteiro).")
    title = params.get("title")
    if title is not None and not isinstance(title, str):
        raise ErroNucleo("NU-001", "Parâmetro 'title' inválido.")
    return repositorio().ramificar(cid, a_partir_do_seq=seq, title=title)


def buscar(params: dict[str, Any]) -> dict[str, Any]:
    termo = params.get("termo")
    if not isinstance(termo, str):
        raise ErroNucleo("NU-001", "Parâmetro 'termo' é obrigatório.")
    workspace = params.get("workspace")
    if workspace is not None and not isinstance(workspace, str):
        raise ErroNucleo("NU-001", "Parâmetro 'workspace' inválido.")
    limite = params.get("limite", 30)
    if not isinstance(limite, int):
        raise ErroNucleo("NU-001", "Parâmetro 'limite' inválido.")
    return repositorio().buscar(termo, workspace=workspace, limite=limite)


# Gravação de mensagem para modo determinístico / testes (galeria também registra).
# Não é chat.enviar (M7) — não chama LLM nem exige sessão.
def gravar_mensagem(params: dict[str, Any]) -> dict[str, Any]:
    cid = _id_obrigatorio(params)
    papel = params.get("papel")
    conteudo = params.get("conteudo")
    if not isinstance(papel, str) or not isinstance(conteudo, str):
        raise ErroNucleo("NU-001", "Parâmetros 'papel' e 'conteudo' são obrigatórios.")
    return repositorio().adicionar_mensagem(
        cid,
        papel=papel,
        conteudo=conteudo,
        mapspec_id=params.get("mapspec_id") if isinstance(params.get("mapspec_id"), str) else None,
        mapspec_versao=params.get("mapspec_versao")
        if isinstance(params.get("mapspec_versao"), int)
        else None,
        cancelada=bool(params.get("cancelada", False)),
    )
