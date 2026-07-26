#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test manual da chave DeepSeek — desenvolvimento local, fora do CI.

O anel 1 do CI (pytest em Linux) e o Vitest do app **não** chamam a API real: o cliente
``deepseek.py`` e os testes de paridade galeria↔chat (G10) ainda não existem (marco M7).
Quando M7 existir, o CI usará provedor fake/VCR — ver F1-10 §anel 2.

Uso
---
    python3 ferramentas/deepseek_smoke.py

Lê ``deepseek_api_key`` de ``secrets.local.json`` (gitignored). Não imprime a chave.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SECRETS = RAIZ / "secrets.local.json"
ENDPOINT = "https://api.deepseek.com/chat/completions"
MODELO_FLASH = "deepseek-v4-flash"


def _carregar_chave() -> str:
    if not SECRETS.exists():
        print(
            f"ERRO: {SECRETS} não existe.\n"
            "Crie a partir de secrets.example.json e preencha deepseek_api_key.",
            file=sys.stderr,
        )
        sys.exit(1)
    dados = json.loads(SECRETS.read_text(encoding="utf-8"))
    chave = (dados.get("deepseek_api_key") or "").strip()
    if not chave:
        print("ERRO: deepseek_api_key vazio em secrets.local.json", file=sys.stderr)
        sys.exit(1)
    return chave


def main() -> None:
    chave = _carregar_chave()
    corpo = json.dumps(
        {
            "model": MODELO_FLASH,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
    ).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=corpo,
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resposta:
            dados = json.loads(resposta.read())
    except urllib.error.HTTPError as exc:
        corpo_erro = exc.read().decode(errors="replace")[:500]
        print(f"FALHA HTTP {exc.code}: {corpo_erro}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"FALHA de rede: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    modelo = dados.get("model", "?")
    texto = dados.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"OK — modelo={modelo} resposta={texto!r}")
    print("Chave válida para desenvolvimento local. CI continua sem chave (fake no M7).")


if __name__ == "__main__":
    main()
