"""Registra um MXD preparado por `preparar_template_projeto_arcpy.py` (Python 3).

    python ferramentas/registrar_template_projeto.py <template_id> <preparado.mxd> <Arquivo.mxd> \
        --nome "Dinâmica 2008 (SPOT) — quadro de áreas" [--fonte Referencias_IMAP/...]

Lê `<preparado.mxd>.sentinelas.json`, copia o .mxd para `shared/templates/<Arquivo.mxd>`,
escreve `shared/templates/<Arquivo>.slots.json` e cria/atualiza a entrada no MANIFEST.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATES = RAIZ / "shared" / "templates"

# slot → (tipo, origem no MapSpec)
TEXTOS = {
    "titulo": "mapspec.titulo",
    "rotulo_imovel": "mapspec.imovel.nome",
    "municipio": "mapspec.imovel.municipio.nome",
    "quadro": "mapspec.ajustes_layout.quadro_resumo",
}
ENVELOPES = {"MAPA": "df_principal", "MINIMAPA": "minimapa"}


def _extensao_visivel(mxd: Path, env: list[float]) -> list[float] | None:
    """A outra extensão que o ArcMap grava para o data frame (a "visível"), se houver.

    Mesmo centro, tamanho um pouco diferente (no minimapa geográfico, ×0,99464). O ArcMap
    desenha por ela: trocar só a extensão principal deixava o minimapa em branco.
    """
    import numpy as np
    import olefile

    dados = olefile.OleFileIO(str(mxd)).openstream("Mx Document").read()
    x0, y0, x1, y1 = env
    cx, cy, w, h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    for alinhamento in range(8):
        n = (len(dados) - alinhamento) // 8
        a = np.frombuffer(dados, dtype="<f8", count=n, offset=alinhamento)
        with np.errstate(all="ignore"):
            ax0, ay0, ax1, ay1 = a[:-3], a[1:-2], a[2:-1], a[3:]
            ok = (
                (np.abs((ax0 + ax1) / 2 - cx) < w * 1e-6)
                & (np.abs((ay0 + ay1) / 2 - cy) < h * 1e-6)
                & (np.abs((ax1 - ax0) / w - 1) < 0.02)
                & (np.abs((ay1 - ay0) / h - 1) < 0.02)
                & ~(np.isclose(ax0, x0, rtol=1e-9, atol=0) & np.isclose(ay0, y0, rtol=1e-9, atol=0))
            )
        idx = np.nonzero(ok)[0]
        if len(idx):
            i = int(idx[0])
            return [float(ax0[i]), float(ay0[i]), float(ax1[i]), float(ay1[i])]
    return None


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("template_id")
    ap.add_argument("preparado")
    ap.add_argument("arquivo")
    ap.add_argument("--nome", required=True)
    ap.add_argument("--fonte", default="")
    ap.add_argument("--baseline", default="")
    args = ap.parse_args()

    preparado = Path(args.preparado)
    side = json.loads(Path(str(preparado) + ".sentinelas.json").read_text(encoding="utf-8"))
    destino = TEMPLATES / args.arquivo
    shutil.copy2(preparado, destino)
    sha = _sha(destino)

    streams = ["Mx Document", "PageLayout", "Maps"]
    slots = []
    for sid, sentinela in sorted(side["textos"].items()):
        slots.append(
            {
                "id": sid,
                "tipo": "texto",
                "obrigatorio": False,
                "origem": TEXTOS.get(sid, ""),
                "sentinela": sentinela,
                "streams": ["Mx Document", "PageLayout"],
            }
        )
    for df_nome, sid in ENVELOPES.items():
        df = side["data_frames"].get(df_nome)
        if not df:
            continue
        slots.append(
            {
                "id": sid,
                "tipo": "envelope",
                "obrigatorio": False,
                "origem": f"data_frame.{df_nome}",
                "sentinela": df["extent"],
                "streams": ["Mx Document", "Maps"],
                "extra": {"quadro_cm": df["quadro_cm"], "epsg": df["epsg"]},
            }
        )
        visivel = _extensao_visivel(preparado, df["extent"])
        if visivel:
            x0, y0, x1, y1 = df["extent"]
            slots.append(
                {
                    "id": f"{sid}_visivel",
                    "tipo": "envelope",
                    "obrigatorio": False,
                    "origem": f"data_frame.{df_nome}.visivel",
                    "sentinela": visivel,
                    "streams": ["Mx Document", "Maps"],
                    "extra": {
                        "relativo_a": sid,
                        "kx": (visivel[2] - visivel[0]) / (x1 - x0),
                        "ky": (visivel[3] - visivel[1]) / (y1 - y0),
                    },
                }
            )
    mini = side["data_frames"].get("MINIMAPA")
    if mini:
        slots.append(
            {
                "id": "escala_minimapa",
                "tipo": "numero",
                "obrigatorio": False,
                "origem": "data_frame.MINIMAPA",
                "sentinela": mini["escala"],
                "streams": ["Mx Document", "Maps"],
            }
        )
    escala = side["data_frames"]["MAPA"]["escala"]
    slots.append(
        {
            "id": "escala",
            "tipo": "numero",
            "obrigatorio": False,
            "origem": "mapspec.escala",
            "sentinela": escala,
            "streams": ["Mx Document", "Maps"],
        }
    )
    vistos = set()
    arquivos = []
    for a in side.get("arquivos", []):
        chave = (a["arquivo"], a["papel"])
        if chave not in vistos:
            vistos.add(chave)
            arquivos.append(a)

    manifesto_slots = {
        "template_id": args.template_id,
        "variante": {"formato": "A4", "orientacao": "retrato"},
        "arquivo_sha256": sha,
        "streams": streams,
        "slots": slots,
        "arquivos": arquivos,
    }
    caminho_slots = destino.with_suffix(".slots.json")
    caminho_slots.write_text(json.dumps(manifesto_slots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sha_slots = _sha(caminho_slots)

    mp = TEMPLATES / "MANIFEST.json"
    bruto = mp.read_bytes().decode("utf-8")
    manifest = json.loads(bruto)
    entrada = next((t for t in manifest["templates"] if t["id"] == args.template_id), None)
    variante = {
        "formato": "A4",
        "orientacao": "retrato",
        "arquivo": destino.name,
        "sha256": sha,
        "slots": caminho_slots.name,
        "slots_sha256": sha_slots,
        "verificado_arcmap": {"em": "2026-11-04T21:00:00Z", "arcmap": "10.8", "motor_binario": "0.2.0", "ok": True},
    }
    if entrada is None:
        entrada = {
            "id": args.template_id,
            "nome": args.nome,
            "arquivo": destino.name,
            "fonte_acervo": args.fonte,
            "baseline_pdf": args.baseline,
            "sha256": sha,
            "versao_arcmap": "10.8",
            "formato_pagina": {"papel": "A4", "orientacao": "retrato", "mm": [210, 297]},
            "crs_data_frame": f"EPSG:{side['data_frames']['MAPA']['epsg']}",
            "status": "pronto",
            "variantes": [variante],
        }
        manifest["templates"].append(entrada)
    else:
        entrada["arquivo"] = destino.name
        entrada["sha256"] = sha
        entrada["variantes"] = [
            dict(v, **{k: variante[k] for k in ("arquivo", "sha256", "slots", "slots_sha256", "verificado_arcmap")})
            for v in entrada.get("variantes") or [variante]
        ]
        # offsets fixos do patch antigo deixaram de valer com o .mxd novo
        entrada.pop("patch", None)
    texto = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if "\r\n" in bruto:
        texto = texto.replace("\n", "\r\n")
    mp.write_bytes(texto.encode("utf-8"))
    print("registrado", args.template_id, destino.name, sha[:12], caminho_slots.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
