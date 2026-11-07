from __future__ import annotations

import datetime
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.agente.aprovacao import (
    GerenciadorAprovacao,
    _calcular_hash_arquivo,
    gerenciador_aprovacao_padrao,
)
from mapasfacil_nucleo.agente.registro import RegistroFerramentas, _erro, _ok
from mapasfacil_nucleo.config import CARACTERES_INVALIDOS_WINDOWS
from mapasfacil_nucleo.protocolo import Emissor

ARQUIVOS_BLOQUEADOS = frozenset(
    {
        ".env",
        "servidor.env",
        "secrets.local.json",
        "secrets.json",
        "auth.json",
    }
)
PASTAS_ESTRUTURA_PROTEGIDA = frozenset({"Mapas", "SHP", "XLSX"})


def _obter_workspace(ctx: dict[str, Any]) -> Path:
    ws = ctx.get("workspace")
    if ws is None:
        from mapasfacil_nucleo.workspace import servico as workspace_servico

        estado = workspace_servico.estado_atual()
        if estado is not None:
            return estado.pasta
        raise ValueError("Workspace não fornecido no contexto.")
    return Path(ws).resolve()


def _resolver_caminho_seguro(
    caminho_rel: str,
    ws_root: Path,
    *,
    permitir_interno: bool = False,
    escrita: bool = False,
) -> Path:
    texto = str(caminho_rel or "").strip()
    if not texto:
        raise ValueError("Caminho não pode ser vazio.")

    # 1. Checagem de caminhos absolutos em todas as plataformas (Windows e POSIX)
    if texto.startswith("/") or texto.startswith("\\"):
        raise ValueError(f"Caminhos absolutos não são permitidos: '{caminho_rel}'.")
    if re.match(r"^[a-zA-Z]:", texto):
        raise ValueError(f"Caminhos com letra de unidade não são permitidos: '{caminho_rel}'.")
    if texto.startswith("\\\\") or texto.startswith("//"):
        raise ValueError("Caminhos UNC não são permitidos.")

    # 2. Path traversal com / ou \
    texto_norm = texto.replace("\\", "/")
    partes_raw = [p for p in texto_norm.split("/") if p]
    if ".." in partes_raw or any(p.startswith("..") for p in partes_raw):
        raise ValueError("Path traversal ('..') não é permitido.")

    # 3. Caracteres inválidos
    if any(ch in CARACTERES_INVALIDOS_WINDOWS for ch in texto):
        raise ValueError("Caminho contém caracteres inválidos.")

    # 4. Detecção estrita de Symlinks antes de seguir qualquer resolução
    p_check = ws_root
    for parte in partes_raw:
        p_check = p_check / parte
        if p_check.is_symlink():
            raise ValueError("Links simbólicos (symlinks) não são permitidos no workspace.")

    # 4. Resolução dentro do workspace
    candidato = (ws_root / texto).resolve()
    ws_root_res = ws_root.resolve()
    try:
        rel = candidato.relative_to(ws_root_res)
    except ValueError as exc:
        raise ValueError("Caminho fora do workspace autorizado.") from exc

    if not permitir_interno:
        rel_partes = rel.parts
        if len(rel_partes) == 0:
            return candidato

        primeiro = rel_partes[0].lower()
        # Negar pastas de controle interno
        if primeiro in {".agente", ".servidor", ".estado", ".git"}:
            raise ValueError(f"Acesso à pasta de controle '{rel_partes[0]}' é estritamente proibido.")

        # Negar chats.sqlite
        if any(p.lower().startswith("chats.sqlite") for p in rel_partes):
            raise ValueError("Acesso ao banco de dados 'chats.sqlite' é proibido.")

        # Negar segredos e arquivos protegidos
        if any(p.lower() == "segredos" or p.lower().startswith("segredos") for p in rel_partes):
            raise ValueError("Acesso a arquivos de segredos é proibido.")

        if candidato.name.lower() in ARQUIVOS_BLOQUEADOS:
            raise ValueError(f"Acesso ao arquivo protegido '{candidato.name}' é proibido.")

        # Negar versões Mapas/vNNN imutáveis
        if escrita and len(rel_partes) >= 2 and rel_partes[0].lower() == "mapas":
            if re.match(r"^v\d+$", rel_partes[1], re.IGNORECASE):
                raise ValueError(f"Versões históricas em 'Mapas/{rel_partes[1]}' são imutáveis e protegidas.")

    # 5. Detecção estrita de Symlinks
    if candidato.is_symlink():
        raise ValueError("Links simbólicos (symlinks) não são permitidos no workspace.")
    curr = candidato
    while curr != ws_root_res and curr != curr.parent:
        if curr.is_symlink():
            raise ValueError("Links simbólicos (symlinks) não são permitidos no workspace.")
        curr = curr.parent

    return candidato


def _resolver_saida_nova(caminho_rel: str, ws_root: Path) -> Path:
    """Saídas de operações binárias nunca sobrescrevem fontes ou versões."""
    alvo = _resolver_caminho_seguro(caminho_rel, ws_root, escrita=True)
    companheiros = (alvo,)
    if alvo.suffix.lower() == '.shp':
        companheiros = tuple(alvo.with_suffix(ext) for ext in ('.shp', '.shx', '.dbf', '.prj', '.cpg'))
    if any(p.exists() for p in companheiros):
        raise ValueError('Destino já existe: escolha nome novo; sobrescrita não foi autorizada.')
    return alvo


def _fazer_backup(alvo: Path, ws_root: Path) -> Path | None:
    if not alvo.exists() or not alvo.is_file():
        return None
    backup_dir = ws_root / ".agente" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    nome_backup = f"{ts}_{alvo.name}"
    destino = backup_dir / nome_backup
    contador = 1
    while destino.exists():
        destino = backup_dir / f"{ts}_{contador}_{alvo.name}"
        contador += 1
    shutil.copy2(alvo, destino)
    return destino


def registrar_tools_workspace(
    registro: RegistroFerramentas,
    gerenciador_aprovacao: GerenciadorAprovacao | None = None,
) -> None:
    gerenciador = gerenciador_aprovacao or gerenciador_aprovacao_padrao

    @registro.ferramenta(
        nome="workspace_listar",
        descricao="Lista arquivos e diretórios dentro do workspace do projeto.",
        categoria="workspace",
        parametros={
            "type": "object",
            "properties": {
                "subpasta": {
                    "type": "string",
                    "description": "Subpasta relativa opcional para listar.",
                }
            },
            "additionalProperties": False,
        },
    )
    def tool_workspace_listar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            subpasta = args.get("subpasta", "")
            alvo = _resolver_caminho_seguro(subpasta, ws_root) if subpasta else ws_root
            if not alvo.exists():
                return _erro("NU-040", f"Diretório '{subpasta}' não existe.")
            if not alvo.is_dir():
                return _erro("NU-041", f"'{subpasta}' não é um diretório.")

            itens = []
            for entrada in sorted(alvo.iterdir()):
                # Omitir diretórios internos de controle do resultado
                if entrada.name.lower() in {".agente", ".servidor", ".estado", ".git"}:
                    continue
                rel = entrada.relative_to(ws_root).as_posix()
                itens.append(
                    {
                        "caminho": rel,
                        "nome": entrada.name,
                        "eh_diretorio": entrada.is_dir(),
                        "tamanho_bytes": entrada.stat().st_size if entrada.is_file() else None,
                    }
                )
            return _ok({"itens": itens, "total": len(itens)})
        except ValueError as exc:
            return _erro("NU-042", str(exc))

    @registro.ferramenta(
        nome="workspace_ler",
        descricao="Lê o conteúdo de um arquivo de texto no workspace do projeto.",
        categoria="workspace",
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo do arquivo."}
            },
            "required": ["caminho"],
            "additionalProperties": False,
        },
    )
    def tool_workspace_ler(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args.get("caminho", "")
            alvo = _resolver_caminho_seguro(caminho_str, ws_root)
            if not alvo.exists():
                return _erro("NU-040", f"Arquivo '{caminho_str}' não existe.")
            if alvo.is_dir():
                return _erro("NU-041", f"'{caminho_str}' é um diretório, não um arquivo.")

            # Leitura bounded diretamente no disco para não saturar memória
            tamanho = alvo.stat().st_size
            limite_bytes = 100_000
            with alvo.open("r", encoding="utf-8", errors="replace") as f:
                conteudo = f.read(limite_bytes)
            truncado = tamanho > limite_bytes or len(conteudo) >= limite_bytes

            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir(
                    "agente.arquivo",
                    {
                        "caminho": alvo.relative_to(ws_root).as_posix(),
                        "acao": "leitura",
                    },
                )

            return _ok(
                {
                    "caminho": alvo.relative_to(ws_root).as_posix(),
                    "conteudo": conteudo,
                    "tamanho_bytes": tamanho,
                    "truncado": truncado,
                }
            )
        except ValueError as exc:
            return _erro("NU-042", str(exc))

    @registro.ferramenta(
        nome="workspace_escrever",
        descricao="Grava ou sobrescreve conteúdo em um arquivo de texto no workspace com backup automático.",
        categoria="workspace",
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo do arquivo."},
                "conteudo": {"type": "string", "description": "Texto a ser gravado."},
                "token_aprovacao": {
                    "type": "string",
                    "description": "Token de aprovação caso exigido.",
                },
            },
            "required": ["caminho", "conteudo"],
            "additionalProperties": False,
        },
    )
    def tool_workspace_escrever(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args.get("caminho", "")
            conteudo = args.get("conteudo", "")
            alvo = _resolver_caminho_seguro(caminho_str, ws_root, escrita=True)

            rel = alvo.relative_to(ws_root).as_posix()
            hash_alvo = _calcular_hash_arquivo(alvo)

            # Se o arquivo já existe, sobrescrita EXIGE aprovação prévia confiável
            if alvo.exists():
                if not gerenciador.verificar_e_consumir_decisao(
                    "sobrescrever", rel, ws_root=ws_root, hash_alvo=hash_alvo
                ):
                    emissor: Emissor | None = ctx.get("emissor")
                    return gerenciador.solicitar(
                        acao="sobrescrever",
                        caminho=rel,
                        motivo=f"Sobrescrita do arquivo existente '{rel}'.",
                        ws_root=ws_root,
                        hash_alvo=hash_alvo,
                        emissor=emissor,
                    )

            # Criar diretório pai se necessário
            alvo.parent.mkdir(parents=True, exist_ok=True)

            # Fazer backup se o arquivo já existia
            backup_feito = _fazer_backup(alvo, ws_root)

            alvo.write_text(conteudo, encoding="utf-8")

            emissor = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel, "acao": "escrita"})

            return _ok(
                {
                    "caminho": rel,
                    "tamanho_bytes": len(conteudo.encode("utf-8")),
                    "backup": backup_feito.relative_to(ws_root).as_posix() if backup_feito else None,
                }
            )
        except ValueError as exc:
            return _erro("NU-042", str(exc))

    @registro.ferramenta(
        nome="workspace_mover",
        descricao="Move ou renomeia um arquivo ou pasta dentro do workspace.",
        categoria="workspace",
        parametros={
            "type": "object",
            "properties": {
                "origem": {"type": "string", "description": "Caminho relativo de origem."},
                "destino": {"type": "string", "description": "Caminho relativo de destino."},
            },
            "required": ["origem", "destino"],
            "additionalProperties": False,
        },
    )
    def tool_workspace_mover(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_origem = args.get("origem", "")
            caminho_destino = args.get("destino", "")

            origem = _resolver_caminho_seguro(caminho_origem, ws_root, escrita=True)
            destino = _resolver_caminho_seguro(caminho_destino, ws_root, escrita=True)

            if origem.resolve() == ws_root.resolve():
                return _erro("NU-042", "Não é permitido mover o diretório raiz do workspace.")

            if destino.resolve() == ws_root.resolve():
                return _erro("NU-042", "Destino não pode ser o diretório raiz do workspace.")

            # Proteger pastas estruturais de serem movidas
            if origem.name in PASTAS_ESTRUTURA_PROTEGIDA and origem.parent.resolve() == ws_root.resolve():
                return _erro("NU-042", f"Não é permitido mover a pasta protegida '{origem.name}' do projeto.")

            if not origem.exists():
                return _erro("NU-040", f"Origem '{caminho_origem}' não existe.")

            destino.parent.mkdir(parents=True, exist_ok=True)
            _fazer_backup(origem, ws_root)

            shutil.move(str(origem), str(destino))

            emissor: Emissor | None = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir(
                    "agente.arquivo",
                    {"caminho": destino.relative_to(ws_root).as_posix(), "acao": "mover"},
                )

            return _ok(
                {
                    "origem": origem.relative_to(ws_root).as_posix(),
                    "destino": destino.relative_to(ws_root).as_posix(),
                }
            )
        except ValueError as exc:
            return _erro("NU-042", str(exc))

    @registro.ferramenta(
        nome="workspace_apagar",
        descricao="Exclui um arquivo do workspace. Ação destrutiva que EXIGE aprovação do usuário.",
        categoria="workspace",
        requer_aprovacao=True,
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo do arquivo."},
                "token_aprovacao": {
                    "type": "string",
                    "description": "Token de aprovação confiável concedido pelo usuário/servidor.",
                },
            },
            "required": ["caminho"],
            "additionalProperties": False,
        },
    )
    def tool_workspace_apagar(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args.get("caminho", "")
            alvo = _resolver_caminho_seguro(caminho_str, ws_root, escrita=True)

            if alvo.resolve() == ws_root.resolve():
                return _erro("NU-042", "Exclusão do diretório raiz do workspace não é permitida.")

            if alvo.name in PASTAS_ESTRUTURA_PROTEGIDA and alvo.parent.resolve() == ws_root.resolve():
                return _erro("NU-042", f"Exclusão da pasta protegida '{alvo.name}' não é permitida.")

            if not alvo.exists():
                return _erro("NU-040", f"Arquivo '{caminho_str}' não existe.")

            rel = alvo.relative_to(ws_root).as_posix()
            hash_alvo = _calcular_hash_arquivo(alvo)

            # Consentimento provém da decisão confiável do proprietário, nunca do LLM
            if not gerenciador.verificar_e_consumir_decisao(
                "apagar", rel, ws_root=ws_root, hash_alvo=hash_alvo
            ):
                emissor: Emissor | None = ctx.get("emissor")
                return gerenciador.solicitar(
                    acao="apagar",
                    caminho=rel,
                    motivo=f"Exclusão definitiva de '{rel}'.",
                    ws_root=ws_root,
                    hash_alvo=hash_alvo,
                    emissor=emissor,
                )

            # Aprovado com decisão válida consumida: faz backup antes de apagar
            backup_feito = _fazer_backup(alvo, ws_root)
            if alvo.is_dir():
                shutil.rmtree(alvo)
            else:
                alvo.unlink()

            emissor = ctx.get("emissor")
            if emissor is not None:
                emissor.emitir("agente.arquivo", {"caminho": rel, "acao": "apagar"})

            return _ok(
                {
                    "caminho": rel,
                    "apagado": True,
                    "backup": backup_feito.relative_to(ws_root).as_posix() if backup_feito else None,
                }
            )
        except ValueError as exc:
            return _erro("NU-042", str(exc))

    @registro.ferramenta(
        nome="workspace_estat",
        descricao="Obtém estatísticas e metadados de um arquivo ou diretório.",
        categoria="workspace",
        parametros={
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho relativo para verificar."}
            },
            "required": ["caminho"],
            "additionalProperties": False,
        },
    )
    def tool_workspace_estat(args: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        try:
            ws_root = _obter_workspace(ctx)
            caminho_str = args.get("caminho", "")
            alvo = _resolver_caminho_seguro(caminho_str, ws_root)

            if not alvo.exists():
                return _ok({"existe": False, "caminho": caminho_str})

            stat = alvo.stat()
            modificado_iso = datetime.datetime.fromtimestamp(
                stat.st_mtime, tz=datetime.timezone.utc
            ).isoformat()
            return _ok(
                {
                    "existe": True,
                    "caminho": alvo.relative_to(ws_root).as_posix(),
                    "eh_arquivo": alvo.is_file(),
                    "eh_diretorio": alvo.is_dir(),
                    "tamanho_bytes": stat.st_size if alvo.is_file() else None,
                    "modificado": modificado_iso,
                }
            )
        except ValueError as exc:
            return _erro("NU-042", str(exc))
