# F1-07 caminho 2 — `.mxd` sem ArcMap: leitura estrutural honestamente limitada.
#
# Um `.mxd` é um compound file OLE com objetos ArcObjects "picklados"; sem
# `arcpy` não dá para navegar a árvore de camadas de verdade (P3 do plano — taxa
# de acerto ainda não medida no acervo de 24 arquivos). O que dá para fazer sem
# fantasiar: varrer os bytes brutos por texto legível (a técnica do utilitário
# `strings`) e aplicar heurísticas simples sobre os candidatos. Isso já é real e
# útil (nomes de shapefile, `definitionQuery` sobrevivem como texto no blob) —
# só não é "ler a estrutura", e o retorno diz isso explicitamente.
#
# AP-09/vazamento: caminho absoluto de outra máquina (`C:\Users\...`) pode
# aparecer nos bytes — só o **nome do arquivo** sai daqui, nunca o caminho
# completo, porque este resultado pode entrar no contexto do chat mais tarde.

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.camadas.catalogo import camadas as camadas_catalogo
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.workspace.papeis import PAPEIS_CANONICOS

TAMANHO_MAXIMO_LEITURA = 60 * 1024 * 1024  # 60 MB — .mxd maior que isso, algo está errado
MIN_CARACTERES_STRING = 4
MAX_CANDIDATOS_SHAPEFILE = 30
MAX_CANDIDATOS_QUERY = 20
MAX_TAMANHO_QUERY = 200

_RE_ASCII = re.compile(rb"[\x20-\x7e]{%d,}" % MIN_CARACTERES_STRING)
_RE_UTF16LE = re.compile(rb"(?:[\x20-\x7e]\x00){%d,}" % MIN_CARACTERES_STRING)
_RE_SHP = re.compile(r"\.shp$", re.IGNORECASE)
_RE_QUERY = re.compile(r"['\"].*['\"]|=\s*['\"]")
_RE_CAMINHO = re.compile(r"[\\/]|^[A-Za-z]:")


@lru_cache(maxsize=1)
def _vocabulario_camadas() -> frozenset[str]:
    """Papéis locais (`workspace/papeis.py`) + sufixo do `layer` do catálogo (A13) —
    vocabulário real, não inventado, pra reconhecer nomes de camada nos bytes crus."""
    termos: set[str] = set()
    for conjunto in PAPEIS_CANONICOS.values():
        termos.update(conjunto)
    for camada in camadas_catalogo():
        layer = str(camada.get("layer") or "")
        sufixo = layer.split(":", 1)[-1].strip().upper()
        if sufixo:
            termos.add(sufixo)
    return frozenset(termos)


def _extrair_strings_brutas(dados: bytes) -> list[str]:
    ascii_ = [m.group().decode("ascii", errors="ignore") for m in _RE_ASCII.finditer(dados)]
    utf16 = [
        m.group().decode("utf-16-le", errors="ignore") for m in _RE_UTF16LE.finditer(dados)
    ]
    return ascii_ + utf16


def _candidatos_camada(strings: list[str]) -> list[str]:
    """`.shp` (nome do arquivo, nunca o caminho — AP-09) + tokens que batem com
    papel local ou `layer` do catálogo (ex.: `CAR_ATP`, `SIMCAR_D_AVN`)."""
    vocabulario = _vocabulario_camadas()
    vistos: dict[str, None] = {}
    for s in strings:
        texto = s.strip().strip('"').strip("'")
        if not texto:
            continue
        if _RE_SHP.search(texto):
            candidato = Path(texto.replace("\\", "/")).name  # nunca o caminho completo
        elif texto.upper() in vocabulario:
            candidato = texto.upper()
        else:
            continue
        if candidato not in vistos:
            vistos[candidato] = None
        if len(vistos) >= MAX_CANDIDATOS_SHAPEFILE:
            break
    return list(vistos)


def _candidatos_definition_query(strings: list[str]) -> list[str]:
    vistos: dict[str, None] = {}
    for s in strings:
        texto = s.strip()
        if len(texto) < 6 or len(texto) > MAX_TAMANHO_QUERY:
            continue
        if _RE_CAMINHO.search(texto):  # descarta o que parece caminho, não SQL
            continue
        if "=" not in texto or not _RE_QUERY.search(texto):
            continue
        if texto not in vistos:
            vistos[texto] = None
        if len(vistos) >= MAX_CANDIDATOS_QUERY:
            break
    return list(vistos)


def extrair(caminho: Path) -> dict[str, Any]:
    """Varredura de strings do `.mxd` bruto — nunca abre com `arcpy` (não existe aqui)."""
    if not caminho.is_file():
        raise ErroNucleo("NU-001", f".mxd não encontrado: {caminho.name}")
    tamanho = caminho.stat().st_size
    if tamanho == 0:
        raise ErroNucleo("NU-001", f".mxd vazio: {caminho.name}")
    if tamanho > TAMANHO_MAXIMO_LEITURA:
        raise ErroNucleo(
            "NU-001",
            f".mxd maior que o esperado ({tamanho} bytes) — leitura recusada.",
            {"tamanho": tamanho},
        )

    dados = caminho.read_bytes()
    strings = _extrair_strings_brutas(dados)
    camadas = _candidatos_camada(strings)
    queries = _candidatos_definition_query(strings)

    return {
        "fonte": "mxd_strings",
        "estrutura_completa": False,
        "candidatos_camada": camadas,
        "candidatos_definition_query": queries,
        "total_strings_lidas": len(strings),
        "avisos": [
            "Leitura por varredura de strings (sem ArcMap) — não é parsing estrutural. "
            "Camadas, CRS do data frame e extent exatos exigem ArcMap/arcpy (P3, F1-07).",
        ],
    }
