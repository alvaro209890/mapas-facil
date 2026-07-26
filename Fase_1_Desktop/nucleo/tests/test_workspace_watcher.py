"""A12 — watcher da pasta → `workspace.mudou` (debounce 500 ms)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from mapasfacil_nucleo.protocolo import configurar_sink_assincrono
from mapasfacil_nucleo.workspace import servico as workspace_servico
from mapasfacil_nucleo.workspace import watcher as watcher_mod
from mapasfacil_nucleo.workspace.watcher import (
    DEBOUNCE_S,
    WatcherWorkspace,
    capturar_fingerprint,
    diff_indices,
    nome_ignorado,
)
from tests.helpers_fixtures import escrever_shapefile_quadrado_utm, montar_workspace_minimo


@pytest.fixture(autouse=True)
def _limpar_workspace():
    workspace_servico.fechar()
    configurar_sink_assincrono(None)
    yield
    workspace_servico.fechar()
    configurar_sink_assincrono(None)


class RelogioFake:
    """Avança o tempo sem dormir — torna o debounce determinístico."""

    def __init__(self) -> None:
        self.agora = 0.0

    def clock(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos

    def sleep(self, _segundos: float) -> None:
        return


def test_nome_ignorado_lock_tmp_office() -> None:
    assert nome_ignorado("arquivo.lock")
    assert nome_ignorado("rascunho.tmp")
    assert nome_ignorado("~$Planilha.xlsx")
    assert nome_ignorado("backup~")
    assert not nome_ignorado("ATP.shp")
    assert not nome_ignorado("recibo.pdf")


def test_diff_indices_adicionado_removido_modificado() -> None:
    antes = {
        "shapefiles": [
            {
                "caminho": "dados/ATP.shp",
                "papel": "ATP",
                "feicoes": 1,
                "area_ha": 10.0,
                "tipo_geometria": "Polygon",
                "valido": True,
                "crs": {"epsg": 31982},
            }
        ],
        "pdfs": [],
        "zips": [],
        "outros": [],
    }
    depois = {
        "shapefiles": [
            {
                "caminho": "dados/ATP.shp",
                "papel": "ATP",
                "feicoes": 2,
                "area_ha": 20.0,
                "tipo_geometria": "Polygon",
                "valido": True,
                "crs": {"epsg": 31982},
            },
            {
                "caminho": "dados/AUAS.shp",
                "papel": "AUAS",
                "feicoes": 8,
                "area_ha": 491.26,
                "tipo_geometria": "Polygon",
                "valido": True,
                "crs": {"epsg": 31982},
            },
        ],
        "pdfs": [],
        "zips": [{"caminho": "pacote.zip"}],
        "outros": [],
    }
    mudancas = diff_indices(antes, depois)
    acoes = {(m["acao"], m["caminho"]) for m in mudancas}
    assert ("modificado", "dados/ATP.shp") in acoes
    assert ("adicionado", "dados/AUAS.shp") in acoes
    assert ("adicionado", "pacote.zip") in acoes
    auas = next(m for m in mudancas if m["caminho"] == "dados/AUAS.shp")
    assert auas["tipo"] == "shapefile"
    assert "apareceu" in auas["resumo"]
    assert "AUAS" in auas["resumo"]


def test_debounce_nao_emite_antes_de_500ms(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    watcher_mod.parar()  # testes usam tick() síncrono; a thread atrapalharia
    emitidos: list[tuple[str, dict]] = []
    relogio = RelogioFake()

    w = WatcherWorkspace(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        emitir=lambda evento, dados: emitidos.append((evento, dados)),
        debounce_s=DEBOUNCE_S,
        clock=relogio.clock,
        sleep=relogio.sleep,
    )

    escrever_shapefile_quadrado_utm(tmp_path / "dados" / "NOVO.shp", nome="NOVO")
    assert w.tick() is False
    assert emitidos == []

    relogio.avancar(0.4)
    assert w.tick() is False
    assert emitidos == []

    relogio.avancar(0.2)  # total 0.6 ≥ 0.5
    assert w.tick() is True
    assert len(emitidos) == 1
    evento, dados = emitidos[0]
    assert evento == "workspace.mudou"
    adicionados = [m for m in dados["mudancas"] if m["acao"] == "adicionado"]
    assert any(m["caminho"] == "dados/NOVO.shp" for m in adicionados)
    assert "workspace" in dados
    assert any(s["caminho"] == "dados/NOVO.shp" for s in dados["workspace"]["shapefiles"])


def test_debounce_reinicia_se_continuar_mudando(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    watcher_mod.parar()
    emitidos: list[tuple[str, dict]] = []
    relogio = RelogioFake()

    w = WatcherWorkspace(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        emitir=lambda evento, dados: emitidos.append((evento, dados)),
        debounce_s=0.5,
        clock=relogio.clock,
        sleep=relogio.sleep,
    )

    escrever_shapefile_quadrado_utm(tmp_path / "dados" / "A.shp", nome="A")
    w.tick()
    relogio.avancar(0.4)
    w.tick()
    escrever_shapefile_quadrado_utm(tmp_path / "dados" / "B.shp", nome="B")
    w.tick()  # reinicia debounce
    relogio.avancar(0.4)
    assert w.tick() is False
    relogio.avancar(0.2)
    assert w.tick() is True
    caminhos = {m["caminho"] for m in emitidos[0][1]["mudancas"]}
    assert "dados/A.shp" in caminhos
    assert "dados/B.shp" in caminhos


def test_ignora_tmp_e_nao_emite(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    watcher_mod.parar()
    emitidos: list = []
    relogio = RelogioFake()
    w = WatcherWorkspace(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        emitir=lambda e, d: emitidos.append((e, d)),
        debounce_s=0.5,
        clock=relogio.clock,
        sleep=relogio.sleep,
    )
    (tmp_path / "rascunho.tmp").write_text("x", encoding="utf-8")
    (tmp_path / "dados" / "arquivo.lock").write_text("x", encoding="utf-8")
    w.tick()
    relogio.avancar(1.0)
    assert w.tick() is False
    assert emitidos == []


def test_pausar_saidas_ignora_mapas_durante_job(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    watcher_mod.parar()
    emitidos: list = []
    relogio = RelogioFake()
    w = WatcherWorkspace(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        emitir=lambda e, d: emitidos.append((e, d)),
        debounce_s=0.5,
        clock=relogio.clock,
        sleep=relogio.sleep,
    )
    w.pausar_pastas_saida(True)
    (tmp_path / "Mapas").mkdir(exist_ok=True)
    (tmp_path / "Mapas" / "parcial.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    w.tick()
    relogio.avancar(1.0)
    assert w.tick() is False
    assert emitidos == []

    # Fora do job, arquivo relevante em dados/ ainda dispara.
    w.pausar_pastas_saida(False)
    escrever_shapefile_quadrado_utm(tmp_path / "dados" / "NOVO.shp", nome="NOVO")
    w.tick()
    relogio.avancar(1.0)
    assert w.tick() is True
    assert emitidos[0][1]["mudancas"][0]["caminho"] == "dados/NOVO.shp"


def test_remover_shapefile_emite_removido(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    watcher_mod.parar()
    emitidos: list = []
    relogio = RelogioFake()
    w = WatcherWorkspace(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        emitir=lambda e, d: emitidos.append((e, d)),
        debounce_s=0.5,
        clock=relogio.clock,
        sleep=relogio.sleep,
    )
    shp = tmp_path / "dados" / "ATP.shp"
    for ext in (".shp", ".dbf", ".shx", ".prj"):
        p = shp.with_suffix(ext)
        if p.exists():
            p.unlink()
    w.tick()
    relogio.avancar(1.0)
    assert w.tick() is True
    assert emitidos[0][1]["mudancas"][0]["acao"] == "removido"
    assert emitidos[0][1]["mudancas"][0]["caminho"] == "dados/ATP.shp"


def test_abrir_liga_watcher_e_fechar_para(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    workspace_servico.abrir(str(tmp_path))
    atual = watcher_mod.atual()
    assert atual is not None
    assert atual.ativo
    workspace_servico.fechar()
    assert watcher_mod.atual() is None


def test_emitir_assincrono_pelo_sink(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    envelopes: list[dict] = []
    configurar_sink_assincrono(lambda e: envelopes.append(e))
    workspace_servico.abrir(str(tmp_path))

    relogio = RelogioFake()
    # Substitui o watcher automático por um controlado (sem thread).
    watcher_mod.parar()
    w = watcher_mod.reiniciar(
        tmp_path,
        obter_indice=lambda: workspace_servico.estado_atual().indice,  # type: ignore[union-attr]
        reindexar=workspace_servico.reindexar,
        debounce_s=0.5,
        clock=relogio.clock,
        sleep=relogio.sleep,
        iniciar_thread=False,
    )
    escrever_shapefile_quadrado_utm(tmp_path / "dados" / "X.shp", nome="X")
    w.tick()
    relogio.avancar(1.0)
    assert w.tick() is True
    assert len(envelopes) == 1
    assert envelopes[0]["tipo"] == "evt"
    assert envelopes[0]["evento"] == "workspace.mudou"
    assert envelopes[0]["v"] == 1
    assert isinstance(envelopes[0]["id"], str) and envelopes[0]["id"]


def test_fingerprint_estavel_sem_mudanca(tmp_path: Path) -> None:
    montar_workspace_minimo(tmp_path)
    a = capturar_fingerprint(tmp_path)
    b = capturar_fingerprint(tmp_path)
    assert a == b
    assert any(k.endswith("ATP.shp") for k in a)
