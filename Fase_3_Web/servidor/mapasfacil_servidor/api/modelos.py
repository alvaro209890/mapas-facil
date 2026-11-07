"""Modelos de entrada/saída da API (W-03 §Rotas)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


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
    texto: str = ""
    resposta: dict[str, Any] | None = None
    contexto: dict[str, Any] | None = None

    @model_validator(mode="after")
    def conferir_conteudo(self) -> MensagemNova:
        tem_texto = bool(self.texto and self.texto.strip())
        tem_resposta = bool(self.resposta)
        tem_contexto = bool(self.contexto)
        if not (tem_texto or tem_resposta or tem_contexto):
            raise ValueError("Mensagem vazia: informe 'texto', 'resposta' ou 'contexto'.")
        if self.texto and len(self.texto) > 8000:
            raise ValueError("Texto excede o limite de 8.000 caracteres.")
        return self


class Cancelamento(BaseModel):
    req_id: str


class ImportacaoNova(BaseModel):
    upload_id: str


class AprovacaoAgenteCorpo(BaseModel):
    acao: str = Field(min_length=1, max_length=20)
    token: str | None = Field(default=None, max_length=200)
    motivo: str | None = Field(default=None, max_length=1000)
    action: str | None = Field(default=None, max_length=100)
    path: str | None = Field(default=None, max_length=500)
    version: int | None = None
    hash: str | None = Field(default=None, max_length=100)
