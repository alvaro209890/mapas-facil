from __future__ import annotations

from mapasfacil_nucleo.quantitativos.conferencia import montar_conferencia


def test_conferencia_sem_recibo() -> None:
    quant = {
        "casas_decimais": 4,
        "areas": {"area_total_ha": 100.0, "avn_ha": 64.0, "ac_ha": None, "auas_ha": 16.0},
    }
    conf = montar_conferencia(quant, None)
    assert conf["tem_recibo"] is False
    assert any(l["classe"].startswith("Área total") for l in conf["linhas"])
    assert any("sem valor no recibo" in a for a in conf["avisos"])


def test_conferencia_bate_com_recibo() -> None:
    quant = {
        "casas_decimais": 4,
        "areas": {
            "area_total_ha": 3823.9033,
            "avn_ha": 2833.7541,
            "ac_ha": 483.8562,
            "auas_ha": 16.0,
        },
    }
    recibo = {
        "area_total_ha": 3823.9033,
        "areas": {
            "vegetacao_nativa_ha": 2833.7541,
            "consolidada_ha": 483.8562,
        },
    }
    conf = montar_conferencia(quant, recibo)
    assert conf["tem_recibo"] is True
    por_classe = {l["classe"]: l for l in conf["linhas"]}
    assert por_classe["Área total da propriedade"]["ok"] is True
    assert por_classe["Área total da propriedade"]["diferenca_ha"] == 0.0
    assert por_classe["Área de vegetação nativa"]["ok"] is True
    # AUAS sem recibo → aviso, mas ok permanece True (só falta declarado)
    assert por_classe["Área Derivada de Desmate Após 2008"]["declarado_ha"] is None
    assert por_classe["Área Derivada de Desmate Após 2008"]["ok"] is True


def test_conferencia_detecta_divergencia() -> None:
    quant = {"casas_decimais": 4, "areas": {"area_total_ha": 100.0}}
    recibo = {"area_total_ha": 90.0, "areas": {}}
    conf = montar_conferencia(quant, recibo, tolerancia_ha=0.01)
    assert conf["ok"] is False
    linha = next(l for l in conf["linhas"] if "total" in l["classe"].lower())
    assert linha["diferenca_ha"] == 10.0
    assert abs(linha["diferenca_pct"] - (10.0 / 90.0)) < 1e-6
