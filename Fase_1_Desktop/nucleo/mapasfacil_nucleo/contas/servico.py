# Handlers NDJSON conta.* — e-mail + senha locais (F1-14 / M5).
# No login: ativa pasta Documentos/database/MapasFacil/<user>/ e chave DeepSeek do projeto.

from __future__ import annotations

from pathlib import Path
from typing import Any

from mapasfacil_nucleo import sessao
from mapasfacil_nucleo.agente.provisao import (
    espelhar_secrets_para_provisao,
    sincronizar_chave_projeto_no_cofre,
)
from mapasfacil_nucleo.contas.repositorio import RepositorioContas
from mapasfacil_nucleo.contas.senha import (
    hashear,
    normalizar_email,
    validar_politica_senha,
    verificar,
)
from mapasfacil_nucleo.dados import (
    garantir_arvore_sistema,
    garantir_arvore_usuario,
    pasta_chats_usuario,
    pasta_workspace_usuario,
)
from mapasfacil_nucleo.erros import ErroNucleo

_repo: RepositorioContas | None = None
_diretorio: Path | None = None
_usuario_ativo: dict[str, str] | None = None  # {email, id, pasta}


def configurar_diretorio(diretorio: Path | str | None) -> None:
    """Testes e boot isolam o SQLite; `None` volta ao caminho padrão."""
    global _repo, _diretorio
    if _repo is not None:
        _repo.fechar()
        _repo = None
    _diretorio = Path(diretorio) if diretorio is not None else None


def repositorio() -> RepositorioContas:
    global _repo
    if _repo is None:
        _repo = RepositorioContas(_diretorio)
    return _repo


def usuario_ativo() -> dict[str, str] | None:
    """Snapshot da pasta do usuário logado (para arquivar saídas / workspace)."""
    return dict(_usuario_ativo) if _usuario_ativo else None


def _conta_publica(conta: dict[str, Any]) -> dict[str, Any]:
    return {"id": conta["id"], "email": conta["email"], "nome": conta.get("nome")}


def _raiz_dados_conta() -> Path:
    """Raiz efetiva: override de testes (ao lado de contas) ou Documentos/database/…"""
    if _diretorio is not None:
        return Path(_diretorio).expanduser().resolve().parent
    from mapasfacil_nucleo.dados import raiz_sistema

    return raiz_sistema()


def _pasta_usuario_apagavel(pasta: Path) -> bool:
    """Só apaga pastas sob a raiz de dados / <slug> (nunca contas/)."""
    try:
        rel = pasta.resolve().relative_to(_raiz_dados_conta().resolve())
    except ValueError:
        return False
    partes = rel.parts
    return len(partes) == 1 and partes[0] not in {"contas", "_sem_usuario"}


def _ativar_dados_usuario(conta: dict[str, Any]) -> dict[str, Any]:
    """Cria árvore do usuário, aponta chats e sincroniza DeepSeek do projeto."""
    global _usuario_ativo
    email = str(conta["email"])
    raiz = _raiz_dados_conta()
    garantir_arvore_sistema(raiz)
    pasta = garantir_arvore_usuario(email=email, raiz=raiz)
    chats = pasta_chats_usuario(email=email, raiz=raiz)
    workspace = pasta_workspace_usuario(email=email, raiz=raiz)

    # Chats isolados por usuário.
    from mapasfacil_nucleo.conversas import servico as conversas_servico

    conversas_servico.configurar_diretorio(chats)

    espelhar_secrets_para_provisao(raiz / "provisao.local.json")
    sync = sincronizar_chave_projeto_no_cofre()

    _usuario_ativo = {
        "id": str(conta["id"]),
        "email": email,
        "pasta": str(pasta),
        "workspace": str(workspace),
        "chats": str(chats),
    }
    return {
        "pasta_usuario": str(pasta),
        "workspace_padrao": str(workspace),
        "deepseek_projeto": bool(sync.get("ok")),
    }


def _desativar_dados_usuario(*, apagar_pasta: bool = False) -> None:
    global _usuario_ativo
    from mapasfacil_nucleo.conversas import servico as conversas_servico

    if apagar_pasta and _usuario_ativo and _usuario_ativo.get("pasta"):
        import shutil

        pasta = Path(_usuario_ativo["pasta"])
        if pasta.is_dir() and _pasta_usuario_apagavel(pasta):
            shutil.rmtree(pasta, ignore_errors=True)
    _usuario_ativo = None
    conversas_servico.configurar_diretorio(None)


def _ativar_sessao(conta: dict[str, Any], *, lembrar: bool) -> dict[str, Any]:
    repo = repositorio()
    local = repo.criar_sessao_local(conta["id"], lembrar_neste_pc=lembrar)
    repo.marcar_login(conta["id"])
    sessao.definir(estado="conectado", conta_id=conta["id"], expira_em=local.get("expira_em"))
    dados = _ativar_dados_usuario(conta)
    return {
        "conta": _conta_publica(conta),
        "sessao": {
            "estado": "conectado",
            "conta_id": conta["id"],
            "expira_em": local.get("expira_em"),
            "lembrar_neste_pc": lembrar,
        },
        "dados": dados,
    }


def restaurar_se_lembrada() -> dict[str, Any]:
    """No boot: se há sessão com ‘lembrar neste PC’, reconecta sem senha."""
    try:
        lembrada = repositorio().sessao_lembrada()
    except ErroNucleo:
        raise
    except Exception as exc:  # noqa: BLE001 — falha de I/O vira AUTH-050
        raise ErroNucleo(
            "AUTH-050",
            "Não foi possível abrir o banco de contas neste PC.",
            {"motivo": str(exc)},
        ) from exc
    if lembrada is None:
        # Boot frio já começa desconectado; não apagar sessão que o main/testes
        # acabaram de definir via `sessao.definir` (mesmo com conta_id sintético).
        atual = sessao.estado_atual()
        return {"estado": atual["estado"], "conta": None}
    conta = {"id": lembrada["conta_id"], "email": lembrada["email"], "nome": lembrada.get("nome")}
    sessao.definir(
        estado="conectado",
        conta_id=conta["id"],
        expira_em=lembrada.get("expira_em"),
    )
    dados = _ativar_dados_usuario(conta)
    return {"estado": "conectado", "conta": _conta_publica(conta), "dados": dados}


def criar(params: dict[str, Any]) -> dict[str, Any]:
    email_bruto = params.get("email")
    senha = params.get("senha")
    nome = params.get("nome")
    if not isinstance(email_bruto, str) or not email_bruto.strip():
        raise ErroNucleo("NU-001", "Parâmetro 'email' é obrigatório.")
    if not isinstance(senha, str) or not senha:
        raise ErroNucleo("NU-001", "Parâmetro 'senha' é obrigatório.")
    if nome is not None and not isinstance(nome, str):
        raise ErroNucleo("NU-001", "Parâmetro 'nome' inválido.")
    email = normalizar_email(email_bruto)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ErroNucleo("NU-001", "E-mail inválido.")
    validar_politica_senha(senha, email)

    repo = repositorio()
    if repo.buscar_por_email(email) is not None:
        raise ErroNucleo(
            "AUTH-070",
            "Já existe uma conta com este e-mail neste PC. Entre em vez de criar.",
            {"email": email},
        )
    try:
        conta = repo.inserir_conta(email=email, senha_hash=hashear(senha), nome=nome)
    except ErroNucleo:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ErroNucleo(
            "AUTH-050",
            "Não foi possível gravar a conta neste PC.",
            {"motivo": str(exc)},
        ) from exc
    return _ativar_sessao(conta, lembrar=True)


def entrar(params: dict[str, Any]) -> dict[str, Any]:
    email_bruto = params.get("email")
    senha = params.get("senha")
    lembrar = params.get("lembrar_neste_pc", True)
    if not isinstance(email_bruto, str) or not email_bruto.strip():
        raise ErroNucleo("NU-001", "Parâmetro 'email' é obrigatório.")
    if not isinstance(senha, str) or not senha:
        raise ErroNucleo("NU-001", "Parâmetro 'senha' é obrigatório.")
    if not isinstance(lembrar, bool):
        raise ErroNucleo("NU-001", "Parâmetro 'lembrar_neste_pc' inválido.")
    email = normalizar_email(email_bruto)
    conta = repositorio().buscar_por_email(email)
    # Mensagem genérica: não revelar se o e-mail existe (AUTH-002).
    if conta is None or not conta.get("ativa"):
        raise ErroNucleo("AUTH-002", "E-mail ou senha incorretos.")
    if not verificar(conta["senha_hash"], senha):
        raise ErroNucleo("AUTH-002", "E-mail ou senha incorretos.")
    if not conta.get("ativa"):
        raise ErroNucleo("AUTH-071", "Esta conta está desativada neste PC.")
    return _ativar_sessao(
        {"id": conta["id"], "email": conta["email"], "nome": conta.get("nome")},
        lembrar=lembrar,
    )


def sair(params: dict[str, Any]) -> dict[str, Any]:
    esquecer = bool(params.get("esquecer_este_pc"))
    repo = repositorio()
    if esquecer:
        repo.apagar_tudo()
        _desativar_dados_usuario(apagar_pasta=True)
    else:
        repo.limpar_sessoes()
        _desativar_dados_usuario(apagar_pasta=False)
    sessao.resetar()
    return {"ok": True, "esquecido": esquecer}


def estado(_params: dict[str, Any] | None = None) -> dict[str, Any]:
    atual = sessao.estado_atual()
    if atual["estado"] != "conectado" or not atual.get("conta_id"):
        return {"estado": atual["estado"], "conta": None}
    conta = repositorio().buscar_por_id(atual["conta_id"])
    if conta is None:
        sessao.resetar()
        return {"estado": "desconectado", "conta": None}
    # Garante árvore + chave se o processo voltou com sessão já marcada.
    ativo = usuario_ativo()
    if ativo is None or ativo.get("id") != conta["id"]:
        dados = _ativar_dados_usuario(conta)
    else:
        dados = {
            "pasta_usuario": ativo["pasta"],
            "workspace_padrao": ativo["workspace"],
            "deepseek_projeto": True,
        }
    return {"estado": "conectado", "conta": _conta_publica(conta), "dados": dados}
