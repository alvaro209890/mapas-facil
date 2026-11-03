"""Backend web do Mapas Fácil — Fase 3.

O servidor **não** reimplementa regra cartográfica (D23): ele hospeda o núcleo
`mapasfacil_nucleo` como processo filho por projeto, falando o mesmo NDJSON por
stdio que o app Electron fala.
"""

from __future__ import annotations

__version__ = "0.1.0"
PROTOCOLO_VERSAO = 1
