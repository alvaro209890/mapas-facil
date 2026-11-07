"""Montador do pacote de entrega MXD/SHP/Mapas/ (W10-10 / D37).

Estrutura gerada:
Fazenda_Boa_Vista__Dinamica_2026__v003.zip
├── MXD/
│   └── Dinamica_2026.mxd             ← caminhos RELATIVOS: ..\\SHP\\…
├── SHP/
│   ├── ATP.shp .shx .dbf .prj .cpg   ← nomes que o template espera, no CRS do data frame
│   ├── AVN.* AREA_CONSOLIDADA.* AUAS.* …
│   ├── externas/terras_indigenas.* … ← camadas WFS materializadas
│   ├── minimapa/municipios_mt.* uf.* ← da base IBGE
│   └── imagens/mosaico_2026_10.tif   ← recorte local do mosaico (GeoTIFF)
├── Mapas/
│   ├── Dinamica_2026.pdf
│   ├── Quantitativos.xlsx            ← se houver
│   └── validacao.json                ← HARD/SOFT da versão
└── LEIA-ME.txt

Política de entrega (D37): o pacote sai sempre. Se G1-G3 falharem no MXD, o MXD
não entra, Mapas/ e SHP/ seguem e o LEIA-ME.txt registra o código de aviso MX-0xx.
"""

from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .documento import DocumentoMxd


@dataclass
class OpcoesPacote:
    """Opções para geração do pacote de entrega."""

    nome_imovel: str = "Imovel"
    nome_template: str = "Mapa"
    versao: int = 1
    mxd_doc: DocumentoMxd | None = None
    mxd_conforme: bool = True
    incluir_mxd: bool = False
    codigo_aviso_mxd: str | None = None
    datum: str = "SIRGAS 2000 / UTM zone 22S"
    data_imagem: str = "2026-10"
    checks_reprovados: list[str] | None = None


def _mxd_habilitado(opcoes: OpcoesPacote) -> bool:
    import os

    return bool(opcoes.incluir_mxd and opcoes.mxd_conforme and os.environ.get("MF_MXD") == "1")


def gerar_leia_me(opcoes: OpcoesPacote) -> str:
    """Gera o conteúdo de texto para LEIA-ME.txt."""
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

    if _mxd_habilitado(opcoes) and opcoes.mxd_doc is not None:
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
        aviso = opcoes.codigo_aviso_mxd or ("MX-020" if opcoes.incluir_mxd else "PDF-FIRST")
        linhas.extend(
            [
                f"AVISO [{aviso}]: O arquivo .mxd não foi incluído nesta versão.",
                "O mapa final aprovado em PDF de alta resolução, planilhas e as geometrias",
                "vetoriais auditadas seguem disponíveis nas pastas 'Mapas/', 'XLSX/' e 'SHP/'.",
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


def montar_pacote_zip(
    pasta_versao: Path,
    caminho_zip_destino: Path,
    opcoes: OpcoesPacote,
) -> Path:
    """Monta o arquivo .zip de entrega conforme o contrato D37 / PDF-first."""
    caminho_zip_destino.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(caminho_zip_destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. LEIA-ME.txt na raiz do zip
        conteudo_leia_me = gerar_leia_me(opcoes)
        zf.writestr("LEIA-ME.txt", conteudo_leia_me)

        # 2. Pasta MXD/ (se habilitado e disponível)
        if _mxd_habilitado(opcoes) and opcoes.mxd_doc is not None:
            bytes_mxd = opcoes.mxd_doc.obter_bytes()
            nome_arq_mxd = f"MXD/{opcoes.nome_template}.mxd"
            zf.writestr(nome_arq_mxd, bytes_mxd)

        # 3. Pasta SHP/ (copia da pasta da versão ou do projeto)
        pasta_shp = pasta_versao / "SHP"
        if pasta_shp.is_dir():
            for arquivo in sorted(pasta_shp.rglob("*")):
                if arquivo.is_file():
                    rel = arquivo.relative_to(pasta_shp)
                    zf.write(arquivo, arcname=f"SHP/{rel.as_posix()}")

        # 4. Pasta Mapas/ e XLSX/ (PDFs, relatórios e validação)
        pasta_mapas = pasta_versao / "Mapas"
        if pasta_mapas.is_dir():
            for arquivo in sorted(pasta_mapas.rglob("*")):
                if arquivo.is_file():
                    rel = arquivo.relative_to(pasta_mapas)
                    if arquivo.suffix.lower() == ".mxd":
                        continue
                    prefixo = "XLSX" if arquivo.suffix.lower() == ".xlsx" else "Mapas"
                    zf.write(arquivo, arcname=f"{prefixo}/{rel.as_posix()}")
        else:
            # Se não houver subpasta Mapas/, procura diretamente na pasta da versão
            for pdf in sorted(pasta_versao.glob("*.pdf")):
                zf.write(pdf, arcname=f"Mapas/{pdf.name}")
            for xlsx in sorted(pasta_versao.glob("*.xlsx")):
                zf.write(xlsx, arcname=f"XLSX/{xlsx.name}")
            for j in sorted(pasta_versao.glob("validacao*.json")):
                zf.write(j, arcname=f"Mapas/{j.name}")

    return caminho_zip_destino
