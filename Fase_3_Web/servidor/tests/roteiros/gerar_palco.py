"""W7-10 — grava um roteiro REAL do palco (NDJSON + assets de `.preview`).

O roteiro não é inventado: roda `gerar_mapa` de ponta a ponta num projeto **sintético** (dois
shapefiles quadrados, zero dado de cliente) e grava, na ordem em que o núcleo emitiu, tudo o que
o palco da web consome — mais os arquivos de `Mapas/.preview/<job>/` ao lado, para o teste de
replay rodar sem rede e sem núcleo.

    cd Fase_1_Desktop/nucleo
    ./.venv/Scripts/python.exe ../../Fase_3_Web/servidor/tests/roteiros/gerar_palco.py

Saída (em `Fase_3_Web/servidor/tests/roteiros/`):

    palco_dinamica.ndjson          um evento por linha, `{seq, evento, dados}` como o SSE entrega
    palco_dinamica/camadas/*.geojson
    palco_dinamica/layout/*.png    recortes por elemento (W7-06)
    palco.json                     metadados: job_id, contagens e sha256 do ndjson

⚠️ O nome NÃO é `dinamica_ok.ndjson`: aquele arquivo já existe desde o W2 e é o roteiro do
`fake_nucleo` (envelopes req/res/evt). Sobrescrevê-lo quebra `test_ponte.py`.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[4]
NUCLEO = RAIZ_REPO / "Fase_1_Desktop" / "nucleo"
DESTINO = Path(__file__).resolve().parent
JOB = "01JOBPALCO0000000000000000"
sys.path.insert(0, str(NUCLEO))

from mapasfacil_nucleo.motores.gerar import gerar_mapa  # noqa: E402
from mapasfacil_nucleo.progresso import RastreadorProgresso  # noqa: E402
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm  # noqa: E402


def montar_projeto(raiz: Path) -> dict:
    for nome in ("Mapas", "SHP", "MXD", "_extraido"):
        (raiz / nome).mkdir(parents=True, exist_ok=True)
    escrever_shapefile_quadrado_utm(raiz / "Dados" / "ATP.shp", nome="Harmonia", lado_m=4000)
    escrever_shapefile_quadrado_utm(raiz / "Dados" / "AVN.shp", nome="AVN", lado_m=1500)
    from mapasfacil_nucleo.fsguard import WorkspaceGuard

    mapspec = {
        "contract_version": 3,
        "perfil": "harmonia",
        "id": "spec_palco_roteiro",
        "versao": 1,
        "titulo": "Dinâmica de uso do solo",
        "template": "dinamica_retrato",
        "folha": {"formato": "A4", "orientacao": "retrato"},
        "saidas": ["pdf"],
        "imovel": {
            "nome": "Fazenda Harmonia",
            "car": "MT102042/2017",
            "municipio": {"nome": "Vila Rica", "uf": "MT"},
            "geometria": "local.ATP",
        },
        "crs": "EPSG:31982",
        "escala": "auto",
        "camadas": [
            {
                "id": "perimetro",
                "nome_no_mxd": "Fazenda Harmonia",
                "fonte": "local.ATP",
                "estilo": "perimetro_imovel",
                "ordem": 10,
            },
            {
                "id": "avn",
                "nome_no_mxd": "Área de vegetação nativa",
                "fonte": "local.AVN",
                "estilo": "avn",
                "ordem": 30,
            },
        ],
        "elementos_layout": {"tabela": False, "minimapa": False},
        "saida": {
            "pasta": "Mapas",
            "nome_base": "Dinamica",
            "materializar_camadas_em": "SHP",
        },
    }
    return {
        "guard": WorkspaceGuard(raiz),
        "mapspec": mapspec,
        "fontes_idx": {
            "ATP": str(raiz / "Dados" / "ATP.shp"),
            "AVN": str(raiz / "Dados" / "AVN.shp"),
        },
        "raiz": raiz,
    }


def main() -> int:
    temporaria = Path(tempfile.mkdtemp(prefix="roteiro-palco-"))
    try:
        projeto = montar_projeto(temporaria / "projeto")
        eventos: list[dict] = []
        prog = RastreadorProgresso(
            lambda evento, dados: eventos.append({"evento": evento, "dados": dados}), job_id=JOB
        )
        gerar_mapa(
            projeto["mapspec"],
            projeto["guard"],
            projeto["fontes_idx"],
            progresso=prog,
        )

        linhas = []
        for seq, evento in enumerate(eventos, start=1):
            linhas.append(json.dumps({"seq": seq, **evento}, ensure_ascii=False))
        texto = "\n".join(linhas) + "\n"

        DESTINO.mkdir(parents=True, exist_ok=True)
        ndjson = DESTINO / "palco_dinamica.ndjson"
        ndjson.write_text(texto, encoding="utf-8")

        preview_origem = projeto["raiz"] / "Mapas" / ".preview" / JOB
        preview_destino = DESTINO / "palco_dinamica"
        if preview_destino.is_dir():
            shutil.rmtree(preview_destino)
        if preview_origem.is_dir():
            shutil.copytree(preview_origem, preview_destino)

        contagem: dict[str, int] = {}
        for evento in eventos:
            contagem[evento["evento"]] = contagem.get(evento["evento"], 0) + 1
        meta = {
            "job_id": JOB,
            "eventos": len(eventos),
            "por_evento": contagem,
            "sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
            "assets": sorted(
                str(p.relative_to(DESTINO)).replace("\\", "/")
                for p in (preview_destino.rglob("*") if preview_destino.is_dir() else [])
                if p.is_file()
            ),
        }
        (DESTINO / "palco.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps({"ndjson": str(ndjson), **{k: v for k, v in meta.items() if k != "assets"}},
                         ensure_ascii=False, indent=2))
        return 0
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
