from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.protocolo import Emissor

PASTA_APROVACOES = ".servidor/aprovacoes"
ARQUIVO_PEDIDO = "pedido.json"
ARQUIVO_DECISAO = "decisao.json"
TTL_DECISAO_SEGUNDOS = 600.0  # 10 minutos


def _calcular_hash_arquivo(caminho_arq: Path) -> str | None:
    if not caminho_arq.exists() or not caminho_arq.is_file():
        return None
    try:
        h = hashlib.sha256()
        with caminho_arq.open("rb") as f:
            for bloco in iter(lambda: f.read(65536), b""):
                h.update(bloco)
        return h.hexdigest()
    except Exception:
        return None


@dataclass
class PedidoAprovacao:
    pedido_id: str
    token: str
    acao: str
    caminho: str
    motivo: str
    hash_alvo: str | None = None
    timestamp: float = field(default_factory=time.time)
    status: str = "pendente"  # pendente, aprovado, recusado, concluido

    def para_dict(self) -> dict[str, Any]:
        return {
            "pedido_id": self.pedido_id,
            "token": self.token,
            "acao": self.acao,
            "caminho": self.caminho,
            "motivo": self.motivo,
            "hash_alvo": self.hash_alvo,
            "timestamp": self.timestamp,
            "status": self.status,
        }

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> PedidoAprovacao:
        return cls(
            pedido_id=str(dados.get("pedido_id", "")),
            token=str(dados.get("token", "")),
            acao=str(dados.get("acao", "")),
            caminho=str(dados.get("caminho", "")),
            motivo=str(dados.get("motivo", "")),
            hash_alvo=dados.get("hash_alvo"),
            timestamp=float(dados.get("timestamp", time.time())),
            status=str(dados.get("status", "pendente")),
        )


class GerenciadorAprovacao:
    """Gerencia aprovações por projeto/workspace em arquivo confiável.

    Não utiliza singleton em memória: o estado confiável de pedidos e decisões
    reside estritamente em `<workspace>/.servidor/aprovacoes/`.

    A LLM NUNCA pode auto-conceder aprovações:
    - O token criptográfico NUNCA é retornado nas tools nem emitido em eventos públicos.
    - Decisões só são concedidas pelo proprietário (servidor/UI fora do modelo).
    - O Workspace Guard bloqueia leitura/escrita da pasta `.servidor/` para a LLM.
    - Cada decisão é estritamente de uso único (single-use), consumida uma única vez.
    """

    def __init__(self, ws_padrao: Path | None = None) -> None:
        self._ws_padrao: Path | None = ws_padrao
        self._ultimo_ws: Path | None = ws_padrao

    def _obter_pasta_aprovacoes(self, ws_root: Path) -> Path:
        pasta = ws_root / ".servidor" / "aprovacoes"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def solicitar(
        self,
        acao: str,
        caminho: str,
        motivo: str,
        ws_root: Path | None = None,
        hash_alvo: str | None = None,
        emissor: Emissor | None = None,
    ) -> dict[str, Any]:
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            raise ValueError("Workspace root é obrigatório para registrar pedido de aprovação.")
        self._ultimo_ws = ws

        pasta = self._obter_pasta_aprovacoes(ws)
        pedido_id = f"ped_{secrets.token_hex(6)}"
        token = secrets.token_hex(32)

        caminho_pedido = pasta / ARQUIVO_PEDIDO
        if caminho_pedido.exists():
            try:
                existente = json.loads(caminho_pedido.read_text(encoding="utf-8"))
                if (
                    existente.get("status") == "pendente"
                    and existente.get("acao") == acao
                    and existente.get("caminho") == caminho
                ):
                    pedido_id = str(existente.get("pedido_id") or pedido_id)
                    token = str(existente.get("token") or token)
            except Exception:
                pass

        if hash_alvo is None:
            hash_alvo = _calcular_hash_arquivo(ws / caminho)

        pedido = PedidoAprovacao(
            pedido_id=pedido_id,
            token=token,
            acao=acao,
            caminho=caminho,
            motivo=motivo,
            hash_alvo=hash_alvo,
        )

        caminho_pedido = pasta / ARQUIVO_PEDIDO
        caminho_pedido.write_text(
            json.dumps(pedido.para_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Remove decisão anterior obsoleta se existir
        caminho_decisao = pasta / ARQUIVO_DECISAO
        if caminho_decisao.exists():
            caminho_decisao.unlink(missing_ok=True)

        if emissor is not None:
            # Token NUNCA é divulgado no evento público
            emissor.emitir(
                "agente.aprovacao",
                {
                    "pedido_id": pedido_id,
                    "acao": acao,
                    "caminho": caminho,
                    "motivo": motivo,
                },
            )

        return {
            "ok": False,
            "aguardando_aprovacao": True,
            "pedido_id": pedido_id,
            "acao": acao,
            "caminho": caminho,
            "motivo": motivo,
            "mensagem": f"Operação '{acao}' em '{caminho}' requer aprovação explícita do usuário: {motivo}",
        }

    def registrar_decisao(
        self,
        token: str,
        aprovado: bool = True,
        ws_root: Path | None = None,
    ) -> bool:
        """Concede ou recusa aprovação a partir do canal seguro do servidor/UI."""
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            return False

        pasta = ws / ".servidor" / "aprovacoes"
        caminho_pedido = pasta / ARQUIVO_PEDIDO
        if not caminho_pedido.exists():
            return False

        try:
            dados_pedido = json.loads(caminho_pedido.read_text(encoding="utf-8"))
        except Exception:
            return False

        if dados_pedido.get("status") != "pendente":
            return False

        token_esperado = str(dados_pedido.get("token", "")).strip()
        if not token or not token_esperado or not hmac.compare_digest(token_esperado, token.strip()):
            return False

        dados_pedido["status"] = "aprovado" if aprovado else "recusado"
        caminho_pedido.write_text(json.dumps(dados_pedido, indent=2), encoding="utf-8")

        caminho_decisao = pasta / ARQUIVO_DECISAO
        dados_decisao = {
            "pedido_id": dados_pedido.get("pedido_id"),
            "acao": dados_pedido.get("acao"),
            "caminho": dados_pedido.get("caminho"),
            "hash_alvo": dados_pedido.get("hash_alvo"),
            "aprovado": bool(aprovado),
            "timestamp": time.time(),
            "consumido": False,
        }
        caminho_decisao.write_text(json.dumps(dados_decisao, indent=2), encoding="utf-8")
        return True

    def verificar_e_consumir_decisao(
        self,
        acao: str,
        caminho: str,
        ws_root: Path | None = None,
        hash_alvo: str | None = None,
    ) -> bool:
        """Verifica se há decisão confiável aprovada e consome exatamente UMA vez (single-use)."""
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            return False

        pasta = ws / ".servidor" / "aprovacoes"
        caminho_decisao = pasta / ARQUIVO_DECISAO
        if not caminho_decisao.exists():
            return False

        try:
            decisao = json.loads(caminho_decisao.read_text(encoding="utf-8"))
        except Exception:
            return False

        if decisao.get("consumido") is True:
            return False

        if decisao.get("aprovado") is not True:
            return False

        if decisao.get("acao") != acao or decisao.get("caminho") != caminho:
            return False

        # Validação de integridade do arquivo: se o hash mudou entre a aprovação e a execução, recusa
        hash_esperado = decisao.get("hash_alvo")
        if hash_alvo is not None and hash_esperado is not None:
            if hash_alvo != hash_esperado:
                return False

        # Validação de expiração
        ts = float(decisao.get("timestamp", 0.0))
        if time.time() - ts > TTL_DECISAO_SEGUNDOS:
            return False

        # Consome imediatamente para evitar reutilização (single-use)
        decisao["consumido"] = True
        try:
            caminho_decisao.unlink(missing_ok=True)
        except Exception:
            caminho_decisao.write_text(json.dumps(decisao), encoding="utf-8")

        # Atualiza pedido
        caminho_pedido = pasta / ARQUIVO_PEDIDO
        if caminho_pedido.exists():
            try:
                pedido = json.loads(caminho_pedido.read_text(encoding="utf-8"))
                pedido["status"] = "concluido"
                caminho_pedido.write_text(json.dumps(pedido), encoding="utf-8")
            except Exception:
                pass

        return True

    def obter_token_pendente(
        self,
        acao: str,
        caminho: str,
        ws_root: Path | None = None,
    ) -> str | None:
        """Acesso exclusivo de infraestrutura/servidor para fornecer token à UI fora do modelo."""
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            return None
        pasta = ws / ".servidor" / "aprovacoes"
        caminho_pedido = pasta / ARQUIVO_PEDIDO
        if not caminho_pedido.exists():
            return None
        try:
            dados = json.loads(caminho_pedido.read_text(encoding="utf-8"))
            if (
                dados.get("status") == "pendente"
                and dados.get("acao") == acao
                and dados.get("caminho") == caminho
            ):
                return str(dados.get("token"))
        except Exception:
            return None
        return None

    def validar_token(
        self,
        token: str,
        acao: str,
        caminho: str,
        ws_root: Path | None = None,
    ) -> bool:
        """Valida token do proprietário e registra a decisão correspondente."""
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            return False
        token_pend = self.obter_token_pendente(acao, caminho, ws_root=ws)
        if not token_pend or not hmac.compare_digest(token_pend, token.strip()):
            return False
        return self.registrar_decisao(token, aprovado=True, ws_root=ws)

    def limpar(self, ws_root: Path | None = None) -> None:
        ws = ws_root or self._ultimo_ws or self._ws_padrao
        if ws is None:
            return
        pasta = ws / ".servidor" / "aprovacoes"
        if pasta.exists():
            for f in pasta.glob("*.json"):
                f.unlink(missing_ok=True)


gerenciador_aprovacao_padrao = GerenciadorAprovacao()
