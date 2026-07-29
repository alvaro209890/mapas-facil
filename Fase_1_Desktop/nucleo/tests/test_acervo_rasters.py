from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from mapasfacil_nucleo.acervo import rasters
from mapasfacil_nucleo.fsguard import WorkspaceGuard
from mapasfacil_nucleo.motores import basemap

BBOX = (-51.2, -12.3, -51.0, -12.1)


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "#47643f").save(buffer, format="PNG")
    return buffer.getvalue()


def test_acervo_rejeita_conteudo_corrompido(tmp_path: Path) -> None:
    base = tmp_path / "acervo"
    imagem = _png()
    caminho = rasters.salvar("fonte", BBOX, "EPSG:4674", 1600, imagem, base=base)
    assert caminho is not None
    assert rasters.obter("fonte", BBOX, "EPSG:4674", 1600, base=base) is not None

    caminho.write_bytes(imagem + b"corrompido")
    assert rasters.obter("fonte", BBOX, "EPSG:4674", 1600, base=base) is None


def test_basemap_reutiliza_acervo_entre_workspaces(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAPASFACIL_ACERVO_RASTERS", str(tmp_path / "acervo"))
    camada = {
        "id": "teste",
        "nome": "Mosaico teste",
        "tipo": "wms_raster",
        "endpoint": "https://example.invalid/wms",
        "layer": "teste:mosaico",
    }
    monkeypatch.setattr(basemap.catalogo_mod, "buscar", lambda _id: camada)
    chamadas = 0

    def baixar(*_args, **_kwargs):
        nonlocal chamadas
        chamadas += 1
        return {"imagem": _png()}

    monkeypatch.setattr(basemap.wms, "buscar_mapa", baixar)

    resultados = []
    for nome in ("projeto-a", "projeto-b"):
        workspace = tmp_path / nome
        (workspace / "Mapas").mkdir(parents=True)
        resultados.append(
            basemap.buscar(
                {"tipo": "teste"},
                guard=WorkspaceGuard(workspace),
                extent=BBOX,
                epsg=4674,
            )
        )

    assert chamadas == 1
    assert [item["origem_acervo"] for item in resultados] == ["miss", "hit"]
    assert all(item["ok"] and item["caminho"].is_file() for item in resultados)
