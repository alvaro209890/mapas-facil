# F1-17 §Contratos — CRUD do histórico de conversas (WAL, transações, paginação).
#
# Fronteiras deste módulo:
#   - **redação na entrada**: todo texto que vira linha passa por `redator.redigir`
#     ANTES do INSERT (AP-09). Ler nunca redige — o dado limpo já está gravado.
#   - **paginação sempre**: nenhuma função devolve conversa inteira; abrir traz as
#     últimas N e `carregar_anteriores` sobe (anti-padrão "carregar 200 de uma vez").
#   - **zero rede** (D20): não há import de socket, urllib ou http aqui, e o teste
#     de fumaça faz `grep` nesta pasta.
#   - **disco só sob `chats/`**: anexo resolve com `_caminho_sob_chats`, o resolvedor
#     restrito de `%APPDATA%\MapasFacil\` (F1-01 §fsguard).

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mapasfacil_nucleo.conversas import banco, fingerprint, redator, titulo
from mapasfacil_nucleo.erros import ErroNucleo
from mapasfacil_nucleo.protocolo import novo_id

PAPEIS = ("usuario", "assistente", "sistema", "tool")
LIMITE_TRECHO = 140
TETO_ARGS_RESUMO = 500
TETO_RESULTADO_RESUMO = 1000


def agora_utc() -> str:
    """ISO-8601 em UTC com sufixo `Z` — ordenar por texto tem de ordenar por tempo."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _trecho(texto: str, teto: int = LIMITE_TRECHO) -> str:
    limpo = " ".join(texto.split())
    return limpo if len(limpo) <= teto else f"{limpo[: teto - 1].rstrip()}…"


def _cortar(texto: str | None, teto: int) -> str | None:
    if texto is None:
        return None
    limpo = redator.redigir(texto) or ""
    return limpo if len(limpo) <= teto else limpo[:teto]


class _Escrita:
    """Transação de escrita como context manager **de classe**, não `@contextmanager`.

    Não é preferência de estilo: `ErroNucleo` é `@dataclass(frozen=True)`, e o
    `@contextmanager` do `contextlib` reatribui `__traceback__` na exceção ao
    repassá-la — o que estoura `FrozenInstanceError` e esconde o erro de verdade.
    Com `__exit__` normal, o `ErroNucleo` levantado dentro do bloco sobe intacto.
    """

    def __init__(self, conexao: sqlite3.Connection) -> None:
        self._conexao = conexao

    def __enter__(self) -> sqlite3.Connection:
        self._conexao.execute("BEGIN IMMEDIATE")
        return self._conexao

    def __exit__(self, tipo: object, valor: object, traco: object) -> bool:
        self._conexao.execute("COMMIT" if tipo is None else "ROLLBACK")
        return False


class RepositorioConversas:
    """Dono da conexão. Uma instância por processo do núcleo; WAL cuida do resto."""

    def __init__(self, caminho: Path | None = None) -> None:
        self.conexao: sqlite3.Connection = banco.conectar(caminho)
        self.caminho = Path(caminho) if caminho else banco.caminho_banco()

    def fechar(self) -> None:
        self.conexao.close()

    # ------------------------------------------------------------------ transações

    def _escrita(self) -> _Escrita:
        """`BEGIN IMMEDIATE` — pega o lock de escrita antes de ler o `MAX(seq)`.

        Com `DEFERRED`, duas janelas calculariam o mesmo `seq` e a segunda morreria
        no `UNIQUE (conversation_id, seq)`. Com `IMMEDIATE` a segunda espera o
        `busy_timeout` e depois lê um `MAX(seq)` já atualizado.
        """
        return _Escrita(self.conexao)

    # -------------------------------------------------------------------- leitura

    def _conversa_ou_erro(self, conversation_id: str) -> sqlite3.Row:
        linha = self.conexao.execute(
            "SELECT * FROM conversas WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        if linha is None:
            raise ErroNucleo(
                "NU-242",
                "Conversa não encontrada. Ela pode ter sido apagada em outra janela.",
                {"conversation_id": conversation_id},
            )
        return linha

    # --------------------------------------------------------------------- criar

    def criar_conversa(
        self,
        *,
        workspace: str | None = None,
        title: str | None = None,
        conta_id: str | None = None,
        modelo: str | None = None,
        parent_conversation_id: str | None = None,
        parent_message_seq: int | None = None,
    ) -> dict[str, Any]:
        conversation_id = novo_id()
        instante = agora_utc()
        titulo_inicial = titulo.encurtar(title) if title and title.strip() else titulo.TITULO_PADRAO
        manual = 1 if title and title.strip() else 0
        with self._escrita() as cx:
            cx.execute(
                """
                INSERT INTO conversas (
                  conversation_id, title, created_at, updated_at,
                  workspace_path, workspace_fingerprint, workspace_nome,
                  conta_id, modelo, parent_conversation_id, parent_message_seq, title_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    titulo_inicial,
                    instante,
                    instante,
                    workspace,
                    fingerprint.calcular(workspace),
                    fingerprint.nome_da_pasta(workspace),
                    conta_id,
                    modelo,
                    parent_conversation_id,
                    parent_message_seq,
                    manual,
                ),
            )
        return {
            "conversation_id": conversation_id,
            "title": titulo_inicial,
            "created_at": instante,
        }

    # ------------------------------------------------------------------ mensagens

    def acrescentar_mensagem(
        self,
        conversation_id: str,
        *,
        papel: str,
        conteudo: str,
        mapspec_id: str | None = None,
        mapspec_versao: int | None = None,
        cancelada: bool = False,
    ) -> dict[str, Any]:
        if papel not in PAPEIS:
            raise ErroNucleo(
                "NU-243",
                f"Papel inválido: {papel}. Use um de {', '.join(PAPEIS)}.",
                {"papel": papel},
            )
        limpo = redator.redigir(conteudo) or ""
        message_id = novo_id()
        instante = agora_utc()
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            linha = cx.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM mensagens WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            seq = int(linha[0])
            cx.execute(
                """
                INSERT INTO mensagens (
                  message_id, conversation_id, seq, papel, conteudo, criado_em,
                  mapspec_id, mapspec_versao, cancelada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    seq,
                    papel,
                    limpo,
                    instante,
                    mapspec_id,
                    mapspec_versao,
                    1 if cancelada else 0,
                ),
            )
            if mapspec_id is not None:
                cx.execute(
                    """
                    INSERT OR IGNORE INTO conversa_mapspecs
                      (conversation_id, mapspec_id, versao, criado_em)
                    VALUES (?, ?, ?, ?)
                    """,
                    (conversation_id, mapspec_id, mapspec_versao or 1, instante),
                )
            cx.execute(
                "UPDATE conversas SET updated_at = ? WHERE conversation_id = ?",
                (instante, conversation_id),
            )
        return {
            "message_id": message_id,
            "conversation_id": conversation_id,
            "seq": seq,
            "papel": papel,
            "conteudo": limpo,
            "criado_em": instante,
        }

    def registrar_tool_trace(
        self,
        conversation_id: str,
        *,
        tool: str,
        message_id: str | None = None,
        args_resumo: str | None = None,
        resultado_resumo: str | None = None,
        ms: int | None = None,
        ok: bool = True,
        erro_codigo: str | None = None,
    ) -> dict[str, Any]:
        """Traço de tool já **resumido**: blob bruto não entra (anti-padrão F1-17)."""
        trace_id = novo_id()
        instante = agora_utc()
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            cx.execute(
                """
                INSERT INTO tool_traces (
                  trace_id, conversation_id, message_id, tool, args_resumo,
                  resultado_resumo, ms, ok, erro_codigo, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    conversation_id,
                    message_id,
                    tool,
                    _cortar(args_resumo, TETO_ARGS_RESUMO),
                    _cortar(resultado_resumo, TETO_RESULTADO_RESUMO),
                    ms,
                    1 if ok else 0,
                    erro_codigo,
                    instante,
                ),
            )
        return {"trace_id": trace_id, "criado_em": instante}

    def registrar_anexo(
        self,
        conversation_id: str,
        *,
        caminho_local: str,
        nome_original: str,
        bytes_: int,
        sha256: str,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        anexo_id = novo_id()
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            cx.execute(
                """
                INSERT INTO anexos (
                  anexo_id, conversation_id, message_id, caminho_local,
                  nome_original, bytes, sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    anexo_id,
                    conversation_id,
                    message_id,
                    caminho_local,
                    nome_original,
                    int(bytes_),
                    sha256,
                ),
            )
        return {"anexo_id": anexo_id}

    def definir_resumo(
        self, conversation_id: str, *, compact_summary: str, compact_ate_seq: int
    ) -> dict[str, Any]:
        """Grava o resumo comprimido do trecho antigo (consumido pelo M7/F1-06)."""
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            cx.execute(
                "UPDATE conversas SET compact_summary = ?, compact_ate_seq = ? "
                "WHERE conversation_id = ?",
                (redator.redigir(compact_summary), int(compact_ate_seq), conversation_id),
            )
        return {"ok": True}

    def somar_tokens(self, conversation_id: str, *, entrada: int = 0, saida: int = 0) -> None:
        with self._escrita() as cx:
            cx.execute(
                "UPDATE conversas SET tokens_entrada = tokens_entrada + ?, "
                "tokens_saida = tokens_saida + ? WHERE conversation_id = ?",
                (int(entrada), int(saida), conversation_id),
            )

    # ---------------------------------------------------------------- listar/abrir

    def listar_conversas(
        self,
        *,
        workspace: str | None = None,
        incluir_arquivadas: bool = False,
        limite: int = 50,
        antes_de: str | None = None,
    ) -> dict[str, Any]:
        """Ordena por `updated_at DESC`; `antes_de` é o cursor (o `updated_at` do último item)."""
        limite = max(1, min(int(limite), 200))
        condicoes: list[str] = []
        parametros: list[Any] = []
        if not incluir_arquivadas:
            condicoes.append("c.arquivada = 0")
        if workspace:
            condicoes.append("c.workspace_fingerprint = ?")
            parametros.append(fingerprint.calcular(workspace))
        if antes_de:
            condicoes.append("c.updated_at < ?")
            parametros.append(antes_de)
        onde = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

        # `limite + 1` só para saber se há próxima página, sem COUNT(*) na tabela toda.
        linhas = self.conexao.execute(
            f"""
            SELECT c.conversation_id, c.title, c.updated_at, c.workspace_nome,
                   c.arquivada, c.parent_conversation_id,
                   (SELECT COUNT(*) FROM mensagens m WHERE m.conversation_id = c.conversation_id)
                     AS mensagens_total,
                   (SELECT m.conteudo FROM mensagens m
                     WHERE m.conversation_id = c.conversation_id
                     ORDER BY m.seq DESC LIMIT 1) AS ultima
            FROM conversas c
            {onde}
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            (*parametros, limite + 1),
        ).fetchall()

        tem_mais = len(linhas) > limite
        conversas = [
            {
                "conversation_id": linha["conversation_id"],
                "title": linha["title"],
                "updated_at": linha["updated_at"],
                "workspace_nome": linha["workspace_nome"],
                "mensagens_total": linha["mensagens_total"],
                "ultimo_trecho": _trecho(linha["ultima"]) if linha["ultima"] else None,
                "arquivada": bool(linha["arquivada"]),
                "ramificada": linha["parent_conversation_id"] is not None,
            }
            for linha in linhas[:limite]
        ]
        return {"conversas": conversas, "tem_mais": tem_mais}

    def _mensagem_para_dict(self, linha: sqlite3.Row) -> dict[str, Any]:
        return {
            "message_id": linha["message_id"],
            "seq": linha["seq"],
            "papel": linha["papel"],
            "conteudo": linha["conteudo"],
            "criado_em": linha["criado_em"],
            "mapspec_id": linha["mapspec_id"],
            "mapspec_versao": linha["mapspec_versao"],
            "cancelada": bool(linha["cancelada"]),
        }

    def _conversa_para_dict(self, linha: sqlite3.Row) -> dict[str, Any]:
        return {
            "conversation_id": linha["conversation_id"],
            "title": linha["title"],
            "title_manual": bool(linha["title_manual"]),
            "created_at": linha["created_at"],
            "updated_at": linha["updated_at"],
            "workspace_nome": linha["workspace_nome"],
            "workspace_fingerprint": linha["workspace_fingerprint"],
            "workspace_path": linha["workspace_path"],
            "conta_id": linha["conta_id"],
            "arquivada": bool(linha["arquivada"]),
            "parent_conversation_id": linha["parent_conversation_id"],
            "parent_message_seq": linha["parent_message_seq"],
            "modelo": linha["modelo"],
            "tokens_entrada": linha["tokens_entrada"],
            "tokens_saida": linha["tokens_saida"],
            "compact_ate_seq": linha["compact_ate_seq"],
        }

    def abrir_conversa(self, conversation_id: str, *, limite: int = 30) -> dict[str, Any]:
        limite = max(1, min(int(limite), 200))
        conversa = self._conversa_ou_erro(conversation_id)
        total = int(
            self.conexao.execute(
                "SELECT COUNT(*) FROM mensagens WHERE conversation_id = ?", (conversation_id,)
            ).fetchone()[0]
        )
        # DESC + reverse: pega as últimas N pelo índice (conversation_id, seq DESC)
        # e devolve em ordem de leitura.
        linhas = self.conexao.execute(
            "SELECT * FROM mensagens WHERE conversation_id = ? ORDER BY seq DESC LIMIT ?",
            (conversation_id, limite),
        ).fetchall()
        mensagens = [self._mensagem_para_dict(linha) for linha in reversed(linhas)]

        traces = [
            {
                "trace_id": linha["trace_id"],
                "message_id": linha["message_id"],
                "tool": linha["tool"],
                "args_resumo": linha["args_resumo"],
                "resultado_resumo": linha["resultado_resumo"],
                "ms": linha["ms"],
                "ok": bool(linha["ok"]),
                "erro_codigo": linha["erro_codigo"],
                "criado_em": linha["criado_em"],
            }
            for linha in self.conexao.execute(
                "SELECT * FROM tool_traces WHERE conversation_id = ? ORDER BY criado_em",
                (conversation_id,),
            ).fetchall()
        ]
        mapspecs = [
            {
                "mapspec_id": linha["mapspec_id"],
                "versao": linha["versao"],
                "criado_em": linha["criado_em"],
            }
            for linha in self.conexao.execute(
                "SELECT mapspec_id, versao, criado_em FROM conversa_mapspecs "
                "WHERE conversation_id = ? ORDER BY criado_em",
                (conversation_id,),
            ).fetchall()
        ]
        return {
            "conversa": self._conversa_para_dict(conversa),
            "mensagens": mensagens,
            "compact_summary": conversa["compact_summary"],
            "total": total,
            "tem_anteriores": bool(mensagens) and mensagens[0]["seq"] > 1,
            "tool_traces": traces,
            "mapspecs": mapspecs,
        }

    def carregar_anteriores(
        self, conversation_id: str, *, antes_de_seq: int, limite: int = 50
    ) -> dict[str, Any]:
        limite = max(1, min(int(limite), 200))
        self._conversa_ou_erro(conversation_id)
        linhas = self.conexao.execute(
            "SELECT * FROM mensagens WHERE conversation_id = ? AND seq < ? "
            "ORDER BY seq DESC LIMIT ?",
            (conversation_id, int(antes_de_seq), limite + 1),
        ).fetchall()
        tem_mais = len(linhas) > limite
        mensagens = [self._mensagem_para_dict(linha) for linha in reversed(linhas[:limite])]
        return {"mensagens": mensagens, "tem_mais": tem_mais}

    # ------------------------------------------------------------------- mutações

    def renomear(self, conversation_id: str, title: str) -> dict[str, Any]:
        """Renomear pelo usuário sela `title_manual = 1` (F1-17 regra 4)."""
        limpo = titulo.encurtar(redator.redigir(title) or "")
        if not limpo:
            raise ErroNucleo("NU-243", "O título não pode ficar vazio.")
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            cx.execute(
                "UPDATE conversas SET title = ?, title_manual = 1 WHERE conversation_id = ?",
                (limpo, conversation_id),
            )
        return {"ok": True, "title": limpo}

    def titular_automaticamente(
        self,
        conversation_id: str,
        *,
        sugestao: str | None = None,
        modelo_galeria: str | None = None,
    ) -> dict[str, Any]:
        """Título de origem automática. Não toca em conversa renomeada pelo usuário."""
        conversa = self._conversa_ou_erro(conversation_id)
        if not titulo.pode_sobrescrever(conversa["title_manual"]):
            return {"ok": False, "title": conversa["title"], "motivo": "title_manual"}
        primeira = self.conexao.execute(
            "SELECT conteudo FROM mensagens WHERE conversation_id = ? AND papel = 'usuario' "
            "ORDER BY seq LIMIT 1",
            (conversation_id,),
        ).fetchone()
        novo = titulo.sugerir(
            modelo_galeria=sugestao or modelo_galeria,
            primeira_mensagem=primeira["conteudo"] if primeira else None,
        )
        with self._escrita() as cx:
            cx.execute(
                "UPDATE conversas SET title = ? WHERE conversation_id = ?",
                (novo, conversation_id),
            )
        return {"ok": True, "title": novo}

    def arquivar(self, conversation_id: str, arquivada: bool = True) -> dict[str, Any]:
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            cx.execute(
                "UPDATE conversas SET arquivada = ? WHERE conversation_id = ?",
                (1 if arquivada else 0, conversation_id),
            )
        return {"ok": True, "arquivada": bool(arquivada)}

    def apagar(self, conversation_id: str) -> dict[str, Any]:
        """Apaga a conversa e os anexos dela — linhas em cascata e arquivos do disco."""
        with self._escrita() as cx:
            self._conversa_ou_erro(conversation_id)
            # ON DELETE CASCADE cobre mensagens, tool_traces, conversa_mapspecs e
            # anexos; os triggers do FTS somem com o texto junto das mensagens.
            cx.execute("DELETE FROM conversas WHERE conversation_id = ?", (conversation_id,))
        return {
            "ok": True,
            "anexos_removidos": _remover_pasta_de_anexos(conversation_id),
        }

    def ramificar(
        self, conversation_id: str, *, a_partir_do_seq: int, title: str | None = None
    ) -> dict[str, Any]:
        """Nova conversa com as mensagens `seq <= a_partir_do_seq` da original.

        Copiar (e não referenciar) é o que permite continuar as duas conversas sem
        que uma edite o passado da outra. Editar mensagem enviada não existe: quem
        quer mudar o rumo ramifica daqui.
        """
        origem = self._conversa_ou_erro(conversation_id)
        corte = int(a_partir_do_seq)
        if corte < 1:
            raise ErroNucleo("NU-243", "O ponto de ramificação precisa ser um seq >= 1.")
        novo_conversation_id = novo_id()
        instante = agora_utc()
        titulo_novo = (
            titulo.encurtar(redator.redigir(title) or "")
            if title and title.strip()
            else titulo.encurtar(f"{origem['title']} (ramo)")
        )
        with self._escrita() as cx:
            mensagens = cx.execute(
                "SELECT * FROM mensagens WHERE conversation_id = ? AND seq <= ? ORDER BY seq",
                (conversation_id, corte),
            ).fetchall()
            if not mensagens:
                raise ErroNucleo(
                    "NU-244",
                    f"A conversa não tem mensagem até o seq {corte}; não há o que ramificar.",
                    {"conversation_id": conversation_id, "a_partir_do_seq": corte},
                )
            cx.execute(
                """
                INSERT INTO conversas (
                  conversation_id, title, created_at, updated_at,
                  workspace_path, workspace_fingerprint, workspace_nome,
                  conta_id, modelo, parent_conversation_id, parent_message_seq,
                  compact_summary, compact_ate_seq, title_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    novo_conversation_id,
                    titulo_novo,
                    instante,
                    instante,
                    origem["workspace_path"],
                    origem["workspace_fingerprint"],
                    origem["workspace_nome"],
                    origem["conta_id"],
                    origem["modelo"],
                    conversation_id,
                    corte,
                    origem["compact_summary"] if (origem["compact_ate_seq"] or 0) <= corte else None,
                    origem["compact_ate_seq"] if (origem["compact_ate_seq"] or 0) <= corte else None,
                    1 if title and title.strip() else 0,
                ),
            )
            id_novo_por_antigo: dict[str, str] = {}
            for linha in mensagens:
                message_id = novo_id()
                id_novo_por_antigo[linha["message_id"]] = message_id
                cx.execute(
                    """
                    INSERT INTO mensagens (
                      message_id, conversation_id, seq, papel, conteudo, criado_em,
                      mapspec_id, mapspec_versao, cancelada
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        novo_conversation_id,
                        linha["seq"],
                        linha["papel"],
                        linha["conteudo"],
                        linha["criado_em"],
                        linha["mapspec_id"],
                        linha["mapspec_versao"],
                        linha["cancelada"],
                    ),
                )
            for linha in cx.execute(
                "SELECT * FROM tool_traces WHERE conversation_id = ? "
                "AND (message_id IS NULL OR message_id IN "
                "     (SELECT message_id FROM mensagens WHERE conversation_id = ? AND seq <= ?))",
                (conversation_id, conversation_id, corte),
            ).fetchall():
                cx.execute(
                    """
                    INSERT INTO tool_traces (
                      trace_id, conversation_id, message_id, tool, args_resumo,
                      resultado_resumo, ms, ok, erro_codigo, criado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        novo_id(),
                        novo_conversation_id,
                        id_novo_por_antigo.get(linha["message_id"]),
                        linha["tool"],
                        linha["args_resumo"],
                        linha["resultado_resumo"],
                        linha["ms"],
                        linha["ok"],
                        linha["erro_codigo"],
                        linha["criado_em"],
                    ),
                )
        return {
            "conversation_id": novo_conversation_id,
            "title": titulo_novo,
            "parent_conversation_id": conversation_id,
            "parent_message_seq": corte,
            "mensagens_copiadas": len(mensagens),
        }

    # --------------------------------------------------------------------- busca

    def buscar(
        self, termo: str, *, workspace: str | None = None, limite: int = 30
    ) -> dict[str, Any]:
        """FTS5 com `remove_diacritics 2`: "orgao" acha "órgão" e vice-versa."""
        limite = max(1, min(int(limite), 200))
        consulta = _consulta_fts(termo)
        if consulta is None:
            return {"resultados": [], "termo": termo}
        parametros: list[Any] = [consulta]
        filtro = ""
        if workspace:
            filtro = "AND c.workspace_fingerprint = ?"
            parametros.append(fingerprint.calcular(workspace))
        parametros.append(limite)
        try:
            linhas = self.conexao.execute(
                f"""
                SELECT m.conversation_id, m.message_id, m.seq, c.title, c.updated_at,
                       c.workspace_nome,
                       snippet(mensagens_fts, 0, '[', ']', '…', 12) AS trecho
                FROM mensagens_fts
                JOIN mensagens m ON m.rowid = mensagens_fts.rowid
                JOIN conversas c ON c.conversation_id = m.conversation_id
                WHERE mensagens_fts MATCH ? {filtro}
                ORDER BY c.updated_at DESC, m.seq
                LIMIT ?
                """,
                parametros,
            ).fetchall()
        except sqlite3.OperationalError as exc:
            raise ErroNucleo(
                "NU-245",
                f"Busca recusada pelo índice de texto: {exc}",
                {"termo": termo},
            ) from exc
        return {
            "resultados": [
                {
                    "conversation_id": linha["conversation_id"],
                    "message_id": linha["message_id"],
                    "seq": linha["seq"],
                    "title": linha["title"],
                    "workspace_nome": linha["workspace_nome"],
                    "trecho_destacado": linha["trecho"],
                    "updated_at": linha["updated_at"],
                }
                for linha in linhas
            ],
            "termo": termo,
        }


def _consulta_fts(termo: str) -> str | None:
    """Termo do usuário → consulta FTS5 segura.

    O que o usuário digita na busca é texto, não sintaxe: `"`, `*`, `:`, `NEAR` e
    `OR` não podem virar operador nem derrubar a consulta. Por isso ficam só os
    tokens de palavra (o mesmo que o `unicode61` indexaria), cada um como frase
    entre aspas; a última ganha `*` para achar por prefixo enquanto se digita.
    """
    palavras = re.findall(r"\w+", termo or "", flags=re.UNICODE)
    if not palavras:
        return None
    partes = [f'"{palavra}"' for palavra in palavras]
    partes[-1] = f"{partes[-1]}*"
    return " AND ".join(partes)


def _caminho_sob_chats(relativo: str) -> Path:
    """Resolve dentro de `chats/`, recusando `..` e symlink que saia da árvore (AP-11)."""
    raiz = banco.pasta_chats().resolve()
    destino = (raiz / relativo).resolve()
    if destino != raiz and raiz not in destino.parents:
        raise ErroNucleo(
            "NU-246",
            "Caminho de anexo fora de %APPDATA%/MapasFacil/chats.",
            {"relativo": relativo},
        )
    return destino


def _remover_pasta_de_anexos(conversation_id: str) -> int:
    """Apaga `chats/anexos/<conversation_id>/` e devolve quantos arquivos saíram."""
    try:
        pasta = _caminho_sob_chats(f"anexos/{conversation_id}")
    except ErroNucleo:
        return 0
    if not pasta.is_dir():
        return 0
    removidos = sum(1 for item in pasta.rglob("*") if item.is_file())
    shutil.rmtree(pasta, ignore_errors=True)
    return removidos


_repositorio: RepositorioConversas | None = None


def atual() -> RepositorioConversas:
    """Repositório do processo, aberto na primeira chamada (não no import)."""
    global _repositorio
    if _repositorio is None:
        _repositorio = RepositorioConversas()
    return _repositorio


def redefinir(caminho: Path | None = None) -> RepositorioConversas:
    """Fecha o repositório atual e abre outro — usado pelos testes e por 'esquecer este PC'."""
    global _repositorio
    if _repositorio is not None:
        _repositorio.fechar()
        _repositorio = None
    _repositorio = RepositorioConversas(caminho)
    return _repositorio


def fechar() -> None:
    global _repositorio
    if _repositorio is not None:
        _repositorio.fechar()
        _repositorio = None
