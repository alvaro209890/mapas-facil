"""Ponto de entrada do binário PyInstaller (evita quirks com -m empacotado)."""
# Backend não-interativo antes de qualquer import do matplotlib (PDF nativo).
import matplotlib

matplotlib.use("Agg")

from mapasfacil_nucleo.__main__ import main_cli

if __name__ == "__main__":
    main_cli()
