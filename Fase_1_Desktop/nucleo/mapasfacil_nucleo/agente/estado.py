from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EstadoAgente:
    """Estado persistido do ciclo de vida do agente no projeto (.agente/estado.json)."""

    conversation_id: str = ""
    status: str = "iniciando"  # pendente, em_andamento, aguardando_aprovacao, concluido, erro, cancelado
    passos: list[dict[str, Any]] = field(default_factory=list)
    arquivos: list[dict[str, Any]] = field(default_factory=list)
    previews: list[dict[str, Any]] = field(default_factory=list)
    aprovacao: dict[str, Any] | None = None
    resumo: str = ""
    versao: int | None = None
    atualizado_em: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    def para_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> EstadoAgente:
        return cls(
            conversation_id=dados.get("conversation_id", ""),
            status=dados.get("status", "iniciando"),
            passos=list(dados.get("passos") or []),
            arquivos=list(dados.get("arquivos") or []),
            previews=list(dados.get("previews") or []),
            aprovacao=dados.get("aprovacao"),
            resumo=dados.get("resumo", ""),
            versao=dados.get("versao"),
            atualizado_em=dados.get(
                "atualizado_em",
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )


def _caminho_estado(ws_root: Path) -> Path:
    return ws_root / ".agente" / "estado.json"


def carregar_estado(ws_root: Path) -> EstadoAgente | None:
    alvo = _caminho_estado(ws_root)
    if not alvo.exists():
        return None
    try:
        conteudo = alvo.read_text(encoding="utf-8")
        dados = json.loads(conteudo)
        return EstadoAgente.de_dict(dados)
    except Exception:
        return None


def salvar_estado(ws_root: Path, estado: EstadoAgente) -> None:
    alvo = _caminho_estado(ws_root)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    estado.atualizado_em = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Grava via arquivo temporário para atomicidade
    temp = alvo.with_suffix(".tmp")
    temp.write_text(json.dumps(estado.para_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(alvo)


def limpar_estado(ws_root: Path) -> None:
    alvo = _caminho_estado(ws_root)
    if alvo.exists():
        alvo.unlink()
