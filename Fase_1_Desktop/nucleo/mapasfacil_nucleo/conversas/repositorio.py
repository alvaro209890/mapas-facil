# Repositório SQLite de conversas — CRUD, WAL, transações (F1-17).

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.conversas.banco import caminho_anexos, conectar, diretorio_chats
from mapasfacil_nucleo.conversas.fingerprint import fingerprint_workspace, nome_workspace
from mapasfacil_nucleo.conversas.redator import redigir, truncar
from mapasfacil_nucleo.conversas.titulo import (
    TITULO_PADRAO,
    pode_atualizar_automatico,
    titulo_da_galeria,
    titulo_da_mensagem,
)
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import novo_id

PAPEIS = frozenset({"usuario", "assistente", "sistema", "tool"})


def agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _trecho(texto: str, limite: int = 120) -> str:
    limpo = " ".join((texto or "").split())
    return truncar(limpo, limite)


class RepositorioConversas:
    """Acesso ao chats.sqlite. Um processo / um path; testes passam ``diretorio``."""

    def __init__(self, diretorio: str | Path | None = None) -> None:
        self.diretorio = diretorio_chats(diretorio)
        self._conn = conectar(self.diretorio / "chats.sqlite")

    @property
    def caminho_banco(self) -> Path:
        return self.diretorio / "chats.sqlite"

    def fechar(self) -> None:
        self._conn.close()

    def criar_conversa(
        self,
        *,
        workspace: str | None = None,
        title: str | None = None,
        conta_id: str | None = None,
    ) -> dict[str, Any]:
        cid = novo_id()
        ts = agora_iso()
        titulo = (title or "").strip() or TITULO_PADRAO
        title_manual = 1 if title and title.strip() else 0
        if workspace:
            fp = fingerprint_workspace(workspace)
            nome = nome_workspace(workspace)
            caminho = str(Path(workspace).expanduser())
        else:
            fp = fingerprint_workspace("__sem_workspace__")
            nome = None
            caminho = None
        self._conn.execute(
            """
            INSERT INTO conversas (
              conversation_id, title, title_manual, created_at, updated_at,
              workspace_path, workspace_fingerprint, workspace_nome, conta_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cid, titulo, title_manual, ts, ts, caminho, fp, nome, conta_id),
        )
        return {"conversation_id": cid, "title": titulo, "created_at": ts}

    def listar_conversas(
        self,
        *,
        workspace: str | None = None,
        incluir_arquivadas: bool = False,
        limite: int = 50,
        antes_de: str | None = None,
    ) -> dict[str, Any]:
        limite = max(1, min(int(limite), 200))
        clausulas = ["1=1"]
        args: list[Any] = []
        if not incluir_arquivadas:
            clausulas.append("arquivada = 0")
        if workspace:
            clausulas.append("workspace_fingerprint = ?")
            args.append(fingerprint_workspace(workspace))
        if antes_de:
            clausulas.append("updated_at < ?")
            args.append(antes_de)
        where = " AND ".join(clausulas)
        rows = self._conn.execute(
            f"""
            SELECT c.*,
              (SELECT COUNT(*) FROM mensagens m WHERE m.conversation_id = c.conversation_id)
                AS mensagens_total,
              (SELECT conteudo FROM mensagens m
                 WHERE m.conversation_id = c.conversation_id
                 ORDER BY m.seq DESC LIMIT 1) AS ultimo_conteudo
            FROM conversas c
            WHERE {where}
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (*args, limite + 1),
        ).fetchall()
        tem_mais = len(rows) > limite
        rows = rows[:limite]
        conversas = []
        for row in rows:
            conversas.append(
                {
                    "conversation_id": row["conversation_id"],
                    "title": row["title"],
                    "updated_at": row["updated_at"],
                    "workspace_nome": row["workspace_nome"],
                    "arquivada": bool(row["arquivada"]),
                    "mensagens_total": int(row["mensagens_total"] or 0),
                    "ultimo_trecho": _trecho(row["ultimo_conteudo"] or ""),
                }
            )
        return {"conversas": conversas, "tem_mais": tem_mais}

    def _obter_ou_404(self, conversation_id: str) -> sqlite3.Row:
        row = self._conn.execute(
            "SELECT * FROM conversas WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            raise ErroNucleo("CH-001", "Conversa não encontrada.", {"conversation_id": conversation_id})
        return row

    def abrir_conversa(self, conversation_id: str, *, limite: int = 30) -> dict[str, Any]:
        limite = max(1, min(int(limite), 200))
        conv = self._obter_ou_404(conversation_id)
        total = self._conn.execute(
            "SELECT COUNT(*) AS n FROM mensagens WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()["n"]
        # últimas N em ordem crescente de seq
        rows = self._conn.execute(
            """
            SELECT * FROM (
              SELECT * FROM mensagens
              WHERE conversation_id = ?
              ORDER BY seq DESC
              LIMIT ?
            ) ORDER BY seq ASC
            """,
            (conversation_id, limite),
        ).fetchall()
        message_ids = [r["message_id"] for r in rows]
        traces_por_msg: dict[str, list[dict[str, Any]]] = {mid: [] for mid in message_ids}
        if message_ids:
            placeholders = ",".join("?" * len(message_ids))
            for tr in self._conn.execute(
                f"""
                SELECT * FROM tool_traces
                WHERE conversation_id = ? AND message_id IN ({placeholders})
                ORDER BY criado_em ASC
                """,
                (conversation_id, *message_ids),
            ):
                traces_por_msg[tr["message_id"]].append(_trace_dict(tr))
        mensagens = []
        for r in rows:
            item = _mensagem_dict(r)
            item["tool_traces"] = traces_por_msg.get(r["message_id"], [])
            mensagens.append(item)
        mapspecs = [
            {
                "mapspec_id": m["mapspec_id"],
                "versao": m["versao"],
                "criado_em": m["criado_em"],
            }
            for m in self._conn.execute(
                """
                SELECT mapspec_id, versao, criado_em FROM conversa_mapspecs
                WHERE conversation_id = ?
                ORDER BY criado_em ASC
                """,
                (conversation_id,),
            )
        ]
        return {
            "conversa": _conversa_dict(conv),
            "mensagens": mensagens,
            "compact_summary": conv["compact_summary"],
            "compact_ate_seq": conv["compact_ate_seq"],
            "total": int(total),
            "mapspecs": mapspecs,
        }

    def carregar_anteriores(
        self,
        conversation_id: str,
        *,
        antes_de_seq: int,
        limite: int = 50,
    ) -> dict[str, Any]:
        self._obter_ou_404(conversation_id)
        limite = max(1, min(int(limite), 200))
        # pega as `limite+1` mais recentes abaixo do cursor; se sobrar 1, tem_mais
        rows = self._conn.execute(
            """
            SELECT * FROM (
              SELECT * FROM mensagens
              WHERE conversation_id = ? AND seq < ?
              ORDER BY seq DESC
              LIMIT ?
            ) ORDER BY seq ASC
            """,
            (conversation_id, int(antes_de_seq), limite + 1),
        ).fetchall()
        tem_mais = len(rows) > limite
        if tem_mais:
            rows = rows[-limite:]
        return {"mensagens": [_mensagem_dict(r) for r in rows], "tem_mais": tem_mais}

    def adicionar_mensagem(
        self,
        conversation_id: str,
        *,
        papel: str,
        conteudo: str,
        mapspec_id: str | None = None,
        mapspec_versao: int | None = None,
        cancelada: bool = False,
        atualizar_titulo: bool = True,
    ) -> dict[str, Any]:
        if papel not in PAPEIS:
            raise ErroNucleo("NU-001", f"Papel inválido: {papel}")
        conv = self._obter_ou_404(conversation_id)
        texto = redigir(conteudo or "")
        mid = novo_id()
        ts = agora_iso()
        seq_row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) AS m FROM mensagens WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        seq = int(seq_row["m"]) + 1
        self._conn.execute("BEGIN")
        try:
            self._conn.execute(
                """
                INSERT INTO mensagens (
                  message_id, conversation_id, seq, papel, conteudo, criado_em,
                  mapspec_id, mapspec_versao, cancelada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mid,
                    conversation_id,
                    seq,
                    papel,
                    texto,
                    ts,
                    mapspec_id,
                    mapspec_versao,
                    1 if cancelada else 0,
                ),
            )
            self._conn.execute(
                "UPDATE conversas SET updated_at = ? WHERE conversation_id = ?",
                (ts, conversation_id),
            )
            if mapspec_id is not None and mapspec_versao is not None:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO conversa_mapspecs
                      (conversation_id, mapspec_id, versao, criado_em)
                    VALUES (?, ?, ?, ?)
                    """,
                    (conversation_id, mapspec_id, mapspec_versao, ts),
                )
            if (
                atualizar_titulo
                and pode_atualizar_automatico(conv["title_manual"])
                and conv["title"] == TITULO_PADRAO
                and papel == "usuario"
                and seq == 1
            ):
                novo_titulo = titulo_da_mensagem(texto)
                self._conn.execute(
                    "UPDATE conversas SET title = ? WHERE conversation_id = ?",
                    (novo_titulo, conversation_id),
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return {
            "message_id": mid,
            "conversation_id": conversation_id,
            "seq": seq,
            "papel": papel,
            "conteudo": texto,
            "criado_em": ts,
        }

    def adicionar_tool_trace(
        self,
        conversation_id: str,
        *,
        message_id: str | None,
        tool: str,
        args_resumo: str | None = None,
        resultado_resumo: str | None = None,
        ms: int | None = None,
        ok: bool = True,
        erro_codigo: str | None = None,
    ) -> dict[str, Any]:
        self._obter_ou_404(conversation_id)
        tid = novo_id()
        ts = agora_iso()
        self._conn.execute(
            """
            INSERT INTO tool_traces (
              trace_id, conversation_id, message_id, tool,
              args_resumo, resultado_resumo, ms, ok, erro_codigo, criado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                conversation_id,
                message_id,
                tool,
                truncar(redigir(args_resumo or ""), 500) or None,
                truncar(redigir(resultado_resumo or ""), 1000) or None,
                ms,
                1 if ok else 0,
                erro_codigo,
                ts,
            ),
        )
        return {"trace_id": tid, "criado_em": ts}

    def renomear(self, conversation_id: str, title: str) -> dict[str, Any]:
        self._obter_ou_404(conversation_id)
        titulo = (title or "").strip()
        if not titulo:
            raise ErroNucleo("NU-001", "Parâmetro 'title' é obrigatório.")
        ts = agora_iso()
        self._conn.execute(
            """
            UPDATE conversas
            SET title = ?, title_manual = 1, updated_at = ?
            WHERE conversation_id = ?
            """,
            (titulo, ts, conversation_id),
        )
        return {"ok": True}

    def definir_titulo_automatico(
        self,
        conversation_id: str,
        *,
        nome_modelo: str | None = None,
        nome_workspace: str | None = None,
        da_mensagem: str | None = None,
    ) -> str | None:
        """Atualiza título se ainda não for manual (galeria / fallback)."""
        conv = self._obter_ou_404(conversation_id)
        if not pode_atualizar_automatico(conv["title_manual"]):
            return None
        if nome_modelo:
            titulo = titulo_da_galeria(nome_modelo, nome_workspace or conv["workspace_nome"])
        elif da_mensagem:
            titulo = titulo_da_mensagem(da_mensagem)
        else:
            return None
        self._conn.execute(
            "UPDATE conversas SET title = ?, updated_at = ? WHERE conversation_id = ?",
            (titulo, agora_iso(), conversation_id),
        )
        return titulo

    def arquivar(self, conversation_id: str, arquivada: bool) -> dict[str, Any]:
        self._obter_ou_404(conversation_id)
        self._conn.execute(
            "UPDATE conversas SET arquivada = ?, updated_at = ? WHERE conversation_id = ?",
            (1 if arquivada else 0, agora_iso(), conversation_id),
        )
        return {"ok": True}

    def apagar(self, conversation_id: str) -> dict[str, Any]:
        self._obter_ou_404(conversation_id)
        pasta_anexos = caminho_anexos(self.diretorio) / conversation_id
        anexos_removidos = 0
        if pasta_anexos.is_dir():
            anexos_removidos = sum(1 for p in pasta_anexos.rglob("*") if p.is_file())
            shutil.rmtree(pasta_anexos, ignore_errors=True)
        self._conn.execute("DELETE FROM conversas WHERE conversation_id = ?", (conversation_id,))
        return {"ok": True, "anexos_removidos": anexos_removidos}

    def ramificar(
        self,
        conversation_id: str,
        *,
        a_partir_do_seq: int,
        title: str | None = None,
    ) -> dict[str, Any]:
        origem = self._obter_ou_404(conversation_id)
        seq_corte = int(a_partir_do_seq)
        if seq_corte < 1:
            raise ErroNucleo("NU-001", "Parâmetro 'a_partir_do_seq' deve ser >= 1.")
        msgs = self._conn.execute(
            """
            SELECT * FROM mensagens
            WHERE conversation_id = ? AND seq <= ?
            ORDER BY seq ASC
            """,
            (conversation_id, seq_corte),
        ).fetchall()
        if not msgs:
            raise ErroNucleo("CH-003", "Nenhuma mensagem até o seq informado.")
        novo = self.criar_conversa(
            workspace=origem["workspace_path"],
            title=title,
            conta_id=origem["conta_id"],
        )
        novo_id_conv = novo["conversation_id"]
        # parent + título herdado se não veio title
        self._conn.execute(
            """
            UPDATE conversas SET
              parent_conversation_id = ?,
              parent_message_seq = ?,
              title = CASE WHEN ? THEN title ELSE ? END,
              title_manual = CASE WHEN ? THEN title_manual ELSE 0 END,
              compact_summary = NULL,
              compact_ate_seq = NULL
            WHERE conversation_id = ?
            """,
            (
                conversation_id,
                seq_corte,
                1 if title else 0,
                origem["title"],
                1 if title else 0,
                novo_id_conv,
            ),
        )
        mapa_msg: dict[str, str] = {}
        for m in msgs:
            nm = self.adicionar_mensagem(
                novo_id_conv,
                papel=m["papel"],
                conteudo=m["conteudo"],
                mapspec_id=m["mapspec_id"],
                mapspec_versao=m["mapspec_versao"],
                cancelada=bool(m["cancelada"]),
                atualizar_titulo=False,
            )
            mapa_msg[m["message_id"]] = nm["message_id"]
        for tr in self._conn.execute(
            """
            SELECT * FROM tool_traces
            WHERE conversation_id = ? AND message_id IN (
              SELECT message_id FROM mensagens WHERE conversation_id = ? AND seq <= ?
            )
            ORDER BY criado_em ASC
            """,
            (conversation_id, conversation_id, seq_corte),
        ):
            self.adicionar_tool_trace(
                novo_id_conv,
                message_id=mapa_msg.get(tr["message_id"]),
                tool=tr["tool"],
                args_resumo=tr["args_resumo"],
                resultado_resumo=tr["resultado_resumo"],
                ms=tr["ms"],
                ok=bool(tr["ok"]),
                erro_codigo=tr["erro_codigo"],
            )
        return {"conversation_id": novo_id_conv}

    def buscar(
        self,
        termo: str,
        *,
        workspace: str | None = None,
        limite: int = 30,
    ) -> dict[str, Any]:
        termo_limpo = (termo or "").strip()
        if not termo_limpo:
            raise ErroNucleo("CH-002", "Parâmetro 'termo' é obrigatório.")
        limite = max(1, min(int(limite), 100))
        # FTS5: frase entre aspas se tiver espaço; escape de " no termo
        termo_fts = '"' + termo_limpo.replace('"', '""') + '"'
        clausulas = ["mensagens_fts MATCH ?"]
        args: list[Any] = [termo_fts]
        if workspace:
            clausulas.append("c.workspace_fingerprint = ?")
            args.append(fingerprint_workspace(workspace))
        where = " AND ".join(clausulas)
        rows = self._conn.execute(
            f"""
            SELECT m.message_id, m.conversation_id, m.seq, m.conteudo,
                   c.updated_at, c.title,
                   snippet(mensagens_fts, 0, '«', '»', '…', 12) AS trecho
            FROM mensagens_fts
            JOIN mensagens m ON m.rowid = mensagens_fts.rowid
            JOIN conversas c ON c.conversation_id = m.conversation_id
            WHERE {where}
            ORDER BY c.updated_at DESC, m.seq DESC
            LIMIT ?
            """,
            (*args, limite),
        ).fetchall()
        resultados = [
            {
                "conversation_id": r["conversation_id"],
                "message_id": r["message_id"],
                "seq": r["seq"],
                "title": r["title"],
                "trecho_destacado": r["trecho"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
        return {"resultados": resultados}

    def conteudo_bruto(self, conversation_id: str, seq: int) -> str | None:
        """Leitura direta do banco (testes de redação)."""
        row = self._conn.execute(
            "SELECT conteudo FROM mensagens WHERE conversation_id = ? AND seq = ?",
            (conversation_id, seq),
        ).fetchone()
        return None if row is None else row["conteudo"]


def _conversa_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "conversation_id": row["conversation_id"],
        "title": row["title"],
        "title_manual": bool(row["title_manual"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "workspace_path": row["workspace_path"],
        "workspace_fingerprint": row["workspace_fingerprint"],
        "workspace_nome": row["workspace_nome"],
        "conta_id": row["conta_id"],
        "arquivada": bool(row["arquivada"]),
        "parent_conversation_id": row["parent_conversation_id"],
        "parent_message_seq": row["parent_message_seq"],
        "modelo": row["modelo"],
        "tokens_entrada": row["tokens_entrada"],
        "tokens_saida": row["tokens_saida"],
    }


def _mensagem_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "message_id": row["message_id"],
        "conversation_id": row["conversation_id"],
        "seq": row["seq"],
        "papel": row["papel"],
        "conteudo": row["conteudo"],
        "criado_em": row["criado_em"],
        "mapspec_id": row["mapspec_id"],
        "mapspec_versao": row["mapspec_versao"],
        "cancelada": bool(row["cancelada"]),
    }


def _trace_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "trace_id": row["trace_id"],
        "message_id": row["message_id"],
        "tool": row["tool"],
        "args_resumo": row["args_resumo"],
        "resultado_resumo": row["resultado_resumo"],
        "ms": row["ms"],
        "ok": bool(row["ok"]),
        "erro_codigo": row["erro_codigo"],
        "criado_em": row["criado_em"],
    }
