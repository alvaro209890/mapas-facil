#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Remove ou reinjeta as chaves de API embutidas nos .mxd de Referencias_IMAP.

Contexto
--------
Os .mxd do acervo IMAP guardam, dentro das camadas WMTS (Planet) e WMS
(GeoServer da SEMA), a chave de API em texto claro (achado original: 24 arquivos, 566
ocorrencias em Referencias_IMAP/MXD/; 2026-07-25 confirmou o mesmo padrao em todo .mxd novo
adicionado ao acervo). O repositorio e publico, entao a versao versionada dos .mxd tem as
chaves zeradas por placeholders **do mesmo comprimento**. Toda pasta nova de .mxd de
referencia precisa entrar em MXD_DIRS (abaixo) antes do primeiro commit.

Substituicao de mesmo comprimento e a unica segura aqui: .mxd e um documento
composto OLE (Compound File Binary), com tabela de setores e tamanhos de stream
gravados no cabecalho. Trocar N bytes por N bytes nao move nada; trocar por um
tamanho diferente corromperia o arquivo. Por isso os placeholders preservam ate
o formato (prefixo ``PLAK`` do Planet, formato UUID da SEMA).

Uso
---
    python3 ferramentas/chaves_mxd.py verificar    # mostra o estado atual
    python3 ferramentas/chaves_mxd.py restaurar    # placeholder -> chave real
    python3 ferramentas/chaves_mxd.py limpar       # chave real -> placeholder

``restaurar`` le as chaves de ``secrets.local.json`` (gitignored). Rode-o quando
precisar abrir um .mxd de referencia no ArcMap com o basemap Planet e o WMS da
SEMA funcionando. **Rode ``limpar`` antes de qualquer commit.**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# Todo diretorio do acervo versionado que guarda .mxd precisa entrar aqui —
# cada pasta nova de referencia traz chave real embutida. O acervo segue o
# esquema Referencias_IMAP/Mapas/NN/, entao a varredura e recursiva a partir
# de Mapas/ e nao precisa de uma linha por pasta nova.
MXD_DIRS = [
    RAIZ / "Referencias_IMAP" / "MXD",
    RAIZ / "Referencias_IMAP" / "Mapas",
]
SECRETS = RAIZ / "secrets.local.json"

# chave_no_secrets -> placeholder (mesmo comprimento, obrigatoriamente)
#
# Os placeholders sao *inequivocos* de proposito. A primeira versao usava
# zeros ("PLAK000...0" e um UUID nulo); o placeholder de 32 zeros do Planet
# antigo passou a casar tambem com o miolo do placeholder de 36 do Planet
# atual, e 'restaurar' teria escrito a chave nova dentro da antiga. Regra:
# nenhum placeholder pode ser substring de outro nem aparecer naturalmente
# num .mxd. O comando 'verificar' confere isso a cada execucao.
PLACEHOLDERS = {
    "planet_api_key": "PLAK_CHAVE_REMOVIDA_VER_FERRAMENTAS_",
    "planet_api_key_antiga": "PLANET_ANTIGA_CHAVE_REMOVIDA_VER",
    "sema_authkey": "5ema4key-0000-0000-0000-remov1da0000",
}

ASSINATURA_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def carregar_chaves() -> dict[str, str]:
    if not SECRETS.exists():
        sys.exit(
            f"ERRO: {SECRETS} nao existe.\n"
            "As chaves reais so vivem neste PC de desenvolvimento. "
            "Crie o arquivo a partir de secrets.example.json."
        )
    dados = json.loads(SECRETS.read_text(encoding="utf-8"))
    chaves = {}
    for nome, placeholder in PLACEHOLDERS.items():
        valor = dados.get(nome, "")
        if not valor:
            continue
        if len(valor) != len(placeholder):
            sys.exit(
                f"ERRO: '{nome}' tem {len(valor)} caracteres, mas o placeholder "
                f"tem {len(placeholder)}. Substituicao de comprimento diferente "
                "corromperia o .mxd. Ajuste o placeholder junto com a chave."
            )
        chaves[nome] = valor
    return chaves


def _arquivos_mxd():
    """Todo .mxd sob MXD_DIRS, recursivamente.

    Recursivo de proposito: o acervo cresce por pastas novas
    (Referencias_IMAP/Mapas/NN/MXD/), e uma varredura rasa deixaria .mxd novo
    com chave real passar batido — foi o que quase aconteceu em 2026-07-25.
    """
    vistos = set()
    for pasta in MXD_DIRS:
        if not pasta.exists():
            continue
        for arquivo in sorted(pasta.rglob("*.mxd")):
            if arquivo not in vistos:
                vistos.add(arquivo)
                yield arquivo


def aplicar(pares: list[tuple[str, str]], rotulo: str) -> None:
    """Aplica substituicoes UTF-16LE de mesmo comprimento em todos os .mxd."""
    total = 0
    for arquivo in _arquivos_mxd():
        original = arquivo.read_bytes()
        if original[:8] != ASSINATURA_OLE:
            print(f"  ! {arquivo.name}: nao e um documento OLE — pulado")
            continue

        conteudo, ocorrencias = original, 0
        for de, para in pares:
            de_b, para_b = de.encode("utf-16-le"), para.encode("utf-16-le")
            ocorrencias += conteudo.count(de_b)
            conteudo = conteudo.replace(de_b, para_b)

        if not ocorrencias:
            continue
        assert len(conteudo) == len(original), arquivo.name
        arquivo.write_bytes(conteudo)
        total += ocorrencias
        print(f"  {arquivo.name:40s} {ocorrencias:4d}")

    print(f"\n{rotulo}: {total} ocorrencias em {', '.join(str(p) for p in MXD_DIRS)}")


def verificar() -> None:
    for a in PLACEHOLDERS.values():
        for b in PLACEHOLDERS.values():
            if a is not b and a in b:
                sys.exit(f"ERRO: placeholder '{a}' e substring de '{b}'.")

    chaves = carregar_chaves() if SECRETS.exists() else {}
    reais: dict[str, int] = {}
    placeholders: dict[str, int] = {}
    for arquivo in _arquivos_mxd():
        dados = arquivo.read_bytes()
        for nome, placeholder in PLACEHOLDERS.items():
            placeholders[nome] = placeholders.get(nome, 0) + dados.count(
                placeholder.encode("utf-16-le")
            )
            if nome in chaves:
                reais[nome] = reais.get(nome, 0) + dados.count(
                    chaves[nome].encode("utf-16-le")
                )

    print(f"{'segredo':24s} {'placeholder':>12s} {'real':>6s}")
    for nome in PLACEHOLDERS:
        print(f"{nome:24s} {placeholders.get(nome, 0):12d} {reais.get(nome, 0):6d}")

    if sum(reais.values()):
        print("\n>>> HA CHAVE REAL NOS .mxd. Rode 'limpar' antes de commitar. <<<")
        sys.exit(1)
    print("\nSeguro para commit.")


def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "verificar"
    if comando == "verificar":
        verificar()
    elif comando == "restaurar":
        chaves = carregar_chaves()
        aplicar([(PLACEHOLDERS[n], v) for n, v in chaves.items()], "Chaves reinjetadas")
        print("LEMBRETE: rode 'limpar' antes do proximo commit.")
    elif comando == "limpar":
        chaves = carregar_chaves()
        aplicar([(v, PLACEHOLDERS[n]) for n, v in chaves.items()], "Chaves removidas")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
