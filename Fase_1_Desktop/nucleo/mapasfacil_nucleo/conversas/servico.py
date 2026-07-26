# F1-17 §Métodos NDJSON — handlers `chat.*` de histórico.
#
# Nenhum destes tem gate de sessão (F1-14): ler o próprio histórico offline, ou com
# sessão expirada, é permitido. Quem ganha gate é `chat.enviar`, que é do M7 e não
# existe aqui — este arquivo **não** fala com IA, não emite `chat.delta` e não
# gera mensagem de assistente.
#
# O workspace é opcional em tudo: o app pode ter conversa antes de conectar pasta,
# e a sidebar lista os chats de todas as pastas (D13).

from __future__ import annotations

from typing import Any

from mapasfacil_nucleo.conversas import repositorio as repo
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace import servico as workspace_servico


def _texto_opcional(params: dict[str, Any], chave: str) -> str | None:
    valor = params.get(chave)
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ErroNucleo("NU-243", f"Parâmetro '{chave}' precisa ser texto.")
    return valor or None


def _id_conversa(params: dict[str, Any]) -> str:
    valor = params.get("conversation_id")
    if not isinstance(valor, str) or not valor:
        raise ErroNucleo("NU-243", "Parâmetro 'conversation_id' é obrigatório.")
    return valor


def _inteiro(params: dict[str, Any], chave: str, padrao: int | None = None) -> int | None:
    valor = params.get(chave, padrao)
    if valor is None:
        return None
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErroNucleo("NU-243", f"Parâmetro '{chave}' precisa ser um inteiro.")
    return valor


def _booleano(params: dict[str, Any], chave: str, padrao: bool) -> bool:
    valor = params.get(chave, padrao)
    if not isinstance(valor, bool):
        raise ErroNucleo("NU-243", f"Parâmetro '{chave}' precisa ser booleano.")
    return valor


def _workspace(params: dict[str, Any]) -> str | None:
    """`workspace` explícito vence; sem ele, usa a pasta aberta, se houver."""
    explicito = _texto_opcional(params, "workspace")
    if explicito:
        return explicito
    estado = workspace_servico.estado_atual()
    return None if estado is None else str(estado.guard.raiz)


def criar_conversa(params: dict[str, Any]) -> dict[str, Any]:
    return repo.atual().criar_conversa(
        workspace=_workspace(params),
        title=_texto_opcional(params, "title"),
        conta_id=_texto_opcional(params, "conta_id"),
        modelo=_texto_opcional(params, "modelo"),
    )


def listar_conversas(params: dict[str, Any]) -> dict[str, Any]:
    # Sem `workspace` nos params a lista é global — é o "todos os chats" da sidebar.
    # O filtro "só desta pasta" é o app mandando o caminho.
    return repo.atual().listar_conversas(
        workspace=_texto_opcional(params, "workspace"),
        incluir_arquivadas=_booleano(params, "incluir_arquivadas", False),
        limite=_inteiro(params, "limite", 50) or 50,
        antes_de=_texto_opcional(params, "antes_de"),
    )


def abrir_conversa(params: dict[str, Any]) -> dict[str, Any]:
    return repo.atual().abrir_conversa(
        _id_conversa(params),
        limite=_inteiro(params, "limite", 30) or 30,
    )


def carregar_anteriores(params: dict[str, Any]) -> dict[str, Any]:
    antes_de_seq = _inteiro(params, "antes_de_seq")
    if antes_de_seq is None:
        raise ErroNucleo("NU-243", "Parâmetro 'antes_de_seq' é obrigatório.")
    return repo.atual().carregar_anteriores(
        _id_conversa(params),
        antes_de_seq=antes_de_seq,
        limite=_inteiro(params, "limite", 50) or 50,
    )


def renomear(params: dict[str, Any]) -> dict[str, Any]:
    title = _texto_opcional(params, "title")
    if not title:
        raise ErroNucleo("NU-243", "Parâmetro 'title' é obrigatório.")
    return repo.atual().renomear(_id_conversa(params), title)


def arquivar(params: dict[str, Any]) -> dict[str, Any]:
    return repo.atual().arquivar(
        _id_conversa(params),
        _booleano(params, "arquivada", True),
    )


def apagar(params: dict[str, Any]) -> dict[str, Any]:
    return repo.atual().apagar(_id_conversa(params))


def ramificar(params: dict[str, Any]) -> dict[str, Any]:
    a_partir_do_seq = _inteiro(params, "a_partir_do_seq")
    if a_partir_do_seq is None:
        raise ErroNucleo("NU-243", "Parâmetro 'a_partir_do_seq' é obrigatório.")
    return repo.atual().ramificar(
        _id_conversa(params),
        a_partir_do_seq=a_partir_do_seq,
        title=_texto_opcional(params, "title"),
    )


def buscar(params: dict[str, Any]) -> dict[str, Any]:
    termo = _texto_opcional(params, "termo")
    if not termo:
        raise ErroNucleo("NU-243", "Parâmetro 'termo' é obrigatório.")
    return repo.atual().buscar(
        termo,
        workspace=_texto_opcional(params, "workspace"),
        limite=_inteiro(params, "limite", 30) or 30,
    )


def registrar_mensagem(params: dict[str, Any]) -> dict[str, Any]:
    """`chat.registrar_mensagem` — grava mensagem **já existente** no histórico.

    Não é `chat.enviar` (M7): não chama IA, não faz streaming e não inventa resposta.
    É o que o modo determinístico usa para registrar "usei o modelo X da galeria e
    saiu o MapSpec Y" — a F1-17 exige que a galeria também registre conversa.
    """
    conteudo = params.get("conteudo")
    if not isinstance(conteudo, str) or not conteudo:
        raise ErroNucleo("NU-243", "Parâmetro 'conteudo' é obrigatório.")
    papel = params.get("papel", "usuario")
    if not isinstance(papel, str):
        raise ErroNucleo("NU-243", "Parâmetro 'papel' precisa ser texto.")
    return repo.atual().acrescentar_mensagem(
        _id_conversa(params),
        papel=papel,
        conteudo=conteudo,
        mapspec_id=_texto_opcional(params, "mapspec_id"),
        mapspec_versao=_inteiro(params, "mapspec_versao"),
    )
