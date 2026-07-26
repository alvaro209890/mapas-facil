"""Contas locais (e-mail + senha em SQLite) — M5 / F1-14."""

from mapasfacil_nucleo.contas import servico
from mapasfacil_nucleo.contas.banco import caminho_banco, diretorio_contas

__all__ = ["caminho_banco", "diretorio_contas", "servico"]
