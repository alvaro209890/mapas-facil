# Edição versionada do MapSpec pelas tools do agente (F1-06 §Versionamento por edição).
#
# Regra: nenhuma tool muta o MapSpec no lugar. Toda alteração produz uma NOVA
# versão (`versao + 1`, `parent_id` apontando para a anterior), validada antes de
# ser adotada — MapSpec inválido nunca vira estado. O retorno ao LLM é o diff
# descrito em português, nunca o JSON inteiro (AP-06 / §3 do plano).

from __future__ import annotations

import copy
from typing import Any, Callable

from mapasfacil_nucleo.mapspec.diff import diff as mapspec_diff
from mapasfacil_nucleo.mapspec.validar import validar as validar_mapspec
from mapasfacil_nucleo.protocolo import novo_id

# rótulo legível por caminho do diff (prefixo → texto)
_ROTULOS: dict[str, str] = {
    "titulo": "título",
    "escala": "escala",
    "basemap": "basemap",
    "tabela": "tabela",
    "metadados": "metadados",
    "imovel": "imóvel",
    "saidas": "saídas",
    "elementos_layout": "elemento de layout",
    "camadas": "camadas",
}


class EdicaoInvalida(Exception):
    """A nova versão não passou na validação — a versão anterior continua valendo."""

    def __init__(self, erros: list[dict[str, Any]]) -> None:
        super().__init__("MapSpec resultante inválido")
        self.erros = erros


def nova_versao(
    mapspec: dict[str, Any],
    mutar: Callable[[dict[str, Any]], None],
    *,
    fontes_locais: frozenset[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Aplica `mutar` sobre uma cópia e devolve `(novo_mapspec, diff)`.

    Levanta `EdicaoInvalida` se o resultado não validar — o chamador devolve o
    erro tipado ao modelo e mantém a versão anterior.
    """
    candidato = copy.deepcopy(mapspec)
    mutar(candidato)
    candidato["parent_id"] = mapspec.get("id")
    candidato["id"] = novo_id()
    candidato["versao"] = int(mapspec.get("versao") or 1) + 1

    resultado = validar_mapspec(candidato, fontes_locais=fontes_locais)
    if not resultado["valido"]:
        raise EdicaoInvalida(resultado["erros"])

    return candidato, mapspec_diff(mapspec, candidato)


_CAMPOS_DE_VERSAO = frozenset({"id", "versao", "parent_id"})


def operacoes_de_conteudo(diff: dict[str, Any]) -> list[dict[str, Any]]:
    """Operações do diff sem o ruído de versionamento (`id`, `versao`, `parent_id`)."""
    return [
        op
        for op in (diff.get("operacoes") or [])
        if str(op.get("caminho") or "") not in _CAMPOS_DE_VERSAO
    ]


def descrever_diff(diff: dict[str, Any], *, limite: int = 12) -> list[str]:
    """Diff → frases em português, prontas para a UI e para o modelo.

    Exemplo: `estilo da camada #1: avn → avn_claro`.
    """
    linhas: list[str] = []
    for op in operacoes_de_conteudo(diff):
        caminho = str(op.get("caminho") or "")
        antes = op.get("antes")
        depois = op.get("depois")
        rotulo = _descrever_caminho(caminho)
        if op.get("op") == "adicionar":
            linhas.append(f"{rotulo}: adicionado ({_valor(depois)})")
        elif op.get("op") == "remover":
            linhas.append(f"{rotulo}: removido ({_valor(antes)})")
        else:
            linhas.append(f"{rotulo}: {_valor(antes)} → {_valor(depois)}")
        if len(linhas) >= limite:
            linhas.append("…")
            break
    return linhas


def _descrever_caminho(caminho: str) -> str:
    partes = caminho.split("/")
    raiz = partes[0]
    if raiz == "elementos_layout" and len(partes) > 1:
        return f"elemento “{partes[1]}”"
    if raiz == "camadas" and len(partes) >= 3:
        return f"{partes[2]} da camada #{partes[1]}"
    if raiz == "camadas" and len(partes) == 2:
        return f"camada #{partes[1]}"
    if len(partes) > 1:
        return f"{_ROTULOS.get(raiz, raiz)} · {'/'.join(partes[1:])}"
    return _ROTULOS.get(raiz, raiz)


def _valor(valor: Any) -> str:
    if valor is None:
        return "nenhum"
    if isinstance(valor, bool):
        return "ligado" if valor else "desligado"
    if isinstance(valor, (list, dict)):
        return f"{len(valor)} item(ns)"
    return str(valor)


def resumo_versao(mapspec: dict[str, Any], diff: dict[str, Any]) -> dict[str, Any]:
    """Envelope padrão devolvido pelas tools de edição — sem geometria, sem JSON inteiro."""
    return {
        "mapspec_id": mapspec.get("id"),
        "versao": mapspec.get("versao"),
        "parent_id": mapspec.get("parent_id"),
        "alteracoes": descrever_diff(diff),
        "total_alteracoes": len(operacoes_de_conteudo(diff)),
    }
