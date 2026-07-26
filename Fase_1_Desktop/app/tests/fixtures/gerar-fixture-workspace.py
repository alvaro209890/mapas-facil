#!/usr/bin/env python3
"""Gera `workspace-abrir.json` e `doctor-rodar.json` chamando o núcleo de verdade.

A fixture do teste do `painel-workspace` **não é escrita à mão**: ela é a resposta
real de `workspace.abrir` sobre uma pasta montada aqui, para que a UI nunca teste
um formato que o núcleo não produz. Rode de dentro do venv do núcleo:

    cd Fase_1_Desktop/nucleo
    .venv/bin/python ../app/tests/fixtures/gerar-fixture-workspace.py

A pasta é temporária e a raiz é reescrita para um caminho neutro — o JSON
versionado não carrega caminho de máquina de ninguém. Nenhum recibo do CAR entra
aqui (AP-09): o PDF da fixture é um mapa de referência sem dado pessoal.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ_NUCLEO = Path(__file__).resolve().parents[4] / "Fase_1_Desktop" / "nucleo"
sys.path.insert(0, str(RAIZ_NUCLEO))
sys.path.insert(0, str(RAIZ_NUCLEO / "tests"))

import fitz  # noqa: E402
from helpers_fixtures import escrever_shapefile_quadrado_utm  # noqa: E402

from mapasfacil_nucleo import doctor  # noqa: E402
from mapasfacil_nucleo.workspace import servico  # noqa: E402

RAIZ_NEUTRA = "/projetos/Analise_de_area-Harmonia"
DESTINO = Path(__file__).with_name("workspace-abrir.json")
DESTINO_DOCTOR = Path(__file__).with_name("doctor-rodar.json")

# lado em metros → área exata em hectares, para o teste conferir a formatação pt-BR
CAMADAS = {
    "SHP/ATP.shp": 6_000.0,  # 3.600,0000 ha
    "SHP/AVN.shp": 1_200.0,  # 144,0000 ha
    "SHP/AUAS.shp": 700.0,  # 49,0000 ha
}
SEM_PRJ = "SHP/AREA_CONSOLIDADA.shp"  # dispara o aviso NU-020


def montar(raiz: Path) -> None:
    for rel, lado in CAMADAS.items():
        escrever_shapefile_quadrado_utm(raiz / rel, lado_m=lado, nome=Path(rel).stem)

    escrever_shapefile_quadrado_utm(raiz / SEM_PRJ, lado_m=500.0, nome="AC")
    (raiz / SEM_PRJ).with_suffix(".prj").unlink()

    (raiz / "Mapas").mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 72), "Mapa de referencia - Dinamica de uso do solo")
    doc.save(raiz / "Mapas" / "Dinamica_referencia.pdf")
    doc.close()


def escrever_doctor() -> None:
    """`doctor.rodar` sem sondar arcpy, com o que é da máquina trocado por valor fixo.

    As chaves viram `false` de propósito: é o caso que o teste precisa exercitar
    (banner informativo de chave ausente, com o app continuando a funcionar).
    Nenhum valor de chave existe aqui — o núcleo só devolve booleanos.
    """
    resultado = doctor.rodar(sondar_arcpy=False)
    resultado["repositorio"] = "/projetos/mapas-facil"
    resultado["espaco_livre_gb"] = 128.4
    resultado["chaves"] = {"deepseek": False, "sema": True, "planet": False}
    DESTINO_DOCTOR.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"escrito: {DESTINO_DOCTOR}")


def main() -> None:
    temporaria = Path(tempfile.mkdtemp(prefix="mapasfacil-fixture-"))
    raiz = temporaria / "Analise_de_area-Harmonia"
    raiz.mkdir(parents=True)
    try:
        montar(raiz)
        resposta = servico.abrir(str(raiz))
        bruto = json.dumps(resposta, ensure_ascii=False, indent=2)
        bruto = bruto.replace(str(raiz), RAIZ_NEUTRA)
        DESTINO.write_text(bruto + "\n", encoding="utf-8")
        print(f"escrito: {DESTINO}")
        escrever_doctor()
    finally:
        shutil.rmtree(temporaria, ignore_errors=True)


if __name__ == "__main__":
    main()
