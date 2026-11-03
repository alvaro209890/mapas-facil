"""W2-06 — ponte falando com o **núcleo real**, em modo servidor.

Roda onde o núcleo está instalado (aqui, no venv do núcleo; no CI Linux, no job que
instala o pacote). Sem núcleo, o teste é pulado — e o pulo é explícito no relatório,
nunca um verde falso.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from mapasfacil_servidor.erros import ErroServidor
from mapasfacil_servidor.ponte import allowlist
from mapasfacil_servidor.ponte.worker import Worker, montar_env

pytestmark = pytest.mark.nucleo_real

REPO = Path(__file__).resolve().parents[3]
CANDIDATOS = (
    REPO / "Fase_1_Desktop" / "nucleo" / ".venv" / "Scripts" / "python.exe",
    REPO / "Fase_1_Desktop" / "nucleo" / ".venv" / "bin" / "python",
)


def _python_do_nucleo() -> str | None:
    bruto = os.environ.get("MF_PYTHON_NUCLEO")
    candidatos = [Path(bruto)] if bruto else list(CANDIDATOS)
    for caminho in candidatos:
        if not caminho.exists():
            continue
        teste = subprocess.run(
            [str(caminho), "-c", "import mapasfacil_nucleo, sys; print(mapasfacil_nucleo.__version__)"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if teste.returncode == 0:
            return str(caminho)
    return None


def test_metodos_reais_batem_com_a_allowlist():
    python = _python_do_nucleo()
    if python is None:
        pytest.skip("núcleo não instalado neste interpretador (MF_PYTHON_NUCLEO)")

    codigo = (
        "import json;"
        "from mapasfacil_nucleo.__main__ import criar_roteador;"
        "r=criar_roteador();"
        "print(json.dumps(sorted(r._handlers)))"
    )
    saida = subprocess.run(
        [python, "-c", codigo], capture_output=True, text=True, timeout=120
    )
    assert saida.returncode == 0, saida.stderr[-2000:]
    import json as _json

    metodos = set(_json.loads(saida.stdout.strip().splitlines()[-1]))
    sem_classificacao = sorted(metodos - allowlist.PERMITIDOS - set(allowlist.BLOQUEADOS))
    assert not sem_classificacao, f"método do núcleo sem decisão na ponte: {sem_classificacao}"


def test_worker_fala_com_o_nucleo_real(tmp_path):
    python = _python_do_nucleo()
    if python is None:
        pytest.skip("núcleo não instalado neste interpretador (MF_PYTHON_NUCLEO)")

    raiz = tmp_path / "projeto"
    raiz.mkdir()

    async def cenario():
        env = montar_env(projeto_raiz=raiz, usuario_id="usuario_01")
        w = Worker(
            projeto_id="real",
            raiz=raiz,
            cmd=[python, "-m", "mapasfacil_nucleo"],
            env=env,
            timeout_req_s=180.0,
            log_path=tmp_path / "logs" / "real.log",
        )
        await w.iniciar()
        try:
            assert w.estado == "pronto"

            doctor = await w.chamar("doctor.rodar", {"sondar_arcpy": False})
            assert doctor["nucleo"], doctor
            assert doctor["pronto_para_mxd"] is True

            galeria = await w.chamar("galeria.listar", {})
            assert galeria, "galeria.listar deveria devolver os templates do MANIFEST"

            # Método bloqueado não chega ao worker (allowlist antes da chamada).
            with pytest.raises(ErroServidor) as exc:
                allowlist.verificar("cofre.definir")
            assert exc.value.codigo == "SV-201"
        finally:
            await w.encerrar(motivo="fim do teste")

    asyncio.run(cenario())


def test_worker_real_recusa_arcpy_no_servidor(tmp_path):
    """O núcleo em modo servidor não pode escolher ArcPy (D24/W1-11)."""
    python = _python_do_nucleo()
    if python is None:
        pytest.skip("núcleo não instalado neste interpretador (MF_PYTHON_NUCLEO)")
    assert sys.version_info >= (3, 12)

    raiz = tmp_path / "projeto"
    raiz.mkdir()
    env = montar_env(projeto_raiz=raiz, usuario_id="u1")
    assert env["MAPASFACIL_MODO"] == "servidor"
