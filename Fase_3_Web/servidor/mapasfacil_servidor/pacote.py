"""Montador do pacote de entrega MXD/SHP/Mapas (W10-10 / D37) no servidor.

Monta a estrutura:
<imovel>__<template>__v<versao>.zip
├── MXD/
│   └── <template>.mxd
├── SHP/
│   └── *.shp, *.dbf, etc.
├── Mapas/
│   └── *.pdf, *.xlsx, validacao.json
└── LEIA-ME.txt

Implementado com biblioteca padrão (zipfile/pathlib), sem dependência cruzada de import.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OpcoesPacote:
    nome_imovel: str = "Imovel"
    nome_template: str = "Mapa"
    versao: int = 1
    mxd_conforme: bool = True
    codigo_aviso_mxd: str | None = None
    datum: str = "SIRGAS 2000 / UTM zone 22S"
    data_imagem: str = "2026-10"
    checks_reprovados: list[str] | None = None


def gerar_leia_me(opcoes: OpcoesPacote) -> str:
    linhas = [
        "==================================================================",
        f"MAPAS FÁCIL — PACOTE DE ENTREGA CARTOGRÁFICA (v{opcoes.versao:03d})",
        "==================================================================",
        "",
        f"Imóvel: {opcoes.nome_imovel}",
        f"Template: {opcoes.nome_template}",
        f"Datum / Projeção: {opcoes.datum}",
        f"Data de Referência da Imagem: {opcoes.data_imagem}",
        "",
        "INSTRUÇÕES DE USO:",
        "------------------",
        "1. Descompacte todo o conteúdo deste arquivo .zip em uma pasta local.",
    ]

    if opcoes.mxd_conforme:
        linhas.extend(
            [
                f"2. Abra o arquivo 'MXD/{opcoes.nome_template}.mxd' no ArcGIS Desktop (ArcMap 10.x).",
                "3. Os vínculos de dados foram gerados como relativos ('..\\SHP\\').",
                "4. Se alguma camada apresentar ponto de exclamação vermelho (!), clique",
                "   com o botão direito nela -> Data -> Repair Data Source e selecione",
                "   o shapefile correspondente na pasta 'SHP/' deste pacote.",
                "   O ArcMap revinculará todas as demais camadas da mesma pasta automaticamente.",
            ]
        )
    else:
        aviso = opcoes.codigo_aviso_mxd or "MX-020"
        linhas.extend(
            [
                f"AVISO [{aviso}]: O arquivo .mxd não foi incluído nesta versão.",
                "O mapa final aprovado em PDF de alta resolução e as geometrias",
                "vetoriais auditadas seguem disponíveis nas pastas 'Mapas/' e 'SHP/'.",
            ]
        )

    if opcoes.checks_reprovados:
        linhas.extend(
            [
                "",
                "CONFORMIDADE CARTOGRÁFICA:",
                "--------------------------",
                "Avisos de validação:",
            ]
        )
        for c in opcoes.checks_reprovados:
            linhas.append(f"  * {c}")

    linhas.extend(
        [
            "",
            "Gerado automaticamente pelo motor Mapas Fácil (Fase 3 Web).",
            "==================================================================",
            "",
        ]
    )
    return "\n".join(linhas)


_PASTAS_INTERNAS = frozenset({"recursos", ".preview"})


def montar_pacote_do_projeto(
    raiz_projeto: Path,
    pasta_versao_rel: str,
    artefatos: dict[str, str],
    caminho_zip_destino: Path,
    opcoes: OpcoesPacote,
) -> Path:
    """Pacote de uma versão no layout real do servidor.

    O núcleo grava `MXD/` e `SHP/` na raiz do projeto e só os mapas em `Mapas/vNNN/` — não
    há `MXD/` dentro da pasta da versão, que é o que `montar_pacote_zip` procura.
    """
    caminho_zip_destino.parent.mkdir(parents=True, exist_ok=True)
    pasta_versao = raiz_projeto / pasta_versao_rel
    with zipfile.ZipFile(caminho_zip_destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("LEIA-ME.txt", gerar_leia_me(opcoes))
        mxd = artefatos.get("mxd")
        if opcoes.mxd_conforme:
            if mxd and (raiz_projeto / mxd).is_file():
                zf.write(raiz_projeto / mxd, arcname=f"MXD/{Path(mxd).name}")
            elif (pasta_versao / "MXD").is_dir():
                for arq in sorted((pasta_versao / "MXD").glob("*.mxd")):
                    zf.write(arq, arcname=f"MXD/{arq.name}")
        # Layout antigo (SHP dentro da versão) ainda vale; o atual é `SHP/` na raiz.
        pasta_shp = pasta_versao / "SHP" if (pasta_versao / "SHP").is_dir() else raiz_projeto / "SHP"
        if pasta_shp.is_dir():
            for arq in sorted(pasta_shp.rglob("*")):
                if arq.is_file():
                    zf.write(arq, arcname=f"SHP/{arq.relative_to(pasta_shp).as_posix()}")
        if pasta_versao.is_dir():
            for arq in sorted(pasta_versao.rglob("*")):
                rel = arq.relative_to(pasta_versao)
                if not arq.is_file() or any(p in _PASTAS_INTERNAS for p in rel.parts[:-1]):
                    continue
                if len(rel.parts) > 1 and rel.parts[0] in {"SHP", "MXD"}:
                    continue
                if arq.name == "miniatura.jpg" or arq.suffix.lower() == ".zip":
                    continue
                zf.write(arq, arcname=f"Mapas/{rel.as_posix()}")
    return caminho_zip_destino


def montar_pacote_zip(
    pasta_versao: Path,
    caminho_zip_destino: Path,
    opcoes: OpcoesPacote,
) -> Path:
    caminho_zip_destino.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(caminho_zip_destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("LEIA-ME.txt", gerar_leia_me(opcoes))

        # 1. Pasta MXD/ (se houver .mxd na pasta da versão e for conforme)
        if opcoes.mxd_conforme:
            pasta_mxd = pasta_versao / "MXD"
            if pasta_mxd.is_dir():
                for arq in pasta_mxd.glob("*.mxd"):
                    zf.write(arq, arcname=f"MXD/{arq.name}")
            else:
                for arq in pasta_versao.glob("*.mxd"):
                    zf.write(arq, arcname=f"MXD/{arq.name}")

        # 2. Pasta SHP/
        pasta_shp = pasta_versao / "SHP"
        if pasta_shp.is_dir():
            for arq in pasta_shp.rglob("*"):
                if arq.is_file():
                    rel = arq.relative_to(pasta_shp)
                    zf.write(arq, arcname=f"SHP/{rel.as_posix()}")

        # 3. Pasta Mapas/
        pasta_mapas = pasta_versao / "Mapas"
        if pasta_mapas.is_dir():
            for arq in pasta_mapas.rglob("*"):
                if arq.is_file():
                    rel = arq.relative_to(pasta_mapas)
                    zf.write(arq, arcname=f"Mapas/{rel.as_posix()}")
        else:
            for pdf in pasta_versao.glob("*.pdf"):
                zf.write(pdf, arcname=f"Mapas/{pdf.name}")
            for xlsx in pasta_versao.glob("*.xlsx"):
                zf.write(xlsx, arcname=f"Mapas/{xlsx.name}")
            for j in pasta_versao.glob("validacao*.json"):
                zf.write(j, arcname=f"Mapas/{j.name}")

    return caminho_zip_destino
