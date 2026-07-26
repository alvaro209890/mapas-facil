"""A12 — watcher da pasta do workspace → `workspace.mudou` (debounce 500 ms).

Observa a raiz aberta, espera o disco assentar (`DEBOUNCE_S`) e só então reindexa
e emite o evento. Sem inventar animação na UI: o contrato é o evento real (AP-07).

Desenho:
- poll leve (stdlib, sem `watchdog`) — pastas GIS cabem num walk curto;
- fingerprint por `(mtime_ns, size)` dos arquivos relevantes;
- debounce reinicia a cada mudança até o disco parar;
- pastas de saída (`Mapas`/`MXD`/`SHP`/`_extraido`) ignoradas **durante** um job;
- testável: relógio/`sleep` injetáveis + `tick()` síncrono sem thread.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.config import PASTAS_ESCRITA
from mapasfacil_nucleo.protocolo import emitir_assincrono

DEBOUNCE_S = 0.5
INTERVALO_POLL_S = 0.2

# Extensões que entram no índice (F1-02) ou sidecars de shapefile cujo mtime
# altera o conteúdo sem mudar o `.shp`.
_EXTENSOES_RELEVANTES = frozenset(
    {
        ".shp",
        ".dbf",
        ".shx",
        ".prj",
        ".cpg",
        ".pdf",
        ".zip",
        ".mxd",
        ".png",
        ".jpg",
        ".jpeg",
    }
)

_DIRS_SEMPRE_IGNORADOS = frozenset({".git", "__pycache__", ".preview", "node_modules"})

Fingerprint = dict[str, tuple[int, int]]  # rel posix → (mtime_ns, size)


def nome_ignorado(nome: str) -> bool:
    """`.lock`, `~$*`, `.tmp` e afins — F1-02 §Watcher."""
    baixo = nome.lower()
    if baixo.endswith(".lock") or baixo.endswith(".tmp"):
        return True
    if nome.startswith("~$"):
        return True
    if baixo.endswith("~"):
        return True
    return False


def caminho_sob_pasta_escrita(rel: str) -> bool:
    primeira = rel.split("/", 1)[0]
    return primeira in PASTAS_ESCRITA


def capturar_fingerprint(
    raiz: Path,
    *,
    ignorar_saidas: bool = False,
) -> Fingerprint:
    """Varre a raiz e devolve o mapa de arquivos relevantes."""
    raiz = raiz.resolve()
    out: Fingerprint = {}
    for dirpath, dirnames, filenames in os.walk(raiz):
        # Prune in-place: não desce em dirs sempre ignorados / saídas (se pausado).
        podar: list[str] = []
        for d in dirnames:
            if d in _DIRS_SEMPRE_IGNORADOS or d.startswith("."):
                # `.preview` já está na lista; outros dot-dirs também ficam de fora.
                if d not in (".", ".."):
                    podar.append(d)
                    continue
            if ignorar_saidas:
                rel_dir = Path(dirpath, d).resolve().relative_to(raiz).as_posix()
                if caminho_sob_pasta_escrita(rel_dir):
                    podar.append(d)
        for d in podar:
            if d in dirnames:
                dirnames.remove(d)

        for nome in filenames:
            if nome_ignorado(nome):
                continue
            sufixo = Path(nome).suffix.lower()
            if sufixo not in _EXTENSOES_RELEVANTES:
                continue
            abs_path = Path(dirpath) / nome
            try:
                rel = abs_path.resolve().relative_to(raiz).as_posix()
            except ValueError:
                continue
            if ignorar_saidas and caminho_sob_pasta_escrita(rel):
                continue
            try:
                st = abs_path.stat()
            except OSError:
                continue
            out[rel] = (getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)), st.st_size)
    return out


def _assinatura_item(categoria: str, item: Mapping[str, Any]) -> tuple[Any, ...]:
    if categoria == "shapefiles":
        return (
            item.get("feicoes"),
            item.get("area_ha"),
            item.get("tipo_geometria"),
            item.get("papel"),
            item.get("valido"),
            (item.get("crs") or {}).get("epsg"),
        )
    if categoria == "pdfs":
        return (item.get("recibo_car"),)
    if categoria == "outros":
        return (item.get("tipo"),)
    return ()


def diff_indices(
    antes: Mapping[str, Any] | None,
    depois: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Compara dois índices e devolve `mudancas` tipadas para `workspace.mudou`."""
    antes = antes or {}
    mudancas: list[dict[str, Any]] = []

    for categoria, tipo in (
        ("shapefiles", "shapefile"),
        ("pdfs", "pdf"),
        ("zips", "zip"),
        ("outros", "outro"),
    ):
        mapa_antes = {i["caminho"]: i for i in antes.get(categoria, []) if "caminho" in i}
        mapa_depois = {i["caminho"]: i for i in depois.get(categoria, []) if "caminho" in i}

        for caminho in sorted(set(mapa_depois) - set(mapa_antes)):
            item = mapa_depois[caminho]
            mudancas.append(_mudanca("adicionado", caminho, tipo, item))

        for caminho in sorted(set(mapa_antes) - set(mapa_depois)):
            item = mapa_antes[caminho]
            mudancas.append(_mudanca("removido", caminho, tipo, item))

        for caminho in sorted(set(mapa_antes) & set(mapa_depois)):
            a, b = mapa_antes[caminho], mapa_depois[caminho]
            if _assinatura_item(categoria, a) != _assinatura_item(categoria, b):
                mudancas.append(_mudanca("modificado", caminho, tipo, b))

    return mudancas


def _mudanca(
    acao: str,
    caminho: str,
    tipo: str,
    item: Mapping[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {"acao": acao, "caminho": caminho, "tipo": tipo}
    papel = item.get("papel")
    if isinstance(papel, str) and papel:
        out["papel"] = papel
    resumo = _resumo(acao, caminho, tipo, item)
    if resumo:
        out["resumo"] = resumo
    return out


def _resumo(acao: str, caminho: str, tipo: str, item: Mapping[str, Any]) -> str:
    nome = Path(caminho).name
    if tipo == "shapefile":
        feicoes = item.get("feicoes")
        area = item.get("area_ha")
        papel = item.get("papel")
        partes = [nome]
        if isinstance(papel, str) and papel:
            partes[0] = f"{nome} ({papel})"
        if isinstance(feicoes, int):
            partes.append(f"{feicoes} feições")
        if isinstance(area, (int, float)) and area is not None:
            partes.append(f"{float(area):.2f} ha".replace(".", ","))
        corpo = ", ".join(partes) if len(partes) == 1 else f"{partes[0]} · " + " · ".join(partes[1:])
        if acao == "adicionado":
            return f"apareceu {corpo}"
        if acao == "removido":
            return f"sumiu {nome}"
        return f"mudou {corpo}"
    if acao == "adicionado":
        return f"apareceu {nome}"
    if acao == "removido":
        return f"sumiu {nome}"
    return f"mudou {nome}"


EmitirFn = Callable[[str, dict[str, Any]], Any]
ReindexarFn = Callable[[], dict[str, Any]]
ClockFn = Callable[[], float]
SleepFn = Callable[[float], None]


class WatcherWorkspace:
    """Poll + debounce. Uma instância por processo (singleton em `servico`)."""

    def __init__(
        self,
        raiz: Path,
        *,
        obter_indice: Callable[[], dict[str, Any]],
        reindexar: ReindexarFn,
        emitir: EmitirFn | None = None,
        debounce_s: float = DEBOUNCE_S,
        intervalo_s: float = INTERVALO_POLL_S,
        clock: ClockFn | None = None,
        sleep: SleepFn | None = None,
    ) -> None:
        self.raiz = Path(raiz).resolve()
        self._obter_indice = obter_indice
        self._reindexar = reindexar
        self._emitir = emitir or (lambda evento, dados: emitir_assincrono(evento, dados))
        self.debounce_s = debounce_s
        self.intervalo_s = intervalo_s
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep

        self._lock = threading.RLock()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._ignorar_saidas = False

        self._baseline: Fingerprint = capturar_fingerprint(self.raiz)
        self._dirty: Fingerprint | None = None
        self._ultimo_change: float | None = None

    @property
    def ativo(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def pausar_pastas_saida(self, pausar: bool) -> None:
        """Durante `mapa.gerar`, ignora Mapas/MXD/SHP/_extraido (F1-02)."""
        with self._lock:
            self._ignorar_saidas = bool(pausar)
            # Recalibra o baseline para não disparar um falso positivo ao retomar.
            self._baseline = capturar_fingerprint(
                self.raiz, ignorar_saidas=self._ignorar_saidas
            )
            self._dirty = None
            self._ultimo_change = None

    def iniciar(self) -> None:
        with self._lock:
            if self.ativo:
                return
            self._parar.clear()
            self._baseline = capturar_fingerprint(
                self.raiz, ignorar_saidas=self._ignorar_saidas
            )
            self._dirty = None
            self._ultimo_change = None
            self._thread = threading.Thread(
                target=self._loop,
                name="mf-workspace-watcher",
                daemon=True,
            )
            self._thread.start()

    def parar(self, *, timeout: float = 2.0) -> None:
        self._parar.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._thread = None

    def tick(self) -> bool:
        """Um passo síncrono (testes). Devolve True se emitiu `workspace.mudou`."""
        with self._lock:
            return self._passo()

    def _loop(self) -> None:
        while not self._parar.is_set():
            try:
                with self._lock:
                    self._passo()
            except Exception:
                # Watcher nunca derruba o sidecar; o próximo tick tenta de novo.
                pass
            self._parar.wait(self.intervalo_s)

    def _passo(self) -> bool:
        agora = self._clock()
        atual = capturar_fingerprint(self.raiz, ignorar_saidas=self._ignorar_saidas)

        if atual == self._baseline:
            # Voltou ao estado estável (ex.: arquivo temporário sumiu) — cancela.
            self._dirty = None
            self._ultimo_change = None
            return False

        if atual != self._dirty:
            # Mudança nova (ou primeira): reinicia o debounce.
            self._dirty = atual
            self._ultimo_change = agora

        if self._ultimo_change is None:
            return False
        if (agora - self._ultimo_change) < self.debounce_s:
            return False

        return self._descarregar()

    def _descarregar(self) -> bool:
        indice_antes = dict(self._obter_indice())
        # Cópia rasa das listas para o diff não ver a mesma referência mutada.
        for chave in ("shapefiles", "pdfs", "zips", "outros", "fontes_locais"):
            if chave in indice_antes and isinstance(indice_antes[chave], list):
                indice_antes[chave] = list(indice_antes[chave])
        resultado = self._reindexar()
        indice_depois = resultado.get("workspace") or self._obter_indice()
        mudancas = diff_indices(indice_antes, indice_depois)

        self._baseline = capturar_fingerprint(
            self.raiz, ignorar_saidas=self._ignorar_saidas
        )
        self._dirty = None
        self._ultimo_change = None

        if not mudancas:
            # Fingerprint mudou (sidecar/tmp filtrado) mas o índice ficou igual — silêncio.
            return False

        self._emitir(
            "workspace.mudou",
            {
                "mudancas": mudancas,
                "workspace": indice_depois,
            },
        )
        return True


# --- singleton de processo -------------------------------------------------

_watcher: WatcherWorkspace | None = None
_watcher_lock = threading.Lock()
_pausar_saidas_global = False


def atual() -> WatcherWorkspace | None:
    return _watcher


def reiniciar(
    raiz: Path,
    *,
    obter_indice: Callable[[], dict[str, Any]],
    reindexar: ReindexarFn,
    emitir: EmitirFn | None = None,
    debounce_s: float = DEBOUNCE_S,
    intervalo_s: float = INTERVALO_POLL_S,
    clock: ClockFn | None = None,
    sleep: SleepFn | None = None,
    iniciar_thread: bool = True,
) -> WatcherWorkspace:
    """Para o watcher anterior (se houver) e liga um novo na `raiz`."""
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            _watcher.parar()
        _watcher = WatcherWorkspace(
            raiz,
            obter_indice=obter_indice,
            reindexar=reindexar,
            emitir=emitir,
            debounce_s=debounce_s,
            intervalo_s=intervalo_s,
            clock=clock,
            sleep=sleep,
        )
        if _pausar_saidas_global:
            _watcher.pausar_pastas_saida(True)
        if iniciar_thread:
            _watcher.iniciar()
        return _watcher


def parar() -> None:
    global _watcher
    with _watcher_lock:
        if _watcher is not None:
            _watcher.parar()
            _watcher = None


def pausar_pastas_saida(pausar: bool) -> None:
    global _pausar_saidas_global
    _pausar_saidas_global = bool(pausar)
    with _watcher_lock:
        if _watcher is not None:
            _watcher.pausar_pastas_saida(pausar)
