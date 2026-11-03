"""Log de eventos por projeto — append-only com `seq` (W-03/W5-01).

`seq` é **gravado antes de enviar**: se o servidor cair no meio, o replay devolve tudo
o que o cliente já viu (nunca some evento). O arquivo é
`<projeto>/.servidor/eventos.ndjson`, uma linha JSON por evento.

`fsync` a cada 50 eventos ou 1 s (o que vier primeiro) equilibra durabilidade e
desempenho; o índice de offsets a cada 1.000 linhas evita reler o arquivo inteiro no
replay.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from . import vocabulario

INTERVALO_FSYNC_S = 1.0
EVENTOS_POR_FSYNC = 50
LINHAS_POR_INDICE = 1000
NOME_ARQUIVO = "eventos.ndjson"
NOME_INDICE = "eventos.idx"

# Caminho absoluto de servidor ou drive do Windows dentro de qualquer string.
_RE_CAMINHO = re.compile(
    r'(?:/home/|/media/|/srv/|/root/)[^\s"\'`<>|]*'
    r'|[A-Za-z]:\\[^\s"\'`<>|]*'
)


def caminho_log(raiz_projeto: Path) -> Path:
    return raiz_projeto / ".servidor" / NOME_ARQUIVO


def caminho_indice(raiz_projeto: Path) -> Path:
    return raiz_projeto / ".servidor" / NOME_INDICE


def _limpar_caminhos_absolutos(dados: dict) -> dict:
    """Caminho absoluto em evento é bug do emissor: troca o trecho, mantém a mensagem."""

    def _limpar(valor):
        if isinstance(valor, str):
            return _RE_CAMINHO.sub("<caminho removido>", valor)
        if isinstance(valor, dict):
            return {chave: _limpar(item) for chave, item in valor.items()}
        if isinstance(valor, list):
            return [_limpar(item) for item in valor]
        return valor

    return _limpar(dados)


@dataclass
class LogEventos:
    """Um log por projeto. Thread-safe: o fan-out do SSE e o worker escrevem aqui."""

    raiz_projeto: Path
    _trava: threading.Lock = field(default_factory=threading.Lock)
    _ultimo_seq: int = 0
    _desde_fsync: int = 0
    _ultimo_fsync: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self._ultimo_seq = self.ultimo_seq()

    # -- leitura ----------------------------------------------------------
    def ultimo_seq(self) -> int:
        caminho = caminho_log(self.raiz_projeto)
        if not caminho.is_file():
            return 0
        ultimo = 0
        for evento in self.ler_todos():
            ultimo = max(ultimo, int(evento["seq"]))
        return ultimo

    def ler_todos(self) -> Iterator[dict]:
        caminho = caminho_log(self.raiz_projeto)
        if not caminho.is_file():
            return
        with open(caminho, "r", encoding="utf-8") as arquivo:
            for linha in arquivo:
                texto = linha.strip()
                if not texto:
                    continue
                try:
                    yield json.loads(texto)
                except json.JSONDecodeError:
                    continue  # linha truncada por queda de energia: ignora, não trava

    def ler_desde(self, desde: int) -> list[dict]:
        """Eventos com `seq > desde`, na ordem. O índice evita reler tudo."""
        caminho = caminho_log(self.raiz_projeto)
        if not caminho.is_file():
            return []
        inicio = self._offset_para(desde)
        encontrados: list[dict] = []
        with open(caminho, "r", encoding="utf-8") as arquivo:
            if inicio:
                arquivo.seek(inicio)
            for linha in arquivo:
                texto = linha.strip()
                if not texto:
                    continue
                try:
                    evento = json.loads(texto)
                except json.JSONDecodeError:
                    continue
                if int(evento.get("seq", 0)) > desde:
                    encontrados.append(evento)
        return encontrados

    def _offset_para(self, desde: int) -> int:
        """Offset da linha mais próxima antes de `desde` (via índice, se existir)."""
        indice = self._ler_indice()
        melhor = 0
        for seq, offset in indice:
            if seq <= desde:
                melhor = offset
            else:
                break
        return melhor

    def _ler_indice(self) -> list[tuple[int, int]]:
        caminho = caminho_indice(self.raiz_projeto)
        if not caminho.is_file():
            return []
        pares: list[tuple[int, int]] = []
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            try:
                seq, offset = linha.split(",", 1)
                pares.append((int(seq), int(offset)))
            except ValueError:
                continue
        return pares

    def _gravar_indice(self, seq: int, offset: int) -> None:
        caminho = caminho_indice(self.raiz_projeto)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"{seq},{offset}\n")

    # -- escrita ----------------------------------------------------------
    def registrar(
        self,
        *,
        origem: str,
        evento: str,
        dados: dict | None = None,
        req_id: str | None = None,
        job_id: str | None = None,
    ) -> dict:
        """Grava e devolve o envelope completo, **já com o `seq`**."""
        if origem not in vocabulario.ORIGENS:
            raise ValueError(f"Origem inválida: {origem!r}")
        vocabulario.exigir(evento)
        dados_limpos = _limpar_caminhos_absolutos(dados or {})

        with self._trava:
            proximo = self._ultimo_seq + 1
            envelope = {
                "seq": proximo,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
                "origem": origem,
                "evento": evento,
                "req_id": req_id,
                "job_id": job_id,
                "dados": dados_limpos,
            }
            linha = json.dumps(envelope, ensure_ascii=False, sort_keys=False) + "\n"
            caminho = caminho_log(self.raiz_projeto)
            caminho.parent.mkdir(parents=True, exist_ok=True)
            offset = caminho.stat().st_size if caminho.exists() else 0
            with open(caminho, "a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
                arquivo.flush()
                self._desde_fsync += 1
                agora = time.monotonic()
                if (
                    self._desde_fsync >= EVENTOS_POR_FSYNC
                    or agora - self._ultimo_fsync >= INTERVALO_FSYNC_S
                ):
                    os.fsync(arquivo.fileno())
                    self._desde_fsync = 0
                    self._ultimo_fsync = agora
            if proximo % LINHAS_POR_INDICE == 0 or offset == 0:
                self._gravar_indice(proximo, offset)
            self._ultimo_seq = proximo
            return envelope

    def compactar(self, eventos: list[dict]) -> list[dict]:
        """`desde=0` numa reabertura: só o essencial de cada job terminado (W-03)."""
        por_job: dict[str, dict] = {}
        sem_job: list[dict] = []
        for evento in eventos:
            job_id = evento.get("job_id")
            nome = evento.get("evento")
            if not job_id:
                if nome in {"camada.renderizada", "layout.elemento", "viewport.foco"}:
                    sem_job.append(evento)
                continue
            atual = por_job.get(job_id)
            if nome == "job.progresso":
                por_job[job_id] = {**(atual or {}), "progresso": evento}
            elif nome in {"camada.renderizada", "layout.elemento", "viewport.foco", "nucleo.res"}:
                chave = f"{nome}:{json.dumps(evento.get('dados'), sort_keys=True)[:80]}"
                guardados = (atual or {}).get("eventos", {})
                guardados[chave] = evento
                por_job[job_id] = {**(atual or {}), "eventos": guardados}
            # chat.delta de turno terminado não volta: a mensagem final está em /mensagens

        resultado: list[dict] = list(sem_job)
        for dados in por_job.values():
            if dados.get("progresso"):
                resultado.append(dados["progresso"])
            resultado.extend((dados.get("eventos") or {}).values())
        resultado.sort(key=lambda e: int(e["seq"]))
        return resultado
