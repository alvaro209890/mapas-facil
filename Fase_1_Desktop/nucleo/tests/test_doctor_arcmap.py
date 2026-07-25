from __future__ import annotations

from unittest.mock import patch

from mapasfacil_nucleo.doctor import _motor_preferido, rodar


def test_motor_preferido_arcpy_quando_disponivel() -> None:
    arcmap = {"encontrado": True, "versao": "10.8", "instavel": False}
    templates = [{"patch_ok": False}]
    assert _motor_preferido(arcmap, templates) == "arcpy"


def test_motor_preferido_patch() -> None:
    arcmap = {"encontrado": False}
    templates = [{"patch_ok": True}]
    assert _motor_preferido(arcmap, templates) == "patch"


def test_motor_preferido_nativo() -> None:
    arcmap = {"encontrado": False}
    templates = [{"patch_ok": False}]
    assert _motor_preferido(arcmap, templates) == "nativo"


@patch("mapasfacil_nucleo.doctor._detectar_arcmap")
def test_doctor_sem_arcmap(mock_detectar) -> None:
    mock_detectar.return_value = {
        "encontrado": False,
        "instavel": False,
        "nota": "Detecção completa disponível apenas no Windows.",
    }
    dados = rodar()
    assert dados["motor_preferido"] == "nativo"
    assert dados["arcmap"]["encontrado"] is False
    assert "templates" in dados
    assert dados["nucleo"] == "0.3.1"
