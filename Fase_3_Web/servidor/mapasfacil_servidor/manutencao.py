"""Manutenção: lixeira e uploads velhos (W-03 `limpar-lixeira`, W12-04)."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from .db import Banco

DIAS_LIXEIRA = 30
HORAS_UPLOAD = 24


def limpar_lixeira(banco: Banco, cfg: object, *, dias: int = DIAS_LIXEIRA) -> dict:
    """Apaga de vez projetos na lixeira há mais de `dias` e uploads não usados."""
    limite = f"-{int(dias)} days"
    con = banco.conectar()
    apagados = 0
    try:
        linhas = con.execute(
            "SELECT id FROM projetos WHERE estado = 'lixeira'"
            " AND COALESCE(apagado_em, atualizado_em) <= datetime('now', ?)",
            (limite,),
        ).fetchall()
        projetos_dir = Path(str(getattr(cfg, "projetos", ""))) if getattr(cfg, "projetos", None) else None
        for linha in linhas:
            projeto_id = linha["id"]
            con.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))
            if projetos_dir is not None:
                pasta = projetos_dir / projeto_id
                if pasta.is_dir():
                    shutil.rmtree(pasta, ignore_errors=True)
            apagados += 1
    finally:
        con.close()

    uploads = 0
    uploads_dir = Path(str(getattr(cfg, "uploads", ""))) if getattr(cfg, "uploads", None) else None
    if uploads_dir is not None and uploads_dir.is_dir():
        limite_s = time.time() - HORAS_UPLOAD * 3600
        for arquivo in uploads_dir.iterdir():
            try:
                if arquivo.is_file() and arquivo.stat().st_mtime < limite_s:
                    arquivo.unlink()
                    uploads += 1
            except OSError:  # pragma: no cover - arquivo travado
                continue

    return {"projetos": apagados, "uploads": uploads}
