from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def gerar(
    *,
    motor: str = "nativo",
    confianca: str = "estrutural",
    checks_hard: list[dict[str, Any]] | None = None,
    checks_soft: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hard = checks_hard or []
    soft = checks_soft or []
    hard_ok = sum(1 for c in hard if c.get("ok"))
    soft_ok = sum(1 for c in soft if c.get("ok"))

    return {
        "versao": 1,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "motor": motor,
        "confianca": confianca,
        "resumo": {
            "hard_total": len(hard),
            "hard_ok": hard_ok,
            "soft_total": len(soft),
            "soft_ok": soft_ok,
            "aprovado": hard_ok == len(hard),
        },
        "checks": {
            "hard": hard,
            "soft": soft,
        },
    }


def salvar(caminho: Path, relatorio: dict[str, Any]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho
