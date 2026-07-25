from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from mapasfacil_nucleo import __version__


from mapasfacil_nucleo import __version__


def test_doctor_cli_json() -> None:
    nucleo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "mapasfacil_nucleo", "doctor", "--json"],
        cwd=nucleo,
        check=True,
        capture_output=True,
        text=True,
    )
    dados = json.loads(proc.stdout)
    assert dados["nucleo"] == __version__
    assert "templates" in dados
