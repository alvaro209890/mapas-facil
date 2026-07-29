from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator
from pyproj import CRS

from mapasfacil_nucleo.config import ESCALAS_PERMITIDAS, PASTAS_ESCRITA, caminho_shared
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.fsguard import nome_base_ascii_valido

# Nomes curtos que os primeiros MapSpecs usavam, antes de a paleta ter um
# estilo por camada. Continuam válidos para não invalidar spec já gravado.
ESTILOS_LEGADOS: frozenset[str] = frozenset({"tipologia", "embargo", "ti", "uc"})


def _estilos_permitidos() -> frozenset[str]:
    """A paleta oficial é `motores/estilos.py` — aqui só se **lê** de lá.

    Manter a lista duplicada custou um bug real: a série ganhou 12 estilos novos
    (medidos dos modelos) e o validador reprovava `limite_estadual` com `NU-211`,
    porque tinha uma cópia de 9 nomes de 2026-07-25.
    """
    from mapasfacil_nucleo.motores.estilos import ESTILOS

    return frozenset(ESTILOS) | ESTILOS_LEGADOS


ESTILOS_PERMITIDOS: frozenset[str] = _estilos_permitidos()

# Plano 02: =, <>, >, <, >=, <=, IN, LIKE — aceitamos != como sinônimo de <>
OPERADORES_FILTRO = frozenset({"=", "<>", "!=", ">", "<", ">=", "<=", "IN", "LIKE"})

CRS_GEOGRAFICOS_COMUNS = frozenset({"EPSG:4326", "EPSG:4674", "EPSG:4269", "EPSG:3889"})


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    caminho = caminho_shared("schemas", "mapspec.schema.json")
    with caminho.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _catalogo_ids() -> frozenset[str]:
    caminho = caminho_shared("catalog", "camadas.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return frozenset(item["id"] for item in dados.get("camadas", []))


@lru_cache(maxsize=1)
def _template_ids() -> frozenset[str]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return frozenset(item["id"] for item in dados.get("templates", []))


@lru_cache(maxsize=1)
def _templates_por_id() -> dict[str, dict[str, Any]]:
    caminho = caminho_shared("templates", "MANIFEST.json")
    with caminho.open(encoding="utf-8") as fh:
        dados = json.load(fh)
    return {item["id"]: item for item in dados.get("templates", []) if item.get("id")}


def _erro(codigo: str, mensagem: str, campo: str | None = None) -> dict[str, str]:
    item = {"codigo": codigo, "mensagem": mensagem}
    if campo:
        item["campo"] = campo
    return item


def _crs_eh_geografico(crs: str) -> bool:
    chave = crs.strip().upper()
    if chave in CRS_GEOGRAFICOS_COMUNS:
        return True
    try:
        return bool(CRS.from_user_input(crs).is_geographic)
    except Exception:
        return False


def _pasta_saida_ok(pasta: str) -> bool:
    """Relativo ao workspace e sob pasta de escrita (Mapas/MXD/SHP/_extraido) ou nome simples."""
    if not pasta or pasta.startswith(("/", "\\")) or ".." in Path(pasta).parts:
        return False
    # UNC / unidade absoluta estilo Windows
    if len(pasta) >= 2 and pasta[1] == ":":
        return False
    primeiro = Path(pasta).parts[0]
    return primeiro in PASTAS_ESCRITA or pasta in PASTAS_ESCRITA


def validar_schema(mapspec: dict[str, Any]) -> list[dict[str, str]]:
    validator = Draft202012Validator(_schema())
    erros: list[dict[str, str]] = []
    for err in sorted(validator.iter_errors(mapspec), key=lambda e: list(e.path)):
        caminho = "/".join(str(p) for p in err.path) or "(raiz)"
        erros.append(_erro("NU-201", f"{caminho}: {err.message}", caminho))
    return erros


def validar_regras(
    mapspec: dict[str, Any],
    *,
    fontes_locais: frozenset[str] | None = None,
) -> list[dict[str, str]]:
    erros: list[dict[str, str]] = []

    template = mapspec.get("template")
    if isinstance(template, str) and template not in _template_ids():
        erros.append(_erro("NU-205", f"Template desconhecido: {template}", "template"))
    elif isinstance(template, str):
        tpl = _templates_por_id().get(template) or {}
        if tpl.get("sha256") is None:
            # Aviso estrutural: template ainda a_preparar (não bloqueia PDF nativo)
            pass  # ver avisos em validar()

    escala = mapspec.get("escala")
    if escala is not None and escala != "auto":
        if not isinstance(escala, int) or escala not in ESCALAS_PERMITIDAS:
            erros.append(
                _erro(
                    "NU-220",
                    f"Escala {escala!r} não está na lista permitida.",
                    "escala",
                )
            )

    crs = mapspec.get("crs")
    if isinstance(crs, str) and _crs_eh_geografico(crs):
        erros.append(
            _erro(
                "NU-221",
                f"CRS geográfico não é permitido em crs (use UTM projetado): {crs}",
                "crs",
            )
        )

    elementos = mapspec.get("elementos_layout") or {}
    if elementos.get("minimapa"):
        municipio = (mapspec.get("imovel") or {}).get("municipio") or {}
        nome_mun = municipio.get("nome")
        if not isinstance(nome_mun, str) or not nome_mun.strip():
            erros.append(
                _erro(
                    "NU-222",
                    "imovel.municipio.nome é obrigatório quando minimapa está ligado.",
                    "imovel/municipio/nome",
                )
            )

    for idx, meta in enumerate(mapspec.get("metadados") or []):
        if not isinstance(meta, dict):
            continue
        valor = meta.get("valor")
        if valor is None or (isinstance(valor, str) and not str(valor).strip()):
            erros.append(
                _erro(
                    "NU-223",
                    "metadados sem valor vazio.",
                    f"metadados[{idx}]/valor",
                )
            )

    camadas = mapspec.get("camadas") or []
    for idx, camada in enumerate(camadas):
        prefixo = f"camadas[{idx}]"
        estilo = camada.get("estilo")
        if isinstance(estilo, str) and estilo not in ESTILOS_PERMITIDOS:
            erros.append(
                _erro(
                    "NU-211",
                    f"Estilo desconhecido: {estilo}",
                    f"{prefixo}/estilo",
                )
            )

        fonte = camada.get("fonte")
        if isinstance(fonte, str):
            if fonte.startswith("catalogo."):
                cat_id = fonte.split(".", 1)[1]
                if cat_id not in _catalogo_ids():
                    erros.append(
                        _erro(
                            "NU-210",
                            f"Camada de catálogo inexistente: {cat_id}",
                            f"{prefixo}/fonte",
                        )
                    )
            elif fonte.startswith("local."):
                local_id = fonte.split(".", 1)[1]
                if fontes_locais is not None and local_id not in fontes_locais:
                    erros.append(
                        _erro(
                            "NU-212",
                            f"Fonte local ausente no workspace: {local_id}",
                            f"{prefixo}/fonte",
                        )
                    )
            else:
                erros.append(
                    _erro(
                        "NU-213",
                        f"Fonte precisa ser local.* ou catalogo.*: {fonte}",
                        f"{prefixo}/fonte",
                    )
                )

        filtro = camada.get("filtro")
        if isinstance(filtro, dict):
            operador = filtro.get("operador")
            if operador not in OPERADORES_FILTRO:
                erros.append(
                    _erro(
                        "NU-214",
                        f"Operador de filtro inválido: {operador!r}",
                        f"{prefixo}/filtro/operador",
                    )
                )

    saida = mapspec.get("saida") or {}
    nome_base = saida.get("nome_base")
    if isinstance(nome_base, str) and not nome_base_ascii_valido(nome_base):
        erros.append(
            _erro(
                "NU-215",
                "saida.nome_base precisa ser ASCII sem acentos.",
                "saida/nome_base",
            )
        )

    pasta = saida.get("pasta")
    if isinstance(pasta, str) and not _pasta_saida_ok(pasta):
        erros.append(
            _erro(
                "NU-224",
                "saida.pasta precisa ser relativa ao workspace e sob Mapas/MXD/SHP/_extraido.",
                "saida/pasta",
            )
        )

    tabela = mapspec.get("tabela")
    if isinstance(tabela, dict):
        colunas = tabela.get("colunas") or []
        for i, linha in enumerate(tabela.get("linhas") or []):
            if len(linha) != len(colunas):
                erros.append(
                    _erro(
                        "NU-216",
                        f"Linha {i} da tabela tem {len(linha)} colunas; esperado {len(colunas)}.",
                        f"tabela/linhas[{i}]",
                    )
                )

    return erros


def _avisos(mapspec: dict[str, Any]) -> list[dict[str, str]]:
    avisos: list[dict[str, str]] = []
    template = mapspec.get("template")
    if isinstance(template, str):
        tpl = _templates_por_id().get(template) or {}
        if tpl.get("sha256") is None:
            avisos.append(
                _erro(
                    "AG-030",
                    f"Template {template} ainda sem sha256 (status={tpl.get('status')}).",
                    "template",
                )
            )
    return avisos


def validar(
    mapspec: dict[str, Any],
    *,
    fontes_locais: frozenset[str] | None = None,
) -> dict[str, Any]:
    erros = validar_schema(mapspec)
    if not erros:
        erros = validar_regras(mapspec, fontes_locais=fontes_locais)
    return {
        "valido": len(erros) == 0,
        "erros": erros,
        "avisos": _avisos(mapspec) if not erros else [],
    }


def validar_ou_erro(mapspec: dict[str, Any]) -> None:
    resultado = validar(mapspec)
    if not resultado["valido"]:
        primeiro = resultado["erros"][0]
        raise ErroNucleo(primeiro["codigo"], primeiro["mensagem"], {"erros": resultado["erros"]})
