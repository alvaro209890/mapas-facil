"""Senhas — scrypt da stdlib, formato versionado (W-11 §Contas).

O plano cita Argon2id (`mapasfacil_nucleo.contas.senha`), mas o servidor **não importa
o núcleo** (AW-01) e não quer depender de `argon2-cffi` no servidor por um detalhe que
a stdlib resolve. `hashlib.scrypt` é memória-dura e vem no Python 3.12; o formato
carrega os parâmetros, então trocar de algoritmo depois é migração, não quebra.

Formato: ``scrypt$n$r$p$salt_b64$hash_b64``
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from pathlib import Path

N_PADRAO = 2**14  # 16 MiB de RAM por hash
R_PADRAO = 8
P_PADRAO = 1
TAMANHO_SENHA_MIN = 10
TAMANHO_SENHA_MAX = 200
COMUNS_PATH = Path(__file__).resolve().parent / "senhas_comuns.txt"

_SENHAS_COMUNS: frozenset[str] | None = None


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def _destexto(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"))


def senhas_comuns() -> frozenset[str]:
    global _SENHAS_COMUNS
    if _SENHAS_COMUNS is None:
        try:
            linhas = COMUNS_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:  # pragma: no cover - arquivo sempre existe no repo
            linhas = []
        _SENHAS_COMUNS = frozenset(l.strip().lower() for l in linhas if l.strip())
    return _SENHAS_COMUNS


def gerar_hash(senha: str) -> str:
    salt = secrets.token_bytes(16)
    derivado = hashlib.scrypt(
        senha.encode("utf-8"), salt=salt, n=N_PADRAO, r=R_PADRAO, p=P_PADRAO, dklen=32
    )
    return f"scrypt${N_PADRAO}${R_PADRAO}${P_PADRAO}${_b64(salt)}${_b64(derivado)}"


def conferir(senha: str, hash_armazenado: str) -> bool:
    try:
        algoritmo, n, r, p, salt_b64, hash_b64 = hash_armazenado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    try:
        derivado = hashlib.scrypt(
            senha.encode("utf-8"),
            salt=_destexto(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_destexto(hash_b64)),
        )
        return hmac.compare_digest(derivado, _destexto(hash_b64))
    except (ValueError, TypeError, MemoryError):
        return False


def problemas(senha: str) -> str | None:
    """Motivo de recusa da senha (`SV-010`), ou `None` se está aceitável."""
    if len(senha) < TAMANHO_SENHA_MIN:
        return f"A senha precisa ter pelo menos {TAMANHO_SENHA_MIN} caracteres."
    if len(senha) > TAMANHO_SENHA_MAX:
        return f"A senha não pode passar de {TAMANHO_SENHA_MAX} caracteres."
    if senha.strip().lower() in senhas_comuns():
        return "Essa senha é uma das mais usadas na internet. Escolha outra."
    if len(set(senha)) < 4:
        return "A senha repete poucos caracteres diferentes."
    return None


def conferir_email(email: str) -> bool:
    """Checagem conservadora: um `@`, ponto no domínio, sem espaço."""
    if not email or any(c.isspace() for c in email):
        return False
    if email.count("@") != 1:
        return False
    local, dominio = email.split("@")
    if not local or len(local) > 64:
        return False
    if "." not in dominio or dominio.startswith(".") or dominio.endswith("."):
        return False
    return True


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def gerar_senha_temporaria() -> str:
    return secrets.token_urlsafe(12)
