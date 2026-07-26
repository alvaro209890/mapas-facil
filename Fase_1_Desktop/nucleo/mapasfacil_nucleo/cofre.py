"""A11 — cofre BYOK (chaves DeepSeek / SEMA / Planet).

Armazena no keyring do SO (`keyring`: Credential Manager no Windows, Secret
Service no Linux). O valor **nunca** volta em resposta NDJSON, log ou erro.

API pública NDJSON: `cofre.definir` / `cofre.existe` / `cofre.testar`.
Uso interno do núcleo: `usar(nome)` — só dentro do processo Python.
"""

from __future__ import annotations

import os
import time
from typing import Any, Protocol

from mapasfacil_nucleo.erros import ErroNucleo

SERVICO = "MapasFacil"

NOMES_PERMITIDOS: frozenset[str] = frozenset(
    {
        "deepseek_api_key",
        "sema_authkey",
        "planet_api_key",
    }
)

# Mapeamento doctor ↔ nome no cofre.
ALIAS_DOCTOR: dict[str, str] = {
    "deepseek": "deepseek_api_key",
    "sema": "sema_authkey",
    "planet": "planet_api_key",
}


class BackendCofre(Protocol):
    def set_password(self, servico: str, usuario: str, senha: str) -> None: ...
    def get_password(self, servico: str, usuario: str) -> str | None: ...
    def delete_password(self, servico: str, usuario: str) -> None: ...


class BackendMemoria:
    """Backend in-process para testes — sem keyring do SO."""

    def __init__(self) -> None:
        self._dados: dict[tuple[str, str], str] = {}

    def set_password(self, servico: str, usuario: str, senha: str) -> None:
        self._dados[(servico, usuario)] = senha

    def get_password(self, servico: str, usuario: str) -> str | None:
        return self._dados.get((servico, usuario))

    def delete_password(self, servico: str, usuario: str) -> None:
        self._dados.pop((servico, usuario), None)


_backend: BackendCofre | None = None


def configurar_backend(backend: BackendCofre | None) -> None:
    """Injeta backend (testes). `None` volta ao keyring do SO."""
    global _backend
    _backend = backend


def _backend_ativo() -> BackendCofre:
    if _backend is not None:
        return _backend
    try:
        import keyring
    except ImportError as exc:  # pragma: no cover - dep declarada no pyproject
        raise ErroNucleo(
            "NU-060",
            "Pacote 'keyring' ausente — não dá para usar o cofre do sistema.",
        ) from exc
    return keyring


def _validar_nome(nome: str) -> str:
    if nome not in NOMES_PERMITIDOS:
        raise ErroNucleo(
            "NU-001",
            f"Chave de cofre desconhecida: {nome}. "
            f"Permitidas: {', '.join(sorted(NOMES_PERMITIDOS))}",
            {"chave": nome},
        )
    return nome


def definir(nome: str, valor: str) -> None:
    """Grava no cofre. Valor vazio apaga a entrada."""
    nome = _validar_nome(nome)
    if not isinstance(valor, str):
        raise ErroNucleo("NU-001", "Parâmetro 'valor' precisa ser texto.")
    backend = _backend_ativo()
    if not valor.strip():
        try:
            backend.delete_password(SERVICO, nome)
        except Exception:
            # Já inexistente — ok.
            pass
        return
    backend.set_password(SERVICO, nome, valor.strip())


def existe(nome: str) -> bool:
    nome = _validar_nome(nome)
    try:
        valor = _backend_ativo().get_password(SERVICO, nome)
    except Exception:
        return False
    return bool(valor and str(valor).strip())


def usar(nome: str) -> str | None:
    """Uso **interno** do núcleo. Nunca exponha o retorno no stdio."""
    nome = _validar_nome(nome)
    try:
        valor = _backend_ativo().get_password(SERVICO, nome)
    except Exception:
        return None
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def apagar(nome: str) -> None:
    definir(nome, "")


def testar(nome: str) -> dict[str, Any]:
    """Valida a chave sem devolver o valor.

    DeepSeek: chamada leve em `/models` (Bearer). Sem rede / falha → ok=False.
    SEMA/Planet: por enquanto só confirma existência (cliente WFS/Planet é A13+).
    """
    nome = _validar_nome(nome)
    valor = usar(nome)
    if not valor:
        return {"ok": False, "chave": nome, "erro": "chave ausente no cofre"}

    if nome == "deepseek_api_key":
        return _testar_deepseek(valor)

    # Sem cliente de rede ainda — existência já é o teste.
    return {"ok": True, "chave": nome, "ms": 0, "modo": "existencia"}


def _testar_deepseek(valor: str) -> dict[str, Any]:
    """HEAD/GET leve. O valor **não** entra no retorno."""
    import json
    import urllib.error
    import urllib.request

    inicio = time.monotonic()
    req = urllib.request.Request(
        "https://api.deepseek.com/models",
        method="GET",
        headers={
            "Authorization": f"Bearer {valor}",
            "Accept": "application/json",
            "User-Agent": "MapasFacil-cofre/1",
        },
    )
    # Em CI / sem rede: MF_COFRE_TESTAR_OFF=1 → só confere formato.
    if os.environ.get("MF_COFRE_TESTAR_OFF") == "1":
        ok = valor.startswith("sk-") and len(valor) > 12
        return {
            "ok": ok,
            "chave": "deepseek_api_key",
            "ms": 0,
            "modo": "offline",
            **({} if ok else {"erro": "formato de chave inválido"}),
        }
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            corpo = resp.read(200)
            _ = json.loads(corpo.decode("utf-8", errors="replace")) if corpo else {}
            ms = int((time.monotonic() - inicio) * 1000)
            return {"ok": True, "chave": "deepseek_api_key", "ms": ms, "modo": "rede"}
    except urllib.error.HTTPError as exc:
        ms = int((time.monotonic() - inicio) * 1000)
        # 401 = chave rejeitada; outros = rede/API.
        return {
            "ok": False,
            "chave": "deepseek_api_key",
            "ms": ms,
            "modo": "rede",
            "erro": f"HTTP {exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 — testar nunca derruba o sidecar
        ms = int((time.monotonic() - inicio) * 1000)
        return {
            "ok": False,
            "chave": "deepseek_api_key",
            "ms": ms,
            "modo": "rede",
            "erro": exc.__class__.__name__,
        }


def chaves_configuradas() -> dict[str, bool]:
    """Booleans para o doctor — nunca os valores."""
    return {
        alias: existe(nome) for alias, nome in ALIAS_DOCTOR.items()
    }


# --- handlers NDJSON (valor nunca ecoa) ------------------------------------


def handler_definir(params: dict[str, Any]) -> dict[str, Any]:
    chave = params.get("chave") or params.get("nome")
    valor = params.get("valor")
    if not isinstance(chave, str) or not chave:
        raise ErroNucleo("NU-001", "Parâmetro 'chave' é obrigatório.")
    if valor is not None and not isinstance(valor, str):
        raise ErroNucleo("NU-001", "Parâmetro 'valor' precisa ser texto.")
    definir(chave, valor or "")
    # Resposta mínima — sem ecoar o segredo.
    return {"ok": True, "chave": chave, "existe": existe(chave)}


def handler_existe(params: dict[str, Any]) -> dict[str, Any]:
    chave = params.get("chave") or params.get("nome")
    if not isinstance(chave, str) or not chave:
        raise ErroNucleo("NU-001", "Parâmetro 'chave' é obrigatório.")
    return {"chave": chave, "existe": existe(chave)}


def handler_testar(params: dict[str, Any]) -> dict[str, Any]:
    chave = params.get("chave") or params.get("nome")
    if not isinstance(chave, str) or not chave:
        raise ErroNucleo("NU-001", "Parâmetro 'chave' é obrigatório.")
    return testar(chave)
