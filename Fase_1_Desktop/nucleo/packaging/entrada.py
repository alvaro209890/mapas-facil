"""Ponto de entrada do binário PyInstaller (evita quirks com -m empacotado)."""
from mapasfacil_nucleo.__main__ import main_cli

if __name__ == "__main__":
    main_cli()
