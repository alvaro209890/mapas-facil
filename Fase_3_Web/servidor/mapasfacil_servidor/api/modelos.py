"""Modelos de entrada/saída da API (W-03 §Rotas)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Cadastro(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=1, max_length=254)
    senha: str = Field(min_length=1, max_length=200)


class Entrada(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    senha: str = Field(min_length=1, max_length=200)


class TrocaSenha(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=200)
    senha_nova: str = Field(min_length=1, max_length=200)


class Folha(BaseModel):
    formato: str
    orientacao: str = "retrato"


class ProjetoNovo(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    folha: Folha


class ProjetoPatch(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)


class UsuarioNovoAdmin(BaseModel):
    email: str
    nome: str
    papel: str = "usuario"


class UsuarioPatchAdmin(BaseModel):
    ativo: bool | None = None
    papel: str | None = None
    redefinir_senha: bool | None = None


class MensagemNova(BaseModel):
    texto: str = Field(min_length=1, max_length=8000)
    resposta: dict[str, Any] | None = None


class Cancelamento(BaseModel):
    req_id: str


class ImportacaoNova(BaseModel):
    upload_id: str
