"""Raiz de dados do Mapas Fácil neste PC.

Layout (pedido do produto):

    <Documentos>/database/MapasFacil/
      contas/contas.sqlite
      provisao.local.json          # chave do projeto (gitignored, nunca no repo)
      <slug-do-usuario>/
        chats/                     # chats.sqlite + anexos + mapspecs
        mxd/ pdf/ xlsx/ artefatos/
        Mapas/ MXD/ SHP/           # saídas estilo workspace
        cache/
        workspace/                 # pasta padrão aberta após login
        config.json

Overrides:
  MAPASFACIL_DATABASE_ROOT — raiz do sistema (em vez de Documentos/database/MapasFacil)
  MAPASFACIL_DADOS         — legado; se setado sem DATABASE_ROOT, vira a raiz
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

NOME_SISTEMA = "MapasFacil"

SUBPASTAS_USUARIO: tuple[str, ...] = (
    "chats",
    "chats/anexos",
    "chats/mapspecs",
    "mxd",
    "pdf",
    "xlsx",
    "artefatos",
    "Mapas",
    "MXD",
    "SHP",
    "cache",
    "workspace",
)

_EXT_DESTINO: dict[str, str] = {
    ".mxd": "mxd",
    ".pdf": "pdf",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".png": "artefatos",
    ".json": "artefatos",
}


def pasta_documentos() -> Path:
    """Pasta Documentos do usuário (Linux: Documentos ou Documents)."""
    home = Path.home()
    for nome in ("Documentos", "Documents"):
        candidata = home / nome
        if candidata.is_dir():
            return candidata
    # Windows: ~\Documents quase sempre existe; se não, cria Documents.
    docs = home / "Documents"
    docs.mkdir(parents=True, exist_ok=True)
    return docs


def raiz_sistema() -> Path:
    """``…/database/MapasFacil`` — contas + pastas por usuário."""
    env_root = os.environ.get("MAPASFACIL_DATABASE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    env_dados = os.environ.get("MAPASFACIL_DADOS")
    if env_dados:
        return Path(env_dados).expanduser().resolve()
    return (pasta_documentos() / "database" / NOME_SISTEMA).resolve()


def slug_usuario(email: str) -> str:
    """Nome de pasta seguro a partir do e-mail (minúsculo, sem path traversal)."""
    bruto = (email or "").strip().lower()
    if not bruto:
        return "usuario"
    # joao@firma.com.br → joao_at_firma_com_br
    texto = bruto.replace("@", "_at_").replace(".", "_")
    texto = re.sub(r"[^a-z0-9_+\-]+", "_", texto)
    texto = re.sub(r"_+", "_", texto).strip("_")
    return (texto or "usuario")[:120]


def pasta_contas() -> Path:
    return raiz_sistema() / "contas"


def caminho_provisao() -> Path:
    """Arquivo local com a chave do projeto (não versionado)."""
    return raiz_sistema() / "provisao.local.json"


def pasta_usuario(*, email: str, raiz: Path | None = None) -> Path:
    return (raiz or raiz_sistema()) / slug_usuario(email)


def garantir_arvore_sistema(raiz: Path | None = None) -> Path:
    base = raiz or raiz_sistema()
    (base / "contas").mkdir(parents=True, exist_ok=True)
    return base


def garantir_arvore_usuario(*, email: str, raiz: Path | None = None) -> Path:
    """Cria a árvore completa do usuário e devolve a pasta dele."""
    base = garantir_arvore_sistema(raiz)
    pasta = pasta_usuario(email=email, raiz=base)
    for sub in SUBPASTAS_USUARIO:
        (pasta / sub).mkdir(parents=True, exist_ok=True)
    return pasta


def pasta_chats_usuario(*, email: str, raiz: Path | None = None) -> Path:
    return garantir_arvore_usuario(email=email, raiz=raiz) / "chats"


def pasta_workspace_usuario(*, email: str, raiz: Path | None = None) -> Path:
    """Workspace padrão do usuário (onde MXD/PDF nascem se não abrir outra pasta)."""
    return garantir_arvore_usuario(email=email, raiz=raiz) / "workspace"


def _copiar_se_arquivo(origem: Path, destino_dir: Path) -> Path | None:
    if not origem.is_file():
        return None
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / origem.name
    if origem.resolve() == destino.resolve():
        return destino
    shutil.copy2(origem, destino)
    return destino


def arquivar_artefatos_do_job(
    artefatos: dict[str, Any],
    *,
    raiz_workspace: Path,
    pasta_usuario_destino: Path | None,
) -> list[str]:
    """Copia MXD/PDF/XLSX/etc. do job para as pastas do usuário.

    Devolve caminhos relativos à pasta do usuário (para log). Não falha o job
    se a cópia der errado — só registra o que conseguiu.
    """
    if pasta_usuario_destino is None:
        return []
    copiados: list[str] = []
    candidatos: list[Path] = []

    def _add(valor: Any) -> None:
        if isinstance(valor, str) and valor.strip():
            p = Path(valor)
            if not p.is_absolute():
                p = raiz_workspace / p
            candidatos.append(p)
        elif isinstance(valor, dict):
            for v in valor.values():
                _add(v)
        elif isinstance(valor, list):
            for v in valor:
                _add(v)

    _add(artefatos)

    vistos: set[Path] = set()
    for origem in candidatos:
        try:
            resolvido = origem.resolve()
        except OSError:
            continue
        if resolvido in vistos:
            continue
        vistos.add(resolvido)
        destino_nome = _EXT_DESTINO.get(resolvido.suffix.lower(), "artefatos")
        try:
            dest = _copiar_se_arquivo(resolvido, pasta_usuario_destino / destino_nome)
        except OSError:
            continue
        if dest is not None:
            try:
                copiados.append(str(dest.relative_to(pasta_usuario_destino)))
            except ValueError:
                copiados.append(str(dest))
    return copiados


def ler_provisao_arquivo(caminho: Path | None = None) -> dict[str, str]:
    """Lê provisao.local.json sem nunca logar valores."""
    alvo = caminho or caminho_provisao()
    if not alvo.is_file():
        return {}
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(dados, dict):
        return {}
    saida: dict[str, str] = {}
    for chave in ("deepseek_api_key", "sema_authkey", "planet_api_key"):
        valor = dados.get(chave)
        if isinstance(valor, str) and valor.strip():
            saida[chave] = valor.strip()
    return saida


def gravar_provisao_arquivo(dados: dict[str, str], caminho: Path | None = None) -> Path:
    """Grava só chaves não vazias. Cria a árvore do sistema se preciso."""
    garantir_arvore_sistema()
    alvo = caminho or caminho_provisao()
    limpo = {k: v.strip() for k, v in dados.items() if isinstance(v, str) and v.strip()}
    alvo.write_text(json.dumps(limpo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(alvo, 0o600)
    except OSError:
        pass
    return alvo
