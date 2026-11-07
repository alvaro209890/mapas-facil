"""Importação de um projeto: copiar, extrair, indexar (W-02 §Indexação e resumo)."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import projetos_repo
from ..erros import ErroServidor
from . import extrair as extrair_mod
from . import upload as upload_mod


@dataclass(frozen=True)
class Raizes:
    projetos: Path
    uploads: Path
    extraido_max_bytes: int


def registrar_importacao(
    con: sqlite3.Connection, *, projeto_id: str, upload_id: str
) -> str:
    importacao_id = uuid.uuid4().hex
    con.execute(
        "INSERT INTO importacoes (id, projeto_id, upload_id, estado, fase, criada_em)"
        " VALUES (?,?,?,?,?,datetime('now'))",
        (importacao_id, projeto_id, upload_id, "na_fila", "verificando"),
    )
    return importacao_id


def marcar_erro(banco: Any, importacao_id: str, *, codigo: str) -> None:
    """Fecha a importação em erro. Usado quando uma exceção inesperada foge do fluxo.

    Sem isto, `TypeError`/`KeyError` deixavam a linha em `rodando` para sempre e o front
    ficava girando (aconteceu no smoke do server em 03/11/2026).
    """
    if banco is None:
        return
    con = banco.conectar()
    try:
        _atualizar(con, importacao_id, estado="erro", erro_codigo=codigo, fim=True)
    finally:
        con.commit()


def _atualizar(
    con: sqlite3.Connection,
    importacao_id: str,
    *,
    estado: str | None = None,
    fase: str | None = None,
    resumo: dict | None = None,
    erro_codigo: str | None = None,
    fim: bool = False,
) -> None:
    campos = []
    valores: list[Any] = []
    if estado is not None:
        campos.append("estado = ?")
        valores.append(estado)
    if fase is not None:
        campos.append("fase = ?")
        valores.append(fase)
    if resumo is not None:
        import json

        campos.append("resumo = ?")
        valores.append(json.dumps(resumo, ensure_ascii=False))
    if erro_codigo is not None:
        campos.append("erro_codigo = ?")
        valores.append(erro_codigo)
    if fim:
        campos.append("fim_em = datetime('now')")
    if not campos:
        return
    valores.append(importacao_id)
    con.execute(f"UPDATE importacoes SET {', '.join(campos)} WHERE id = ?", valores)


def importar(
    *,
    banco,
    raizes: Raizes,
    projeto: projetos_repo.Projeto,
    upload_id: str,
    importacao_id: str,
    pool: Any | None = None,
    chamar=None,
    ao_progresso=None,
) -> dict:
    """Executa a importação de ponta a ponta e devolve o resumo.

    Falha sempre deixa o projeto em `erro` com o código, nunca em estado mentiroso.
    """
    con = banco.conectar()
    try:
        _atualizar(con, importacao_id, estado="rodando", fase="verificando")
        projeto = projetos_repo.transicionar(con, projeto, "importando")

        pasta = raizes.projetos / projeto.id
        pasta.mkdir(parents=True, exist_ok=True)
        up = upload_mod.abrir(raizes.uploads, upload_id)
        destino_zip = pasta / "entrada.zip"
        if not destino_zip.exists():
            origem = raizes.uploads / up.id / "entrada.zip"
            if not origem.is_file():
                raise ErroServidor(
                    "SV-100",
                    "O upload ainda não foi concluído.",
                    status_http=409,
                    o_que_fazer="Termine o envio das partes antes de importar.",
                )
            extrair_mod.copiar_zip(origem, destino_zip)

        pasta_entrada = pasta / "entrada"
        if pasta_entrada.is_dir():
            # Reimportação: guarda a versão anterior em vez de apagar.
            carimbo = str(int(pasta_entrada.stat().st_mtime))
            anterior = pasta / "entrada.anterior" / carimbo
            anterior.parent.mkdir(parents=True, exist_ok=True)
            if not anterior.exists():
                pasta_entrada.rename(anterior)

        _atualizar(con, importacao_id, fase="extraindo")
        resultado = extrair_mod.extrair(
            destino_zip,
            pasta_entrada,
            max_extraido_bytes=raizes.extraido_max_bytes,
            ao_progresso=ao_progresso,
        )
        extrair_mod.marcar_somente_leitura(pasta_entrada)

        _atualizar(con, importacao_id, fase="indexando")
        projeto = projetos_repo.transicionar(con, projeto, "indexando")
        if ao_progresso is not None:
            # A barra da tela troca de "extraindo N de M" para "lendo os shapefiles".
            ao_progresso({"fase": "indexando", "total": resultado.total})

        resumo: dict[str, Any] = {}
        if pool is not None:
            import asyncio

            async def _pedido():
                # Precisa ser corrotina: o app entrega `chamar` como
                # `asyncio.run_coroutine_threadsafe(pedido, laco).result()`, e passar o
                # resultado já aguardado dava `TypeError: A coroutine object is required`
                # (medido no smoke do server em 03/11/2026 — a importação ficava em
                # "rodando" para sempre).
                return await pool.chamar(projeto.id, "workspace.abrir", {"caminho": str(pasta)})

            try:
                # `chamar` existe quando quem chama já está num event loop (o worker do
                # núcleo pertence a esse loop — `asyncio.run` aqui criaria outro e
                # quebraria os pipes). Sem ele, caminho síncrono de teste.
                if chamar is not None:
                    bruto = chamar(_pedido())
                else:
                    bruto = asyncio.run(_pedido())
                resumo = bruto.get("workspace") or {}
                if bruto.get("projeto"):
                    resumo["projeto"] = bruto["projeto"]
                if bruto.get("imoveis"):
                    resumo["imoveis"] = bruto["imoveis"]
            except ErroServidor as exc:
                # Extração boa, indexação falhou: guarda o código e deixa o projeto em erro.
                _atualizar(
                    con,
                    importacao_id,
                    estado="erro",
                    erro_codigo=exc.codigo,
                    fim=True,
                )
                projetos_repo.transicionar(con, projeto, "erro", erro_codigo=exc.codigo)
                raise
        else:
            resumo = {"avisos": [{"codigo": "SV-123", "mensagem": "indexação pendente: worker não configurado"}]}

        if resultado.avisos:
            resumo.setdefault("avisos", [])
            resumo["avisos"] = list(resumo["avisos"]) + resultado.avisos
        resumo["arquivos"] = resultado.total
        resumo["bytes"] = resultado.bytes_extraidos
        resumo["ignorados"] = resultado.ignorados

        projeto = projetos_repo.transicionar(con, projeto, "pronto")
        imoveis_lista = resumo.get("imoveis") if isinstance(resumo, dict) else None
        if not imoveis_lista and isinstance(resumo, dict) and pasta_entrada.is_dir():
            # Não importa o núcleo diretamente no servidor (CI gate).
            # Identifica candidatos estritamente com evidência real de ATP/perímetro,
            # nunca promovendo camadas ambientais (APP, hidro, reserva) a imóveis.
            import re
            termos_tematicos = {
                "app", "hidro", "hidrografia", "nascente", "rio", "corrego", "curso_dagua",
                "reserva", "reserva_legal", "vegetacao", "uso", "antropica", "consolidada",
                "estrada", "via", "rodovia", "sede", "benfeitoria", "grade", "talhao",
            }
            termos_atp = {"atp", "air", "perimetro", "lote", "imovel", "gleba"}

            candidatos_atp: list[str] = []
            for p in sorted(pasta_entrada.rglob("*.shp")):
                stem = p.stem.lower()
                partes = set(re.split(r"[^a-zA-Z0-9]+", stem))
                if any(t in partes for t in termos_tematicos):
                    continue
                if any(t in partes for t in termos_atp) or stem.startswith("atp") or stem.startswith("air"):
                    candidatos_atp.append(p.relative_to(pasta_entrada).as_posix())

            if candidatos_atp:
                imoveis_lista = []
                for idx, cand in enumerate(candidatos_atp, start=1):
                    stem = Path(cand).stem
                    nome = stem.replace("_", " ").title()
                    imoveis_lista.append(
                        {
                            "id": f"imovel_{idx}_{stem.lower()}",
                            "nome": nome,
                            "car": None,
                            "matricula": None,
                            "area": None,
                            "atp": cand,
                            "principal": (idx == 1),
                        }
                    )
                resumo["imoveis"] = imoveis_lista
            else:
                # Sem ATP com evidência: emite aviso de indisponibilidade em vez de inventar
                resumo.setdefault("avisos", [])
                resumo["avisos"].append(
                    {
                        "codigo": "IM-030",
                        "mensagem": "Detecção de imóveis múltiplos indisponível ou nenhum perímetro (ATP) com evidência encontrado.",
                    }
                )

        if imoveis_lista:
            resumo["imoveis"] = imoveis_lista
            projetos_repo.salvar_imoveis(con, projeto.id, imoveis_lista)
            im_principal = next((i for i in imoveis_lista if i.get("principal")), imoveis_lista[0])
            mun_nome = None
            mun_uf = None
            if isinstance(im_principal.get("municipio"), dict):
                mun_nome = im_principal["municipio"].get("nome")
                mun_uf = im_principal["municipio"].get("uf")
            imovel_comp = {
                "nome": im_principal.get("nome"),
                "car": im_principal.get("car"),
                "municipio": mun_nome,
                "uf": mun_uf,
            }
            projeto = projetos_repo.atualizar_imovel(con, projeto, imovel_comp)
        else:
            # Preserva dados de imóveis anteriores se a detecção atual falhar/estiver indisponível
            imoveis_anteriores = projetos_repo.listar_imoveis(con, projeto.id)
            if imoveis_anteriores:
                resumo["imoveis"] = imoveis_anteriores
            else:
                imovel = (resumo.get("imovel") or {}) if isinstance(resumo, dict) else {}
                if imovel:
                    projeto = projetos_repo.atualizar_imovel(con, projeto, imovel)
                    projetos_repo.salvar_imoveis(
                        con,
                        projeto.id,
                        [
                            {
                                "id": "imovel_principal",
                                "nome": imovel.get("nome") or projeto.nome,
                                "car": imovel.get("car"),
                                "principal": True,
                            }
                        ],
                    )
        _atualizar(con, importacao_id, estado="pronto", fase="pronto", resumo=resumo, fim=True)
        upload_mod.descartar(up)
        return resumo
    except ErroServidor as exc:
        _atualizar(con, importacao_id, estado="erro", erro_codigo=exc.codigo, fim=True)
        atual = projetos_repo.obter(con, projeto.id, usuario_id=projeto.usuario_id, admin=True)
        if atual is not None and atual.estado != "erro":
            try:
                projetos_repo.transicionar(con, atual, "erro", erro_codigo=exc.codigo)
            except ErroServidor:  # pragma: no cover - estado já terminal
                pass
        raise
    finally:
        con.close()


def estado(con: sqlite3.Connection, importacao_id: str) -> dict:
    linha = con.execute(
        "SELECT * FROM importacoes WHERE id = ?", (importacao_id,)
    ).fetchone()
    if linha is None:
        raise ErroServidor("SV-124", "Importação não encontrada.", status_http=404)
    import json

    return {
        "id": linha["id"],
        "projeto_id": linha["projeto_id"],
        "estado": linha["estado"],
        "fase": linha["fase"],
        "resumo": json.loads(linha["resumo"]) if linha["resumo"] else None,
        "erro_codigo": linha["erro_codigo"],
        "criada_em": linha["criada_em"],
        "fim_em": linha["fim_em"],
    }
