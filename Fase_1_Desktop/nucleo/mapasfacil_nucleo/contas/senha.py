# Hash Argon2id da senha local — nunca texto claro (F1-14 / M5).

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from mapasfacil_nucleo.erros import ErroNucleo

# Parâmetros conservadores para desktop; PHC string fica em contas.senha_hash.
_HASHER = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)

SENHA_MINIMA = 8


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def validar_politica_senha(senha: str, email: str) -> None:
    if len(senha) < SENHA_MINIMA:
        raise ErroNucleo(
            "AUTH-003",
            f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.",
            {"minimo": SENHA_MINIMA},
        )
    if senha.strip().lower() == normalizar_email(email):
        raise ErroNucleo("AUTH-003", "A senha não pode ser igual ao e-mail.")


def hashear(senha: str) -> str:
    return _HASHER.hash(senha)


def verificar(senha_hash: str, senha: str) -> bool:
    try:
        return bool(_HASHER.verify(senha_hash, senha))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
