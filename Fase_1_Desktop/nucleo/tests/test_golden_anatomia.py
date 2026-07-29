from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

from mapasfacil_nucleo.motores.gerar import gerar_mapa
from mapasfacil_nucleo.validacao import anatomia
from mapasfacil_nucleo.workspace import servico as workspace_servico
from tests.helpers_fixtures import montar_workspace_minimo

GOLDEN = Path(__file__).parent / "golden" / "anatomia_dinamica_retrato.png"
TOLERANCIA_PCT = 0.3


def test_golden_anatomia_renderizador_nativo(tmp_path: Path, repo_root: Path) -> None:
    """Regressão de layout estável no Linux e no Windows, sem rede nem ArcMap."""
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    estado = workspace_servico.estado_atual()
    assert estado is not None
    spec = json.loads(
        (repo_root / "shared/fixtures/mapspecs/dinamica_2026_canonico.json").read_text(
            encoding="utf-8"
        )
    )
    spec = copy.deepcopy(spec)
    spec["camadas"] = [c for c in spec["camadas"] if c["fonte"].startswith("local.")]
    spec["basemap"] = {"tipo": "nenhum"}
    spec["saidas"] = ["pdf"]
    spec["elementos_layout"]["tabela"] = False
    spec["saida"] = {
        "pasta": "Mapas",
        "nome_base": "golden_anatomia",
        "caminhos_relativos": True,
    }

    resultado = gerar_mapa(
        spec,
        estado.guard,
        workspace_servico.fontes_idx(estado),
    )
    pdf = tmp_path / resultado["pdf"]
    obtida = anatomia.imagem_anatomia(anatomia.medir(pdf))

    if os.environ.get("MAPASFACIL_ATUALIZAR_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        obtida.save(GOLDEN, format="PNG", optimize=True)

    assert GOLDEN.is_file(), (
        "golden ausente; gere conscientemente com "
        "MAPASFACIL_ATUALIZAR_GOLDEN=1 pytest tests/test_golden_anatomia.py"
    )

    with Image.open(GOLDEN) as esperado_img:
        esperado = esperado_img.convert("RGB")
    assert esperado.size == obtida.size

    arr = np.asarray(ImageChops.difference(esperado, obtida))
    diferenca_pct = float(np.any(arr != 0, axis=2).mean() * 100)
    if diferenca_pct > TOLERANCIA_PCT:
        diagnostico = repo_root / "output" / "golden-anatomia"
        diagnostico.mkdir(parents=True, exist_ok=True)
        esperado.save(diagnostico / "esperado.png")
        obtida.save(diagnostico / "obtido.png")
        Image.fromarray(np.where(np.any(arr != 0, axis=2), 255, 0).astype(np.uint8)).save(
            diagnostico / "diff.png"
        )
    assert diferenca_pct <= TOLERANCIA_PCT, (
        f"anatomia divergiu {diferenca_pct:.4f}% (tolerância {TOLERANCIA_PCT}%); "
        "veja output/golden-anatomia"
    )
